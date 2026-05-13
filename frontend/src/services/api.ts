/**
 * ============================================================
 * API 服务 - Axios 封装
 * ============================================================
 * 
 * 统一的HTTP请求服务
 * - 请求拦截器（添加Token）
 * - 响应拦截器（处理错误）
 * - 类型定义
 * 
 * Author: CoolAI Team
 * Date: 2026-05-13
 */

import axios, { AxiosInstance, AxiosError, AxiosRequestConfig } from 'axios';

// API基础URL
const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

/**
 * 创建Axios实例
 */
const axiosInstance: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 30000, // 30秒超时
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * 请求拦截器
 * 
 * 功能：
 * 1. 从localStorage获取Token
 * 2. 添加到请求头
 */
axiosInstance.interceptors.request.use(
  (config) => {
    // 获取Token
    const token = localStorage.getItem('coolai-auth');
    
    if (token) {
      try {
        // 从持久化的状态中获取accessToken
        const authData = JSON.parse(token);
        if (authData.state?.accessToken) {
          config.headers.Authorization = `Bearer ${authData.state.accessToken}`;
        }
      } catch {
        // 忽略解析错误
      }
    }

    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

/**
 * 响应拦截器
 * 
 * 功能：
 * 1. 处理业务错误（code !== 0）
 * 2. 处理HTTP错误（401跳转登录等）
 * 3. 统一错误提示
 */
axiosInstance.interceptors.response.use(
  (response) => {
    // 直接返回数据部分
    return response.data;
  },
  async (error: AxiosError) => {
    // 原始请求配置
    const originalRequest = error.config as AxiosRequestConfig & { _retry?: boolean };

    // 处理401未授权
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        // 尝试刷新Token
        const token = localStorage.getItem('coolai-auth');
        if (token) {
          const authData = JSON.parse(token);
          const refreshToken = authData.state?.refreshToken;

          if (refreshToken) {
            const response = await axios.post(`${BASE_URL}/auth/refresh`, {
              refresh_token: refreshToken,
            });

            // 更新Token
            const newAuthData = {
              ...authData,
              state: {
                ...authData.state,
                accessToken: response.access_token,
                refreshToken: response.refresh_token,
              },
            };
            localStorage.setItem('coolai-auth', JSON.stringify(newAuthData));

            // 重试原请求
            originalRequest.headers = {
              ...originalRequest.headers,
              Authorization: `Bearer ${response.access_token}`,
            };
            return axios(originalRequest);
          }
        }
      } catch {
        // 刷新失败，清除登录状态
        localStorage.removeItem('coolai-auth');
        window.location.href = '/login';
      }
    }

    // 处理403禁止访问
    if (error.response?.status === 403) {
      console.error('没有权限访问该资源');
    }

    // 处理404
    if (error.response?.status === 404) {
      console.error('请求的资源不存在');
    }

    // 处理500
    if (error.response?.status >= 500) {
      console.error('服务器错误');
    }

    return Promise.reject(error);
  }
);

/**
 * API对象
 * 
 * 提供get、post、put、delete等方法
 */
export const api = {
  /**
   * GET请求
   */
  get: <T = any>(url: string, params?: object, config?: AxiosRequestConfig): Promise<T> => {
    return axiosInstance.get(url, { params, ...config });
  },

  /**
   * POST请求
   */
  post: <T = any>(url: string, data?: object, config?: AxiosRequestConfig): Promise<T> => {
    return axiosInstance.post(url, data, config);
  },

  /**
   * PUT请求
   */
  put: <T = any>(url: string, data?: object, config?: AxiosRequestConfig): Promise<T> => {
    return axiosInstance.put(url, data, config);
  },

  /**
   * DELETE请求
   */
  delete: <T = any>(url: string, config?: AxiosRequestConfig): Promise<T> => {
    return axiosInstance.delete(url, config);
  },

  /**
   * PATCH请求
   */
  patch: <T = any>(url: string, data?: object, config?: AxiosRequestConfig): Promise<T> => {
    return axiosInstance.patch(url, data, config);
  },

  /**
   * 上传文件
   */
  upload: <T = any>(
    url: string,
    file: File | Blob,
    fieldName = 'file',
    onProgress?: (percent: number) => void
  ): Promise<T> => {
    const formData = new FormData();
    formData.append(fieldName, file);

    return axiosInstance.post(url, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (progressEvent) => {
        if (progressEvent.total && onProgress) {
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          onProgress(percent);
        }
      },
    });
  },
};

export default api;
