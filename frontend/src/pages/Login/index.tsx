/**
 * ============================================================
 * 登录页面
 * ============================================================
 * 
 * 用户登录/注册页面
 * - 登录表单
 * - 注册表单（Modal弹窗）
 * 
 * Author: CoolAI Team
 * Date: 2026-05-13
 */

import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Form, Input, Button, Card, Typography, message, Space, Modal } from 'antd';
import { UserOutlined, LockOutlined, MailOutlined } from '@ant-design/icons';
import { useAuthStore } from '../../store/authStore';
import { api } from '../../services/api';
import type { LoginForm, RegisterForm } from '../../types/auth';

const { Title, Text, Link } = Typography;

const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuthStore();
  const [loading, setLoading] = useState(false);
  const [registerModalVisible, setRegisterModalVisible] = useState(false);
  const [registerLoading, setRegisterLoading] = useState(false);

  // 获取登录成功后的跳转路径
  const from = (location.state as any)?.from?.pathname || '/';

  /**
   * 处理登录表单提交
   */
  const handleSubmit = async (values: LoginForm) => {
    setLoading(true);
    
    try {
      await login(values);
      message.success('登录成功');
      navigate(from, { replace: true });
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '登录失败，请检查用户名和密码');
    } finally {
      setLoading(false);
    }
  };

  /**
   * 处理注册表单提交
   */
  const handleRegister = async (values: RegisterForm) => {
    // 校验两次密码是否一致
    if (values.password !== values.confirm_password) {
      message.error('两次输入的密码不一致');
      return;
    }

    setRegisterLoading(true);
    
    try {
      await api.post('/auth/register', {
        username: values.username,
        email: values.email,
        password: values.password,
      });
      message.success('注册成功，请登录');
      setRegisterModalVisible(false);
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      if (typeof detail === 'string') {
        message.error(detail);
      } else if (Array.isArray(detail)) {
        // FastAPI 验证错误格式
        const messages = detail.map((e: any) => e.msg).join('; ');
        message.error(messages);
      } else {
        message.error('注册失败，请稍后重试');
      }
    } finally {
      setRegisterLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      }}
    >
      <Card
        style={{
          width: 400,
          boxShadow: '0 10px 40px rgba(0,0,0,0.2)',
          borderRadius: 16,
        }}
        bodyStyle={{ padding: 40 }}
      >
        {/* Logo区域 */}
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div
            style={{
              width: 64,
              height: 64,
              borderRadius: 16,
              background: 'linear-gradient(135deg, #3B82F6, #8B5CF6)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 16px',
              color: '#fff',
              fontSize: 24,
              fontWeight: 'bold',
            }}
          >
            AI
          </div>
          <Title level={3} style={{ margin: 0 }}>CoolAI</Title>
          <Text type="secondary">智能业务平台</Text>
        </div>

        {/* 登录表单 */}
        <Form
          name="login"
          onFinish={handleSubmit}
          layout="vertical"
          requiredMark={false}
          initialValues={{ username: '', password: '' }}
        >
          <Form.Item
            name="username"
            rules={[
              { required: true, message: '请输入用户名' },
              { min: 3, message: '用户名至少3个字符' },
            ]}
          >
            <Input
              prefix={<UserOutlined />}
              placeholder="用户名"
              size="large"
            />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[
              { required: true, message: '请输入密码' },
              { min: 6, message: '密码至少6个字符' },
            ]}
          >
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="密码"
              size="large"
            />
          </Form.Item>

          <Form.Item style={{ marginBottom: 16 }}>
            <Button
              type="primary"
              htmlType="submit"
              loading={loading}
              block
              size="large"
              style={{ borderRadius: 8 }}
            >
              登录
            </Button>
          </Form.Item>

          <div style={{ textAlign: 'center' }}>
            <Space>
              <Text type="secondary">还没有账号？</Text>
              <Link onClick={() => setRegisterModalVisible(true)}>立即注册</Link>
            </Space>
          </div>
        </Form>

        {/* 演示账号提示 */}
        <div
          style={{
            marginTop: 24,
            padding: 16,
            background: '#f6f8fa',
            borderRadius: 8,
            fontSize: 12,
          }}
        >
          <Text type="secondary">
            <strong>演示账号：</strong> admin / admin123
          </Text>
        </div>
      </Card>

      {/* 注册弹窗 */}
      <Modal
        title="注册新账号"
        open={registerModalVisible}
        onCancel={() => setRegisterModalVisible(false)}
        footer={null}
        destroyOnClose
      >
        <Form
          name="register"
          onFinish={handleRegister}
          layout="vertical"
          requiredMark={false}
        >
          <Form.Item
            name="username"
            label="用户名"
            rules={[
              { required: true, message: '请输入用户名' },
              { min: 3, message: '用户名至少3个字符' },
              { max: 50, message: '用户名不超过50个字符' },
              { pattern: /^[a-zA-Z0-9_\u4e00-\u9fa5]+$/, message: '用户名只能包含字母、数字、下划线和中文' },
            ]}
          >
            <Input prefix={<UserOutlined />} placeholder="请输入用户名" />
          </Form.Item>

          <Form.Item
            name="email"
            label="邮箱"
            rules={[
              { required: true, message: '请输入邮箱' },
              { type: 'email', message: '请输入有效的邮箱地址' },
            ]}
          >
            <Input prefix={<MailOutlined />} placeholder="请输入邮箱" />
          </Form.Item>

          <Form.Item
            name="password"
            label="密码"
            rules={[
              { required: true, message: '请输入密码' },
              { min: 6, message: '密码至少6个字符' },
            ]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="请输入密码" />
          </Form.Item>

          <Form.Item
            name="confirm_password"
            label="确认密码"
            dependencies={['password']}
            rules={[
              { required: true, message: '请确认密码' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('password') === value) {
                    return Promise.resolve();
                  }
                  return Promise.reject(new Error('两次输入的密码不一致'));
                },
              }),
            ]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="请再次输入密码" />
          </Form.Item>

          <Form.Item style={{ marginBottom: 0 }}>
            <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
              <Button onClick={() => setRegisterModalVisible(false)}>
                取消
              </Button>
              <Button type="primary" htmlType="submit" loading={registerLoading}>
                注册
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default LoginPage;
