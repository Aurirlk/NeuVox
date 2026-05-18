# NeuVox - 多模态 Agent 语音服务基座

NeuVox 是一个专为"下一代智能体"打造的轻量级、去硬件绑定、纯净解耦的多模态语音服务基座。

它不仅仅是一个"语音转文字再转语音"的管道，而是一个具备**思考能力、记忆沉淀与工具调用**的 AI 神经中枢。

---

## 核心特性

- **意图路由** - 智能识别用户意图（天气/新闻/搜索/知识库/时间/闲聊），自动分发到对应处理器
- **Function Calling** - 原生支持工具调用，可扩展天气、新闻、搜索、知识库、时间等工具
- **AI CRM** - 后台异步提取用户画像（姓名、职业、偏好），存入数据库
- **服务工厂** - 工厂模式动态创建 ASR/LLM/TTS，支持运行时切换和自动回退
- **重试熔断** - 网络超时自动重试（指数退避），API 故障自动熔断
- **成本控制** - 追踪 DeepSeek API 调用的 token 消耗，支持日/月限额
- **向量数据库 RAG** - ChromaDB 向量检索 + SQLite 全文检索
- **VAD 流式输入** - Silero VAD 实时端点检测
- **意图打断** - TTS 播放时支持用户语音打断
- **情感分析** - 从语音/文本提取情绪标签
- **情绪 TTS** - 根据情绪调整语音语调
- **VLLM 视觉** - Qwen-VL 图片理解
- **摄像头流分析** - 实时视频帧处理
- **Redis 会话** - 分布式会话管理
- **Celery 消息队列** - 异步任务处理
- **Coze 工作流** - HTTP API 对接
- **统一配置** - YAML 配置文件，支持环境变量替换
- **个性化主题** - 支持多种颜色主题切换（深蓝/橙/绿/紫/红/青）

---

## 功能模块

### 已完成功能

| 功能 | 说明 | 状态 |
|------|------|------|
| 语音对话 | ASR → LLM → TTS 全链路 | ✅ |
| 文本对话 | 直接 LLM 对话 | ✅ |
| 意图路由 | 关键词+LLM 意图分类 | ✅ |
| Function Calling | 工具调用（天气/新闻/搜索/知识库/时间） | ✅ |
| AI CRM | 用户画像提取 | ✅ |
| 对话历史 | 滑动窗口多轮上下文 | ✅ |
| 成本控制 | Token 用量追踪、日/月限额 | ✅ |
| 服务工厂 | 动态创建、自动回退 | ✅ |
| 重试熔断 | 指数退避、熔断保护 | ✅ |
| 向量数据库 RAG | ChromaDB + SQLite | ✅ |
| Coze 工作流 | HTTP API 对接 | ✅ |
| 统一配置 | YAML 配置管理 | ✅ |
| VAD 流式输入 | Silero VAD 实时端点检测 | ✅ |
| 意图打断 | TTS 播放时支持语音打断 | ✅ |
| Redis 会话 | 分布式会话管理 | ✅ |
| 流式 TTS | 边合成边推送 | ✅ |
| VLLM 视觉 | Qwen-VL 图片理解 | ✅ |
| 情感分析 | 语音/文本情绪提取 | ✅ |
| 情绪 TTS | 根据情绪调整语调 | ✅ |
| 摄像头流分析 | 实时视频帧处理 | ✅ |
| 时间查询 | Python 硬编码获取时间 | ✅ |
| Celery 消息队列 | 异步任务处理 | ✅ |
| WebSocket SDK | 标准化前端对接 | ✅ |

### 待实现功能（企业级）

| 功能 | 说明 | 优先级 |
|------|------|--------|
| 多租户系统 | AppID/AppSecret 鉴权 | P3 |
| Token 隔离 | 每用户独立用量统计 | P3 |
| Flutter 移动端 | 移动 App 壳 | P3 |

---

## 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                      客户端 (Gradio UI)                      │
│                     http://localhost:7860                    │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTP / WebSocket
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI 后端服务                           │
│                    http://localhost:8000                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              IntentRouter (意图路由器)                │   │
│  │   关键词匹配 + LLM 分类 → 分发到对应处理器            │   │
│  └───────────────────────┬─────────────────────────────┘   │
│                          │                                  │
│    ┌─────────┬───────────┼───────────┬─────────┬─────────┐ │
│    ▼         ▼           ▼           ▼         ▼         ▼ │
│ ┌──────┐ ┌──────┐   ┌──────┐   ┌──────┐ ┌──────┐ ┌──────┐│
│ │天气   │ │新闻   │   │搜索   │   │知识库 │ │时间   │ │闲聊   ││
│ │Tool  │ │Tool  │   │Tool  │   │Tool  │ │Tool  │ │Chat  ││
│ └──┬───┘ └──┬───┘   └──┬───┘   └──┬───┘ └──┬───┘ └──┬───┘│
│    │        │          │          │         │         │    │
│    └────────┴──────────┴──────────┴─────────┴─────────┘    │
│                          │                                  │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              ServiceFactory (服务工厂)                │   │
│  │         动态创建 ASR/LLM/TTS，支持自动回退            │   │
│  └───────────────────────┬─────────────────────────────┘   │
│                          │                                  │
│         ┌────────────────┼────────────────┐                │
│         ▼                ▼                ▼                │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐          │
│  │ ASR      │     │ LLM      │     │ TTS      │          │
│  │ MiniMax  │     │ DeepSeek │     │ MiMo     │          │
│  └──────────┘     └──────────┘     └──────────┘          │
│                          │                                 │
│                          ▼                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              CRM Analyzer (异步后台)                 │   │
│  │         用户画像提取 → 意图记录 → 存入数据库          │   │
│  └───────────────────────┬─────────────────────────────┘   │
│                          │                                  │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              SQLite + ChromaDB                       │   │
│  │         users / interactions / user_profiles         │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 项目结构

```
NeuVox/
├── configs/                          # 配置文件
│   └── .config.yaml                 # 主配置（统一入口）
├── data/
│   └── Knowledge/                   # 知识库文件目录
├── docker/                           # Docker 部署
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── nginx.conf
│   └── 部署手册.md
├── sdk/
│   └── neuvox-sdk.js                # WebSocket JS SDK
├── app/
│   ├── services/
│   │   ├── intent/                  # 意图路由器
│   │   ├── coze/                    # Coze 客户端
│   │   ├── vllm/                    # 视觉大模型
│   │   ├── emotion/                 # 情感分析
│   │   ├── vad/                     # VAD 语音检测
│   │   ├── session/                 # Redis 会话管理
│   │   ├── vision/                  # 摄像头流分析
│   │   ├── asr/                     # ASR 服务
│   │   ├── llm/                     # LLM 服务
│   │   └── tts/                     # TTS 服务
│   ├── tasks/                       # Celery 任务队列
│   ├── tools/                       # Function Calling 工具
│   │   ├── weather_tool.py          # 天气工具
│   │   ├── news_tool.py             # 新闻工具
│   │   ├── search_tool.py           # 搜索工具
│   │   ├── knowledge_tool.py        # 知识库工具
│   │   └── time_tool.py             # 时间工具
│   ├── knowledge/                   # 知识库服务
│   ├── crm/                         # CRM 分析
│   ├── plugins/                     # 插件
│   ├── routers/                     # API 路由
│   └── utils/                       # 工具函数
├── tests/                           # 测试
├── docs/                            # 文档
├── fastAPI.py                       # 主应用
├── main.py                          # 启动入口
├── voice_chat_ui.py                 # Gradio UI
└── requirements.txt                 # Python 依赖
```

---

## 快速开始

### 1. 环境准备

```bash
conda create -n xiaozhi python=3.10
conda activate xiaozhi
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入 API Keys
```

必填项：
- `DEEPSEEK_API_KEY` - DeepSeek API 密钥
- `MIMO_TTS_API_KEY` - MiMo TTS API 密钥

### 3. 启动服务

```bash
# 激活环境
conda activate xiaozhi

# 启动后端服务（终端1）
python main.py

# 启动 Gradio UI（终端2）
python voice_chat_ui.py
```

> **注意**: 启动 Gradio UI 前请确保已关闭系统代理（如 Clash），否则会报 502 错误。

### 4. 访问地址

| 服务 | 地址 |
|------|------|
| API 文档 | http://localhost:8000/docs |
| Gradio UI | http://localhost:7860 |
| WebSocket | ws://localhost:8000/ws/v1/chat/stream |

---

## API 接口

### 核心接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/ask` | POST | 统一问答接口（文本/语音） |
| `/api/v1/ask_stream` | POST | 流式问答（SSE） |
| `/api/v1/sessions/{id}` | DELETE | 清空会话 |

### 意图统计

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/crm/intent/stats` | GET | 意图统计 |
| `/api/v1/crm/intent/{type}` | GET | 按意图查询 |

### CRM 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/crm/users` | GET/POST | 用户管理 |
| `/api/v1/crm/users/{id}/profile` | GET/PUT | 用户画像 |
| `/api/v1/crm/interactions` | GET | 交互记录 |
| `/api/v1/crm/stats` | GET | 统计信息 |

---

## 使用示例

### 文本问答

```bash
curl -X POST http://localhost:8000/api/v1/ask \
  -F "session_id=test_001" \
  -F "text=北京天气怎么样" \
  -F "need_tts=false"
```

### 意图统计

```bash
curl http://localhost:8000/api/v1/crm/intent/stats
```

---

## 测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行意图测试
pytest tests/test_intent/ -v

# 运行工具测试
pytest tests/test_tools/ -v
```

---

## 模型配置

| 类型 | 主选 | 备选 |
|------|------|------|
| LLM | DeepSeek v4 flash | MiniMax |
| TTS | MiMo 2.5 TTS | MiniMax Speech-01 |
| ASR | MiniMax ASR | - |

---

## 已完成功能清单

### Phase 1-7

| Phase | 内容 | 状态 |
|-------|------|------|
| Phase 1 | API 配置管理 (configs/*.yaml) | ✅ |
| Phase 2 | 意图路由器 (intent classifier + router) | ✅ |
| Phase 3 | Function Calling 工具链 (tools/) | ✅ |
| Phase 4 | 知识库 RAG + ChromaDB | ✅ |
| Phase 5 | Coze 工作流对接 | ✅ |
| Phase 6 | CRM 增强 (意图字段) | ✅ |
| Phase 7 | 测试与文档 | ✅ |

### P0-P2 功能

| 功能 | 状态 | 说明 |
|------|------|------|
| VAD 流式输入 | ✅ | Silero VAD 集成 |
| 意图打断机制 | ✅ | WebSocket 双工打断 |
| 向量数据库 RAG | ✅ | ChromaDB 向量检索 |
| Docker 部署 | ✅ | Dockerfile + docker-compose |
| Redis 会话管理 | ✅ | 替换内存存储 |
| 流式 TTS | ✅ | 边合成边推送 |
| VLLM 视觉大模型 | ✅ | Qwen-VL 图片理解 |
| 情感分析 | ✅ | 语音/文本情绪提取 |
| 情绪 TTS | ✅ | 根据情绪调整语调 |
| 摄像头流分析 | ✅ | 实时视频帧处理 |
| 时间查询工具 | ✅ | Python 硬编码获取时间 |
| 消息队列解耦 | ✅ | Celery + Redis |
| WebSocket JS SDK | ✅ | 标准化前端对接 |

---

## 技术债务

| # | 问题 | 状态 | 说明 |
|---|------|------|------|
| 1 | 无 API 鉴权 | ❌ 未解决 | 任何人都能调用接口 |
| 2 | 无 MQTT 支持 | ❌ 未解决 | 缺少 IoT 通信协议 |
| 3 | 无 IoT 控制 | ❌ 未解决 | 缺少智能设备控制 |
| 4 | 无管理后台 | ❌ 未实现 | 缺少 Web 管理界面 |
| 5 | 无移动端 | ❌ 未实现 | 缺少移动管理端 |

---

## 未来优化计划

### 阶段一：通信协议扩展（1-2周）

| 任务 | 说明 | 优先级 |
|------|------|--------|
| **MQTT 支持** | 添加 MQTT 协议支持，对接 IoT 设备 | P1 |
| **IoT 控制** | 智能设备控制协议（灯光、开关等） | P2 |

### 阶段二：前端与管理（2-3周）

| 任务 | 说明 | 优先级 |
|------|------|--------|
| **管理后台** | Vue.js Web 管理界面 | P1 |
| **移动端** | uni-app 移动管理端 | P2 |
| **API 鉴权** | AppID/AppSecret 认证 | P1 |

---

## License

MIT
