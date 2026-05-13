/**
 * ============================================================
 * 设置页面
 * ============================================================
 * 
 * 个人设置
 * - 个人信息
 * - API配置
 * 
 * Author: CoolAI Team
 * Date: 2026-05-13
 */

import { Card, Form, Input, Button, Typography, Space, Divider, message } from 'antd';
import { SaveOutlined, KeyOutlined } from '@ant-design/icons';
import { useAuthStore } from '../../store/authStore';

const { Title, Text } = Typography;

/**
 * 设置页面组件
 */
const SettingsPage: React.FC = () => {
  const { user, updateUser } = useAuthStore();
  const [form] = Form.useForm();

  // 处理保存
  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      // TODO: 调用更新用户API
      updateUser(values);
      message.success('设置已保存');
    } catch (error) {
      // 表单验证失败
    }
  };

  return (
    <div style={{ maxWidth: 800 }}>
      <Title level={3}>个人设置</Title>
      
      {/* 个人信息 */}
      <Card title="个人信息" style={{ marginBottom: 16 }}>
        <Form
          form={form}
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
            onClick={handleSave}
          >
            保存修改
          </Button>
        </Form>
      </Card>

      {/* API配置 */}
      <Card title={<><KeyOutlined /> API配置</>} style={{ marginBottom: 16 }}>
        <Form layout="vertical">
          <Form.Item label="OpenAI API Key">
            <Input.Password placeholder="sk-..." />
          </Form.Item>
          
          <Form.Item label="Anthropic API Key">
            <Input.Password placeholder="sk-ant-..." />
          </Form.Item>
          
          <Text type="secondary" style={{ fontSize: 12 }}>
            API密钥将安全存储，仅用于调用相应服务
          </Text>
        </Form>
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
