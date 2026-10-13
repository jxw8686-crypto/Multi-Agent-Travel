<script setup lang="ts">
/**
 * 根组件：左右分栏布局。
 *
 * 左侧：对话面板（聊天框 + 输入区）
 * 右侧：出行信息表单 + 历史记录
 * 底部：状态栏（连接状态 + token 用量）
 */

import { onMounted } from 'vue'
import { useWebSocket } from '@/composables/useWebSocket'
import { useChatStore } from '@/stores/chat'
import ChatPanel from '@/components/ChatPanel.vue'
import InfoPanel from '@/components/InfoPanel.vue'

const { isConnected, connect, sendMessage } = useWebSocket()
const store = useChatStore()

onMounted(() => {
  connect()
})

/** 处理用户发送消息（来自聊天面板或信息面板） */
function handleSend(payload: { message: string; formData: import('@/types').TravelFormData | null }) {
  store.addUserMessage(payload.message, payload.formData)
  sendMessage(payload.message, payload.formData)
}
</script>

<template>
  <div class="app-root">
    <!-- 顶部标题栏 -->
    <header class="app-header">
      <div class="header-left">
        <span class="header-icon">🧳</span>
        <h1 class="header-title">智能旅行助手</h1>
        <span class="header-badge">OpenHarness 多 Agent</span>
      </div>
      <div class="header-right">
        <span
          class="status-dot"
          :class="{
            'status-connected': isConnected,
            'status-disconnected': !isConnected,
          }"
        ></span>
        <span class="status-text">
          {{ isConnected ? '已连接' : '未连接' }}
        </span>
      </div>
    </header>

    <!-- 主体区域 -->
    <main class="app-main">
      <div class="main-left">
        <ChatPanel @send="handleSend" />
      </div>
      <aside class="main-right">
        <InfoPanel @send="handleSend" />
      </aside>
    </main>

    <!-- 底部状态栏 -->
    <footer class="app-footer">
      <span>模型: {{ store.connectionStatus === 'connected' ? 'OpenHarness' : '降级模式' }}</span>
      <span v-if="store.totalUsage" class="footer-usage">
        累计 Token: 输入 {{ store.totalUsage.input_tokens.toLocaleString() }}
        / 输出 {{ store.totalUsage.output_tokens.toLocaleString() }}
      </span>
    </footer>
  </div>
</template>

<style>
/* ========== 全局重置 ========== */
*,
*::before,
*::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

:root {
  --primary: #4f6ef7;
  --primary-light: #eef1fe;
  --bg: #f5f6fa;
  --bg-white: #ffffff;
  --text: #1a1a2e;
  --text-secondary: #6b7280;
  --border: #e5e7eb;
  --success: #10b981;
  --warning: #f59e0b;
  --error: #ef4444;
  --shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.1);
  --radius: 10px;
  --radius-sm: 6px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial,
    'Noto Sans SC', sans-serif;
  font-size: 15px;
  line-height: 1.6;
  color: var(--text);
}

body {
  background: var(--bg);
  min-height: 100vh;
  overflow: hidden;
}

#app {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

/* ========== 布局 ========== */
.app-root {
  display: flex;
  flex-direction: column;
  height: 100vh;
  max-width: 1440px;
  margin: 0 auto;
  width: 100%;
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 24px;
  background: var(--bg-white);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-icon {
  font-size: 24px;
}

.header-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text);
}

.header-badge {
  font-size: 11px;
  background: var(--primary-light);
  color: var(--primary);
  padding: 2px 10px;
  border-radius: 20px;
  font-weight: 500;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-secondary);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

.status-connected {
  background: var(--success);
  box-shadow: 0 0 6px rgba(16, 185, 129, 0.4);
}

.status-disconnected {
  background: var(--error);
}

.app-main {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.main-left {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  border-right: 1px solid var(--border);
}

.main-right {
  width: 360px;
  flex-shrink: 0;
  overflow-y: auto;
  background: var(--bg-white);
}

.app-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 24px;
  background: var(--bg-white);
  border-top: 1px solid var(--border);
  font-size: 12px;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.footer-usage {
  font-variant-numeric: tabular-nums;
}

/* ========== 响应式 ========== */
@media (max-width: 768px) {
  .app-main {
    flex-direction: column;
  }

  .main-right {
    width: 100%;
    max-height: 40vh;
    border-top: 1px solid var(--border);
  }

  .header-badge {
    display: none;
  }
}
</style>
