/**
 * ============================================================
 * 声音克隆页面
 * ============================================================
 * 
 * 声音克隆功能：
 * - 创建声音模型
 * - 上传参考音频
 * - 启动克隆训练
 * - 使用克隆声音合成语音
 * 
 * Author: CoolAI Team
 * Date: 2026-05-13
 */

import { useState, useEffect, useRef } from 'react';
import {
  Card, Row, Col, Button, Typography, Space, Table, Modal, Form,
  Input, Upload, message, Tag, Popconfirm, Spin, Select, Slider,
  Progress, Tooltip, Empty, Divider,
} from 'antd';
import {
  SoundOutlined, PlusOutlined, UploadOutlined, DeleteOutlined,
  PlayCircleOutlined, RocketOutlined, DownloadOutlined,
  ExperimentOutlined, InfoCircleOutlined, AudioOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import type { UploadFile } from 'antd/es/upload/interface';
import { api } from '../../services/api';
import type {
  VoiceModel, VoiceModelsResponse, CloneEnginesResponse,
  CloneSynthesizeResponse, TrainResult, UploadRefResponse,
} from '../../types/auth';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;


/**
 * 声音克隆页面组件
 */
const VoiceClonePage: React.FC = () => {
  // 声音模型列表
  const [models, setModels] = useState<VoiceModel[]>([]);
  const [availableEngine, setAvailableEngine] = useState<string>('');
  const [enginesInfo, setEnginesInfo] = useState<CloneEnginesResponse | null>(null);
  const [loading, setLoading] = useState(false);

  // 创建模型弹窗
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [createForm] = Form.useForm();
  const [creating, setCreating] = useState(false);

  // 上传参考音频
  const [uploadingModelId, setUploadingModelId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  // 训练
  const [trainingModelId, setTrainingModelId] = useState<string | null>(null);
  const [training, setTraining] = useState(false);

  // 合成弹窗
  const [synthModalOpen, setSynthModalOpen] = useState(false);
  const [synthModel, setSynthModel] = useState<VoiceModel | null>(null);
  const [synthForm] = Form.useForm();
  const [synthesizing, setSynthesizing] = useState(false);
  const [synthAudioUrl, setSynthAudioUrl] = useState<string | null>(null);

  // ============================================================
  // 数据加载
  // ============================================================

  /** 加载声音模型列表 */
  const fetchModels = async () => {
    setLoading(true);
    try {
      const data: VoiceModelsResponse = await api.get('/voice/models');
      setModels(data.models || []);
      setAvailableEngine(data.available_engine || 'edge_simulate');
    } catch (err: any) {
      message.error('加载声音模型失败');
    } finally {
      setLoading(false);
    }
  };

  /** 加载引擎信息 */
  const fetchEngines = async () => {
    try {
      const data: CloneEnginesResponse = await api.get('/voice/engines');
      setEnginesInfo(data);
    } catch {
      // 静默失败
    }
  };

  useEffect(() => {
    fetchModels();
    fetchEngines();
  }, []);

  // ============================================================
  // 创建模型
  // ============================================================

  const handleCreateModel = async () => {
    try {
      const values = await createForm.validateFields();
      setCreating(true);
      await api.post('/voice/models', {
        name: values.name,
        description: values.description,
      });
      message.success('声音模型创建成功');
      setCreateModalOpen(false);
      createForm.resetFields();
      fetchModels();
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error(err?.detail || '创建失败');
    } finally {
      setCreating(false);
    }
  };

  // ============================================================
  // 上传参考音频
  // ============================================================

  const handleUploadRef = async (modelId: string, file: File) => {
    setUploadingModelId(modelId);
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const result: UploadRefResponse = await api.post(
        `/voice/models/${modelId}/reference`,
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } },
      );
      if (result.success) {
        message.success(`参考音频上传成功，时长: ${result.duration?.toFixed(1) || '?'}秒`);
        fetchModels();
      } else {
        message.error(result.error || '上传失败');
      }
    } catch (err: any) {
      message.error(err?.detail || '上传参考音频失败');
    } finally {
      setUploadingModelId(null);
      setUploading(false);
    }
  };

  // ============================================================
  // 启动训练
  // ============================================================

  const handleTrain = async (modelId: string) => {
    setTrainingModelId(modelId);
    setTraining(true);
    try {
      const result: TrainResult = await api.post(`/voice/models/${modelId}/train`);
      message.success(result.message || '训练已启动');
      fetchModels();
    } catch (err: any) {
      message.error(err?.detail || '训练启动失败');
    } finally {
      setTrainingModelId(null);
      setTraining(false);
    }
  };

  // ============================================================
  // 删除模型
  // ============================================================

  const handleDelete = async (modelId: string) => {
    try {
      await api.delete(`/voice/models/${modelId}`);
      message.success('模型已删除');
      fetchModels();
    } catch (err: any) {
      message.error(err?.detail || '删除失败');
    }
  };

  // ============================================================
  // 克隆合成
  // ============================================================

  const openSynthModal = (model: VoiceModel) => {
    setSynthModel(model);
    setSynthAudioUrl(null);
    synthForm.resetFields();
    synthForm.setFieldsValue({ speed: 1.0, format: 'mp3' });
    setSynthModalOpen(true);
  };

  const handleSynthesize = async () => {
    if (!synthModel) return;
    try {
      const values = await synthForm.validateFields();
      setSynthesizing(true);
      setSynthAudioUrl(null);

      const result: CloneSynthesizeResponse = await api.post('/voice/synthesize', {
        text: values.text,
        model_id: synthModel.id,
        speed: values.speed,
        format: values.format,
      });

      if (result.success && result.output_path) {
        // 通过后端静态文件服务获取音频
        const audioUrl = `/api/v1/voice/audio/${result.output_path.split('/').pop()}`;
        setSynthAudioUrl(audioUrl);
        message.success(`合成成功（引擎: ${result.engine}）`);
      } else {
        message.error(result.error || '合成失败');
      }
    } catch (err: any) {
      message.error(err?.detail || '合成失败');
    } finally {
      setSynthesizing(false);
    }
  };

  // ============================================================
  // 表格列定义
  // ============================================================

  const columns = [
    {
      title: '模型名称',
      dataIndex: 'name',
      key: 'name',
      render: (name: string) => (
        <Space>
          <SoundOutlined style={{ color: '#8B5CF6' }} />
          <Text strong>{name}</Text>
        </Space>
      ),
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      render: (desc: string) => desc || <Text type="secondary">暂无描述</Text>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const config: Record<string, { color: string; label: string }> = {
          pending: { color: 'default', label: '待上传' },
          training: { color: 'processing', label: '训练中' },
          ready: { color: 'success', label: '就绪' },
          failed: { color: 'error', label: '失败' },
        };
        const c = config[status] || { color: 'default', label: status };
        return <Tag color={c.color}>{c.label}</Tag>;
      },
    },
    {
      title: '参考音频',
      dataIndex: 'reference_audio',
      key: 'reference_audio',
      render: (ref: string) => ref
        ? <Tag color="blue" icon={<AudioOutlined />}>已上传</Tag>
        : <Tag>未上传</Tag>,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (time: string) => time ? new Date(time).toLocaleString('zh-CN') : '-',
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: VoiceModel) => (
        <Space>
          {!record.reference_audio && (
            <Upload
              accept=".wav,.mp3"
              showUploadList={false}
              beforeUpload={(file) => {
                handleUploadRef(record.id, file);
                return false;
              }}
            >
              <Button
                size="small"
                icon={<UploadOutlined />}
                loading={uploadingModelId === record.id}
              >
                上传音频
              </Button>
            </Upload>
          )}
          {record.reference_audio && record.status === 'pending' && (
            <Button
              size="small"
              type="primary"
              icon={<RocketOutlined />}
              onClick={() => handleTrain(record.id)}
              loading={trainingModelId === record.id}
            >
              开始训练
            </Button>
          )}
          {record.status === 'ready' && (
            <Button
              size="small"
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={() => openSynthModal(record)}
            >
              合成语音
            </Button>
          )}
          <Popconfirm
            title="确定删除该声音模型？"
            onConfirm={() => handleDelete(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  // ============================================================
  // 渲染
  // ============================================================

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Title level={3} style={{ margin: 0 }}>声音克隆</Title>
          <Text type="secondary">上传参考音频，克隆专属声音</Text>
        </Col>
        <Col>
          <Space>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => setCreateModalOpen(true)}
            >
              创建声音模型
            </Button>
          </Space>
        </Col>
      </Row>

      {/* 引擎状态卡片 */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={8}>
          <Card size="small">
            <Space>
              <ThunderboltOutlined style={{ fontSize: 24, color: '#3B82F6' }} />
              <div>
                <Text type="secondary">当前引擎</Text>
                <div>
                  <Text strong>
                    {availableEngine === 'xtts_v2' ? 'XTTS-v2 零样本克隆' : 'Edge-TTS 音色模拟'}
                  </Text>
                </div>
              </div>
            </Space>
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small">
            <Space>
              <ExperimentOutlined style={{ fontSize: 24, color: enginesInfo?.engines?.[0]?.available ? '#52C41A' : '#FAAD14' }} />
              <div>
                <Text type="secondary">XTTS-v2 (GPU)</Text>
                <div>
                  <Tag color={enginesInfo?.engines?.[0]?.available ? 'success' : 'warning'}>
                    {enginesInfo?.engines?.[0]?.available ? '可用' : '不可用'}
                  </Tag>
                </div>
              </div>
            </Space>
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small">
            <Space>
              <AudioOutlined style={{ fontSize: 24, color: '#52C41A' }} />
              <div>
                <Text type="secondary">Edge-TTS 模拟</Text>
                <div><Tag color="success">始终可用</Tag></div>
              </div>
            </Space>
          </Card>
        </Col>
      </Row>

      {/* 声音模型列表 */}
      <Card>
        <Table
          columns={columns}
          dataSource={models}
          rowKey="id"
          loading={loading}
          pagination={false}
          locale={{
            emptyText: (
              <Empty
                description="暂无声音模型"
                image={Empty.PRESENTED_IMAGE_SIMPLE}
              >
                <Button
                  type="primary"
                  icon={<PlusOutlined />}
                  onClick={() => setCreateModalOpen(true)}
                >
                  创建第一个声音模型
                </Button>
              </Empty>
            ),
          }}
        />
      </Card>

      {/* 使用说明 */}
      <Card size="small" style={{ marginTop: 16 }}>
        <Title level={5}>
          <InfoCircleOutlined style={{ marginRight: 8 }} />
          使用说明
        </Title>
        <Row gutter={24}>
          <Col span={12}>
            <Paragraph type="secondary" style={{ marginBottom: 4 }}>
              <Text strong>1. 创建模型</Text> - 输入名称和描述创建声音模型
            </Paragraph>
            <Paragraph type="secondary" style={{ marginBottom: 4 }}>
              <Text strong>2. 上传音频</Text> - 上传3~30秒的参考音频（WAV/MP3）
            </Paragraph>
            <Paragraph type="secondary" style={{ marginBottom: 0 }}>
              <Text strong>3. 开始训练</Text> - XTTS-v2零样本克隆无需等待训练
            </Paragraph>
          </Col>
          <Col span={12}>
            <Paragraph type="secondary" style={{ marginBottom: 4 }}>
              <Text strong>4. 合成语音</Text> - 使用克隆的声音合成任意文本
            </Paragraph>
            <Paragraph type="secondary" style={{ marginBottom: 4 }}>
              <Text strong>GPU加速</Text> - XTTS-v2需GPU（显存>=4GB），无GPU自动降级为Edge-TTS模拟
            </Paragraph>
            <Paragraph type="secondary" style={{ marginBottom: 0 }}>
              <Text strong>音质建议</Text> - 参考音频越清晰，克隆效果越好
            </Paragraph>
          </Col>
        </Row>
      </Card>

      {/* 创建模型弹窗 */}
      <Modal
        title="创建声音模型"
        open={createModalOpen}
        onOk={handleCreateModel}
        onCancel={() => {
          setCreateModalOpen(false);
          createForm.resetFields();
        }}
        confirmLoading={creating}
        okText="创建"
        cancelText="取消"
      >
        <Form form={createForm} layout="vertical">
          <Form.Item
            name="name"
            label="声音名称"
            rules={[
              { required: true, message: '请输入声音名称' },
              { max: 50, message: '名称不能超过50个字符' },
            ]}
          >
            <Input placeholder="例如：我的声音、播音腔" />
          </Form.Item>
          <Form.Item
            name="description"
            label="描述"
            rules={[{ max: 200, message: '描述不能超过200个字符' }]}
          >
            <TextArea rows={3} placeholder="可选：对声音特征的描述（如：男声、低沉、磁性）" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 克隆合成弹窗 */}
      <Modal
        title={`语音合成 - ${synthModel?.name || ''}`}
        open={synthModalOpen}
        onCancel={() => {
          setSynthModalOpen(false);
          setSynthAudioUrl(null);
        }}
        width={600}
        footer={null}
      >
        <Form form={synthForm} layout="vertical">
          <Form.Item
            name="text"
            label="待合成文本"
            rules={[
              { required: true, message: '请输入要合成的文本' },
              { max: 5000, message: '文本长度不能超过5000字' },
            ]}
          >
            <TextArea
              rows={5}
              placeholder="请输入要使用克隆声音合成的文本..."
              showCount
              maxLength={5000}
            />
          </Form.Item>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="speed" label="语速">
                <Slider
                  min={0.5}
                  max={2.0}
                  step={0.1}
                  marks={{ 0.5: '0.5x', 1: '1x', 1.5: '1.5x', 2: '2x' }}
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="format" label="输出格式">
                <Select options={[
                  { label: 'MP3', value: 'mp3' },
                  { label: 'WAV', value: 'wav' },
                ]} />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item>
            <Space>
              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                onClick={handleSynthesize}
                loading={synthesizing}
              >
                开始合成
              </Button>
              {synthAudioUrl && (
                <Button
                  icon={<DownloadOutlined />}
                  onClick={() => {
                    const link = document.createElement('a');
                    link.href = synthAudioUrl;
                    link.download = `clone_${synthModel?.id}_${Date.now()}.mp3`;
                    link.click();
                  }}
                >
                  下载
                </Button>
              )}
            </Space>
          </Form.Item>
        </Form>

        {/* 合成结果预览 */}
        {synthesizing && (
          <div style={{ textAlign: 'center', padding: 30 }}>
            <Spin size="large" />
            <div style={{ marginTop: 12 }}>
              <Text type="secondary">正在合成语音，请稍候...</Text>
            </div>
          </div>
        )}
        {synthAudioUrl && !synthesizing && (
          <Card size="small" style={{ background: '#f6f8fa' }}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Text strong>合成结果</Text>
              <audio controls src={synthAudioUrl} style={{ width: '100%' }} />
            </Space>
          </Card>
        )}
      </Modal>
    </div>
  );
};

export default VoiceClonePage;
