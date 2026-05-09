# 小智语音交互服务 (XiaoZhi)

基于 DeepSeek v4 flash + MiMo 2.5 TTS 的智能语音交互后端服务，集成 AI CRM 功能。

---

## 一、功能描述

### 1.1 核心功能

| 功能模块 | 说明 |
|---------|------|
| **语音对话** | 用户通过麦克风输入语音，系统自动 ASR 识别 → LLM 生成回复 → TTS 合成语音返回 |
| **文本对话** | 用户直接输入文字，系统调用 LLM 生成回复并可选合成语音 |
| **流式交互** | WebSocket 双工通信，支持边识别、边思考、边合成的流式响应 |
| **AI CRM** | 后台异步分析对话内容，自动提取用户姓名、职业、偏好等画像信息并存入数据库 |
| **对话历史** | 持久化存储用户的多轮对话记录，支持上下文理解 |
| **成本控制** | 追踪 DeepSeek API 调用的 token 消耗，支持日/月限额管理 |
| **服务工厂** | 工厂模式动态创建 ASR/LLM/TTS 服务实例，支持运行时切换模型 |
| **重试熔断** | 网络超时自动重试（指数退避），API 连续失败自动熔断保护 |
| **多模型备选** | DeepSeek 为主、MiniMax 为备，主模型故障自动回退 |

### 1.2 语音对话流程

```
用户语音 → ASR(语音识别) → LLM(大模型思考) → TTS(语音合成) → 播放回复
                                    ↓ (异步后台)
                              CRM(用户画像提取) → 数据库存储
```

### 1.3 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                    客户端 (Gradio UI / 浏览器)            │
│                   http://localhost:7860                  │
└─────────────────────┬───────────────────────────────────┘
                      │ HTTP / WebSocket
                      ▼
┌─────────────────────────────────────────────────────────┐
│                  FastAPI 后端服务                          │
│                  http://localhost:8000                  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │  聊天路由     │  │  CRM 路由    │  │  WebSocket  │    │
│  │  chat.py    │  │  crm.py     │  │  ws_chat.py │    │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘    │
│         │                │                │            │
│         ▼                ▼                ▼            │
│  ┌─────────────────────────────────────────────────┐   │
│  │              ServiceFactory (服务工厂)             │   │
│  │         动态创建 ASR/LLM/TTS 服务实例              │   │
│  └─────┬───────────────┬───────────────┬───────────┘   │
│        │               │               │               │
│        ▼               ▼               ▼               │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐          │
│  │ ASR 服务  │   │ LLM 服务  │   │ TTS 服务  │          │
│  │ MiniMax  │   │ DeepSeek │   │ MiMo     │          │
│  └──────────┘   └──────────┘   └──────────┘          │
│                       │                               │
│                       ▼                               │
│              ┌──────────────┐                         │
│              │  CRM Analyzer │                         │
│              │  (异步分析)    │                         │
│              └──────┬───────┘                         │
│                     ▼                                 │
│              ┌──────────────┐                         │
│              │   SQLite /   │                         │
│              │  PostgreSQL  │                         │
│              └──────────────┘                         │
└─────────────────────────────────────────────────────────┘
```

---

## 二、核心源代码实现

### 2.1 服务工厂模式 (`app/services/factory.py`)

核心设计：通过抽象基类定义统一接口，工厂类负责创建实例，支持自动回退。

```python
class ServiceFactory:
    """服务工厂 - 统一创建和管理服务实例"""
    
    @staticmethod
    def create_llm(provider: str = "auto") -> LLMBase:
        if provider == "auto":
            return ServiceFactory._create_llm_auto()
        if provider == "deepseek":
            from app.services.llm.deepseek_llm import DeepSeekLLM
            return DeepSeekLLM()
        if provider == "minimax":
            from app.services.llm.minimax_llm import MiniMaxLLM
            return MiniMaxLLM()
        raise ValueError(f"不支持的 LLM 提供商: {provider}")
    
    @staticmethod
    def _create_llm_auto() -> LLMBase:
        """自动选择（优先 DeepSeek，失败回退 MiniMax）"""
        if settings.DEEPSEEK_API_KEY:
            return DeepSeekLLM()
        if settings.MINIMAX_API_KEY:
            return MiniMaxLLM()
        raise ValueError("未配置任何 LLM API Key")
```

### 2.2 语音对话全链路 (`app/routers/chat.py`)

ASR → LLM → TTS 三步串联，并异步触发 CRM 分析：

```python
@router.post("/chat/audio", response_model=VoiceChatResponse)
async def audio_chat(file: UploadFile = File(...)):
    # 1. ASR: 语音转文本
    asr_service = ServiceFactory.create_asr()
    user_text = await asr_service.transcribe(temp_path)
    
    # 2. LLM: 生成回复
    llm_service = ServiceFactory.create_llm(llm_provider)
    reply = await llm_service.chat(user_text)
    
    # 3. TTS: 文本转语音
    tts_service = ServiceFactory.create_tts(tts_provider)
    audio_path = await tts_service.synthesize(reply)
    
    # 4. 异步触发 CRM 分析（不阻塞响应）
    asyncio.create_task(
        analyze_interaction_background(interaction_id, user_id, user_text, reply)
    )
    
    return VoiceChatResponse(success=True, text=user_text, reply=reply, ...)
```

### 2.3 重试与熔断器 (`app/utils/retry.py`)

指数退避重试 + 熔断器保护：

```python
def retry(max_retries=3, delay=1.0, backoff_factor=2.0, exceptions=(Exception,)):
    """重试装饰器 - 指数退避策略"""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            current_delay = delay
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    if attempt < max_retries:
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff_factor  # 1s → 2s → 4s
                    else:
                        raise
        return async_wrapper
    return decorator

class CircuitBreaker:
    """熔断器 - 连续失败后自动断开"""
    def __init__(self, failure_threshold=5, recovery_timeout=60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
    
    def record_failure(self):
        self._failure_count += 1
        if self._failure_count >= self.failure_threshold:
            self._state = "open"  # 熔断开启，拒绝请求
```

### 2.4 AI CRM 信息提取 (`app/crm/analyzer.py`)

利用 LLM 从对话中自动提取用户画像：

```python
CRM_EXTRACTION_PROMPT = """你是一个专业的用户信息分析助手。请从以下对话中提取用户特征。

对话内容：
{conversation}

请以 JSON 格式返回：
{{
    "name": "姓名", "gender": "性别", "occupation": "职业",
    "city": "城市", "preferences": {{"hobbies": ["爱好"]}},
    "intent": "意向", "tags": ["标签"]
}}"""

class CRMAnalyzer:
    async def analyze_and_save(self, db, interaction_id, user_id, conversation):
        # 1. 调用 LLM 提取用户信息
        user_info = await self.extract_user_info(conversation)
        
        # 2. 合并到用户画像（UPSERT 语义）
        profile = self._merge_profile(profile, user_info)
        
        # 3. 存入数据库
        await db.commit()
```

### 2.5 WebSocket 流式对话 (`app/routers/ws_chat.py`)

双工通信协议设计：

```python
# 客户端 → 服务端消息类型
{"type": "text", "content": "你好"}        # 文本消息
{"type": "audio_start"}                    # 开始录音
{"type": "audio_chunk", "data": "..."}     # 音频数据块
{"type": "audio_end"}                      # 结束录音
{"type": "ping"}                           # 心跳

# 服务端 → 客户端消息类型
{"type": "llm_token", "token": "你好"}     # LLM 流式 token
{"type": "llm_done", "text": "完整回复"}    # LLM 回复完成
{"type": "tts_done", "audio_path": "..."}  # TTS 合成完成
{"type": "asr_final", "text": "识别结果"}   # ASR 最终结果
```

### 2.6 对话历史管理 (`app/services/chat_history.py`)

多轮对话上下文获取：

```python
async def get_context_for_llm(self, db, conversation_id, max_turns=10):
    """获取用于 LLM 的对话上下文（最近 N 轮）"""
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conversation_id)
        .where(ChatMessage.role.in_(["user", "assistant"]))
        .order_by(desc(ChatMessage.created_at))
        .limit(max_turns * 2)
    )
    messages = list(reversed(result.scalars().all()))
    return [{"role": msg.role, "content": msg.content} for msg in messages]
```

### 2.7 成本追踪 (`app/services/cost_tracker.py`)

DeepSeek API 调用成本监控：

```python
class CostTracker:
    PRICING = {
        "deepseek-v4-flash": {"input": 0.001, "output": 0.002}  # 元/千token
    }
    
    def calculate_cost(self, model, prompt_tokens, completion_tokens):
        pricing = self.PRICING.get(model, self.PRICING["deepseek-v4-flash"])
        return (prompt_tokens / 1000 * pricing["input"] + 
                completion_tokens / 1000 * pricing["output"])
    
    async def check_budget(self, db):
        daily_cost = await self.get_daily_cost(db)
        monthly_cost = await self.get_monthly_cost(db)
        if daily_cost >= self.daily_limit:
            return {"allowed": False, "message": "已达日限额"}
```

---

## 三、项目结构

```
XiaoZhi/
├── app/
│   ├── config.py                # 配置模块
│   ├── database/                # 数据库配置 (SQLAlchemy async)
│   ├── models/
│   │   ├── schemas.py           # Pydantic 数据模型
│   │   └── crm_models.py        # CRM ORM 模型 (User/Interaction/Conversation)
│   ├── routers/
│   │   ├── chat.py              # 聊天路由 (HTTP)
│   │   ├── crm.py               # CRM 路由
│   │   └── ws_chat.py           # WebSocket 路由
│   ├── services/
│   │   ├── factory.py           # 服务工厂 (核心)
│   │   ├── cost_tracker.py      # 成本追踪
│   │   ├── chat_history.py      # 对话历史管理
│   │   ├── base/                # 抽象基类 (asr/llm/tts_base)
│   │   ├── asr/                 # ASR 实现 (minimax)
│   │   ├── llm/                 # LLM 实现 (deepseek/minimax)
│   │   └── tts/                 # TTS 实现 (mimo/minimax)
│   ├── crm/
│   │   └── analyzer.py          # CRM 分析服务
│   ├── utils/
│   │   ├── logger.py            # 日志配置
│   │   └── retry.py             # 重试/熔断器
│   └── ws/
│       └── manager.py           # WebSocket 连接管理
├── tests/                       # 单元测试/集成测试/端到端测试
├── main.py                      # FastAPI 主入口
├── voice_chat_ui.py             # Gradio UI 界面
├── nginx.conf                   # Nginx 反向代理配置
├── Dockerfile                   # Docker 构建文件
├── docker-compose.yml           # Docker Compose 编排
├── requirements.txt             # Python 依赖
└── .env                         # 环境变量 (不入库)
```

---

## 四、快速开始

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
# 后端服务
python main.py

# Gradio UI (可选，需关闭系统代理)
python voice_chat_ui.py
```

### 4. 访问地址

| 服务 | 地址 |
|------|------|
| Swagger API 文档 | http://localhost:8000/docs |
| Gradio UI | http://localhost:7860 |
| WebSocket | ws://localhost:8000/ws/v1/chat/stream |

---

## 五、API 接口

### 核心接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/ask` | POST | 统一问答接口（文本/语音） |
| `/api/v1/ask_stream` | POST | 流式问答接口（SSE） |
| `/api/v1/assets/audio/{filename}` | GET | 获取合成音频文件 |
| `/api/v1/sessions/{session_id}` | DELETE | 清空会话历史 |

### 配置接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/` | GET | API 信息 |
| `/docs` | GET | Swagger 文档 |
| `/api/v1/health` | GET | 健康检查 |
| `/api/v1/providers` | GET | 可用提供商 |
| `/api/v1/voices` | GET | 音色列表 |

### CRM 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/crm/users` | GET | 用户列表 |
| `/api/v1/crm/users/{id}` | GET | 用户详情 |
| `/api/v1/crm/users/{id}/profile` | GET | 用户画像 |
| `/api/v1/crm/interactions` | GET | 交互记录 |
| `/api/v1/crm/stats` | GET | 统计信息 |

---

## 六、使用示例

### 文本问答

```bash
curl -X POST http://localhost:8000/api/v1/ask \
  -F "session_id=test_001" \
  -F "text=你好，请介绍一下你自己" \
  -F "need_tts=false"
```

响应：
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "session_id": "test_001",
    "recognized_text": null,
    "reply_text": "你好！我是智能语音助手...",
    "audio_url": "/api/v1/assets/audio/tts_xxx.wav",
    "processing_time_ms": 1250
  }
}
```

### 语音问答

```bash
curl -X POST http://localhost:8000/api/v1/ask \
  -F "session_id=test_001" \
  -F "audio_file=@recording.wav" \
  -F "need_tts=true"
```

### 流式问答

```javascript
const response = await fetch("/api/v1/ask_stream", {
  method: "POST",
  body: new URLSearchParams({
    session_id: "test_001",
    text: "你好"
  })
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  
  const text = decoder.decode(value);
  const lines = text.split("\n");
  
  for (const line of lines) {
    if (line.startsWith("data: ")) {
      const data = JSON.parse(line.slice(6));
      if (data.type === "token") {
        process.stdout.write(data.content);
      }
      if (data.type === "done") {
        console.log("\n语音文件:", data.audio_url);
      }
    }
  }
}
```

---

## 七、模型配置

| 类型 | 主选 | 备选 |
|------|------|------|
| LLM | DeepSeek v4 flash | MiniMax |
| TTS | MiMo 2.5 TTS | MiniMax Speech-01 |
| ASR | MiniMax ASR | - |

---

## 八、测试

```bash
# 运行单元测试
pytest tests/test_services/ -v

# 运行所有测试
pytest tests/ -v

# 压力测试
pip install locust
locust -f tests/locustfile.py --host=http://localhost:8000
# 访问 http://localhost:8089
```

---

## 九、部署

详见 [部署手册.md](部署手册.md)

```bash
# Docker 部署
docker-compose up -d

# 查看日志
docker-compose logs -f
```

---

## License

MIT
