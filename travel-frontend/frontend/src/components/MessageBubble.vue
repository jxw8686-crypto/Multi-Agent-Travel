<script setup lang="ts">
/**
 * 消息气泡组件。
 *
 * 用户消息：右对齐，蓝色背景
 * 助手消息：左对齐，思考块（可折叠）→ 内容区域（流式 Markdown）
 */

import { computed } from 'vue'
import type { Message } from '@/types'
import ThinkingBlock from './ThinkingBlock.vue'
import StreamingText from './StreamingText.vue'

const props = defineProps<{ message: Message }>()

const isUser = computed(() => props.message.role === 'user')
const isAssistant = computed(() => props.message.role === 'assistant')

const formattedTime = computed(() => {
  const d = new Date(props.message.timestamp)
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
})

const hasThinking = computed(
  () => isAssistant.value && props.message.thinkingEntries.length > 0
)
const hasContent = computed(
  () => isAssistant.value && props.message.content.trim().length > 0
)
</script>

<template>
  <div class="message-bubble" :class="{ 'message-user': isUser, 'message-assistant': isAssistant }">
    <!-- 头像 -->
    <div class="message-avatar">
      <span class="avatar-icon">{{ isUser ? '👤' : '🧳' }}</span>
    </div>

    <div class="message-body">
      <!-- 元信息 -->
      <div class="message-meta">
        <span class="message-sender">{{ isUser ? '你' : '旅行助手' }}</span>
        <span class="message-time">{{ formattedTime }}</span>
        <span v-if="message.isStreaming" class="message-live">● 实时</span>
        <span v-if="message.usage" class="message-tokens">
          {{ message.usage.input_tokens }}↑ / {{ message.usage.output_tokens }}↓ tokens
        </span>
      </div>

      <!-- 用户消息 -->
      <div v-if="isUser" class="message-content user-content">
        {{ message.content }}
      </div>

      <!-- 助手消息：思考块 → 流式内容 -->
      <template v-if="isAssistant">
        <ThinkingBlock v-if="hasThinking" :entries="message.thinkingEntries" />

        <div v-if="hasContent" class="message-content assistant-content">
          <StreamingText :text="message.content" :is-streaming="message.isStreaming" />
        </div>

        <!-- 等待中 -->
        <div v-if="!hasContent && message.isStreaming && !hasThinking" class="message-waiting">
          <span class="waiting-dots"><span class="dot"></span><span class="dot"></span><span class="dot"></span></span>
          <span class="waiting-text">正在思考...</span>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.message-bubble {
  display: flex;
  gap: 12px;
  padding: 14px 20px;
  animation: fadeIn 0.25s ease-out;
}
@keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }

.message-user { flex-direction: row-reverse; }

.message-avatar {
  flex-shrink: 0;
  width: 34px; height: 34px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 17px;
}
.message-user .message-avatar { background: var(--primary-light); }
.message-assistant .message-avatar { background: linear-gradient(135deg, #e0f2fe, #f0f9ff); }

.message-body { flex: 1; min-width: 0; max-width: 88%; }
.message-user .message-body { display: flex; flex-direction: column; align-items: flex-end; }

.message-meta {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 3px; font-size: 12px;
}
.message-sender { font-weight: 600; color: var(--text); }
.message-time { color: var(--text-secondary); }
.message-live { color: var(--success); font-size: 10px; animation: pulse 1.5s ease-in-out infinite; }
.message-tokens {
  font-size: 10px; color: var(--text-secondary);
  font-family: 'SF Mono', 'Cascadia Code', 'Consolas', monospace;
  margin-left: auto;
}
@keyframes pulse { 0%, 100% { opacity: 0.5; } 50% { opacity: 1; } }

.message-content { line-height: 1.7; word-break: break-word; }

.user-content {
  background: var(--primary); color: #fff;
  padding: 10px 16px; border-radius: 18px 4px 18px 18px;
  display: inline-block; max-width: 100%;
}

.assistant-content {
  background: var(--bg-white);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 14px 18px;
  box-shadow: var(--shadow);
}

.message-waiting {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 0; color: var(--text-secondary); font-size: 13px;
}

.waiting-dots { display: inline-flex; gap: 4px; }
.waiting-dots .dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--primary);
  animation: dotPulse 1.4s ease-in-out infinite;
}
.waiting-dots .dot:nth-child(2) { animation-delay: 0.2s; }
.waiting-dots .dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes dotPulse {
  0%, 80%, 100% { opacity: 0.2; }
  40% { opacity: 1; }
}
</style>
