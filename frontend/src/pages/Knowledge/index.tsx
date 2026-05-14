/**
 * ============================================================
 * 知识库管理页面
 * ============================================================
 * 
 * 管理RAG知识库
 * - 知识库列表
 * - 文档上传
 * - 检索测试
 * - RAG知识问答（新增）
 * 
 * Author: CoolAI Team
 * Date: 2026-05-13
 */

import { useState } from 'react';
import {
  Card, Table, Button, Space, Modal, Form, Input, Upload, Tabs,
  Tag, Typography, Popconfirm, message, Progress, Empty, Row, Col, List
} from 'antd';
import {
  PlusOutlined, UploadOutlined, DeleteOutlined, SearchOutlined,
  FileTextOutlined, DatabaseOutlined, QuestionCircleOutlined,
  RobotOutlined, BookOutlined
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../services/api';
import type { KnowledgeBase, Document, KnowledgeQueryResponse } from '../../types/auth';

const { Title, Text, Paragraph } = Typography;
const { Dragger } = Upload;

/**
 * 知识库页面组件
 */
const KnowledgePage: React.FC = () => {
  const queryClient = useQueryClient();
  
  // 状态
  const [createModalVisible, setCreateModalVisible] = useState(false);
  const [selectedKB, setSelectedKB] = useState<KnowledgeBase | null>(null);
  const [searchText, setSearchText] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);
  
  // RAG问答相关状态
  const [qaQuestion, setQaQuestion] = useState('');
  const [qaAnswer, setQaAnswer] = useState('');
  const [qaReferences, setQaReferences] = useState<any[]>([]);
  const [qaLoading, setQaLoading] = useState(false);
  
  // 创建知识库表单
  const [createForm] = Form.useForm();

  // 获取知识库列表
  const { data: knowledgeBases, isLoading } = useQuery<KnowledgeBase[]>({
    queryKey: ['knowledgeBases'],
    queryFn: () => api.get('/knowledge/bases'),
  });

  // 获取文档列表
  const { data: documents } = useQuery<Document[]>({
    queryKey: ['documents', selectedKB?.id],
    queryFn: () => api.get(`/knowledge/bases/${selectedKB?.id}/documents`),
    enabled: !!selectedKB,
  });

  // 创建知识库
  const createKBMutation = useMutation({
    mutationFn: (data: { name: string; description?: string }) =>
      api.post('/knowledge/bases', data),
    onSuccess: () => {
      message.success('知识库创建成功');
      setCreateModalVisible(false);
      createForm.resetFields();
      queryClient.invalidateQueries({ queryKey: ['knowledgeBases'] });
    },
  });

  // 删除知识库
  const deleteKBMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/knowledge/bases/${id}`),
    onSuccess: () => {
      message.success('知识库已删除');
      queryClient.invalidateQueries({ queryKey: ['knowledgeBases'] });
      if (selectedKB) setSelectedKB(null);
    },
  });

  // 知识检索
  const searchMutation = useMutation({
    mutationFn: (data: { query: string; top_k?: number }) =>
      api.post(`/knowledge/bases/${selectedKB?.id}/query`, data),
    onSuccess: (response) => {
      setSearchResults(response.results || []);
    },
  });

  // 上传文档
  const uploadMutation = useMutation({
    mutationFn: ({ file }: { file: File }) => {
      const formData = new FormData();
      formData.append('file', file);
      return api.post(`/knowledge/bases/${selectedKB?.id}/documents`, formData);
    },
    onSuccess: () => {
      message.success('文档上传成功');
      queryClient.invalidateQueries({ queryKey: ['documents'] });
    },
  });

  // 处理创建知识库
  const handleCreateKB = async () => {
    try {
      const values = await createForm.validateFields();
      createKBMutation.mutate(values);
    } catch (error) {
      // 表单验证失败
    }
  };

  /**
   * RAG知识问答
   * 调用后端 /knowledge/bases/{id}/query 接口，获取增强回答
   */
  const handleRAGQuery = async () => {
    if (!qaQuestion.trim() || !selectedKB) return;
    
    setQaLoading(true);
    setQaAnswer('');
    setQaReferences([]);
    
    try {
      const response = await api.post<KnowledgeQueryResponse & { answer?: string; model?: string }>(
        `/knowledge/bases/${selectedKB.id}/query`,
        { query: qaQuestion, generate_answer: true, return_context: true }
      );
      
      // 如果后端返回了答案（RAG Pipeline已对接LLM）
      if (response.answer) {
        setQaAnswer(response.answer);
      } else if (response.results && response.results.length > 0) {
        // 降级：只有检索结果，拼接为简易答案
        setQaAnswer(`基于${response.results.length}条检索结果：\n\n` +
          response.results.map((r, i) => `[${i+1}] ${r.content}`).join('\n\n')
        );
      } else {
        setQaAnswer('未找到相关内容，请尝试换个问题或上传更多文档。');
      }
      
      // 保存参考来源
      if (response.results) {
        setQaReferences(response.results);
      }
    } catch (error: any) {
      setQaAnswer('查询失败：' + (error?.response?.data?.detail || error.message));
    } finally {
      setQaLoading(false);
    }
  };

  // 文档列定义
  const documentColumns = [
    {
      title: '文件名',
      dataIndex: 'filename',
      key: 'filename',
      render: (text: string) => (
        <Space>
          <FileTextOutlined />
          {text}
        </Space>
      ),
    },
    {
      title: '大小',
      dataIndex: 'file_size',
      key: 'file_size',
      render: (size: number) => size ? `${(size / 1024 / 1024).toFixed(2)} MB` : '-',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const statusMap: Record<string, { color: string; text: string }> = {
          pending: { color: 'default', text: '等待中' },
          processing: { color: 'processing', text: '处理中' },
          completed: { color: 'success', text: '完成' },
          failed: { color: 'error', text: '失败' },
        };
        const config = statusMap[status] || statusMap.pending;
        return <Tag color={config.color}>{config.text}</Tag>;
      },
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: Document) => (
        <Popconfirm
          title="确定删除此文档？"
          onConfirm={() => message.info('删除功能开发中')}
        >
          <Button type="text" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      ),
    },
  ];

  return (
    <div>
      <Title level={3}>知识库管理</Title>
      
      <Row gutter={16}>
        {/* 左侧：知识库列表 */}
        <Col span={8}>
          <Card
            title={<Space><DatabaseOutlined /> 知识库</Space>}
            extra={
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={() => setCreateModalVisible(true)}
              >
                新建
              </Button>
            }
          >
            <Table
              loading={isLoading}
              dataSource={knowledgeBases || []}
              rowKey="id"
              size="small"
              pagination={false}
              rowSelection={{
                selectedRowKeys: selectedKB ? [selectedKB.id] : [],
                onChange: (keys) => {
                  const kb = knowledgeBases?.find((k) => k.id === keys[0]);
                  setSelectedKB(kb || null);
                },
              }}
              columns={[
                { title: '名称', dataIndex: 'name', key: 'name' },
                { 
                  title: '文档', 
                  dataIndex: 'doc_count', 
                  key: 'doc_count',
                  render: (count: number) => `${count || 0} 个`,
                },
                {
                  title: '操作',
                  key: 'action',
                  render: (_: any, record: KnowledgeBase) => (
                    <Popconfirm
                      title="确定删除此知识库？"
                      onConfirm={() => deleteKBMutation.mutate(record.id)}
                    >
                      <Button type="text" danger icon={<DeleteOutlined />} size="small" />
                    </Popconfirm>
                  ),
                },
              ]}
            />
          </Card>
        </Col>

        {/* 右侧：文档、检索和问答 */}
        <Col span={16}>
          {selectedKB ? (
            <Space direction="vertical" style={{ width: '100%' }} size="large">
              {/* Tab切换：检索测试 / 知识问答 / 文档管理 */}
              <Card>
                <Tabs
                  defaultActiveKey="search"
                  items={[
                    {
                      key: 'search',
                      label: <span><SearchOutlined /> 检索测试</span>,
                      children: (
                        <>
                          <Space.Compact style={{ width: '100%', marginBottom: 16 }}>
                            <Input.Search
                              placeholder="输入问题进行检索..."
                              enterButton={<Button type="primary" icon={<SearchOutlined />}>检索</Button>}
                              onSearch={(value) => searchMutation.mutate({ query: value })}
                              loading={searchMutation.isPending}
                            />
                          </Space.Compact>
                          
                          {searchResults.length > 0 ? (
                            <div>
                              <Text type="secondary">找到 {searchResults.length} 条相关结果</Text>
                              {searchResults.map((result, index) => (
                                <Card key={index} size="small" style={{ marginTop: 8 }}>
                                  <Paragraph ellipsis={{ rows: 3 }}>{result.content}</Paragraph>
                                  <Text type="secondary" style={{ fontSize: 12 }}>
                                    相似度: {(result.score * 100).toFixed(1)}%
                                    {result.source && ` | 来源: ${result.source}`}
                                  </Text>
                                </Card>
                              ))}
                            </div>
                          ) : (
                            <Empty description="输入问题查看检索结果" />
                          )}
                        </>
                      ),
                    },
                    {
                      key: 'qa',
                      label: <span><QuestionCircleOutlined /> 知识问答</span>,
                      children: (
                        <div>
                          <div style={{ marginBottom: 16, padding: 12, background: '#f6f8fa', borderRadius: 8 }}>
                            <Space>
                              <RobotOutlined style={{ color: '#8B5CF6', fontSize: 16 }} />
                              <Text>基于「{selectedKB.name}」知识库的AI问答，输入问题获取智能回答</Text>
                            </Space>
                          </div>
                          
                          <Space.Compact style={{ width: '100%', marginBottom: 16 }}>
                            <Input
                              placeholder="输入你的问题，AI将基于知识库内容回答..."
                              value={qaQuestion}
                              onChange={(e) => setQaQuestion(e.target.value)}
                              onPressEnter={handleRAGQuery}
                              size="large"
                            />
                            <Button
                              type="primary"
                              icon={<RobotOutlined />}
                              onClick={handleRAGQuery}
                              loading={qaLoading}
                              size="large"
                            >
                              提问
                            </Button>
                          </Space.Compact>
                          
                          {/* AI回答区域 */}
                          {qaAnswer && (
                            <Card
                              style={{ marginTop: 16 }}
                              title={
                                <Space>
                                  <RobotOutlined style={{ color: '#8B5CF6' }} />
                                  <span>AI回答</span>
                                </Space>
                              }
                            >
                              <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.8 }}>
                                {qaAnswer}
                              </div>
                              
                              {/* 参考来源 */}
                              {qaReferences.length > 0 && (
                                <div style={{ marginTop: 16, borderTop: '1px solid #f0f0f0', paddingTop: 12 }}>
                                  <Text type="secondary" style={{ fontSize: 12 }}>
                                    <BookOutlined /> 参考 {qaReferences.length} 条来源
                                  </Text>
                                  <List
                                    size="small"
                                    dataSource={qaReferences}
                                    renderItem={(ref, idx) => (
                                      <List.Item style={{ padding: '4px 0' }}>
                                        <Paragraph
                                          ellipsis={{ rows: 2 }}
                                          style={{ margin: 0, fontSize: 12, color: '#666' }}
                                        >
                                          [{idx + 1}] {ref.content}
                                          {ref.score && <Tag style={{ marginLeft: 4 }} color="blue">{(ref.score * 100).toFixed(0)}%</Tag>}
                                        </Paragraph>
                                      </List.Item>
                                    )}
                                  />
                                </div>
                              )}
                            </Card>
                          )}
                          
                          {!qaAnswer && !qaLoading && (
                            <Empty
                              description="输入问题开始知识问答"
                              image={Empty.PRESENTED_IMAGE_SIMPLE}
                            />
                          )}
                        </div>
                      ),
                    },
                    {
                      key: 'docs',
                      label: <span><FileTextOutlined /> 文档管理</span>,
                      children: (
                        <>
                          <div style={{ marginBottom: 16 }}>
                            <Upload
                              showUploadList={false}
                              beforeUpload={(file) => {
                                uploadMutation.mutate({ file });
                                return false;
                              }}
                            >
                              <Button icon={<UploadOutlined />} type="primary">
                                上传文档
                              </Button>
                            </Upload>
                            <Text type="secondary" style={{ marginLeft: 8, fontSize: 12 }}>
                              支持 PDF、Word、TXT、Markdown 格式
                            </Text>
                          </div>
                          <Table
                            dataSource={documents || []}
                            rowKey="id"
                            columns={documentColumns}
                            pagination={{ pageSize: 10 }}
                          />
                        </>
                      ),
                    },
                  ]}
                />
              </Card>
            </Space>
          ) : (
            <Card>
              <Empty description="请选择一个知识库" />
            </Card>
          )}
        </Col>
      </Row>

      {/* 创建知识库弹窗 */}
      <Modal
        title="新建知识库"
        open={createModalVisible}
        onOk={handleCreateKB}
        onCancel={() => setCreateModalVisible(false)}
        confirmLoading={createKBMutation.isPending}
      >
        <Form form={createForm} layout="vertical">
          <Form.Item
            name="name"
            label="知识库名称"
            rules={[{ required: true, message: '请输入知识库名称' }]}
          >
            <Input placeholder="请输入知识库名称" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={3} placeholder="可选：知识库描述" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default KnowledgePage;
