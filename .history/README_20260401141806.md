# 学生个性化发展教育智能体系统

基于 LangGraph 构建的多 Agent 教育智能体，面向书院学生提供个性化政策咨询、资源推荐与主动推送服务。系统融合学生兴趣画像、书院政策知识图谱与大语言模型推理能力，实现"问完即办"的智能化学生服务体验。

---

## 系统架构概览

### 整体技术架构

### Agent 逻辑架构

![Agent 逻辑架构](asserts/image-1.png)

系统采用分层 Agent 架构，分为认证层、画像层、调度层与执行层四个阶段：

各层详细说明：

- **AuthAgent**：入口节点，验证用户学号/手机号。验证失败时调用 `interrupt()` 挂起图等待 human input，验证成功后流转至 ProfileAgent。
- **ProfileAgent**：加载用户画像，将画像标签写入 Redis 上下文记忆，为后续所有 Agent 提供个性化背景。
- **Supervisor**：核心调度节点，负责意图分类（政策咨询 / 推荐 / 推送 / 管理）、路由到对应 subagent，以及每轮结束后的 `save_memory` 更新。
- **DialogueAgent**：主对话 subagent，调用政策知识图谱（Neo4j）与向量检索（ES），结合用户画像由 LLM 生成个性化回答。
- **RecommendAgent**：个性化推荐 subagent，调用推荐引擎与画像引擎，生成书籍/活动/奖学金推荐列表。
- **PushAgent**：主动推送 subagent，支持对话触发与定时任务两种模式。

---

## 目录结构

```
project/
├── README.md
├── requirements.txt                  # 项目依赖
│
├── agent/                            # 所有 Agent 与核心图逻辑
│   ├── graph.py                      # LangGraph 主图定义（节点注册、边连接、条件路由）
│   ├── memory.py                     # Redis 记忆管理（上下文读写、画像缓存）
│   ├── states.py                     # 全局 State 类型定义（AgentState、各阶段状态）
│   │
│   ├── auth/                         # 认证层
│   │   ├── __init__.py
│   │   ├── verify_info.py            # AuthAgent 节点：身份验证逻辑，失败时 interrupt()
│   │   └── human_input.py            # Human-in-the-loop 节点：处理用户补充输入
│   │
│   ├── profile/                      # 画像层
│   │   ├── __init__.py
│   │   ├── ProfileAgent.py           # ProfileAgent 节点：加载画像并写入记忆
│   │   └── tools.py                  # 画像相关工具（get_profile、update_profile，当前为模拟）
│   │
│   ├── supervisor/                   # 调度层
│   │   ├── __init__.py
│   │   ├── Supervisor.py             # Supervisor 节点：意图分类与路由决策
│   │   └── tools.py                  # 调度相关工具（save_memory、intent_classify，当前为模拟）
│   │
│   ├── dialogue/                     # 对话推理执行层
│   │   ├── __init__.py
│   │   ├── DialogueAgent.py          # DialogueAgent 节点：LLM 推理 + 政策库查询
│   │   └── tools.py                  # 对话工具（query_neo4j、query_es，当前为模拟）
│   │
│   ├── recommend/                    # 推荐执行层
│   │   ├── __init__.py
│   │   ├── RecommendAgent.py         # RecommendAgent 节点：个性化推荐生成
│   │   └── tools.py                  # 推荐工具（recommend_engine、profile_engine，当前为模拟）
│   │
│   └── push/                         # 推送执行层
│       ├── __init__.py
│       ├── PushAgent.py              # PushAgent 节点：主动推送服务（对话触发/定时触发）
│       └── tools.py                  # 推送工具（send_push、query_push_list，当前为模拟）
│
└── common/                           # 公共模块
    ├── __init__.py
    ├── models.py                     # 模型初始化与配置（LLM 客户端、统一模型入口）
    └── utils.py                      # 通用工具函数（日志、格式化、异常处理等）
```

---

## 核心文件说明

### `agent/states.py`

定义系统全局流转状态 `AgentState`，贯穿整个 LangGraph 图的所有节点。主要字段包括：

- `user_id`：当前用户标识
- `is_authenticated`：身份认证状态
- `user_profile`：从画像数据库加载的用户标签信息
- `messages`：多轮对话消息历史
- `intent`：Supervisor 判定的当前意图类别
- `next_agent`：Supervisor 路由目标
- `memory_context`：从 Redis 读取的上下文记忆

### `agent/graph.py`

主图构建入口，使用 `StateGraph` 注册所有节点并定义路由逻辑：

- `AuthAgent → ProfileAgent`（验证成功时）
- `AuthAgent → HumanInput → AuthAgent`（验证失败时的 interrupt 循环）
- `ProfileAgent → Supervisor`
- `Supervisor → DialogueAgent / RecommendAgent / PushAgent`（条件路由，依据 `state.next_agent`）
- 各 subagent → `Supervisor`（结果回流）

### `agent/memory.py`

封装 Redis 操作，提供：

- `load_memory(user_id)`：对话开始时加载历史上下文
- `save_memory(user_id, state)`：每轮结束后持久化状态
- `cache_profile(user_id, profile)`：缓存画像标签，避免重复查询数据库

### `common/models.py`

统一的模型初始化入口。当前壳子阶段所有 Agent 共用同一模型实例（qWen3.5），后续可按 Agent 拆分配置。

---

## 快速开始

### 环境要求

- Python >= 3.11
- [uv](https://github.com/astral-sh/uv) 包管理器

### 安装依赖

```bash
uv pip install -r requirements.txt
```

### 配置环境变量

在项目根目录创建 `.env` 文件：

```env
# 模型配置
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://your-llm-endpoint
LLM_MODEL_NAME=qwen3.5

# Redis 配置（记忆模块）
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# 数据库配置（当前壳子阶段为模拟，可留空）
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
ES_HOST=http://localhost:9200
MYSQL_DSN=mysql+pymysql://user:password@localhost/dbname
```

### 启动

```bash
python -m agent.graph
```

---

## 当前实现状态

系统目前处于**壳子阶段**，核心图结构与 Agent 路由逻辑已完整搭建，各 Agent 的外部依赖工具均使用模拟实现，便于在无真实数据库环境下验证整体流程。

| 模块 | 状态 | 说明 |
|------|------|------|
| LangGraph 图结构 | ✅ 完成 | 节点注册、条件路由、状态流转 |
| AuthAgent + interrupt | ✅ 完成 | 身份验证与 human-in-the-loop |
| ProfileAgent | ✅ 完成 | 画像加载逻辑（工具为模拟） |
| Supervisor 路由 | ✅ 完成 | 意图分类与 subagent 路由 |
| DialogueAgent | ✅ 完成 | LLM 调用逻辑（政策库为模拟） |
| RecommendAgent | ✅ 完成 | 推荐逻辑框架（引擎为模拟） |
| PushAgent | ✅ 完成 | 推送框架（实际推送为模拟） |
| Redis 记忆持久化 | ✅ 完成 | 上下文读写已实现 |
| Neo4j 政策知识图谱 | 🔲 待接入 | 当前返回模拟数据 |
| ES 向量检索 | 🔲 待接入 | 当前返回模拟数据 |
| MySQL 画像数据库 | 🔲 待接入 | 当前返回模拟画像 |
| 画像引擎（分类模型） | 🔲 待接入 | 当前使用静态标签 |
| 推荐引擎 | 🔲 待接入 | 当前返回模拟推荐列表 |
| TTS / ASR 服务 | 🔲 待接入 | 语音交互能力 |

---

## 技术栈

| 类别 | 技术 |
|------|------|
| Agent 框架 | LangGraph |
| 大语言模型 | qWen 2.5:7b（通义千问） |
| 记忆存储 | Redis |
| 政策知识图谱 | Neo4j |
| 文档向量检索 | Elasticsearch |
| 画像数据库 | MySQL |
| 包管理 | uv |

---

## 开发约定

- 每个 Agent 目录内的 `tools.py` 只放该 Agent 专属的工具函数，公共工具放 `common/utils.py`
- 所有外部 I/O（数据库、API）均通过 `tools.py` 中的函数封装，便于从模拟切换到真实实现时只改一处
- 新增 Agent 时需同步更新 `agent/graph.py` 中的节点注册与条件路由逻辑
- State 字段变更需同步更新 `agent/states.py` 的类型定义