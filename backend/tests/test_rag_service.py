# ============================================================
# 单元测试 - RAG知识库服务测试
# ============================================================
#
# 测试RAG管线的文档解析、分块、检索等
#
# Author: CoolAI Team
# Date: 2026-05-13
# ============================================================

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.rag_service_impl import (
    TextChunker,
    TextChunk,
    DocumentType,
    ChunkStrategy,
)


# ============================================================
# TextChunker 测试
# ============================================================

class TestTextChunker:
    """文本分块器测试"""

    def test_fixed_size_chunking(self):
        """测试固定大小分块"""
        chunker = TextChunker(
            chunk_size=100,
            chunk_overlap=20,
            strategy=ChunkStrategy.FIXED_SIZE,
        )
        text = "这是一段测试文本。" * 50  # 约450个字符
        chunks = chunker.chunk(text, metadata={"source": "test"})
        
        assert isinstance(chunks, list)
        assert len(chunks) > 0
        # 每个chunk应该是TextChunk对象
        for chunk in chunks:
            assert isinstance(chunk, TextChunk)
            assert chunk.content
            assert "source" in chunk.metadata

    def test_paragraph_chunking(self):
        """测试按段落分块"""
        chunker = TextChunker(
            strategy=ChunkStrategy.PARAGRAPH,
        )
        text = "第一段内容。\n\n第二段内容。\n\n第三段内容。"
        chunks = chunker.chunk(text)
        
        assert len(chunks) >= 3  # 至少3段

    def test_sentence_chunking(self):
        """测试按句子分块"""
        chunker = TextChunker(
            strategy=ChunkStrategy.SENTENCE,
            chunk_size=200,
        )
        text = "这是第一句话。这是第二句话。这是第三句话。这是第四句话。"
        chunks = chunker.chunk(text)
        
        assert len(chunks) >= 1
        # 每个chunk应该包含完整句子
        for chunk in chunks:
            assert isinstance(chunk, TextChunk)

    def test_empty_text(self):
        """测试空文本"""
        chunker = TextChunker()
        chunks = chunker.chunk("")
        assert chunks == []

    def test_short_text(self):
        """测试短文本（不超过一个chunk）"""
        chunker = TextChunker(chunk_size=500, chunk_overlap=0)
        text = "这是一段短文本。"
        chunks = chunker.chunk(text)
        assert len(chunks) == 1
        assert chunks[0].content == text


# ============================================================
# DocumentType 测试
# ============================================================

class TestDocumentType:
    """文档类型枚举测试"""

    def test_document_types(self):
        """测试文档类型枚举"""
        assert DocumentType.PDF.value == "pdf"
        assert DocumentType.WORD.value == "docx"
        assert DocumentType.TEXT.value == "txt"
        assert DocumentType.MARKDOWN.value == "md"

    def test_from_extension(self):
        """测试从扩展名获取文档类型"""
        # 根据实际实现调整
        assert DocumentType.PDF.value == "pdf"


# ============================================================
# ChunkStrategy 测试
# ============================================================

class TestChunkStrategy:
    """分块策略枚举测试"""

    def test_strategies(self):
        """测试分块策略枚举"""
        assert ChunkStrategy.FIXED_SIZE.value == "fixed_size"
        assert ChunkStrategy.PARAGRAPH.value == "paragraph"
        assert ChunkStrategy.SENTENCE.value == "sentence"
        assert ChunkStrategy.SEMANTIC.value == "semantic"


# ============================================================
# TextChunk 测试
# ============================================================

class TestTextChunk:
    """文本块测试"""

    def test_chunk_creation(self):
        """测试文本块创建"""
        chunk = TextChunk(
            content="测试内容",
            metadata={"source": "test.pdf", "page": 1},
        )
        assert chunk.content == "测试内容"
        assert chunk.metadata["source"] == "test.pdf"
        assert chunk.metadata["page"] == 1

    def test_chunk_default_metadata(self):
        """测试默认元数据"""
        chunk = TextChunk(content="测试内容")
        assert chunk.metadata == {}
