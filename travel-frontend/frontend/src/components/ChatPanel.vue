<script setup lang="ts">
/**
 * 聊天面板组件：消息列表 + 底部输入框。
 */

import { ref, watch, nextTick, computed } from 'vue'
import { useChatStore } from '@/stores/chat'
import type { TravelFormData } from '@/types'
import MessageBubble from './MessageBubble.vue'

const emit = defineEmits<{
  send: [payload: { message: string; formData: TravelFormData | null }]
}>()

const store = useChatStore()

const inputText = ref('')
const messagesContainer = ref<HTMLElement | null>(null)

/** 是否可以发送 */
const canSend = computed(() => inputText.value.trim().length > 0 && !store.isStreaming)

/** 发送消息 */
function handleSend() {
  const text = inputText.value.trim()
  if (!text || store.isStreaming) return

  emit('send', {
    message: text,
    formData: null, // 纯聊天模式，不带表单数据
  })
  inputText.value = ''
}

/** 回车发送（Shift+Enter 换行） */
function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

/** 滚动到底部 */
async function scrollToBottom() {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

// 监听消息变化，自动滚动
watch(() => store.messages.length, scrollToBottom)
watch(() => store.currentText, scrollToBottom)
</script>

<template>
  <div class="chat-panel">
    <!-- 消息列表 -->
    <div ref="messagesContainer" class="chat-messages">
      <!-- 空状态 -->
      <div v-if="store.messages.length === 0" class="chat-empty">
        <div class="empty-icon">🧳</div>
        <h3>欢迎使用智能旅行助手</h3>
        <p>输入出行需求，或点击右侧填写出行信息</p>
        <div class="empty-examples">
          <button
            v-for="example in [
              '帮我规划北京到杭州3天舒适游',
              '从上海出发去三亚玩5天，预算5000',
              '成都到重庆周末特种兵，要最快',
            ]"
            :key="example"
            class="example-btn"
            @click="inputText = example"
          >
            {{ example }}
          </button>
        </div>
      </div>

      <!-- 消息列表 -->
      <MessageBubble
        v-for="msg in store.messages"
        :key="msg.id"
        :message="msg"
      />

      <!-- 滚动锚点 -->
      <div class="scroll-anchor"></div>
    </div>

    <!-- 输入区域 -->
    <div class="chat-input-area">
      <div class="input-wrapper">
        <textarea
          v-model="inputText"
          class="chat-input"
          placeholder="输入出行需求，如：从北京到杭州玩3天，要舒适的..."
          :disabled="store.isStreaming"
          @keydown="handleKeydown"
          rows="1"
          ref="inputEl"
        ></textarea>
        <button
          class="send-btn"
          :disabled="!canSend"
          @click="handleSend"
          :title="store.isStreaming ? '正在生成中...' : '发送 (Enter)'"
        >
          <span v-if="!store.isStreaming">➤</span>
          <span v-else class="sending-spinner">⏳</span>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-white);
}

/* ========== 消息区域 ========== */
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
  scroll-behavior: smooth;
}

.chat-messages::-webkit-scrollbar {
  width: 6px;
}

.chat-messages::-webkit-scrollbar-track {
  background: transparent;
}

.chat-messages::-webkit-scrollbar-thumb {
  background: #d1d5db;
  border-radius: 3px;
}

.chat-messages::-webkit-scrollbar-thumb:hover {
  background: #9ca3af;
}

/* ========== 空状态 ========== */
.chat-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 40px;
  text-align: center;
}

.empty-icon {
  font-size: 56px;
  margin-bottom: 16px;
}

.chat-empty h3 {
  font-size: 20px;
  color: var(--text);
  margin-bottom: 6px;
}

.chat-empty p {
  color: var(--text-secondary);
  font-size: 14px;
  margin-bottom: 24px;
}

.empty-examples {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
  max-width: 400px;
}

.example-btn {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 10px 14px;
  text-align: left;
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.15s;
}

.example-btn:hover {
  border-color: var(--primary);
  color: var(--primary);
  background: var(--primary-light);
}

/* ========== 输入区域 ========== */
.chat-input-area {
  border-top: 1px solid var(--border);
  padding: 12px 20px;
  background: var(--bg-white);
}

.input-wrapper {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 8px 12px;
  transition: border-color 0.2s;
}

.input-wrapper:focus-within {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(79, 110, 247, 0.1);
}

.chat-input {
  flex: 1;
  border: none;
  outline: none;
  background: none;
  resize: none;
  font-size: 14px;
  font-family: inherit;
  line-height: 1.5;
  color: var(--text);
  max-height: 120px;
  min-height: 24px;
}

.chat-input::placeholder {
  color: #c4c7d0;
}

.chat-input:disabled {
  opacity: 0.6;
}

.send-btn {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 50%;
  background: var(--primary);
  color: white;
  font-size: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.send-btn:hover:not(:disabled) {
  background: #3d5de7;
  transform: scale(1.05);
}

.send-btn:disabled {
  background: #c4c7d0;
  cursor: not-allowed;
}

.sending-spinner {
  animation: spin 2s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
