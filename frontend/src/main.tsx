/**
 * ============================================================
 * CoolAI 前端应用入口
 * ============================================================
 * 
 * 应用主入口文件
 * - 初始化React应用
 * - 配置路由
 * - 配置全局状态管理
 * - 配置请求库
 * 
 * Author: CoolAI Team
 * Date: 2026-05-13
 */

import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import App from './App';

// 导入全局样式
import './assets/styles/global.css';

/**
 * 创建React Query客户端
 * 
 * 配置说明：
 * - staleTime: 数据被认为过时之前的时间（毫秒）
 * - gcTime: 缓存数据保留时间（毫秒）
 * - retry: 失败重试次数
 */
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // 数据在5分钟内被认为新鲜，不会自动重新获取
      staleTime: 5 * 60 * 1000,
      // 缓存数据保留10分钟
      gcTime: 10 * 60 * 1000,
      // 请求失败时重试3次
      retry: 3,
      // 失败后重新渲染视图
      refetchOnWindowFocus: false,
    },
  },
});

/**
 * Ant Design全局配置
 */
const themeConfig = {
  // Token: 设计令牌，用于自定义主题
  token: {
    // 主色调 - 科技蓝
    colorPrimary: '#3B82F6',
    // 边框圆角
    borderRadius: 6,
    // 成功色
    colorSuccess: '#10B981',
    // 警告色
    colorWarning: '#F59E0B',
    // 错误色
    colorError: '#EF4444',
    // 标题字体大小
    fontSize: 14,
    // 中文字体
    fontFamily: "'PingFang SC', 'Microsoft YaHei', sans-serif",
  },
};

/**
 * 渲染应用
 */
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    {/* BrowserRouter: HTML5 History API 路由 */}
    <BrowserRouter>
      {/* QueryClientProvider: React Query数据获取框架 */}
      <QueryClientProvider client={queryClient}>
        {/* ConfigProvider: Ant Design全局配置 */}
        <ConfigProvider locale={zhCN} theme={themeConfig}>
          {/* 应用主组件 */}
          <App />
        </ConfigProvider>
      </QueryClientProvider>
    </BrowserRouter>
  </React.StrictMode>
);
