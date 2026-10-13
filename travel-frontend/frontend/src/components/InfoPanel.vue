<script setup lang="ts">
/**
 * 右侧信息面板：出行信息表单 + 历史记录。
 */

import { ref, reactive, computed } from 'vue'
import { useChatStore } from '@/stores/chat'
import type { TravelFormData } from '@/types'

const emit = defineEmits<{
  send: [payload: { message: string; formData: TravelFormData }]
}>()

const store = useChatStore()

// ========== 表单状态 ==========

const form = reactive<TravelFormData>({
  departure: '',
  destination: '',
  date: '',
  days: '',
  people: '',
  budget: '',
  preference: 'balanced',
  hotelBrand: '',
  hotelLocation: '',
})

/** 表单是否填写了必要信息 */
const canPlan = computed(() =>
  form.departure.trim().length > 0 &&
  form.destination.trim().length > 0 &&
  !store.isStreaming
)

/** 偏好选项 */
const preferenceOptions = [
  { value: 'balanced', label: '综合推荐' },
  { value: 'comfort', label: '舒适享受' },
  { value: 'cheap', label: '经济实惠' },
  { value: 'fast', label: '最快到达' },
  { value: 'unlimited', label: '不限预算' },
]

// ========== 历史记录 ==========

const showHistory = ref(false)

function loadHistoryForm(item: typeof store.history[number]) {
  Object.assign(form, item.formData)
  showHistory.value = false
}

function deleteHistoryItem(id: string) {
  store.history = store.history.filter((h) => h.id !== id)
  localStorage.setItem('travel_history', JSON.stringify(store.history))
}

// ========== 提交 ==========

function handlePlan() {
  if (!canPlan.value) return

  const formData: TravelFormData = { ...form }

  // 构建自然语言提示
  const parts: string[] = []
  parts.push(`从${form.departure}到${form.destination}`)
  if (form.date) parts.push(`${form.date}出发`)
  if (form.days) parts.push(`玩${form.days}天`)
  if (form.people) parts.push(`${form.people}人`)
  if (form.budget) parts.push(`预算${form.budget}元`)

  const prefLabel = preferenceOptions.find((o) => o.value === form.preference)?.label || ''
  if (prefLabel && form.preference !== 'balanced') {
    parts.push(`偏好${prefLabel}`)
  }
  if (form.hotelBrand) parts.push(`住${form.hotelBrand}`)
  if (form.hotelLocation.trim()) parts.push(`酒店位置要求：${form.hotelLocation.trim()}`)

  const message = parts.join('，') + '。请帮我规划行程。'

  emit('send', { message, formData })
}
</script>

<template>
  <div class="info-panel">
    <!-- 出行信息表单 -->
    <div class="panel-section">
      <div class="section-header">
        <span class="section-icon">📝</span>
        <h3>出行信息</h3>
      </div>
      <p class="section-desc">填写信息后点击规划，或直接在左侧对话框输入需求</p>

      <div class="form-grid">
        <!-- 出发城市（必填） -->
        <div class="form-group">
          <label class="form-label">
            出发城市 <span class="required">*</span>
          </label>
          <input
            v-model="form.departure"
            type="text"
            class="form-input"
            placeholder="如：北京"
          />
        </div>

        <!-- 目的城市（必填） -->
        <div class="form-group">
          <label class="form-label">
            目的城市 <span class="required">*</span>
          </label>
          <input
            v-model="form.destination"
            type="text"
            class="form-input"
            placeholder="如：杭州"
          />
        </div>

        <!-- 出发日期 -->
        <div class="form-group">
          <label class="form-label">出发日期</label>
          <input
            v-model="form.date"
            type="date"
            class="form-input"
          />
        </div>

        <!-- 出行天数 -->
        <div class="form-group">
          <label class="form-label">出行天数</label>
          <input
            v-model="form.days"
            type="number"
            class="form-input"
            placeholder="如：3"
            min="1"
            max="30"
          />
        </div>

        <!-- 出行人数 -->
        <div class="form-group">
          <label class="form-label">出行人数</label>
          <input
            v-model="form.people"
            type="number"
            class="form-input"
            placeholder="如：2"
            min="1"
            max="20"
          />
        </div>

        <!-- 预算范围 -->
        <div class="form-group">
          <label class="form-label">预算范围（元）</label>
          <input
            v-model="form.budget"
            type="number"
            class="form-input"
            placeholder="如：5000"
            min="0"
            step="500"
          />
        </div>

        <!-- 偏好类型 -->
        <div class="form-group form-group-full">
          <label class="form-label">偏好类型</label>
          <div class="preference-options">
            <button
              v-for="opt in preferenceOptions"
              :key="opt.value"
              class="pref-btn"
              :class="{ 'pref-active': form.preference === opt.value }"
              @click="form.preference = opt.value"
            >
              {{ opt.label }}
            </button>
          </div>
        </div>

        <!-- 酒店品牌 -->
        <div class="form-group form-group-full">
          <label class="form-label">偏好酒店品牌</label>
          <input
            v-model="form.hotelBrand"
            type="text"
            class="form-input"
            placeholder="如：希尔顿、亚朵（可选）"
          />
        </div>

        <!-- 酒店位置偏好 -->
        <div class="form-group form-group-full">
          <label class="form-label">酒店位置偏好</label>
          <input
            v-model="form.hotelLocation"
            type="text"
            class="form-input"
            placeholder="如：近1号线地铁站、近西湖商圈、近杭州东站（可选）"
          />
        </div>
      </div>

      <!-- 提交按钮 -->
      <button
        class="plan-btn"
        :disabled="!canPlan"
        @click="handlePlan"
      >
        <span v-if="store.isStreaming" class="btn-spinner">⏳</span>
        <span v-else>🚀</span>
        {{ store.isStreaming ? '生成中...' : '开始规划' }}
      </button>
    </div>

    <!-- 历史记录 -->
    <div class="panel-section">
      <div class="section-header clickable" @click="showHistory = !showHistory">
        <span class="section-icon">📜</span>
        <h3>历史记录</h3>
        <span class="section-arrow">{{ showHistory ? '▲' : '▼' }}</span>
      </div>

      <div v-show="showHistory" class="history-list">
        <div v-if="store.history.length === 0" class="history-empty">
          暂无历史记录
        </div>
        <div
          v-for="item in store.history"
          :key="item.id"
          class="history-item"
          @click="loadHistoryForm(item)"
        >
          <div class="history-title">{{ item.title }}</div>
          <div class="history-time">
            {{ new Date(item.timestamp).toLocaleDateString('zh-CN') }}
          </div>
          <button
            class="history-delete"
            @click.stop="deleteHistoryItem(item.id)"
            title="删除"
          >
            ×
          </button>
        </div>
        <button
          v-if="store.history.length > 0"
          class="clear-btn"
          @click="store.clearHistory()"
        >
          清空历史
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.info-panel {
  padding: 20px;
}

.panel-section {
  margin-bottom: 20px;
}

.panel-section + .panel-section {
  border-top: 1px solid var(--border);
  padding-top: 20px;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.section-header.clickable {
  cursor: pointer;
  user-select: none;
}

.section-header.clickable:hover {
  opacity: 0.8;
}

.section-icon {
  font-size: 16px;
}

.section-header h3 {
  font-size: 15px;
  font-weight: 700;
  color: var(--text);
}

.section-arrow {
  margin-left: auto;
  font-size: 10px;
  color: var(--text-secondary);
}

.section-desc {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 14px;
  line-height: 1.4;
}

/* ========== 表单 ========== */
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.form-group-full {
  grid-column: 1 / -1;
}

.form-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}

.required {
  color: var(--error);
}

.form-input {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 8px 10px;
  font-size: 13px;
  font-family: inherit;
  color: var(--text);
  background: var(--bg);
  transition: border-color 0.2s;
  outline: none;
}

.form-input:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 2px rgba(79, 110, 247, 0.1);
}

.form-input::placeholder {
  color: #c4c7d0;
}

/* ========== 偏好选择 ========== */
.preference-options {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.pref-btn {
  padding: 5px 12px;
  border: 1px solid var(--border);
  border-radius: 20px;
  font-size: 12px;
  color: var(--text-secondary);
  background: var(--bg);
  cursor: pointer;
  transition: all 0.15s;
}

.pref-btn:hover {
  border-color: var(--primary);
  color: var(--primary);
}

.pref-active {
  background: var(--primary);
  color: white;
  border-color: var(--primary);
}

/* ========== 提交按钮 ========== */
.plan-btn {
  width: 100%;
  margin-top: 16px;
  padding: 12px 0;
  border: none;
  border-radius: var(--radius);
  background: linear-gradient(135deg, #4f6ef7, #6c8cff);
  color: white;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: all 0.2s;
  box-shadow: 0 2px 8px rgba(79, 110, 247, 0.3);
}

.plan-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 16px rgba(79, 110, 247, 0.4);
}

.plan-btn:disabled {
  background: #c4c7d0;
  box-shadow: none;
  cursor: not-allowed;
}

.btn-spinner {
  animation: spin 2s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* ========== 历史记录 ========== */
.history-list {
  margin-top: 10px;
}

.history-empty {
  text-align: center;
  color: var(--text-secondary);
  font-size: 13px;
  padding: 20px 0;
}

.history-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background 0.15s;
  position: relative;
}

.history-item:hover {
  background: var(--bg);
}

.history-title {
  flex: 1;
  font-size: 13px;
  color: var(--text);
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-time {
  font-size: 11px;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.history-delete {
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}

.history-delete:hover {
  background: #fee;
  color: var(--error);
}

.clear-btn {
  width: 100%;
  margin-top: 8px;
  padding: 6px 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg);
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}

.clear-btn:hover {
  color: var(--error);
  border-color: var(--error);
}
</style>
