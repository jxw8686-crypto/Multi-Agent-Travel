<script setup lang="ts">
/**
 * DeepSeek 风格可折叠思考过程组件。
 *
 * 展示 Agent 的工具调用、子 Agent 启停等思考过程，
 * 默认展开，超过最大高度后可滚动，有新条目时自动滚到底部。
 */

import { ref, watch, nextTick } from 'vue'
import type { ThinkingEntry } from '@/types'

const props = defineProps<{
  entries: ThinkingEntry[]
}>()

const isExpanded = ref(true)
const contentRef = ref<HTMLElement | null>(null)

function toggleExpand() {
  isExpanded.value = !isExpanded.value
}

/** 新条目加入时自动滚动到底部 */
watch(
  () => props.entries.length,
  async () => {
    await nextTick()
    if (contentRef.value) {
      contentRef.value.scrollTop = contentRef.value.scrollHeight
    }
  }
)

function statusIcon(status: string): string {
  switch (status) {
    case 'running': return '⏳'
    case 'done': return '✅'
    case 'error': return '❌'
    default: return '•'
  }
}

function entryIcon(entry: ThinkingEntry): string {
  switch (entry.type) {
    case 'tool_call': return '🔧'
    case 'agent_spawn': return '🤖'
    case 'phase': return '📌'
    default: return '•'
  }
}

function formatDetail(detail: string): string {
  if (!detail) return ''
  if (detail.length > 200) return detail.slice(0, 200) + '...'
  return detail
}

const runningCount = computedCountByStatus('running')
const doneCount = computedCountByStatus('done')
const errorCount = computedCountByStatus('error')

function computedCountByStatus(status: string) {
  return () => props.entries.filter((e) => e.status === status).length
}
</script>

<template>
  <div class="thinking-block" v-if="entries.length > 0">
    <div class="thinking-header" @click="toggleExpand">
      <span class="thinking-arrow">{{ isExpanded ? '▼' : '▶' }}</span>
      <span class="thinking-label">🤔 思考过程</span>
      <span class="thinking-badges">
        <span v-if="runningCount() > 0" class="badge badge-running">{{ runningCount() }} 进行中</span>
        <span v-if="doneCount() > 0" class="badge badge-done">{{ doneCount() }}</span>
        <span v-if="errorCount() > 0" class="badge badge-error">{{ errorCount() }} 失败</span>
      </span>
      <span class="thinking-count">{{ entries.length }} 步</span>
    </div>

    <Transition name="collapse">
      <div v-show="isExpanded" ref="contentRef" class="thinking-content">
        <div
          v-for="entry in entries"
          :key="entry.id"
          class="thinking-entry"
          :class="`entry-${entry.status}`"
        >
          <span class="entry-status">{{ statusIcon(entry.status) }}</span>
          <span class="entry-type">{{ entryIcon(entry) }}</span>
          <div class="entry-body">
            <span class="entry-title">{{ entry.title }}</span>
            <span v-if="entry.detail && entry.status !== 'running'" class="entry-detail">
              {{ formatDetail(entry.detail) }}
            </span>
            <span v-if="entry.status === 'running'" class="entry-loading">
              <span class="loading-dots">
                <span class="dot"></span><span class="dot"></span><span class="dot"></span>
              </span>
            </span>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.thinking-block {
  background: #f8f9fd;
  border: 1px solid #e8ecf4;
  border-radius: var(--radius);
  margin-bottom: 10px;
  overflow: hidden;
}

.thinking-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 14px;
  cursor: pointer;
  user-select: none;
  font-size: 13px;
  color: var(--text-secondary);
  transition: background 0.15s;
  flex-shrink: 0;
}
.thinking-header:hover { background: #f0f2f8; }

.thinking-arrow {
  font-size: 10px;
  transition: transform 0.2s;
  width: 14px;
  text-align: center;
}

.thinking-label {
  font-weight: 600;
  color: var(--text);
}

.thinking-badges {
  display: flex;
  gap: 4px;
  margin-left: auto;
}

.badge {
  font-size: 10px;
  padding: 0 6px;
  border-radius: 8px;
  font-weight: 500;
  line-height: 18px;
}
.badge-running { background: #fef3c7; color: #92400e; }
.badge-done { background: #d1fae5; color: #065f46; }
.badge-error { background: #fee2e2; color: #991b1b; }

.thinking-count {
  font-size: 11px;
  background: var(--border);
  padding: 0 7px;
  border-radius: 10px;
  color: var(--text-secondary);
  line-height: 18px;
}

/* 核心：限定最大高度，超出滚动 */
.thinking-content {
  border-top: 1px solid #e8ecf4;
  padding: 6px 14px;
  max-height: 300px;
  overflow-y: auto;
  scroll-behavior: smooth;
}

.thinking-content::-webkit-scrollbar { width: 4px; }
.thinking-content::-webkit-scrollbar-track { background: transparent; }
.thinking-content::-webkit-scrollbar-thumb { background: #d1d5db; border-radius: 2px; }

.thinking-entry {
  display: flex;
  align-items: flex-start;
  gap: 7px;
  padding: 4px 0;
  font-size: 12px;
}
.thinking-entry + .thinking-entry { border-top: 1px solid #f0f2f8; }

.entry-status { flex-shrink: 0; width: 16px; text-align: center; font-size: 11px; }
.entry-type { flex-shrink: 0; width: 18px; text-align: center; font-size: 12px; }

.entry-body { flex: 1; min-width: 0; }
.entry-title { color: var(--text); font-weight: 500; }

.entry-detail {
  display: block;
  font-size: 10px;
  color: var(--text-secondary);
  margin-top: 1px;
  word-break: break-all;
  font-family: 'SF Mono', 'Cascadia Code', 'Consolas', monospace;
  background: #f0f0f5;
  padding: 1px 5px;
  border-radius: 3px;
  max-height: 50px;
  overflow: hidden;
}

.entry-loading { display: inline-block; margin-left: 4px; vertical-align: middle; }

.loading-dots { display: inline-flex; gap: 2px; }
.loading-dots .dot {
  width: 4px; height: 4px; border-radius: 50%;
  background: var(--primary);
  animation: dotPulse 1.4s ease-in-out infinite;
}
.loading-dots .dot:nth-child(2) { animation-delay: 0.2s; }
.loading-dots .dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes dotPulse {
  0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
  40% { opacity: 1; transform: scale(1.2); }
}

.entry-error .entry-title { color: var(--error); }

/* 折叠/展开动画 */
.collapse-enter-active, .collapse-leave-active {
  transition: all 0.2s ease;
  max-height: 300px;
}
.collapse-enter-from, .collapse-leave-to {
  max-height: 0;
  opacity: 0;
  padding-top: 0;
  padding-bottom: 0;
}
</style>
