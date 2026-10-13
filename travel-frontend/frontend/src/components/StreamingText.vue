<script setup lang="ts">
/**
 * 流式文字组件：接收实时文本增量，渲染 Markdown + 光标闪烁。
 */
import { computed } from 'vue'
import { marked } from 'marked'

const props = defineProps<{
  text: string
  isStreaming: boolean
}>()

/** 配置 marked 以安全渲染 */
marked.setOptions({
  breaks: true,
  gfm: true,
})

const renderedHtml = computed(() => {
  if (!props.text) return ''
  try {
    return marked.parse(props.text) as string
  } catch {
    // Markdown 解析失败时回退到纯文本
    return escapeHtml(props.text).replace(/\n/g, '<br>')
  }
})

function escapeHtml(str: string): string {
  const div = document.createElement('div')
  div.textContent = str
  return div.innerHTML
}
</script>

<template>
  <div class="streaming-text">
    <!-- eslint-disable-next-line vue/no-v-html -->
    <div class="markdown-body" v-html="renderedHtml"></div>
    <span v-if="isStreaming && text" class="cursor-blink">▌</span>
  </div>
</template>

<style scoped>
.streaming-text {
  position: relative;
}

.markdown-body {
  word-break: break-word;
  line-height: 1.7;
}

/* ========== Markdown 内容样式 ========== */
.markdown-body :deep(h1) {
  font-size: 1.4em;
  margin: 0.8em 0 0.4em;
  padding-bottom: 0.3em;
  border-bottom: 1px solid var(--border);
}
.markdown-body :deep(h2) {
  font-size: 1.2em;
  margin: 0.7em 0 0.35em;
}
.markdown-body :deep(h3) {
  font-size: 1.05em;
  margin: 0.6em 0 0.3em;
}
.markdown-body :deep(p) {
  margin: 0.4em 0;
}
.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  padding-left: 1.5em;
  margin: 0.3em 0;
}
.markdown-body :deep(li) {
  margin: 0.15em 0;
}
.markdown-body :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 0.6em 0;
  font-size: 0.9em;
}
.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid var(--border);
  padding: 6px 10px;
  text-align: left;
}
.markdown-body :deep(th) {
  background: var(--primary-light);
  font-weight: 600;
  color: var(--primary);
}
.markdown-body :deep(tr:nth-child(even)) {
  background: #fafbfc;
}
.markdown-body :deep(code) {
  background: #f0f0f5;
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 0.9em;
}
.markdown-body :deep(pre) {
  background: #1e1e2e;
  color: #cdd6f4;
  padding: 12px 16px;
  border-radius: var(--radius-sm);
  overflow-x: auto;
  margin: 0.5em 0;
}
.markdown-body :deep(pre code) {
  background: none;
  padding: 0;
  color: inherit;
}
.markdown-body :deep(blockquote) {
  border-left: 3px solid var(--primary);
  padding-left: 12px;
  color: var(--text-secondary);
  margin: 0.5em 0;
  background: var(--primary-light);
  padding: 6px 12px;
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
}
.markdown-body :deep(a) {
  color: var(--primary);
  text-decoration: none;
}
.markdown-body :deep(a:hover) {
  text-decoration: underline;
}
.markdown-body :deep(hr) {
  border: none;
  border-top: 1px solid var(--border);
  margin: 1em 0;
}
.markdown-body :deep(strong) {
  font-weight: 600;
}
.markdown-body :deep(img) {
  max-width: 100%;
}
/* 隐藏 Markdown 渲染中可能出现的标题锚点 */
.markdown-body :deep(.header-anchor) {
  display: none;
}

/* ========== 光标动画 ========== */
.cursor-blink {
  display: inline-block;
  color: var(--primary);
  font-weight: bold;
  animation: blink 1s step-end infinite;
  margin-left: 1px;
  vertical-align: text-bottom;
  line-height: 1;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}
</style>
