/**
 * ============================================================
 * 登录页面
 * ============================================================
 * 
 * 用户登录页面
 * - 登录表单
 * - 注册入口
 * 
 * Author: CoolAI Team
 * Date: 2026-05-13
 */

import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Form, Input, Button, Card, Typography, message, Space } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import { useAuthStore } from '../../store/authStore';
import type { LoginForm } from '../../types/auth';

const { Title, Text, Link } = Typography;

const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuthStore();
  const [loading, setLoading] = useState(false);

  // 获取登录成功后的跳转路径
  const from = (location.state as any)?.from?.pathname || '/';

  /**
   * 处理表单提交
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
              <Link onClick={() => message.info('注册功能开发中')}>立即注册</Link>
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
    </div>
  );
};

export default LoginPage;
