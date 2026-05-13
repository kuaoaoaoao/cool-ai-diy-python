/**
 * ============================================================
 * 工作台/仪表盘页面
 * ============================================================
 * 
 * 首页仪表盘
 * - 统计数据卡片
 * - 快捷入口
 * - 最近对话
 * 
 * Author: CoolAI Team
 * Date: 2026-05-13
 */

import { Card, Row, Col, Statistic, List, Avatar, Typography, Space } from 'antd';
import {
  MessageOutlined,
  BookOutlined,
  AudioOutlined,
  RiseOutlined,
  UserOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import type { StatsResponse, Conversation } from '../../types/auth';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../services/api';

const { Title, Text } = Typography;

/**
 * 统计数据卡片
 */
const StatCard = ({
  title,
  value,
  icon,
  color,
  trend,
}: {
  title: string;
  value: number;
  icon: React.ReactNode;
  color: string;
  trend?: string;
}) => (
  <Card hoverable>
    <Statistic
      title={title}
      value={value}
      prefix={<span style={{ color }}>{icon}</span>}
      suffix={trend && <Text type="success" style={{ fontSize: 14 }}>{trend}</Text>}
    />
  </Card>
);

/**
 * 快捷入口卡片
 */
const QuickAccessCard = ({
  title,
  description,
  icon,
  color,
  path,
}: {
  title: string;
  description: string;
  icon: React.ReactNode;
  color: string;
  path: string;
}) => {
  const navigate = useNavigate();

  return (
    <Card
      hoverable
      onClick={() => navigate(path)}
      style={{ textAlign: 'center' }}
    >
      <div
        style={{
          width: 48,
          height: 48,
          borderRadius: 12,
          background: `${color}15`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          margin: '0 auto 12px',
          fontSize: 24,
          color,
        }}
      >
        {icon}
      </div>
      <Title level={5} style={{ margin: 0 }}>{title}</Title>
      <Text type="secondary" style={{ fontSize: 12 }}>{description}</Text>
    </Card>
  );
};

/**
 * 工作台页面组件
 */
const DashboardPage: React.FC = () => {
  // 获取统计数据
  const { data: stats } = useQuery<StatsResponse>({
    queryKey: ['stats'],
    queryFn: () => api.get('/system/stats'),
  });

  // 获取最近对话
  const { data: recentConversations } = useQuery<Conversation[]>({
    queryKey: ['conversations', 'recent'],
    queryFn: () => api.get('/chat/conversations', { limit: 5 }),
  });

  return (
    <div>
      {/* 页面标题 */}
      <Title level={3}>工作台</Title>
      <Text type="secondary">欢迎使用 CoolAI 智能业务平台</Text>

      {/* 统计数据 */}
      <Row gutter={[16, 16]} style={{ marginTop: 24 }}>
        <Col xs={24} sm={12} lg={6}>
          <StatCard
            title="总会话数"
            value={stats?.total_conversations || 0}
            icon={<MessageOutlined />}
            color="#3B82F6"
            trend="+12%"
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <StatCard
            title="总消息数"
            value={stats?.total_messages || 0}
            icon={<UserOutlined />}
            color="#8B5CF6"
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <StatCard
            title="知识库数量"
            value={stats?.total_knowledge_bases || 0}
            icon={<BookOutlined />}
            color="#10B981"
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <StatCard
            title="文档数量"
            value={stats?.total_documents || 0}
            icon={<AudioOutlined />}
            color="#F59E0B"
          />
        </Col>
      </Row>

      {/* 快捷入口 */}
      <Title level={4} style={{ marginTop: 32 }}>快捷入口</Title>
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <QuickAccessCard
            title="AI 聊天"
            description="与AI智能对话"
            icon={<MessageOutlined />}
            color="#3B82F6"
            path="/chat"
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <QuickAccessCard
            title="知识库管理"
            description="构建专属知识库"
            icon={<BookOutlined />}
            color="#10B981"
            path="/knowledge"
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <QuickAccessCard
            title="语音合成"
            description="文字转语音"
            icon={<AudioOutlined />}
            color="#8B5CF6"
            path="/tts"
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <QuickAccessCard
            title="系统设置"
            description="个性化配置"
            icon={<RiseOutlined />}
            color="#F59E0B"
            path="/settings"
          />
        </Col>
      </Row>

      {/* 最近对话 */}
      <Title level={4} style={{ marginTop: 32 }}>最近对话</Title>
      <Card>
        <List
          itemLayout="horizontal"
          dataSource={recentConversations || []}
          locale={{ emptyText: '暂无对话记录' }}
          renderItem={(item: Conversation) => (
            <List.Item
              actions={[
                <a key="continue" onClick={() => window.location.href = `/chat/${item.id}`}>
                  继续
                </a>
              ]}
            >
              <List.Item.Meta
                avatar={<Avatar icon={<MessageOutlined />} style={{ backgroundColor: '#3B82F6' }} />}
                title={item.title || '未命名会话'}
                description={
                  <Space>
                    <span>{item.model}</span>
                    <ClockCircleOutlined style={{ marginLeft: 8 }} />
                    <span>{new Date(item.updated_at).toLocaleDateString()}</span>
                  </Space>
                }
              />
            </List.Item>
          )}
        />
      </Card>
    </div>
  );
};

export default DashboardPage;
