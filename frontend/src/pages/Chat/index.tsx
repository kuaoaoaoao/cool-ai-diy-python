/**
 * ============================================================
 * AI聊天页面
 * ============================================================
 * 
 * AI对话主界面
 * - 会话列表
 * - 聊天区域
 * - 模型选择
 * - Agent模式开关
 * - 知识库检索开关
 * 
 * Author: CoolAI Team
 * Date: 2026-05-13
 */

import { useState, useRef, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, List, Input, Button, Select, Avatar, Spin, Typography, Space, Badge, Switch, Tooltip } from 'antd';
import { SendOutlined, PlusOutlined, RobotOutlined, UserOutlined, ClearOutlined, ThunderboltOutlined, BookOutlined } from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../services/api';
import type { Conversation, Message, ChatRequest, ModelInfo } from '../../types/auth';

const { TextArea } = Input;
const { Title, Text } = Typography;

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
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
        }}
      >
        {/* Agent模式标记 */}
        {!isUser && message.metadata?.use_agent && (
          <div style={{ marginBottom: 4, fontSize: 11, opacity: 0.7 }}>
            <ThunderboltOutlined /> Agent模式
          </div>
        )}
        {/* 知识库增强标记 */}
        {!isUser && message.metadata?.use_knowledge && (
          <div style={{ marginBottom: 4, fontSize: 11, opacity: 0.7 }}>
            <BookOutlined /> 知识库增强
          </div>
        )}
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
  const [useAgent, setUseAgent] = useState(false);  // Agent模式开关
  const [useKnowledge, setUseKnowledge] = useState(false);  // 知识库增强开关
  const [streamingMessage, setStreamingMessage] = useState('');  // 流式消息内容
  const [isStreaming, setIsStreaming] = useState(false);  // 是否正在流式输出
  
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
    enabled: !!currentConvId && !isStreaming,  // 流式输出时不刷新
  });

  // 获取模型列表
  const { data: modelList } = useQuery<{ models: ModelInfo[] }>({
    queryKey: ['models'],
    queryFn: () => api.get('/system/models'),
  });

  // 发送消息（非流式）
  const sendMessageMutation = useMutation({
    mutationFn: (data: ChatRequest) => api.post('/chat/', data),
    onSuccess: (response) => {
      if (!currentConvId) {
        setCurrentConvId(response.conversation_id);
        navigate(`/chat/${response.conversation_id}`);
      }
      queryClient.invalidateQueries({ queryKey: ['messages'] });
      queryClient.invalidateQueries({ queryKey: ['conversations'] });
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
  }, [messages, streamingMessage]);

  /**
   * 使用SSE流式发送消息
   */
  const sendStreamMessage = useCallback(async () => {
    if (!inputValue.trim() || isStreaming) return;
    
    const message = inputValue.trim();
    setInputValue('');
    setIsStreaming(true);
    setStreamingMessage('');
    
    try {
      const baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
      
      // 获取Token
      const authData = localStorage.getItem('coolai-auth');
      let token = '';
      if (authData) {
        try {
          const parsed = JSON.parse(authData);
          token = parsed.state?.accessToken || '';
        } catch { /* ignore */ }
      }
      
      const response = await fetch(`${baseURL}/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          conversation_id: currentConvId,
          message,
          model: selectedModel,
          use_agent: useAgent,
          use_knowledge: useKnowledge,
          stream: true,
        } as ChatRequest),
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let fullContent = '';
      
      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          
          const text = decoder.decode(value, { stream: true });
          // 解析SSE数据
          const lines = text.split('\n');
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6));
                if (data.type === 'token') {
                  fullContent += data.content;
                  setStreamingMessage(fullContent);
                } else if (data.type === 'error') {
                  setStreamingMessage(prev => prev + `\n\n[错误] ${data.content}`);
                } else if (data.type === 'done') {
                  // 流结束
                }
              } catch { /* ignore parse errors */ }
            }
          }
        }
      }
      
      // 流式结束，刷新消息列表
      if (!currentConvId && fullContent) {
        // 新会话，需要从响应中获取ID（简化处理：刷新列表）
        queryClient.invalidateQueries({ queryKey: ['conversations'] });
      }
      queryClient.invalidateQueries({ queryKey: ['messages'] });
      
    } catch (error: any) {
      setStreamingMessage(prev => prev + `\n\n[发送失败] ${error.message}`);
    } finally {
      setIsStreaming(false);
      setStreamingMessage('');
    }
  }, [inputValue, currentConvId, selectedModel, useAgent, useKnowledge, isStreaming, queryClient, navigate]);

  // 处理发送消息（使用流式）
  const handleSend = () => {
    if (!inputValue.trim()) return;
    sendStreamMessage();
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
            flexWrap: 'wrap',
            gap: 8,
          }}
        >
          <Space wrap>
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
            
            {/* Agent模式开关 */}
            <Tooltip title="开启后使用Agent模式（Plan-Execute），AI会先规划再执行">
              <Space size={4}>
                <ThunderboltOutlined style={{ color: useAgent ? '#8B5CF6' : '#999' }} />
                <Switch
                  size="small"
                  checked={useAgent}
                  onChange={setUseAgent}
                />
                <Text style={{ fontSize: 12, color: useAgent ? '#8B5CF6' : '#999' }}>
                  Agent
                </Text>
              </Space>
            </Tooltip>
            
            {/* 知识库增强开关 */}
            <Tooltip title="开启后会从知识库检索相关内容增强回答">
              <Space size={4}>
                <BookOutlined style={{ color: useKnowledge ? '#3B82F6' : '#999' }} />
                <Switch
                  size="small"
                  checked={useKnowledge}
                  onChange={setUseKnowledge}
                />
                <Text style={{ fontSize: 12, color: useKnowledge ? '#3B82F6' : '#999' }}>
                  知识库
                </Text>
              </Space>
            </Tooltip>
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
          {currentConvId || isStreaming ? (
            <>
              {msgLoading && !isStreaming ? (
                <div style={{ textAlign: 'center', padding: 40 }}>
                  <Spin />
                </div>
              ) : (
                <>
                  {messages?.map((msg) => (
                    <MessageBubble key={msg.id} message={msg} />
                  ))}
                  {/* 流式输出中的消息 */}
                  {isStreaming && streamingMessage && (
                    <MessageBubble 
                      message={{
                        id: 'streaming',
                        conversation_id: currentConvId || '',
                        role: 'assistant',
                        content: streamingMessage,
                        metadata: { use_agent: useAgent, use_knowledge: useKnowledge },
                        created_at: new Date().toISOString(),
                      }} 
                    />
                  )}
                  {/* 流式加载指示器 */}
                  {isStreaming && !streamingMessage && (
                    <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: 16 }}>
                      <Avatar icon={<RobotOutlined />} style={{ backgroundColor: '#8B5CF6', marginRight: 12 }} />
                      <div style={{ padding: '12px 16px', borderRadius: '16px 16px 16px 4px', backgroundColor: '#f5f5f5' }}>
                        <Spin size="small" /> <Text type="secondary">思考中...</Text>
                      </div>
                    </div>
                  )}
                </>
              )}
              <div ref={messagesEndRef} />
            </>
          ) : (
            <div style={{ textAlign: 'center', padding: 60, color: '#999' }}>
              <RobotOutlined style={{ fontSize: 48, marginBottom: 16 }} />
              <Title level={4}>开始新对话</Title>
              <Text type="secondary">选择或创建一个会话开始聊天</Text>
              <div style={{ marginTop: 16 }}>
                <Space>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    <ThunderboltOutlined /> Agent模式：AI自动规划执行
                  </Text>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    <BookOutlined /> 知识库：检索增强回答
                  </Text>
                </Space>
              </div>
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
              placeholder={
                useAgent 
                  ? "Agent模式：描述你的需求，AI会制定计划并执行..." 
                  : "输入消息... (Shift+Enter 换行)"
              }
              autoSize={{ minRows: 1, maxRows: 4 }}
              style={{ flex: 1 }}
              disabled={isStreaming}
            />
            <Button
              type="primary"
              icon={<SendOutlined />}
              onClick={handleSend}
              loading={isStreaming || sendMessageMutation.isPending}
              style={{ height: 'auto' }}
            >
              发送
            </Button>
          </Space.Compact>
          {/* 当前模式提示 */}
          <div style={{ marginTop: 4, fontSize: 11, color: '#999' }}>
            {useAgent && <span><ThunderboltOutlined /> Agent模式已开启 · </span>}
            {useKnowledge && <span><BookOutlined /> 知识库增强已开启 · </span>}
            当前模型：{selectedModel}
          </div>
        </div>
      </Card>
    </div>
  );
};

export default ChatPage;
