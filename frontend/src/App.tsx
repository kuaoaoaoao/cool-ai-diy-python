/**
 * ============================================================
 * CoolAI 主应用组件
 * ============================================================
 * 
 * 应用根组件
 * - 路由配置
 * - 布局组件
 * - 权限控制
 * 
 * Author: CoolAI Team
 * Date: 2026-05-13
 */

import { useEffect } from 'react';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { Spin } from 'antd';
import { useAuthStore } from './store/authStore';

// 布局组件
import MainLayout from './components/Layout/MainLayout';

// 页面组件
import LoginPage from './pages/Login';
import DashboardPage from './pages/Dashboard';
import ChatPage from './pages/Chat';
import KnowledgePage from './pages/Knowledge';
import TTTSPage from './pages/TTS';
import VoiceClonePage from './pages/VoiceClone';
import SettingsPage from './pages/Settings';

/**
 * 加载动画组件
 * 用于路由切换时的过渡效果
 */
const Loading = () => (
  <div style={{
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    height: '100vh',
    background: '#f0f2f5'
  }}>
    <Spin size="large" tip="加载中..." />
  </div>
);

/**
 * 路由守卫组件
 * 
 * 功能：
 * - 检查用户是否已登录
 * - 已登录则显示目标页面
 * - 未登录则跳转到登录页
 */
const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const { isAuthenticated, isLoading } = useAuthStore();
  const location = useLocation();

  // 加载中状态
  if (isLoading) {
    return <Loading />;
  }

  // 未登录，跳转到登录页
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // 已登录，显示内容
  return <>{children}</>;
};

/**
 * 公共路由
 * 已登录用户访问这些页面会跳转到首页
 */
const PublicRoute = ({ children }: { children: React.ReactNode }) => {
  const { isAuthenticated, isLoading } = useAuthStore();

  if (isLoading) {
    return <Loading />;
  }

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
};

/**
 * App根组件
 */
function App() {
  const { checkAuth } = useAuthStore();

  // 应用启动时检查登录状态
  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  return (
    <Routes>
      {/* 公共路由 */}
      <Route
        path="/login"
        element={
          <PublicRoute>
            <LoginPage />
          </PublicRoute>
        }
      />

      {/* 受保护的路由 */}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <MainLayout />
          </ProtectedRoute>
        }
      >
        {/* 首页/仪表盘 */}
        <Route index element={<DashboardPage />} />
        
        {/* AI聊天 */}
        <Route path="chat" element={<ChatPage />} />
        <Route path="chat/:conversationId" element={<ChatPage />} />
        
        {/* 知识库 */}
        <Route path="knowledge" element={<KnowledgePage />} />
        
        {/* TTS语音合成 */}
        <Route path="tts" element={<TTTSPage />} />
        
        {/* 声音克隆 */}
        <Route path="voice-clone" element={<VoiceClonePage />} />
        
        {/* 设置 */}
        <Route path="settings" element={<SettingsPage />} />
      </Route>

      {/* 404页面 */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
