/**
 * ============================================================
 * AI聊天页面
 * ============================================================
 * 
 * AI对话主界面
 * - 会话列表
 * - 聊天区域
 * - 模型选择
 * 
 * Author: CoolAI Team
 * Date: 2026-05-13
 */

import { useState, useRef, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, List, Input, Button, Select, Avatar, Spin, Typography, Space, Badge } from 'antd';
import { SendOutlined, PlusOutlined, RobotOutlined, UserOutlined, ClearOutlined } from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../services/api';
import type { Conversation, Message, ChatRequest, ModelInfo } from '../../types/auth';

const { TextArea } = Input;
const { Title } = Typography;

/**
 * 消息气泡组件
 */
const MessageBubble = ({ message }: { message: Message }) => {
  const isUser = message.role === 'user';
  
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: isUser ? 'flex-end' : 'flex-start',
        marginBottom: 16,
      }}
    >
      {/* 头像 */}
      <Avatar
        icon={isUser ? <UserOutlined /> : <RobotOutlined />}
        style={{
          backgroundColor: isUser ? '#3B82F6' : '#8B5CF6',
          marginRight: isUser ? 0 : 12,
          marginLeft: isUser ? 12 : 0,
          flexShrink: 0,
        }}
      />
      
      {/* 消息内容 */}
      <div
        style={{
          maxWidth: '70%',
          padding: '12px 16px',
          borderRadius: isUser ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
          backgroundColor: isUser ? '#3B82F6' : '#f5f5f5',
          color: isUser ? '#fff' : '#333',
        }}
      >
        {message.content}
      </div>
    </div>
  );
};

/**
 * AI聊天页面组件
 */
const ChatPage: React.FC = () => {
  const { conversationId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  
  // 状态
  const [inputValue, setInputValue] = useState('');
  const [selectedModel, setSelectedModel] = useState('gpt-4-turbo-preview');
  const [currentConvId, setCurrentConvId] = useState<string | undefined>(conversationId);
  
  // 消息列表滚动引用
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 获取会话列表
  const { data: conversations, isLoading: convLoading } = useQuery<Conversation[]>({
    queryKey: ['conversations'],
    queryFn: () => api.get('/chat/conversations'),
  });

  // 获取消息列表
  const { data: messages, isLoading: msgLoading } = useQuery<Message[]>({
    queryKey: ['messages', currentConvId],
    queryFn: () => api.get(`/chat/${currentConvId}/messages`),
    enabled: !!currentConvId,
  });

  // 获取模型列表
  const { data: modelList } = useQuery<{ models: ModelInfo[] }>({
    queryKey: ['models'],
    queryFn: () => api.get('/system/models'),
  });

  // 发送消息
  const sendMessageMutation = useMutation({
    mutationFn: (data: ChatRequest) => api.post('/chat/', data),
    onSuccess: (response) => {
      // 如果是新建会话，刷新会话列表并跳转
      if (!currentConvId) {
        setCurrentConvId(response.conversation_id);
        navigate(`/chat/${response.conversation_id}`);
      }
      // 刷新消息列表
      queryClient.invalidateQueries({ queryKey: ['messages'] });
      setInputValue('');
    },
  });

  // 创建新会话
  const createConversationMutation = useMutation({
    mutationFn: () => api.post('/chat/conversations', {}),
    onSuccess: (conv) => {
      setCurrentConvId(conv.id);
      navigate(`/chat/${conv.id}`);
    },
  });

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // 处理发送消息
  const handleSend = () => {
    if (!inputValue.trim()) return;
    
    sendMessageMutation.mutate({
      conversation_id: currentConvId,
      message: inputValue,
      model: selectedModel,
    });
  };

  // 处理回车发送
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 180px)', gap: 16 }}>
      {/* 左侧：会话列表 */}
      <Card
        style={{ width: 280, flexShrink: 0 }}
        bodyStyle={{ padding: 0, height: '100%', display: 'flex', flexDirection: 'column' }}
      >
        {/* 新建按钮 */}
        <div style={{ padding: 16, borderBottom: '1px solid #f0f0f0' }}>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            block
            onClick={() => createConversationMutation.mutate()}
            loading={createConversationMutation.isPending}
          >
            新建对话
          </Button>
        </div>

        {/* 会话列表 */}
        <div style={{ flex: 1, overflow: 'auto' }}>
          <List
            loading={convLoading}
            dataSource={conversations || []}
            renderItem={(item: Conversation) => (
              <List.Item
                onClick={() => {
                  setCurrentConvId(item.id);
                  navigate(`/chat/${item.id}`);
                }}
                style={{
                  cursor: 'pointer',
                  backgroundColor: currentConvId === item.id ? '#e6f7ff' : 'transparent',
                  padding: '12px 16px',
                }}
              >
                <List.Item.Meta
                  title={item.title || '未命名会话'}
                  description={
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {new Date(item.updated_at).toLocaleDateString()}
                    </Text>
                  }
                />
                {item.message_count > 0 && (
                  <Badge count={item.message_count} size="small" />
                )}
              </List.Item>
            )}
          />
        </div>
      </Card>

      {/* 右侧：聊天区域 */}
      <Card
        style={{ flex: 1, display: 'flex', flexDirection: 'column' }}
        bodyStyle={{ padding: 0, height: '100%', display: 'flex', flexDirection: 'column' }}
      >
        {/* 顶部工具栏 */}
        <div
          style={{
            padding: '12px 16px',
            borderBottom: '1px solid #f0f0f0',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <Space>
            <span>模型：</span>
            <Select
              value={selectedModel}
              onChange={setSelectedModel}
              style={{ width: 180 }}
              options={modelList?.models.map((m) => ({
                label: m.display_name,
                value: m.name,
                disabled: !m.is_available,
              }))}
            />
          </Space>
          
          <Button
            icon={<ClearOutlined />}
            onClick={() => message.info('清空对话功能开发中')}
          >
            清空
          </Button>
        </div>

        {/* 消息区域 */}
        <div style={{ flex: 1, overflow: 'auto', padding: 16 }}>
          {currentConvId ? (
            <>
              {msgLoading ? (
                <div style={{ textAlign: 'center', padding: 40 }}>
                  <Spin />
                </div>
              ) : (
                messages?.map((msg) => (
                  <MessageBubble key={msg.id} message={msg} />
                ))
              )}
              <div ref={messagesEndRef} />
            </>
          ) : (
            <div style={{ textAlign: 'center', padding: 60, color: '#999' }}>
              <RobotOutlined style={{ fontSize: 48, marginBottom: 16 }} />
              <Title level={4}>开始新对话</Title>
              <Text type="secondary">选择或创建一个会话开始聊天</Text>
            </div>
          )}
        </div>

        {/* 输入区域 */}
        <div style={{ padding: 16, borderTop: '1px solid #f0f0f0' }}>
          <Space.Compact style={{ width: '100%' }}>
            <TextArea
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyPress}
              placeholder="输入消息... (Shift+Enter 换行)"
              autoSize={{ minRows: 1, maxRows: 4 }}
              style={{ flex: 1 }}
            />
            <Button
              type="primary"
              icon={<SendOutlined />}
              onClick={handleSend}
              loading={sendMessageMutation.isPending}
              style={{ height: 'auto' }}
            >
              发送
            </Button>
          </Space.Compact>
        </div>
      </Card>
    </div>
  );
};

export default ChatPage;
