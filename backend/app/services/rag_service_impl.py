# ============================================================
# RAG (检索增强生成) 知识库服务 - 完整实现
# ============================================================
#
# 本模块实现完整的RAG Pipeline，支持：
# 1. 文档解析：PDF、Word、TXT、Markdown等
# 2. 文本分块：固定长度、递归、语义、段落分块
# 3. 向量存储：Milvus向量数据库
# 4. 混合检索：向量检索 + 关键词检索的RRF融合
# 5. 生成增强：检索结果注入到LLM提示词
#
# 使用方法：
# from app.services.rag_service import RAGPipeline, initialize_rag_pipeline
#
# pipeline = initialize_rag_pipeline()
# result = await pipeline.add_document("path/to/file.pdf")
# response = await pipeline.query("用户问题")
#
# Author: CoolAI Team
# Date: 2026-05-13
# ============================================================

import hashlib
import re
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, AsyncIterator, Callable
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import asyncio
from concurrent.futures import ThreadPoolExecutor

# 异步HTTP客户端
import httpx

# 数据库
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# 配置文件
from app.core.config import settings


# ============================================================
# 枚举定义
# ============================================================

class DocumentType(str, Enum):
    """
    文档类型枚举
    
    定义系统支持的文档格式
    """
    PDF = "pdf"
    WORD = "docx"
    TXT = "txt"
    MARKDOWN = "md"
    HTML = "html"
    CSV = "csv"
    JSON = "json"
    UNKNOWN = "unknown"


class ChunkStrategy(str, Enum):
    """
    文本分块策略枚举
    
    不同的分块策略会影响检索效果：
    - FIXED_SIZE: 固定长度，最简单
    - RECURSIVE: 递归切分，保持语义
    - SEMANTIC: 语义分块，效果最好但最慢
    - PARAGRAPH: 段落分块，适合结构化文档
    """
    FIXED_SIZE = "fixed_size"     # 固定长度分块
    RECURSIVE = "recursive"        # 递归分块
    SEMANTIC = "semantic"          # 语义分块
    PARAGRAPH = "paragraph"        # 段落分块


class ProcessStatus(str, Enum):
    """文档处理状态"""
    PENDING = "pending"      # 等待处理
    PROCESSING = "processing"  # 处理中
    COMPLETED = "completed"   # 处理完成
    FAILED = "failed"        # 处理失败


# ============================================================
# 数据类定义
# ============================================================

@dataclass
class Document:
    """
    文档数据类
    
    表示一个待处理的原始文档
    
    Attributes:
        doc_id: 文档唯一标识符
        title: 文档标题
        content: 文档原始内容
        doc_type: 文档类型
        metadata: 文档元数据
        file_path: 原始文件路径
    """
    doc_id: str
    title: str
    content: str
    doc_type: DocumentType
    metadata: Dict[str, Any] = field(default_factory=dict)
    file_path: Optional[str] = None


@dataclass
class TextChunk:
    """
    文本块数据类
    
    表示文档分块后的一个文本片段
    
    Attributes:
        chunk_id: 块唯一标识符
        content: 文本内容
        doc_id: 所属文档ID
        chunk_index: 在文档中的顺序索引
        vector_id: 向量数据库中的ID
        metadata: 元数据
    """
    chunk_id: str
    content: str
    doc_id: str
    chunk_index: int
    vector_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "chunk_id": self.chunk_id,
            "content": self.content,
            "doc_id": self.doc_id,
            "chunk_index": self.chunk_index,
            "vector_id": self.vector_id,
            "metadata": self.metadata,
        }


@dataclass
class SearchResult:
    """
    搜索结果数据类
    
    表示一次检索返回的单个结果
    
    Attributes:
        chunk: 匹配的文本块
        score: 相似度得分 (0-1)
        rank: 排名
    """
    chunk: TextChunk
    score: float
    rank: int = 0


# ============================================================
# 文档解析器
# ============================================================

class DocumentParser(ABC):
    """
    文档解析器抽象基类
    
    定义文档解析器的接口规范
    不同的文档格式需要实现不同的解析器
    
    设计模式：策略模式（Strategy Pattern）
    """
    
    @abstractmethod
    def parse(self, file_path: str) -> Document:
        """
        解析文档
        
        Args:
            file_path: 文件路径
        
        Returns:
            Document: 解析后的Document对象
        """
        pass
    
    @abstractmethod
    def can_parse(self, file_path: str) -> bool:
        """
        判断当前解析器是否能解析该文件
        
        Args:
            file_path: 文件路径
        
        Returns:
            bool: 是否可以解析
        """
        pass


class TxtParser(DocumentParser):
    """
    纯文本解析器
    
    用于解析.txt格式的文本文档
    最简单的解析器，直接读取文件内容
    """
    
    def parse(self, file_path: str) -> Document:
        """解析文本文件"""
        path = Path(file_path)
        title = path.stem
        
        # 读取文件内容
        encodings = ['utf-8', 'gbk', 'gb2312', 'iso-8859-1']
        content = None
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                break
            except UnicodeDecodeError:
                continue
        
        if content is None:
            raise ValueError(f"无法解码文件: {file_path}")
        
        # 生成文档ID
        doc_id = hashlib.md5(file_path.encode()).hexdigest()
        
        return Document(
            doc_id=doc_id,
            title=title,
            content=content.strip(),
            doc_type=DocumentType.TXT,
            metadata={
                "source": str(file_path),
                "size": len(content),
                "encoding": "utf-8"
            },
            file_path=str(file_path)
        )
    
    def can_parse(self, file_path: str) -> bool:
        """判断是否为文本文件"""
        return file_path.lower().endswith('.txt')


class PDFParser(DocumentParser):
    """
    PDF文档解析器
    
    使用pdfplumber提取PDF文本内容
    支持：
    - 逐页读取文本
    - 保留页码信息
    - 提取基本元数据
    """
    
    def __init__(self):
        """初始化PDF解析器"""
        self._pdfplumber = None
    
    def _get_pdfplumber(self):
        """懒加载pdfplumber"""
        if self._pdfplumber is None:
            try:
                import pdfplumber
                self._pdfplumber = pdfplumber
            except ImportError:
                raise ImportError(
                    "请安装pdfplumber: pip install pdfplumber\n"
                    "或者使用: pip install coolai[pdf]"
                )
        return self._pdfplumber
    
    def parse(self, file_path: str) -> Document:
        """解析PDF文件"""
        pdfplumber = self._get_pdfplumber()
        path = Path(file_path)
        title = path.stem
        full_content = []
        page_count = 0
        
        # 使用pdfplumber提取文本
        try:
            with pdfplumber.open(file_path) as pdf:
                page_count = len(pdf.pages)
                
                for page_num, page in enumerate(pdf.pages, start=1):
                    # 提取文本
                    page_text = page.extract_text()
                    
                    if page_text:
                        # 清理文本
                        page_text = self._clean_text(page_text)
                        # 添加页码标记
                        full_content.append(f"[第{page_num}页]\n{page_text}")
                    
                    # 提取表格（如果需要）
                    tables = page.extract_tables()
                    for table_idx, table in enumerate(tables):
                        if table:
                            table_text = self._table_to_text(table)
                            full_content.append(f"[第{page_num}页-表格{table_idx + 1}]\n{table_text}")
        except Exception as e:
            raise ValueError(f"PDF解析失败: {e}")
        
        content = "\n\n".join(full_content)
        
        # 生成文档ID
        doc_id = hashlib.md5(file_path.encode()).hexdigest()
        
        return Document(
            doc_id=doc_id,
            title=title,
            content=content.strip(),
            doc_type=DocumentType.PDF,
            metadata={
                "source": str(file_path),
                "size": path.stat().st_size if path.exists() else 0,
                "page_count": page_count
            },
            file_path=str(file_path)
        )
    
    def _clean_text(self, text: str) -> str:
        """清理PDF提取的文本"""
        # 移除多余空白
        text = re.sub(r'\s+', ' ', text)
        # 移除特殊字符（可选）
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
        return text.strip()
    
    def _table_to_text(self, table: List[List[str]]) -> str:
        """将表格转换为文本"""
        lines = []
        for row in table:
            lines.append(" | ".join(str(cell) if cell else "" for cell in row))
        return "\n".join(lines)
    
    def can_parse(self, file_path: str) -> bool:
        """判断是否为PDF文件"""
        return file_path.lower().endswith('.pdf')


class DocxParser(DocumentParser):
    """
    Word文档解析器
    
    使用python-docx提取Word文档文本
    支持：
    - 段落文本提取
    - 表格内容提取
    - 保留基本格式信息
    """
    
    def __init__(self):
        """初始化Word解析器"""
        self._docx = None
    
    def _get_docx(self):
        """懒加载python-docx"""
        if self._docx is None:
            try:
                import docx
                self._docx = docx
            except ImportError:
                raise ImportError(
                    "请安装python-docx: pip install python-docx\n"
                    "或者使用: pip install coolai[docx]"
                )
        return self._docx
    
    def parse(self, file_path: str) -> Document:
        """解析Word文档"""
        docx = self._get_docx()
        path = Path(file_path)
        title = path.stem
        full_content = []
        
        try:
            doc = docx.Document(file_path)
            
            # 提取段落
            for para in doc.paragraphs:
                if para.text.strip():
                    full_content.append(para.text.strip())
            
            # 提取表格
            for table_idx, table in enumerate(doc.tables):
                table_text = f"[表格 {table_idx + 1}]\n"
                for row in table.rows:
                    cells = [cell.text.strip() for cell in row.cells]
                    table_text += " | ".join(cells) + "\n"
                full_content.append(table_text)
        
        except Exception as e:
            raise ValueError(f"Word文档解析失败: {e}")
        
        content = "\n\n".join(full_content)
        
        # 生成文档ID
        doc_id = hashlib.md5(file_path.encode()).hexdigest()
        
        return Document(
            doc_id=doc_id,
            title=title,
            content=content.strip(),
            doc_type=DocumentType.WORD,
            metadata={
                "source": str(file_path),
                "size": path.stat().st_size if path.exists() else 0,
            },
            file_path=str(file_path)
        )
    
    def can_parse(self, file_path: str) -> bool:
        """判断是否为Word文件"""
        return file_path.lower().endswith(('.docx', '.doc'))


class MarkdownParser(DocumentParser):
    """
    Markdown文档解析器
    
    解析Markdown文件，保留基本结构
    """
    
    def parse(self, file_path: str) -> Document:
        """解析Markdown文件"""
        path = Path(file_path)
        title = path.stem
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 生成文档ID
        doc_id = hashlib.md5(file_path.encode()).hexdigest()
        
        return Document(
            doc_id=doc_id,
            title=title,
            content=content.strip(),
            doc_type=DocumentType.MARKDOWN,
            metadata={
                "source": str(file_path),
                "size": len(content),
            },
            file_path=str(file_path)
        )
    
    def can_parse(self, file_path: str) -> bool:
        """判断是否为Markdown文件"""
        return file_path.lower().endswith('.md')


class DocumentParserFactory:
    """
    文档解析器工厂
    
    根据文件类型自动选择合适的解析器
    """
    
    def __init__(self):
        """初始化解析器工厂"""
        self._parsers: List[DocumentParser] = [
            PDFParser(),
            DocxParser(),
            MarkdownParser(),
            TxtParser(),
        ]
    
    def get_parser(self, file_path: str) -> Optional[DocumentParser]:
        """
        获取合适的解析器
        
        Args:
            file_path: 文件路径
        
        Returns:
            DocumentParser: 合适的解析器，或None
        """
        for parser in self._parsers:
            if parser.can_parse(file_path):
                return parser
        return None
    
    def parse(self, file_path: str) -> Document:
        """
        解析文档（自动选择解析器）
        
        Args:
            file_path: 文件路径
        
        Returns:
            Document: 解析后的文档
        
        Raises:
            ValueError: 不支持的文档格式
        """
        parser = self.get_parser(file_path)
        if parser is None:
            raise ValueError(f"不支持的文档格式: {file_path}")
        return parser.parse(file_path)


# ============================================================
# 文本分块器
# ============================================================

class TextChunker:
    """
    文本分块器
    
    负责将长文档切分成适合检索的小块
    支持多种分块策略
    
    设计考量：
    1. 块大小：太大会引入噪声，太小会丢失上下文
    2. 块重叠：增加重叠区域可以提高召回率
    3. 保留边界：尽量在语义完整处切分
    """
    
    def __init__(
        self,
        strategy: ChunkStrategy = ChunkStrategy.RECURSIVE,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        min_chunk_size: int = 50
    ):
        """
        初始化分块器
        
        Args:
            strategy: 分块策略
            chunk_size: 目标块大小（字符数）
            chunk_overlap: 相邻块的重叠大小
            min_chunk_size: 最小块大小
        """
        self.strategy = strategy
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
    
    def chunk_document(self, document: Document) -> List[TextChunk]:
        """
        将文档分块
        
        Args:
            document: 待分块的文档
        
        Returns:
            List[TextChunk]: 文本块列表
        """
        if self.strategy == ChunkStrategy.FIXED_SIZE:
            return self._fixed_size_chunk(document)
        elif self.strategy == ChunkStrategy.RECURSIVE:
            return self._recursive_chunk(document)
        elif self.strategy == ChunkStrategy.PARAGRAPH:
            return self._paragraph_chunk(document)
        elif self.strategy == ChunkStrategy.SEMANTIC:
            return self._semantic_chunk(document)
        else:
            return self._recursive_chunk(document)
    
    def _fixed_size_chunk(self, document: Document) -> List[TextChunk]:
        """
        固定长度分块
        
        按固定字符数切分文档，简单高效
        """
        content = document.content
        chunks = []
        
        start = 0
        index = 0
        
        while start < len(content):
            end = start + self.chunk_size
            
            # 尽量在句子边界处切分
            if end < len(content):
                # 向前查找最近的句子边界
                for i in range(min(end, len(content) - 1), max(start, end - 100), -1):
                    if content[i] in '。！？.!?\n':
                        end = i + 1
                        break
            
            # 提取块内容
            chunk_content = content[start:end].strip()
            
            if len(chunk_content) >= self.min_chunk_size:
                chunks.append(TextChunk(
                    chunk_id=f"{document.doc_id}_{index}",
                    content=chunk_content,
                    doc_id=document.doc_id,
                    chunk_index=index,
                    metadata={
                        **document.metadata,
                        "title": document.title
                    }
                ))
                index += 1
            
            # 移动窗口
            start = end - self.chunk_overlap if end < len(content) else len(content)
        
        return chunks
    
    def _recursive_chunk(self, document: Document) -> List[TextChunk]:
        """
        递归分块（推荐使用）
        
        从大到小依次尝试切分：
        段落 -> 句子 -> 固定长度
        
        尽量保持语义完整性
        """
        content = document.content
        chunks = []
        
        # 第一步：按段落分割
        paragraphs = self._split_paragraphs(content)
        
        current_chunk = ""
        index = 0
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # 如果段落超过目标块大小，继续分割
            if len(para) > self.chunk_size:
                # 先保存当前块
                if current_chunk:
                    chunks.append(TextChunk(
                        chunk_id=f"{document.doc_id}_{index}",
                        content=current_chunk.strip(),
                        doc_id=document.doc_id,
                        chunk_index=index,
                        metadata={**document.metadata, "title": document.title}
                    ))
                    index += 1
                    current_chunk = ""
                
                # 分割长段落
                sub_chunks = self._split_long_paragraph(para)
                for sub_chunk in sub_chunks:
                    if len(sub_chunk) >= self.min_chunk_size:
                        chunks.append(TextChunk(
                            chunk_id=f"{document.doc_id}_{index}",
                            content=sub_chunk.strip(),
                            doc_id=document.doc_id,
                            chunk_index=index,
                            metadata={**document.metadata, "title": document.title}
                        ))
                        index += 1
            else:
                # 尝试将段落加入当前块
                if len(current_chunk) + len(para) + 1 <= self.chunk_size:
                    current_chunk += "\n" + para if current_chunk else para
                else:
                    # 当前块已满，保存并开始新块
                    if current_chunk:
                        chunks.append(TextChunk(
                            chunk_id=f"{document.doc_id}_{index}",
                            content=current_chunk.strip(),
                            doc_id=document.doc_id,
                            chunk_index=index,
                            metadata={**document.metadata, "title": document.title}
                        ))
                        index += 1
                    
                    # 新块可能需要与当前段落重叠
                    overlap_text = current_chunk[-self.chunk_overlap:] if current_chunk else ""
                    current_chunk = overlap_text + "\n" + para if overlap_text else para
        
        # 保存最后一个块
        if current_chunk and len(current_chunk.strip()) >= self.min_chunk_size:
            chunks.append(TextChunk(
                chunk_id=f"{document.doc_id}_{index}",
                content=current_chunk.strip(),
                doc_id=document.doc_id,
                chunk_index=index,
                metadata={**document.metadata, "title": document.title}
            ))
        
        return chunks
    
    def _split_paragraphs(self, text: str) -> List[str]:
        """按段落分割文本"""
        # 按换行符分割
        parts = text.split('\n\n')
        return [p.strip() for p in parts if p.strip()]
    
    def _split_long_paragraph(self, para: str) -> List[str]:
        """分割长段落"""
        chunks = []
        
        # 按句子分割
        sentences = re.split(r'([。！？.!?\n])', para)
        
        # 重新组合句子
        current_sentences = []
        current_len = 0
        
        for i in range(0, len(sentences), 2):
            sentence = sentences[i]
            separator = sentences[i + 1] if i + 1 < len(sentences) else ""
            full_sentence = sentence + separator
            
            if current_len + len(full_sentence) <= self.chunk_size:
                current_sentences.append(full_sentence)
                current_len += len(full_sentence)
            else:
                # 保存当前块
                if current_sentences:
                    chunks.append("".join(current_sentences))
                
                # 开始新块（可能有重叠）
                overlap = "".join(current_sentences[-2:]) if current_sentences else ""
                current_sentences = [overlap, full_sentence]
                current_len = len(overlap) + len(full_sentence)
        
        # 保存最后一个块
        if current_sentences:
            chunks.append("".join(current_sentences))
        
        return chunks
    
    def _paragraph_chunk(self, document: Document) -> List[TextChunk]:
        """
        段落分块
        
        按自然段落分割文档，适合结构清晰的文档
        """
        paragraphs = self._split_paragraphs(document.content)
        
        chunks = []
        for index, para in enumerate(paragraphs):
            if len(para) < self.min_chunk_size:
                continue
            
            chunks.append(TextChunk(
                chunk_id=f"{document.doc_id}_{index}",
                content=para,
                doc_id=document.doc_id,
                chunk_index=index,
                metadata={
                    **document.metadata,
                    "title": document.title,
                    "paragraph_num": index + 1
                }
            ))
        
        return chunks
    
    def _semantic_chunk(self, document: Document) -> List[TextChunk]:
        """
        语义分块（高级功能）
        
        使用嵌入模型计算句子相似度
        将相似的连续句子分组在一起
        
        注意：此功能需要嵌入模型支持，当前为简化实现
        """
        # 简化实现：使用递归分块
        # 完整实现可以使用句子嵌入计算相似度
        return self._recursive_chunk(document)


# ============================================================
# 嵌入模型
# ============================================================

class EmbeddingModel:
    """
    嵌入模型封装
    
    负责将文本转换为向量表示
    支持多种嵌入模型：
    - OpenAI text-embedding-ada-002
    - 本地模型（Sentence Transformers）
    
    Attributes:
        model_name: 模型名称
        dimension: 向量维度
        batch_size: 批处理大小
        api_key: API密钥
    """
    
    def __init__(
        self,
        model_name: Optional[str] = None,
        dimension: Optional[int] = None,
        batch_size: int = 32,
        api_key: Optional[str] = None
    ):
        """
        初始化嵌入模型
        
        Args:
            model_name: 模型名称
            dimension: 向量维度
            batch_size: 批处理大小
            api_key: API密钥
        """
        self.model_name = model_name or settings.EMBEDDING_MODEL
        self.dimension = dimension or settings.EMBEDDING_DIMENSION
        self.batch_size = batch_size
        self.api_key = api_key or settings.OPENAI_API_KEY
        self._model = None
        self._is_local = "sentence-transformers" in self.model_name.lower()
    
    def load(self):
        """
        加载模型
        
        懒加载模式，首次使用时加载模型
        """
        if self._model is not None:
            return
        
        if self._is_local:
            # 加载Sentence Transformers模型
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
                # 更新维度
                self.dimension = self._model.get_sentence_embedding_dimension()
            except ImportError:
                raise ImportError(
                    "请安装sentence-transformers: pip install sentence-transformers\n"
                    "或者使用: pip install coolai[embedding]"
                )
        # OpenAI等远程模型不需要预加载
    
    def encode(self, texts: List[str]) -> List[List[float]]:
        """
        将文本列表转换为向量
        
        Args:
            texts: 文本列表
        
        Returns:
            List[List[float]]: 向量列表
        """
        if not texts:
            return []
        
        if self._is_local:
            return self._encode_local(texts)
        else:
            return self._encode_remote(texts)
    
    def _encode_local(self, texts: List[str]) -> List[List[float]]:
        """使用本地模型编码"""
        self.load()
        
        # 分批处理
        all_embeddings = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            embeddings = self._model.encode(batch)
            all_embeddings.extend(embeddings.tolist())
        
        return all_embeddings
    
    def _encode_remote(self, texts: List[str]) -> List[List[float]]:
        """
        使用远程API编码（OpenAI等）
        
        注意：此处需要真实的API Key
        """
        if not self.api_key:
            # 如果没有API Key，使用模拟向量
            # 后期替换为真实的API调用
            import random
            return [[random.random() for _ in range(self.dimension)] for _ in texts]
        
        # TODO: 实现OpenAI API调用
        # async with httpx.AsyncClient() as client:
        #     response = await client.post(
        #         "https://api.openai.com/v1/embeddings",
        #         headers={
        #             "Authorization": f"Bearer {self.api_key}",
        #             "Content-Type": "application/json"
        #         },
        #         json={
        #             "input": texts,
        #             "model": "text-embedding-ada-002"
        #         }
        #     )
        #     result = response.json()
        #     return [item["embedding"] for item in result["data"]]
        
        # 临时返回模拟向量
        import random
        return [[random.random() for _ in range(self.dimension)] for _ in texts]
    
    def encode_single(self, text: str) -> List[float]:
        """
        单条文本嵌入
        
        Args:
            text: 待嵌入文本
        
        Returns:
            List[float]: 向量
        """
        return self.encode([text])[0]


# ============================================================
# 向量存储
# ============================================================

class VectorStore(ABC):
    """
    向量存储抽象基类
    
    定义向量存储的接口规范
    支持多种向量数据库后端
    
    设计模式：适配器模式（Adapter Pattern）
    """
    
    @abstractmethod
    def connect(self) -> bool:
        """建立连接"""
        pass
    
    @abstractmethod
    async def insert(self, chunks: List[TextChunk], embeddings: List[List[float]]) -> bool:
        """
        插入向量数据
        
        Args:
            chunks: 文本块列表
            embeddings: 对应的向量列表
        
        Returns:
            bool: 是否插入成功
        """
        pass
    
    @abstractmethod
    async def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        filter_conditions: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        向量相似度搜索
        
        Args:
            query_vector: 查询向量
            top_k: 返回前K个结果
            filter_conditions: 过滤条件
        
        Returns:
            List[SearchResult]: 搜索结果列表
        """
        pass
    
    @abstractmethod
    async def delete(self, chunk_ids: List[str]) -> bool:
        """
        删除向量数据
        
        Args:
            chunk_ids: 要删除的块ID列表
        
        Returns:
            bool: 是否删除成功
        """
        pass
    
    @abstractmethod
    async def create_collection(self, dimension: int, collection_name: str) -> bool:
        """
        创建Collection
        
        Args:
            dimension: 向量维度
            collection_name: Collection名称
        
        Returns:
            bool: 是否创建成功
        """
        pass


class MilvusVectorStore(VectorStore):
    """
    Milvus向量数据库适配器
    
    使用pymilvus连接Milvus向量数据库
    实现高效的向量存储和检索
    
    Milvus特点：
    - 专为向量设计，支持十亿级向量
    - 支持多种索引类型（IVF、HNSW等）
    - 提供Python SDK，易于集成
    """
    
    def __init__(
        self,
        host: str = None,
        port: int = None,
        collection_name: str = None,
        dimension: int = None
    ):
        """
        初始化Milvus连接
        
        Args:
            host: Milvus服务器地址
            port: Milvus服务器端口
            collection_name: Collection名称
            dimension: 向量维度
        """
        self.host = host or settings.MILVUS_HOST
        self.port = port or settings.MILVUS_PORT
        self.collection_name = collection_name or settings.MILVUS_COLLECTION
        self.dimension = dimension or settings.EMBEDDING_DIMENSION
        self._client = None
        self._collection = None
    
    def connect(self) -> bool:
        """
        建立数据库连接
        
        Returns:
            bool: 连接是否成功
        """
        try:
            from pymilvus import connections, Collection, CollectionSchema, FieldSchema, DataType
            
            # 建立连接
            connections.connect(
                alias="default",
                host=self.host,
                port=str(self.port),
                # 后期可添加认证：
                # user=settings.MILVUS_USER,
                # password=settings.MILVUS_PASSWORD,
            )
            
            # 获取或创建Collection
            self._ensure_collection()
            
            return True
        except Exception as e:
            print(f"Milvus连接失败: {e}")
            return False
    
    def _ensure_collection(self):
        """确保Collection存在"""
        try:
            from pymilvus import Collection
            
            # 尝试获取已存在的Collection
            self._collection = Collection(self.collection_name)
            self._collection.load()
        except Exception:
            # Collection不存在，创建新的
            self.create_collection(self.dimension, self.collection_name)
    
    def create_collection(self, dimension: int, collection_name: str) -> bool:
        """
        创建Collection
        
        Args:
            dimension: 向量维度
            collection_name: Collection名称
        
        Returns:
            bool: 是否创建成功
        """
        try:
            from pymilvus import (
                connections, Collection, CollectionSchema,
                FieldSchema, DataType, utility
            )
            
            # 如果Collection已存在，删除
            if utility.has_collection(collection_name):
                utility.drop_collection(collection_name)
            
            # 定义字段
            fields = [
                FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=100, is_primary=True),
                FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
                FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=dimension),
                FieldSchema(name="metadata", dtype=DataType.VARCHAR, max_length=65535),  # JSON字符串
            ]
            
            # 创建Schema
            schema = CollectionSchema(fields=fields, description="RAG Knowledge Base")
            
            # 创建Collection
            self._collection = Collection(name=collection_name, schema=schema)
            
            # 创建索引（使用IVF_FLAT）
            index_params = {
                "metric_type": "L2",  # 或 "IP" (内积)
                "index_type": "IVF_FLAT",
                "params": {"nlist": 128}
            }
            self._collection.create_index(field_name="vector", index_params=index_params)
            
            # 加载Collection
            self._collection.load()
            
            return True
        except Exception as e:
            print(f"创建Collection失败: {e}")
            return False
    
    async def insert(self, chunks: List[TextChunk], embeddings: List[List[float]]) -> bool:
        """
        批量插入向量数据
        
        Args:
            chunks: 文本块列表
            embeddings: 对应的向量列表
        
        Returns:
            bool: 插入是否成功
        """
        if not self._collection:
            if not self.connect():
                return False
        
        try:
            from pymilvus import Collection
            
            entities = [
                [chunk.chunk_id for chunk in chunks],      # chunk_id
                [chunk.doc_id for chunk in chunks],       # doc_id
                [chunk.content for chunk in chunks],       # content
                embeddings,                                # vector
                [json.dumps(chunk.metadata) for chunk in chunks],  # metadata
            ]
            
            # 插入数据
            result = self._collection.insert(entities)
            
            # 更新chunk的vector_id
            for i, chunk in enumerate(chunks):
                chunk.vector_id = str(result.primary_keys[i])
            
            # 刷新数据
            self._collection.flush()
            
            return True
        except Exception as e:
            print(f"插入向量数据失败: {e}")
            return False
    
    async def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        filter_conditions: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        向量相似度搜索
        
        Args:
            query_vector: 查询向量
            top_k: 返回前K个结果
            filter_conditions: 过滤条件（doc_id等）
        
        Returns:
            List[SearchResult]: 搜索结果列表
        """
        if not self._collection:
            if not self.connect():
                return []
        
        try:
            from pymilvus import Collection
            
            # 构建搜索参数
            search_params = {
                "metric_type": "L2",
                "params": {"nprobe": 10}
            }
            
            # 执行搜索
            results = self._collection.search(
                data=[query_vector],
                anns_field="vector",
                param=search_params,
                limit=top_k,
                output_fields=["chunk_id", "doc_id", "content", "metadata"]
            )
            
            # 转换为SearchResult
            search_results = []
            for i, hit in enumerate(results[0]):
                # 计算相似度分数（L2距离转换为相似度）
                # 距离越小越相似，转换为1/(1+distance)
                distance = hit.distance
                score = 1 / (1 + distance)
                
                # 解析metadata
                metadata = {}
                if hit.entity.get("metadata"):
                    try:
                        metadata = json.loads(hit.entity["metadata"])
                    except:
                        pass
                
                chunk = TextChunk(
                    chunk_id=hit.entity["chunk_id"],
                    content=hit.entity["content"],
                    doc_id=hit.entity["doc_id"],
                    chunk_index=0,
                    vector_id=str(hit.id),
                    metadata=metadata
                )
                
                search_results.append(SearchResult(
                    chunk=chunk,
                    score=score,
                    rank=i + 1
                ))
            
            return search_results
        except Exception as e:
            print(f"向量搜索失败: {e}")
            return []
    
    async def delete(self, chunk_ids: List[str]) -> bool:
        """
        删除向量数据
        
        Args:
            chunk_ids: 要删除的块ID列表
        
        Returns:
            bool: 删除是否成功
        """
        if not self._collection:
            if not self.connect():
                return False
        
        try:
            # 删除数据
            expr = f"chunk_id in {chunk_ids}"
            self._collection.delete(expr)
            self._collection.flush()
            return True
        except Exception as e:
            print(f"删除向量数据失败: {e}")
            return False


class InMemoryVectorStore(VectorStore):
    """
    内存向量存储（用于测试/开发）
    
    简单的内存实现，不依赖外部服务
    适合小规模数据或测试环境
    """
    
    def __init__(self, dimension: int = 384):
        """
        初始化内存存储
        
        Args:
            dimension: 向量维度
        """
        self.dimension = dimension
        self._vectors: Dict[str, Dict[str, Any]] = {}
        self._ids: List[str] = []
    
    def connect(self) -> bool:
        """内存存储始终可用"""
        return True
    
    async def insert(self, chunks: List[TextChunk], embeddings: List[List[float]]) -> bool:
        """插入向量数据"""
        import math
        
        for i, chunk in enumerate(chunks):
            self._vectors[chunk.chunk_id] = {
                "chunk": chunk,
                "embedding": embeddings[i]
            }
            self._ids.append(chunk.chunk_id)
        
        return True
    
    async def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        filter_conditions: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        简单的余弦相似度搜索
        
        复杂度O(n)，适合小规模数据
        """
        import math
        
        if not self._vectors:
            return []
        
        # 计算所有向量的相似度
        similarities = []
        for chunk_id, data in self._vectors.items():
            embedding = data["embedding"]
            
            # 余弦相似度
            dot_product = sum(a * b for a, b in zip(query_vector, embedding))
            norm1 = math.sqrt(sum(a * a for a in query_vector))
            norm2 = math.sqrt(sum(a * a for a in embedding))
            
            if norm1 > 0 and norm2 > 0:
                similarity = dot_product / (norm1 * norm2)
            else:
                similarity = 0
            
            # 过滤条件
            chunk = data["chunk"]
            if filter_conditions:
                match = True
                for key, value in filter_conditions.items():
                    if chunk.metadata.get(key) != value:
                        match = False
                        break
                if not match:
                    continue
            
            similarities.append((chunk, similarity))
        
        # 按相似度排序
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        # 取前K个
        results = []
        for i, (chunk, score) in enumerate(similarities[:top_k]):
            results.append(SearchResult(
                chunk=chunk,
                score=score,
                rank=i + 1
            ))
        
        return results
    
    async def delete(self, chunk_ids: List[str]) -> bool:
        """删除向量数据"""
        for chunk_id in chunk_ids:
            if chunk_id in self._vectors:
                del self._vectors[chunk_id]
            if chunk_id in self._ids:
                self._ids.remove(chunk_id)
        return True
    
    async def create_collection(self, dimension: int, collection_name: str) -> bool:
        """创建Collection（内存存储无意义）"""
        self.dimension = dimension
        return True


# ============================================================
# RRF排名融合
# ============================================================

class RRFusion:
    """
    RRF (Reciprocal Rank Fusion) 排名融合
    
    将多个检索结果进行融合排序
    RRF是一种简单而有效的融合方法：
    score = Σ(1 / (k + rank_i))
    
    优势：
    - 不需要训练
    - 对不同规模的检索结果都好
    - 简单易实现
    
    Reference: 
    https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf
    """
    
    def __init__(self, k: int = 60):
        """
        初始化RRF融合器
        
        Args:
            k: RRF公式中的常数，用于平滑排名差异
                k值越大，不同排名位置的差异越小
                通常取60
        """
        self.k = k
    
    def fuse(
        self,
        result_lists: List[List[SearchResult]]
    ) -> List[SearchResult]:
        """
        融合多个检索结果
        
        Args:
            result_lists: 多个检索结果列表
        
        Returns:
            List[SearchResult]: 融合后的排序结果
        """
        if not result_lists:
            return []
        
        # 合并所有结果的得分
        chunk_scores: Dict[str, tuple] = {}  # chunk_id -> (chunk, total_score)
        
        for result_list in result_lists:
            for rank, result in enumerate(result_list, start=1):
                chunk_id = result.chunk.chunk_id
                
                # RRF公式计算得分
                rrf_score = 1.0 / (self.k + rank)
                
                if chunk_id in chunk_scores:
                    existing_chunk, existing_score = chunk_scores[chunk_id]
                    chunk_scores[chunk_id] = (existing_chunk, existing_score + rrf_score)
                else:
                    chunk_scores[chunk_id] = (result.chunk, rrf_score)
        
        # 按RRF得分排序
        sorted_chunks = sorted(
            chunk_scores.items(),
            key=lambda x: x[1][1],
            reverse=True
        )
        
        # 构建最终的SearchResult列表
        fused_results = []
        for i, (chunk_id, (chunk, score)) in enumerate(sorted_chunks):
            fused_results.append(SearchResult(
                chunk=chunk,
                score=score,
                rank=i + 1
            ))
        
        return fused_results


# ============================================================
# RAG Pipeline
# ============================================================

class RAGPipeline:
    """
    RAG Pipeline 编排器
    
    整合RAG系统的各个组件，提供端到端的检索增强生成能力
    
    Pipeline流程：
    1. Query Processing: 查询预处理（扩展、同义改写）
    2. Retrieval: 检索（向量 + 关键词）
    3. RRF Fusion: 结果融合
    4. Re-ranking: 重排序（可选）
    5. Generation: 生成增强
    
    Attributes:
        embedding_model: 嵌入模型
        vector_store: 向量存储
        chunker: 分块器
        parser_factory: 文档解析器工厂
        llm_router: LLM路由器（用于生成）
    """
    
    def __init__(
        self,
        embedding_model: Optional[EmbeddingModel] = None,
        vector_store: Optional[VectorStore] = None,
        chunk_size: int = None,
        chunk_overlap: int = None,
        chunk_strategy: ChunkStrategy = ChunkStrategy.RECURSIVE,
        use_hybrid_search: bool = True,
        top_k: int = None,
        similarity_threshold: float = None
    ):
        """
        初始化RAG Pipeline
        
        Args:
            embedding_model: 嵌入模型实例
            vector_store: 向量存储实例
            chunk_size: 分块大小
            chunk_overlap: 分块重叠
            chunk_strategy: 分块策略
            use_hybrid_search: 是否使用混合检索
            top_k: 检索返回数量
            similarity_threshold: 相似度阈值
        """
        # 嵌入模型
        self.embedding_model = embedding_model or EmbeddingModel()
        
        # 向量存储
        self.vector_store = vector_store
        
        # 分块器
        self.chunker = TextChunker(
            strategy=chunk_strategy,
            chunk_size=chunk_size or settings.RAG_CHUNK_SIZE,
            chunk_overlap=chunk_overlap or settings.RAG_CHUNK_OVERLAP
        )
        
        # 文档解析器工厂
        self.parser_factory = DocumentParserFactory()
        
        # RRF融合器
        self.rrf_fusion = RRFusion(k=settings.RAG_RRF_K)
        
        # 配置
        self.use_hybrid_search = use_hybrid_search
        self.top_k = top_k or settings.RAG_TOP_K
        self.similarity_threshold = similarity_threshold or settings.RAG_SIMILARITY_THRESHOLD
        
        # 索引：doc_id -> 文档信息
        self._doc_index: Dict[str, Dict[str, Any]] = {}
    
    def initialize(self) -> bool:
        """
        初始化Pipeline
        
        连接向量数据库，创建索引等
        
        Returns:
            bool: 初始化是否成功
        """
        if self.vector_store:
            return self.vector_store.connect()
        return True
    
    async def add_document(
        self,
        file_path: str,
        document_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        添加文档到知识库
        
        完整流程：解析 -> 分块 -> 向量化 -> 存储
        
        Args:
            file_path: 文档路径
            document_id: 文档ID（可选，不提供则自动生成）
            metadata: 额外的元数据
        
        Returns:
            Dict: 操作结果
        """
        try:
            # 1. 解析文档
            document = self.parser_factory.parse(file_path)
            
            # 如果提供了document_id，使用它
            if document_id:
                document.doc_id = document_id
            
            # 合并元数据
            if metadata:
                document.metadata.update(metadata)
            
            # 2. 分块
            chunks = self.chunker.chunk_document(document)
            
            if not chunks:
                return {
                    "success": False,
                    "error": "文档分块失败或文档为空"
                }
            
            # 3. 向量化
            texts = [chunk.content for chunk in chunks]
            embeddings = self.embedding_model.encode(texts)
            
            # 4. 存储到向量数据库
            if self.vector_store:
                success = await self.vector_store.insert(chunks, embeddings)
                if not success:
                    return {
                        "success": False,
                        "error": "向量存储失败"
                    }
            
            # 5. 更新索引
            self._doc_index[document.doc_id] = {
                "title": document.title,
                "type": document.doc_type.value,
                "metadata": document.metadata,
                "chunk_count": len(chunks)
            }
            
            return {
                "success": True,
                "doc_id": document.doc_id,
                "title": document.title,
                "chunk_count": len(chunks),
                "file_path": file_path
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def delete_document(self, doc_id: str) -> Dict[str, Any]:
        """
        从知识库删除文档
        
        Args:
            doc_id: 文档ID
        
        Returns:
            Dict: 操作结果
        """
        try:
            if doc_id not in self._doc_index:
                return {
                    "success": False,
                    "error": "文档不存在"
                }
            
            # 删除向量数据
            if self.vector_store:
                # 查找所有相关的chunk_id
                chunk_ids = [f"{doc_id}_{i}" for i in range(100)]  # 假设最多100个块
                await self.vector_store.delete(chunk_ids)
            
            # 删除索引
            del self._doc_index[doc_id]
            
            return {
                "success": True,
                "doc_id": doc_id
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def retrieve(
        self,
        query: str,
        top_k: int = None,
        doc_ids: Optional[List[str]] = None,
        use_knowledge: bool = True
    ) -> List[SearchResult]:
        """
        检索相关文档块
        
        Args:
            query: 用户查询
            top_k: 返回结果数量
            doc_ids: 仅从指定文档检索
            use_knowledge: 是否使用知识库
        
        Returns:
            List[SearchResult]: 检索结果列表
        """
        if not use_knowledge:
            return []
        
        top_k = top_k or self.top_k
        
        # 1. 将查询向量化
        query_vector = self.embedding_model.encode_single(query)
        
        # 2. 构建过滤条件
        filter_conditions = None
        if doc_ids:
            filter_conditions = {"doc_id": doc_ids[0]}  # Milvus暂不支持IN查询
        
        # 3. 向量检索
        if self.vector_store:
            results = await self.vector_store.search(
                query_vector,
                top_k=top_k,
                filter_conditions=filter_conditions
            )
        else:
            # 使用内存存储
            memory_store = InMemoryVectorStore()
            await memory_store.insert([], [])
            results = await memory_store.search(query_vector, top_k)
        
        # 4. 过滤低于阈值的结果
        filtered_results = [
            r for r in results
            if r.score >= self.similarity_threshold
        ]
        
        return filtered_results[:top_k]
    
    def build_prompt(
        self,
        query: str,
        context_chunks: List[SearchResult],
        system_prompt: Optional[str] = None
    ) -> str:
        """
        构建增强提示词
        
        将检索到的上下文注入到Prompt中
        
        Args:
            query: 用户问题
            context_chunks: 检索到的相关文档块
            system_prompt: 自定义系统提示词
        
        Returns:
            str: 构建好的提示词
        """
        if not context_chunks:
            return f"问题：{query}\n\n回答："
        
        # 拼接上下文
        context_parts = []
        for i, result in enumerate(context_chunks, start=1):
            source = result.chunk.metadata.get('source', '未知来源')
            title = result.chunk.metadata.get('title', '')
            context_parts.append(
                f"[参考资料{i}](来源: {title})\n{result.chunk.content}"
            )
        
        context_text = "\n\n".join(context_parts)
        
        # 默认系统提示词
        default_system = """你是一个知识渊博的助手。请根据以下参考资料回答问题。

要求：
1. 仅根据参考资料回答，不要编造信息
2. 如果资料中没有相关信息，请如实说明
3. 适当引用参考资料来源
4. 回答要清晰、准确、有条理
"""
        
        system = system_prompt or default_system
        
        # 构建完整Prompt
        prompt = f"""{system}

参考资料：
{context_text}

问题：{query}

回答："""
        
        return prompt
    
    async def query(
        self,
        query: str,
        use_knowledge: bool = True,
        doc_ids: Optional[List[str]] = None,
        system_prompt: Optional[str] = None,
        return_context: bool = False,
        top_k: int = None
    ) -> Dict[str, Any]:
        """
        RAG查询主入口
        
        执行完整的检索-增强-生成流程
        
        Args:
            query: 用户问题
            use_knowledge: 是否使用知识库
            doc_ids: 仅从指定文档检索
            system_prompt: 自定义系统提示词
            return_context: 是否返回检索上下文
            top_k: 检索返回数量
        
        Returns:
            Dict: 包含答案和检索信息的字典
        
        Note:
            LLM生成部分需要接入实际的LLM服务
            当前返回的是带上下文的提示词，供后续使用
        """
        # 1. 检索相关文档
        retrieval_results = await self.retrieve(
            query,
            top_k=top_k,
            doc_ids=doc_ids,
            use_knowledge=use_knowledge
        )
        
        # 2. 构建增强Prompt
        prompt = self.build_prompt(query, retrieval_results, system_prompt)
        
        # TODO: 调用LLM生成答案
        # 需要接入LangChain或直接调用LLM API
        # answer = await self.llm_router.chat(prompt)
        
        # 临时返回
        if use_knowledge and retrieval_results:
            answer = f"[模拟回答] 基于{len(retrieval_results)}个参考资料回答您的问题。"
        else:
            answer = f"[模拟回答] {query}"
        
        # 构建结果
        result = {
            "answer": answer,
            "prompt": prompt,  # 供调试/使用其他LLM
            "model": "mock",
            "use_knowledge": use_knowledge,
        }
        
        if return_context:
            result["retrieval_results"] = [
                {
                    "content": r.chunk.content,
                    "score": r.score,
                    "source": r.chunk.metadata.get('title', ''),
                    "metadata": r.chunk.metadata
                }
                for r in retrieval_results
            ]
        
        return result
    
    def get_document_info(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        获取文档信息
        
        Args:
            doc_id: 文档ID
        
        Returns:
            Dict: 文档信息
        """
        return self._doc_index.get(doc_id)
    
    def list_documents(self) -> List[Dict[str, Any]]:
        """
        列出所有已索引的文档
        
        Returns:
            List[Dict]: 文档列表
        """
        return [
            {"doc_id": doc_id, **info}
            for doc_id, info in self._doc_index.items()
        ]


# ============================================================
# 全局RAG Pipeline实例
# ============================================================

# 全局Pipeline实例
_rag_pipeline: Optional[RAGPipeline] = None


def get_rag_pipeline() -> RAGPipeline:
    """
    获取RAG Pipeline单例
    
    Returns:
        RAGPipeline: Pipeline实例
    """
    global _rag_pipeline
    
    if _rag_pipeline is None:
        _rag_pipeline = RAGPipeline()
        _rag_pipeline.initialize()
    
    return _rag_pipeline


async def initialize_rag_pipeline(
    use_milvus: bool = True,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    top_k: int = 5
) -> RAGPipeline:
    """
    初始化RAG Pipeline
    
    异步初始化方法，用于应用启动时调用
    
    Args:
        use_milvus: 是否使用Milvus（False则使用内存存储）
        chunk_size: 分块大小
        chunk_overlap: 分块重叠
        top_k: 检索返回数量
    
    Returns:
        RAGPipeline: 初始化的Pipeline实例
    """
    global _rag_pipeline
    
    # 创建Pipeline
    if use_milvus:
        # Milvus向量存储
        vector_store = MilvusVectorStore()
        vector_store.connect()
    else:
        # 内存存储（开发/测试用）
        vector_store = InMemoryVectorStore()
    
    # 创建嵌入模型
    embedding_model = EmbeddingModel()
    
    # 创建Pipeline
    _rag_pipeline = RAGPipeline(
        embedding_model=embedding_model,
        vector_store=vector_store,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        top_k=top_k,
        use_hybrid_search=True
    )
    
    return _rag_pipeline
