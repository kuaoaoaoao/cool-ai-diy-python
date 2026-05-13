/**
 * ============================================================
 * TTS语音合成页面
 * ============================================================
 * 
 * 文字转语音功能
 * - 文本输入
 * - 语音选择
 * - 参数调节
 * 
 * Author: CoolAI Team
 * Date: 2026-05-13
 */

import { useState } from 'react';
import { Card, Form, Input, Select, Slider, Button, Typography, Space, Row, Col, message, Spin, AudioRecorder } from 'antd';
import { AudioOutlined, PlayCircleOutlined, DownloadOutlined, ReloadOutlined } from '@ant-design/icons';
import { useQuery, useMutation } from '@tanstack/react-query';
import { api } from '../../services/api';
import type { VoiceInfo } from '../../types/auth';

const { Title, Text } = Typography;
const { TextArea } = Input;

/**
 * TTS页面组件
 */
const TTTSPage: React.FC = () => {
  // 状态
  const [form] = Form.useForm();
  const [selectedVoice, setSelectedVoice] = useState<string>('zh-CN-XiaoxiaoNeural');
  const [speed, setSpeed] = useState<number>(1.0);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);

  // 获取可用语音列表
  const { data: voiceList } = useQuery<VoiceInfo[]>({
    queryKey: ['voices'],
    queryFn: () => api.get('/tts/voices'),
  });

  // 合成语音
  const synthesizeMutation = useMutation({
    mutationFn: (data: { text: string; voice: string; speed: number; format: string }) =>
      api.post('/tts/synthesize', data, { responseType: 'blob' }),
    onSuccess: (response) => {
      // 创建音频URL
      const blob = new Blob([response], { type: 'audio/mp3' });
      const url = URL.createObjectURL(blob);
      setAudioUrl(url);
      message.success('语音合成成功');
    },
    onError: () => {
      message.error('语音合成失败');
    },
  });

  // 处理合成
  const handleSynthesize = async () => {
    try {
      const values = await form.validateFields();
      setAudioUrl(null);
      synthesizeMutation.mutate({
        text: values.text,
        voice: selectedVoice,
        speed: speed,
        format: 'mp3',
      });
    } catch (error) {
      // 表单验证失败
    }
  };

  // 下载音频
  const handleDownload = () => {
    if (!audioUrl) return;
    
    const link = document.createElement('a');
    link.href = audioUrl;
    link.download = `tts_${Date.now()}.mp3`;
    link.click();
  };

  // 内置语音选项
  const builtInVoices = voiceList?.filter(v => !v.is_custom) || [
    { voice_id: 'zh-CN-XiaoxiaoNeural', name: '晓晓（女声）', language: 'zh-CN', gender: 'Female' },
    { voice_id: 'zh-CN-XiaoyiNeural', name: '小艺（女声）', language: 'zh-CN', gender: 'Female' },
    { voice_id: 'zh-CN-YunxiNeural', name: '云希（女声）', language: 'zh-CN', gender: 'Female' },
    { voice_id: 'zh-CN-YunyangNeural', name: '云扬（男声）', language: 'zh-CN', gender: 'Male' },
  ];

  return (
    <div>
      <Title level={3}>语音合成</Title>
      <Text type="secondary">将文字转换为自然流畅的语音</Text>

      <Row gutter={24} style={{ marginTop: 24 }}>
        {/* 左侧：输入区域 */}
        <Col span={14}>
          <Card title="文本输入">
            <Form form={form} layout="vertical">
              <Form.Item
                name="text"
                label="待合成文本"
                rules={[
                  { required: true, message: '请输入要合成的文本' },
                  { max: 10000, message: '文本长度不能超过10000字' },
                ]}
              >
                <TextArea
                  rows={8}
                  placeholder="请输入要转换为语音的文本..."
                  showCount
                  maxLength={10000}
                />
              </Form.Item>
            </Form>

            {/* 参数调节 */}
            <Card size="small" title="参数调节" style={{ marginTop: 16 }}>
              <Space direction="vertical" style={{ width: '100%' }}>
                <div>
                  <Text>选择语音：</Text>
                  <Select
                    value={selectedVoice}
                    onChange={setSelectedVoice}
                    style={{ width: '100%', marginTop: 8 }}
                    options={builtInVoices.map(v => ({
                      label: `${v.name} (${v.language})`,
                      value: v.voice_id,
                    }))}
                  />
                </div>

                <div>
                  <Space>
                    <Text>语速：</Text>
                    <Slider
                      min={0.5}
                      max={2.0}
                      step={0.1}
                      value={speed}
                      onChange={setSpeed}
                      style={{ width: 200 }}
                      marks={{
                        0.5: '0.5x',
                        1: '1x',
                        1.5: '1.5x',
                        2: '2x',
                      }}
                    />
                    <Text style={{ minWidth: 40 }}>{speed.toFixed(1)}x</Text>
                  </Space>
                </div>
              </Space>
            </Card>

            {/* 操作按钮 */}
            <Space style={{ marginTop: 16 }}>
              <Button
                type="primary"
                icon={<AudioOutlined />}
                onClick={handleSynthesize}
                loading={synthesizeMutation.isPending}
                size="large"
              >
                开始合成
              </Button>
              <Button
                icon={<ReloadOutlined />}
                onClick={() => {
                  form.resetFields();
                  setAudioUrl(null);
                }}
              >
                重置
              </Button>
            </Space>
          </Card>
        </Col>

        {/* 右侧：预览区域 */}
        <Col span={10}>
          <Card title="预览播放">
            {synthesizeMutation.isPending ? (
              <div style={{ textAlign: 'center', padding: 60 }}>
                <Spin size="large" />
                <div style={{ marginTop: 16 }}>
                  <Text>正在合成语音，请稍候...</Text>
                </div>
              </div>
            ) : audioUrl ? (
              <div style={{ textAlign: 'center' }}>
                <div
                  style={{
                    width: 120,
                    height: 120,
                    borderRadius: '50%',
                    background: 'linear-gradient(135deg, #3B82F6, #8B5CF6)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    margin: '0 auto 24px',
                    cursor: 'pointer',
                  }}
                  onClick={() => new Audio(audioUrl).play()}
                >
                  <PlayCircleOutlined style={{ fontSize: 48, color: '#fff' }} />
                </div>
                
                <Text strong style={{ display: 'block', marginBottom: 16 }}>
                  语音已生成
                </Text>
                
                <audio controls src={audioUrl} style={{ width: '100%', marginBottom: 16 }} />
                
                <Button
                  type="primary"
                  icon={<DownloadOutlined />}
                  onClick={handleDownload}
                >
                  下载音频
                </Button>
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: 60, color: '#999' }}>
                <AudioOutlined style={{ fontSize: 64, marginBottom: 16 }} />
                <div>
                  <Text type="secondary">输入文本并点击"开始合成"按钮</Text>
                </div>
              </div>
            )}
          </Card>

          {/* 使用说明 */}
          <Card size="small" style={{ marginTop: 16 }}>
            <Title level={5}>使用说明</Title>
            <ul style={{ paddingLeft: 20, margin: 0, color: '#666' }}>
              <li>支持中英文混合输入</li>
              <li>单次合成文本最多10000字</li>
              <li>可调节语速（0.5x - 2x）</li>
              <li>支持下载为MP3格式</li>
            </ul>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default TTTSPage;
