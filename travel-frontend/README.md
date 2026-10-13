# 🧳 智能旅行助手

基于 OpenHarness 多 Agent 框架的智能出行规划 Web 应用。支持酒店、机票、火车票、路线、景点门票一站式查询与推荐。

## 技术栈

- **前端**：Vue 3 + TypeScript + Pinia + Vite
- **后端**：Python FastAPI + WebSocket
- **AI 引擎**：OpenHarness（多 Agent 协调，集成途牛/12306/高德 MCP 服务）

## 快速开始

### 1. 后端

```bash
cd backend
# 安装依赖（需要 Python 3.11+）
uv pip install -r requirements.txt
# 启动服务
uv run python main.py
```

服务默认运行在 `http://localhost:8000`。

### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

浏览器打开 `http://localhost:5173`。

## 环境变量

后端通过 `.env` 文件或环境变量配置，参见 `backend/.env.example`。

## 项目结构

```
travel-frontend/
├── backend/
│   ├── main.py              # FastAPI 入口 + WebSocket
│   ├── harness_service.py   # OpenHarness 运行时管理
│   └── event_bridge.py      # 事件转换
└── frontend/
    └── src/
        ├── components/       # Vue 组件
        ├── composables/      # 组合式函数
        ├── stores/           # Pinia 状态
        └── types/            # TypeScript 类型
```
