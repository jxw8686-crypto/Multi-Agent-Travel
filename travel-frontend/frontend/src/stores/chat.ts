/**
 * 聊天状态管理（Pinia store）。
 *
 * 每次用户查询只产生一条助手消息，多轮 tool-calling 的
 * 思考块和文本增量都累积到同一条消息中。
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Message, ThinkingEntry, HistoryItem, TravelFormData } from '@/types'

export const useChatStore = defineStore('chat', () => {
  // ========== 状态 ==========

  const messages = ref<Message[]>([])
  /** 当前正在流式接收的助手消息 ID（null 表示没有进行中的消息） */
  const streamingMsgId = ref<string | null>(null)
  /** 当前回合的思考块（累积到 streamingMsgId 对应的消息中） */
  const currentThinking = ref<ThinkingEntry[]>([])
  /** 当前流式累积文本 */
  const currentText = ref('')

  const totalUsage = ref<{ input_tokens: number; output_tokens: number } | null>(null)
  const connectionStatus = ref<'connecting' | 'connected' | 'disconnected'>('disconnected')
  const history = ref<HistoryItem[]>(loadHistory())

  // ========== 计算属性 ==========

  /** 是否正在接收流式响应 */
  const isStreaming = computed(() => streamingMsgId.value !== null)

  const lastMessage = computed(() => messages.value[messages.value.length - 1] || null)

  // ========== 消息管理 ==========

  function addUserMessage(content: string, formData: TravelFormData | null = null) {
    const msg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
      thinkingEntries: [],
      usage: null,
      timestamp: Date.now(),
      isStreaming: false,
    }
    messages.value.push(msg)

    if (formData?.destination) {
      addHistoryItem(buildHistoryTitle(content, formData), formData)
    }
  }

  /** 确保有一条正在进行的助手消息（幂等） */
  function _ensureStreamingMsg(): Message {
    if (streamingMsgId.value) {
      const found = messages.value.find((m) => m.id === streamingMsgId.value)
      if (found) return found
    }
    // 创建新的助手消息
    currentThinking.value = []
    currentText.value = ''
    const msg: Message = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '',
      thinkingEntries: [],
      usage: null,
      timestamp: Date.now(),
      isStreaming: true,
    }
    messages.value.push(msg)
    streamingMsgId.value = msg.id
    return msg
  }

  function appendText(text: string) {
    const msg = _ensureStreamingMsg()
    currentText.value += text
    msg.content = currentText.value
  }

  /** 最终结束（整个查询完成时调用） */
  function finalizeMessage() {
    if (!streamingMsgId.value) return
    const msg = messages.value.find((m) => m.id === streamingMsgId.value)
    if (msg) {
      msg.isStreaming = false
      msg.thinkingEntries = [...currentThinking.value]
    }
    streamingMsgId.value = null
    currentThinking.value = []
    currentText.value = ''
  }

  // ========== 思考块管理 ==========

  function addThinkingEntry(entry: ThinkingEntry) {
    _ensureStreamingMsg()
    currentThinking.value.push(entry)
  }

  function updateLastThinkingEntry(
    predicate: (e: ThinkingEntry) => boolean,
    status: 'done' | 'error',
    detail: string
  ) {
    for (let i = currentThinking.value.length - 1; i >= 0; i--) {
      if (predicate(currentThinking.value[i])) {
        currentThinking.value[i].status = status
        if (detail) currentThinking.value[i].detail = detail
        break
      }
    }
  }

  function finalizeAllThinking() {
    for (const entry of currentThinking.value) {
      if (entry.status === 'running') entry.status = 'done'
    }
  }

  // ========== 用量管理 ==========

  function setUsage(usage: { input_tokens: number; output_tokens: number }) {
    if (totalUsage.value) {
      totalUsage.value.input_tokens += usage.input_tokens
      totalUsage.value.output_tokens += usage.output_tokens
    } else {
      totalUsage.value = { ...usage }
    }
    if (streamingMsgId.value) {
      const msg = messages.value.find((m) => m.id === streamingMsgId.value)
      if (msg) msg.usage = { ...usage }
    }
  }

  // ========== 连接状态 ==========

  function setConnectionStatus(status: 'connecting' | 'connected' | 'disconnected') {
    connectionStatus.value = status
  }

  // ========== 历史记录 ==========

  function loadHistory(): HistoryItem[] {
    try {
      const raw = localStorage.getItem('travel_history')
      return raw ? JSON.parse(raw).slice(0, 20) : []
    } catch { return [] }
  }

  function addHistoryItem(title: string, formData: TravelFormData) {
    const exists = history.value.find(
      (h) => h.formData.destination === formData.destination && h.formData.days === formData.days
    )
    if (!exists) {
      history.value.unshift({ id: crypto.randomUUID(), title, formData, timestamp: Date.now() })
      if (history.value.length > 20) history.value = history.value.slice(0, 20)
      saveHistory()
    }
  }

  function saveHistory() {
    try { localStorage.setItem('travel_history', JSON.stringify(history.value)) } catch { /* */ }
  }

  function clearHistory() {
    history.value = []
    localStorage.removeItem('travel_history')
  }

  function clearMessages() {
    messages.value = []
    currentThinking.value = []
    currentText.value = ''
    streamingMsgId.value = null
    totalUsage.value = null
  }

  function buildHistoryTitle(message: string, formData: TravelFormData | null): string {
    if (formData?.destination) {
      let title = `${formData.departure || '?'} → ${formData.destination}`
      if (formData.days) title += ` ${formData.days}天`
      return title
    }
    return message.slice(0, 20) + (message.length > 20 ? '...' : '')
  }

  return {
    messages, currentThinking, currentText, isStreaming,
    totalUsage, connectionStatus, history,
    lastMessage,
    addUserMessage, appendText, finalizeMessage,
    addThinkingEntry, updateLastThinkingEntry, finalizeAllThinking,
    setUsage, setConnectionStatus, clearMessages, clearHistory,
  }
})
