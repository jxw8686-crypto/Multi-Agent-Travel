/**
 * 旅行助手前端类型定义
 */

// ========== 表单数据 ==========

export interface TravelFormData {
  departure: string    // 出发城市
  destination: string  // 目的城市
  date: string         // 出发日期 (yyyy-MM-dd)
  days: string         // 出行天数
  people: string       // 出行人数
  budget: string       // 预算范围（元）
  preference: string   // 偏好类型: comfort | cheap | fast | unlimited | balanced
  hotelBrand: string   // 偏好酒店品牌
  hotelLocation: string // 酒店位置偏好，自由文本，如"近1号线地铁站"
}

// ========== 发送消息 ==========

export interface OutgoingMessage {
  type: 'chat'
  message: string
  form_data: TravelFormData | null
}

// ========== 接收事件 ==========

export type ServerEventType =
  | 'text_delta'
  | 'thinking'
  | 'tool_start'
  | 'tool_end'
  | 'agent_start'
  | 'agent_end'
  | 'turn_complete'
  | 'done'
  | 'error'
  | 'status'

export interface ServerEvent {
  type: ServerEventType

  // text_delta
  content?: string
  turn?: number

  // thinking
  stage?: string
  agent_name?: string

  // tool_start / tool_end
  tool_name?: string
  input?: Record<string, unknown>
  output?: string
  is_error?: boolean

  // agent_start
  task?: string

  // agent_end
  summary?: string
  status?: 'running' | 'done' | 'error'

  // turn_complete
  usage?: {
    input_tokens: number
    output_tokens: number
  }

  // error
  message?: string
  recoverable?: boolean
}

// ========== 思考块 ==========

export interface ThinkingEntry {
  id: string
  type: 'tool_call' | 'agent_spawn' | 'phase'
  title: string
  detail: string
  status: 'running' | 'done' | 'error'
  timestamp: number
  toolName?: string
}

// ========== 消息 ==========

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  thinkingEntries: ThinkingEntry[]
  usage: { input_tokens: number; output_tokens: number } | null
  timestamp: number
  isStreaming: boolean  // 助手消息是否仍在接收中
}

// ========== 历史记录 ==========

export interface HistoryItem {
  id: string
  title: string
  formData: TravelFormData
  timestamp: number
}
