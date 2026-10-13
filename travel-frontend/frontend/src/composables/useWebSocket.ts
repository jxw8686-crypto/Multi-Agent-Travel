/**
 * WebSocket 连接管理 composable。
 *
 * 负责建立/维护 WebSocket 连接、自动重连、
 * 消息发送和事件分发到 Pinia store。
 */

import { ref, onUnmounted } from 'vue'
import { useChatStore } from '@/stores/chat'
import type { OutgoingMessage, ServerEvent, TravelFormData } from '@/types'

const WS_URL = 'ws://localhost:8001/ws'
const MAX_RECONNECT_ATTEMPTS = 5
const RECONNECT_BASE_DELAY_MS = 1000

export function useWebSocket() {
  const ws = ref<WebSocket | null>(null)
  const isConnected = ref(false)
  const reconnectAttempts = ref(0)
  const messageQueue = ref<OutgoingMessage[]>([])

  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  const store = useChatStore()

  function connect() {
    if (ws.value && (ws.value.readyState === WebSocket.OPEN || ws.value.readyState === WebSocket.CONNECTING)) {
      return
    }

    store.setConnectionStatus('connecting')

    try {
      ws.value = new WebSocket(WS_URL)

      ws.value.onopen = () => {
        console.log('[WebSocket] 已连接')
        isConnected.value = true
        reconnectAttempts.value = 0
        store.setConnectionStatus('connected')

        // 发送队列中缓存的消息
        while (messageQueue.value.length > 0) {
          const msg = messageQueue.value.shift()
          if (msg) sendRaw(msg)
        }
      }

      ws.value.onmessage = (event: MessageEvent) => {
        try {
          const data: ServerEvent = JSON.parse(event.data)
          handleServerEvent(data)
        } catch (e) {
          console.error('[WebSocket] 消息解析失败:', e)
        }
      }

      ws.value.onclose = (event: CloseEvent) => {
        console.log(`[WebSocket] 断开 (code=${event.code})`)
        isConnected.value = false
        store.setConnectionStatus('disconnected')

        // 自动重连（非正常关闭时）
        if (event.code !== 1000 && reconnectAttempts.value < MAX_RECONNECT_ATTEMPTS) {
          const delay = RECONNECT_BASE_DELAY_MS * Math.pow(2, reconnectAttempts.value)
          console.log(`[WebSocket] ${delay}ms 后尝试重连 (第${reconnectAttempts.value + 1}次)`)
          reconnectTimer = setTimeout(() => {
            reconnectAttempts.value++
            connect()
          }, delay)
        }
      }

      ws.value.onerror = (error: Event) => {
        console.error('[WebSocket] 连接错误:', error)
      }
    } catch (e) {
      console.error('[WebSocket] 创建连接失败:', e)
      store.setConnectionStatus('disconnected')
    }
  }

  function disconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    reconnectAttempts.value = MAX_RECONNECT_ATTEMPTS // 阻止重连
    if (ws.value) {
      ws.value.close(1000, '用户主动断开')
      ws.value = null
    }
    isConnected.value = false
    store.setConnectionStatus('disconnected')
  }

  function sendRaw(msg: OutgoingMessage) {
    if (ws.value && ws.value.readyState === WebSocket.OPEN) {
      ws.value.send(JSON.stringify(msg))
    } else {
      console.warn('[WebSocket] 未连接，消息加入队列')
      messageQueue.value.push(msg)
      if (!isConnected.value) {
        connect()
      }
    }
  }

  function sendMessage(message: string, formData: TravelFormData | null = null) {
    sendRaw({
      type: 'chat',
      message,
      form_data: formData,
    })
  }

  function handleServerEvent(event: ServerEvent) {
    switch (event.type) {
      case 'text_delta':
        if (event.content) {
          store.appendText(event.content)
        }
        break

      case 'thinking':
        store.addThinkingEntry({
          id: crypto.randomUUID(),
          type: 'phase',
          title: event.content || '',
          detail: event.stage || '',
          status: 'running',
          timestamp: Date.now(),
        })
        break

      case 'tool_start':
        store.addThinkingEntry({
          id: crypto.randomUUID(),
          type: 'tool_call',
          title: `🔧 ${event.tool_name || '未知工具'}`,
          detail: event.input ? JSON.stringify(event.input, null, 2).slice(0, 300) : '',
          status: 'running',
          timestamp: Date.now(),
          toolName: event.tool_name,
        })
        break

      case 'tool_end': {
        const status = event.is_error ? 'error' as const : 'done' as const
        // 更新最近一个匹配的工具调用思考块状态
        store.updateLastThinkingEntry(
          (e) => e.type === 'tool_call' && e.toolName === event.tool_name,
          status,
          event.output?.slice(0, 300) || ''
        )
        break
      }

      case 'agent_start':
        store.addThinkingEntry({
          id: crypto.randomUUID(),
          type: 'agent_spawn',
          title: `🤖 ${event.agent_name || '子Agent'}`,
          detail: event.task || event.tool_name || '',
          status: 'running',
          timestamp: Date.now(),
          toolName: event.agent_name,
        })
        break

      case 'agent_end': {
        const agentStatus = event.is_error ? 'error' as const : 'done' as const
        store.updateLastThinkingEntry(
          (e) => e.type === 'agent_spawn' && e.toolName === event.agent_name,
          agentStatus,
          event.summary || ''
        )
        break
      }

      case 'turn_complete':
        if (event.usage) {
          store.setUsage(event.usage)
        }
        // 将 running 状态的思考块标记为 done，但消息保持流式
        store.finalizeAllThinking()
        break

      case 'done':
        store.finalizeAllThinking()
        store.finalizeMessage()
        break

      case 'error':
        console.error('[WebSocket] 服务器错误:', event.message)
        store.addThinkingEntry({
          id: crypto.randomUUID(),
          type: 'phase',
          title: `❌ ${event.message || '未知错误'}`,
          detail: '',
          status: 'error',
          timestamp: Date.now(),
        })
        break

      case 'status':
        if (event.content === 'ready') {
          console.log('[WebSocket] AI 服务就绪')
        } else if (event.content === 'degraded') {
          console.warn('[WebSocket] AI 服务未就绪，使用降级模式')
          store.addThinkingEntry({
            id: crypto.randomUUID(),
            type: 'phase',
            title: '⚠️ AI 服务未就绪，当前为降级演示模式',
            detail: event.message || '',
            status: 'done',
            timestamp: Date.now(),
          })
        }
        break
    }
  }

  onUnmounted(() => {
    disconnect()
  })

  return {
    isConnected,
    connect,
    disconnect,
    sendMessage,
  }
}
