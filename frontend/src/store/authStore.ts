/**
 * ============================================================
 * 认证状态管理 - Zustand Store
 * ============================================================
 * 
 * 使用Zustand管理用户认证状态
 * - 登录/登出
 * - Token管理
 * - 用户信息
 * 
 * Author: CoolAI Team
 * Date: 2026-05-13
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { api } from '../services/api';
import type { UserInfo, LoginForm } from '../types/auth';

/**
 * 认证状态接口
 */
interface AuthState {
  // 用户信息
  user: UserInfo | null;
  
  // 访问令牌
  accessToken: string | null;
  
  // 刷新令牌
  refreshToken: string | null;
  
  // 是否正在加载
  isLoading: boolean;
  
  // 是否已认证
  isAuthenticated: boolean;
  
  // 登录方法
  login: (data: LoginForm) => Promise<void>;
  
  // 登出方法
  logout: () => void;
  
  // 检查认证状态
  checkAuth: () => Promise<void>;
  
  // 更新用户信息
  updateUser: (user: Partial<UserInfo>) => void;
}

/**
 * 创建认证Store
 * 
 * persist中间件：将状态持久化到localStorage
 * 这样页面刷新后登录状态不会丢失
 */
export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      // 初始状态
      user: null,
      accessToken: null,
      refreshToken: null,
      isLoading: true,
      isAuthenticated: false,

      /**
       * 用户登录
       * @param data 登录表单数据
       */
      login: async (data: LoginForm) => {
        set({ isLoading: true });
        
        try {
          // 调用登录API
          const response = await api.post<{
            access_token: string;
            refresh_token: string;
            user: UserInfo;
          }>('/auth/login', data);

          // 更新状态
          set({
            user: response.user,
            accessToken: response.access_token,
            refreshToken: response.refresh_token,
            isAuthenticated: true,
            isLoading: false,
          });
        } catch (error) {
          set({ isLoading: false });
          throw error;
        }
      },

      /**
       * 用户登出
       */
      logout: () => {
        set({
          user: null,
          accessToken: null,
          refreshToken: null,
          isAuthenticated: false,
        });
      },

      /**
       * 检查认证状态
       * 从localStorage恢复登录状态时调用
       */
      checkAuth: async () => {
        const { accessToken } = get();
        
        if (!accessToken) {
          set({ isLoading: false, isAuthenticated: false });
          return;
        }

        try {
          // 调用获取当前用户API
          const user = await api.get<UserInfo>('/auth/me');
          set({ user, isAuthenticated: true, isLoading: false });
        } catch {
          // token无效，清除状态
          get().logout();
          set({ isLoading: false });
        }
      },

      /**
       * 更新用户信息
       * @param userData 部分用户信息
       */
      updateUser: (userData: Partial<UserInfo>) => {
        const currentUser = get().user;
        if (currentUser) {
          set({ user: { ...currentUser, ...userData } });
        }
      },
    }),
    {
      // 持久化配置
      name: 'coolai-auth', // localStorage的key
      partialize: (state) => ({
        // 只持久化这些字段
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        user: state.user,
      }),
    }
  )
);
