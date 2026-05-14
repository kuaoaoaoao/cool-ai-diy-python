/**
 * ============================================================
 * 设置页面
 * ============================================================
 * 
 * 个人设置
 * - 个人信息（可保存）
 * - API配置（可保存）
 * - 关于
 * 
 * Author: CoolAI Team
 * Date: 2026-05-13
 */

import { useState, useEffect } from 'react';
import { Card, Form, Input, Button, Typography, Space, Divider, message, Spin } from 'antd';
import { SaveOutlined, KeyOutlined, CheckCircleOutlined } from '@ant-design/icons';
import { useAuthStore } from '../../store/authStore';
import { api } from '../../services/api';

const { Title, Text } = Typography;

/**
 * 设置页面组件
 */
const SettingsPage: React.FC = () => {
  const { user, updateUser } = useAuthStore();
  const [profileForm] = Form.useForm();
  const [apiKeysForm] = Form.useForm();
  const [profileLoading, setProfileLoading] = useState(false);
  const [apiKeysLoading, setApiKeysLoading] = useState(false);
  const [apiKeysStatus, setApiKeysStatus] = useState({ openai_set: false, anthropic_set: false });
  const [statusLoading, setStatusLoading] = useState(true);

  // 初始化：获取API Key状态
  useEffect(() => {
    const fetchApiKeysStatus = async () => {
      try {
        const response = await api.get<{ openai_api_key_set: boolean; anthropic_api_key_set: boolean }>('/auth/api-keys');
        setApiKeysStatus({
          openai_set: response.openai_api_key_set,
          anthropic_set: response.anthropic_api_key_set,
        });
      } catch {
        // 获取失败不影响页面
      } finally {
        setStatusLoading(false);
      }
    };
    fetchApiKeysStatus();
  }, []);

  // 保存个人信息
  const handleSaveProfile = async () => {
    try {
      const values = await profileForm.validateFields();
      setProfileLoading(true);
      
      const response = await api.put('/auth/profile', {
        email: values.email,
        full_name: values.full_name,
      });
      
      // 更新本地用户状态
      updateUser(response);
      message.success('个人信息已保存');
    } catch (error: any) {
      if (error?.errorFields) {
        // 表单验证错误，不显示message
        return;
      }
      message.error(error?.response?.data?.detail || '保存失败');
    } finally {
      setProfileLoading(false);
    }
  };

  // 保存API密钥
  const handleSaveApiKeys = async () => {
    try {
      const values = await apiKeysForm.validateFields();
      setApiKeysLoading(true);
      
      const response = await api.put<{ openai_api_key_set: boolean; anthropic_api_key_set: boolean }>('/auth/api-keys', {
        openai_api_key: values.openai_api_key || undefined,
        anthropic_api_key: values.anthropic_api_key || undefined,
      });
      
      setApiKeysStatus({
        openai_set: response.openai_api_key_set,
        anthropic_set: response.anthropic_api_key_set,
      });
      
      // 清空输入框（安全考虑，不保留已输入的key）
      apiKeysForm.setFieldsValue({
        openai_api_key: '',
        anthropic_api_key: '',
      });
      
      message.success('API密钥已保存');
    } catch (error: any) {
      if (error?.errorFields) return;
      message.error(error?.response?.data?.detail || '保存失败');
    } finally {
      setApiKeysLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 800 }}>
      <Title level={3}>个人设置</Title>
      
      {/* 个人信息 */}
      <Card title="个人信息" style={{ marginBottom: 16 }}>
        <Form
          form={profileForm}
          layout="vertical"
          initialValues={{
            username: user?.username,
            email: user?.email,
            full_name: user?.full_name,
          }}
        >
          <Form.Item
            name="username"
            label="用户名"
          >
            <Input disabled />
          </Form.Item>
          
          <Form.Item
            name="email"
            label="邮箱"
            rules={[
              { required: true, message: '请输入邮箱' },
              { type: 'email', message: '请输入有效的邮箱地址' },
            ]}
          >
            <Input />
          </Form.Item>
          
          <Form.Item
            name="full_name"
            label="姓名"
          >
            <Input placeholder="请输入您的姓名" />
          </Form.Item>
          
          <Button
            type="primary"
            icon={<SaveOutlined />}
            onClick={handleSaveProfile}
            loading={profileLoading}
          >
            保存修改
          </Button>
        </Form>
      </Card>

      {/* API配置 */}
      <Card title={<><KeyOutlined /> API配置</>} style={{ marginBottom: 16 }}>
        {statusLoading ? (
          <div style={{ textAlign: 'center', padding: 20 }}><Spin /></div>
        ) : (
          <Form
            form={apiKeysForm}
            layout="vertical"
          >
            <Form.Item 
              label="OpenAI API Key"
              name="openai_api_key"
              extra={apiKeysStatus.openai_set ? <Text type="success" style={{ fontSize: 12 }}><CheckCircleOutlined /> 已配置</Text> : <Text type="warning" style={{ fontSize: 12 }}>未配置</Text>}
            >
              <Input.Password placeholder={apiKeysStatus.openai_set ? "已设置，留空则不修改" : "sk-..."} />
            </Form.Item>
            
            <Form.Item 
              label="Anthropic API Key"
              name="anthropic_api_key"
              extra={apiKeysStatus.anthropic_set ? <Text type="success" style={{ fontSize: 12 }}><CheckCircleOutlined /> 已配置</Text> : <Text type="warning" style={{ fontSize: 12 }}>未配置</Text>}
            >
              <Input.Password placeholder={apiKeysStatus.anthropic_set ? "已设置，留空则不修改" : "sk-ant-..."} />
            </Form.Item>
            
            <Button
              type="primary"
              icon={<SaveOutlined />}
              onClick={handleSaveApiKeys}
              loading={apiKeysLoading}
            >
              保存密钥
            </Button>
            
            <div style={{ marginTop: 12 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                API密钥将安全存储在服务器端，仅用于调用相应服务。留空则不修改已有密钥。
              </Text>
            </div>
          </Form>
        )}
      </Card>

      {/* 关于 */}
      <Card title="关于">
        <Space direction="vertical">
          <Text><strong>CoolAI 智能业务平台</strong></Text>
          <Text type="secondary">版本：1.0.0</Text>
          <Divider />
          <Text type="secondary">
            一个综合性的AI业务平台，提供AI Agent、RAG知识库、TTS语音合成等功能。
          </Text>
        </Space>
      </Card>
    </div>
  );
};

export default SettingsPage;
