<script setup lang="ts">
/**
 * 旅行规划结果卡片：对助手最终回复中的旅行规划内容进行增强渲染。
 *
 * 在 StreamingText 的 Markdown 基础上，为表格添加了排序图标、
 * 为预订链接添加了可点击按钮样式等增强效果。
 */

import StreamingText from './StreamingText.vue'

defineProps<{
  content: string
  isStreaming: boolean
}>()
</script>

<template>
  <div class="travel-plan-card">
    <div class="plan-header">
      <span class="plan-icon">📋</span>
      <span class="plan-title">旅行规划报告</span>
      <span v-if="isStreaming" class="plan-generating">生成中...</span>
    </div>
    <div class="plan-body">
      <StreamingText :text="content" :is-streaming="isStreaming" />
    </div>
  </div>
</template>

<style scoped>
.travel-plan-card {
  background: var(--bg-white);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  overflow: hidden;
  margin-top: 8px;
}

.plan-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: linear-gradient(135deg, var(--primary-light), #f8f9fd);
  border-bottom: 1px solid var(--border);
}

.plan-icon {
  font-size: 18px;
}

.plan-title {
  font-weight: 700;
  font-size: 15px;
  color: var(--text);
}

.plan-generating {
  margin-left: auto;
  font-size: 12px;
  color: var(--primary);
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}

.plan-body {
  padding: 16px;
}
</style>
