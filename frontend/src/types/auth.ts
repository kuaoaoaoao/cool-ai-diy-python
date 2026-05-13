/**
 * ============================================================
 * 类型定义文件
 * ============================================================
 * 
 * 集中管理TypeScript类型定义
 * 
 * Author: CoolAI Team
 * Date: 2026-05-13
 */

// ============================================================
// 用户认证相关类型
// ============================================================

/** 用户角色 */
export type UserRole = 'admin' | 'user';

/** 用户信息 */
export interface UserInfo {
  id: string;
  username: string;
  email: string;
  full_name?: string;
  avatar_url?: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

/** 登录表单数据 */
export interface LoginForm {
  username: string;
  password: string;
}

/** 注册表单数据 */
export interface RegisterForm {
  username: string;
  email: string;
  password: string;
  confirm_password: string;
}

/** Token响应 */
export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}


// ============================================================
// 对话相关类型
// ============================================================

/** 消息角色 */
export type MessageRole = 'user' | 'assistant' | 'system' | 'tool';

/** 消息 */
export interface Message {
  id: string;
  conversation_id: string;
  role: MessageRole;
  content: string;
  metadata?: Record<string, any>;
  tokens?: number;
  created_at: string;
}

/** 对话会话 */
export interface Conversation {
  id: string;
  user_id: string;
  title?: string;
  model: string;
  system_prompt?: string;
  config?: Record<string, any>;
  message_count: number;
  is_deleted: boolean;
  created_at: string;
  updated_at: string;
}

/** 创建会话请求 */
export interface CreateConversationRequest {
  title?: string;
  model?: string;
  system_prompt?: string;
  config?: Record<string, any>;
}

/** 聊天请求 */
export interface ChatRequest {
  conversation_id?: string;
  message: string;
  model?: string;
  system_prompt?: string;
  temperature?: number;
  max_tokens?: number;
  use_knowledge?: boolean;
  knowledge_base_id?: string;
  stream?: boolean;
}

/** 聊天响应 */
export interface ChatResponse {
  conversation_id: string;
  message_id: string;
  content: string;
  model: string;
  usage: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
  created_at: string;
}


// ============================================================
// 知识库相关类型
// ============================================================

/** 文档状态 */
export type DocumentStatus = 'pending' | 'processing' | 'completed' | 'failed';

/** 知识库 */
export interface KnowledgeBase {
  id: string;
  user_id: string;
  name: string;
  description?: string;
  config?: Record<string, any>;
  chunk_count: number;
  doc_count: number;
  is_public: boolean;
  created_at: string;
  updated_at: string;
}

/** 文档 */
export interface Document {
  id: string;
  knowledge_base_id: string;
  filename: string;
  file_size?: number;
  file_type?: string;
  status: DocumentStatus;
  error_message?: string;
  created_at: string;
  processed_at?: string;
}

/** 知识库查询结果 */
export interface KnowledgeQueryResult {
  content: string;
  score: number;
  source?: string;
  metadata?: Record<string, any>;
}

/** 知识库查询响应 */
export interface KnowledgeQueryResponse {
  query: string;
  results: KnowledgeQueryResult[];
  total_count: number;
}


// ============================================================
// TTS相关类型
// ============================================================

/** 任务状态 */
export type TaskStatus = 'pending' | 'processing' | 'completed' | 'failed';

/** 语音信息 */
export interface VoiceInfo {
  voice_id: string;
  name: string;
  language: string;
  gender: string;
  preview_url?: string;
  is_custom: boolean;
}

/** TTS请求 */
export interface TTSRequest {
  text: string;
  voice?: string;
  speed?: number;
  pitch?: number;
  format?: 'mp3' | 'wav' | 'ogg';
}

/** TTS任务 */
export interface TTSTask {
  id: string;
  user_id: string;
  text: string;
  voice_id?: string;
  status: TaskStatus;
  output_path?: string;
  error_message?: string;
  created_at: string;
  completed_at?: string;
}


// ============================================================
// 系统相关类型
// ============================================================

/** 健康检查响应 */
export interface HealthResponse {
  status: string;
  version: string;
  database: string;
  redis: string;
  milvus: string;
}

/** 统计数据 */
export interface StatsResponse {
  total_users: number;
  total_conversations: number;
  total_messages: number;
  total_knowledge_bases: number;
  total_documents: number;
}

/** 模型信息 */
export interface ModelInfo {
  name: string;
  display_name: string;
  provider: string;
  description: string;
  is_available: boolean;
}


// ============================================================
// 通用类型
// ============================================================

/** 分页参数 */
export interface PaginationParams {
  page?: number;
  page_size?: number;
  skip?: number;
  limit?: number;
}

/** 分页响应 */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

/** 通用响应 */
export interface ApiResponse<T = any> {
  success: boolean;
  message?: string;
  data?: T;
  error?: string;
  detail?: string;
}

/** 下拉选项 */
export interface SelectOption {
  label: string;
  value: string | number;
  disabled?: boolean;
}
