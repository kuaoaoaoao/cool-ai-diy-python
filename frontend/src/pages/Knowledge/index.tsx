/**
 * ============================================================
 * 知识库管理页面
 * ============================================================
 * 
 * 管理RAG知识库
 * - 知识库列表
 * - 文档上传
 * - 检索测试
 * 
 * Author: CoolAI Team
 * Date: 2026-05-13
 */

import { useState } from 'react';
import {
  Card, Table, Button, Space, Modal, Form, Input, Upload,
  Tag, Typography, Popconfirm, message, Progress, Empty, Row, Col
} from 'antd';
import {
  PlusOutlined, UploadOutlined, DeleteOutlined, SearchOutlined,
  FileTextOutlined, DatabaseOutlined
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../services/api';
import type { KnowledgeBase, Document, UploadProps } from 'antd';

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

        {/* 右侧：文档和检索 */}
        <Col span={16}>
          {selectedKB ? (
            <Space direction="vertical" style={{ width: '100%' }} size="large">
              {/* 检索测试 */}
              <Card title={<><SearchOutlined /> 检索测试</>}>
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
              </Card>

              {/* 文档管理 */}
              <Card
                title={<><FileTextOutlined /> 文档管理</>}
                extra={
                  <Upload
                    showUploadList={false}
                    beforeUpload={(file) => {
                      uploadMutation.mutate({ file });
                      return false;
                    }}
                  >
                    <Button icon={<UploadOutlined />}>上传文档</Button>
                  </Upload>
                }
              >
                <Table
                  dataSource={documents || []}
                  rowKey="id"
                  columns={documentColumns}
                  pagination={{ pageSize: 10 }}
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
