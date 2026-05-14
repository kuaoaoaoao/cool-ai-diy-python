/**
 * ============================================================
 * 主布局组件
 * ============================================================
 * 
 * 应用主布局
 * - 顶部导航栏
 * - 侧边菜单
 * - 内容区域
 * 
 * Author: CoolAI Team
 * Date: 2026-05-13
 */

import { useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu, Avatar, Dropdown, Badge, Button, theme } from 'antd';
import {
  DashboardOutlined,
  MessageOutlined,
  BookOutlined,
  AudioOutlined,
  SoundOutlined,
  SettingOutlined,
  BellOutlined,
  UserOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
} from '@ant-design/icons';
import { useAuthStore } from '../../store/authStore';

const { Header, Sider, Content } = Layout;

/**
 * 菜单配置
 */
const menuItems = [
  {
    key: '/',
    icon: <DashboardOutlined />,
    label: '工作台',
  },
  {
    key: '/chat',
    icon: <MessageOutlined />,
    label: 'AI聊天',
  },
  {
    key: '/knowledge',
    icon: <BookOutlined />,
    label: '知识库',
  },
  {
    key: '/tts',
    icon: <AudioOutlined />,
    label: '语音合成',
  },
  {
    key: '/voice-clone',
    icon: <SoundOutlined />,
    label: '声音克隆',
  },
  {
    key: '/settings',
    icon: <SettingOutlined />,
    label: '设置',
  },
];

/**
 * 主布局组件
 */
const MainLayout: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuthStore();
  const [collapsed, setCollapsed] = useState(false);
  
  // 使用Ant Design主题
  const {
    token: { colorBgContainer, colorPrimary },
  } = theme.useToken();

  /**
   * 处理菜单点击
   */
  const handleMenuClick = ({ key }: { key: string }) => {
    navigate(key);
  };

  /**
   * 处理退出登录
   */
  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  /**
   * 用户下拉菜单
   */
  const userMenuItems = [
    {
      key: 'profile',
      icon: <UserOutlined />,
      label: '个人中心',
    },
    {
      key: 'settings',
      icon: <SettingOutlined />,
      label: '设置',
    },
    {
      type: 'divider' as const,
    },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      danger: true,
    },
  ];

  const handleUserMenuClick = ({ key }: { key: string }) => {
    if (key === 'logout') {
      handleLogout();
    } else {
      navigate(`/${key}`);
    }
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      {/* 侧边栏 */}
      <Sider
        trigger={null}
        collapsible
        collapsed={collapsed}
        width={220}
        style={{
          background: colorBgContainer,
          boxShadow: '2px 0 8px rgba(0,0,0,0.05)',
        }}
      >
        {/* Logo区域 */}
        <div
          style={{
            height: 64,
            display: 'flex',
            alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'flex-start',
            padding: collapsed ? 0 : '0 20px',
            borderBottom: '1px solid #f0f0f0',
          }}
        >
          {/* Logo图标 */}
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: 8,
              background: `linear-gradient(135deg, ${colorPrimary}, #8B5CF6)`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#fff',
              fontWeight: 'bold',
              fontSize: 14,
            }}
          >
            AI
          </div>
          
          {/* Logo文字 */}
          {!collapsed && (
            <span
              style={{
                marginLeft: 12,
                fontSize: 16,
                fontWeight: 600,
                color: '#1f1f1f',
              }}
            >
              CoolAI
            </span>
          )}
        </div>

        {/* 菜单 */}
        <Menu
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={handleMenuClick}
          style={{
            border: 'none',
            padding: '12px 8px',
          }}
        />
      </Sider>

      <Layout>
        {/* 顶部导航栏 */}
        <Header
          style={{
            padding: '0 24px',
            background: colorBgContainer,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            boxShadow: '0 1px 4px rgba(0,0,0,0.05)',
          }}
        >
          {/* 左侧：折叠按钮 */}
          <Button
            type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed(!collapsed)}
            style={{ fontSize: 16 }}
          />

          {/* 右侧：用户信息 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            {/* 通知 */}
            <Badge count={3} size="small">
              <BellOutlined style={{ fontSize: 18, cursor: 'pointer' }} />
            </Badge>

            {/* 用户下拉 */}
            <Dropdown
              menu={{
                items: userMenuItems,
                onClick: handleUserMenuClick,
              }}
              placement="bottomRight"
              trigger={['click']}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  cursor: 'pointer',
                  padding: '4px 8px',
                  borderRadius: 8,
                  transition: 'background 0.2s',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = '#f5f5f5';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'transparent';
                }}
              >
                <Avatar
                  src={user?.avatar_url}
                  icon={<UserOutlined />}
                  style={{ backgroundColor: colorPrimary }}
                />
                <span style={{ fontSize: 14 }}>
                  {user?.full_name || user?.username || '用户'}
                </span>
              </div>
            </Dropdown>
          </div>
        </Header>

        {/* 内容区域 */}
        <Content
          style={{
            margin: 24,
            padding: 24,
            background: colorBgContainer,
            borderRadius: 8,
            minHeight: 280,
            overflow: 'auto',
          }}
        >
          {/* 路由出口 */}
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
};

export default MainLayout;
