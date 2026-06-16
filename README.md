# MedGraphRAG — 基于知识图谱增强的医疗问答系统

结合**大语言模型**与**医学知识图谱**的增强型 RAG 问答系统。通过图结构推理弥补传统向量检索在多跳医学问题上的不足，提供精准、可溯源的医疗问答。

## 架构概览

```
用户提问 → 实体识别 → 图谱检索 (Neo4j 多跳)  ─┐
                    → 向量检索 (ChromaDB 重排序) ─┤→ 检索融合 → LLM 生成 → 流式输出
                                                                       ↓
                                                              答案 + 溯源 + 图谱可视化
```

## 模块结构

```
src/
├── kg/                  # 知识图谱构建
│   ├── schema.py            # 16种关系 + 14种实体类型
│   ├── data_loader.py       # 多科室CSV加载 + 分层抽样
│   ├── data_cleaner.py      # 文本清洗去重
│   ├── entity_relation_extractor.py  # LLM实体关系抽取（多模型自动切换）
│   ├── neo4j_importer.py    # Neo4j约束索引 + 批量导入 + JSON导出/导入
│   └── build_graph.py       # 端到端编排脚本（断点续传）
├── retrieval/           # 混合检索引擎
│   ├── embedding_service.py # BGE中文Embedding (512维)
│   ├── vector_store.py      # ChromaDB 余弦检索 + 关键词重排序 + 噪声过滤
│   ├── build_index.py       # 向量索引构建
│   ├── graph_retriever.py   # 实体链接 + 多跳Cypher查询 + 实体质量过滤
│   └── fusion.py            # 向量+图谱检索融合 + 置信度把关
├── qa/                  # 问答生成
│   ├── prompts.py           # 医学系统提示词（防幻觉 + 边界约束）
│   ├── memory_manager.py    # 对话记忆压缩
│   └── pipeline.py          # LangChain QA流水线（流式 + 模型切换）
└── api/                 # FastAPI 后端
    ├── main.py              # FastAPI 应用入口
    ├── schemas.py           # API 数据模型
    ├── dependencies.py      # 懒加载单例依赖注入
    └── routes/
        ├── chat.py          # /api/chat, /api/chat/stream, /api/health
        └── trace.py         # /api/trace

frontend/                # Vue 3 前端
└── src/
    ├── App.vue              # 主布局 + 对话管理 + 清空功能
    ├── api/index.js         # API 客户端 (axios)
    └── components/
        ├── ChatWindow.vue       # 对话窗口 + 设置面板
        ├── MessageBubble.vue    # 消息气泡（支持流式渲染）
        ├── SourcePanel.vue      # 知识溯源面板
        ├── GraphViewer.vue      # 图谱子图可视化 (vis-network)
        └── ThinkingSteps.vue    # 推理步骤展示
```

## 功能特性

- **知识图谱构建** — LLM 自动抽取医学实体关系，支持 16 种医学关系类型，断点续传 + 多模型自动切换
- **知识图谱可移植** — Neo4j 数据可导出为 JSON 文件，在其他环境一行命令重新导入
- **混合检索** — 向量语义检索 + 图谱多跳推理，关键词重排序优化中文匹配
- **检索质量把关** — 噪声词过滤、实体质量过滤、低置信度阈值自动清空不相关结果
- **多跳推理** — 支持 1~3 跳图查询，可回答"糖尿病→手脚麻木→检查项目"类复杂问题
- **流式输出** — SSE 实时推送，逐 token 渲染
- **知识溯源** — 答案附带引用文档 + 图谱子图可视化
- **可视化** — vis-network 渲染知识图谱，节点按实体类型着色
- **对话记忆** — 多轮对话上下文压缩
- **对话管理** — 新建对话、切换对话、单个删除、清空全部
- **自定义 API Key** — Web 界面直接输入，即时验证，快速报错
- **防幻觉设计** — 系统提示词严格限定答案来源，无相关数据时诚实告知

## 快速开始

### 环境要求

| 组件 | 说明 |
|------|------|
| Python | 3.13 (conda 环境 `DP_QA_improve`) |
| Neo4j | Community 5.26+ (bolt://localhost:7687) |
| Node.js | v24+ |
| Java | JDK 21+ (Neo4j 依赖) |

### 安装

```bash
# 1. 安装 Python 依赖
pip install -r requirements.txt

# 2. 安装前端依赖
cd frontend && npm install && cd ..

# 3. 下载 Embedding 模型
# 首次运行时自动下载 BAAI/bge-small-zh-v1.5 到 models/embedding/

# 4. 配置环境变量
cp .env.example .env   # 编辑 .env 填入你的 DashScope API Key 和 Neo4j 密码
```

### 构建数据

```bash
# 构建知识图谱（抽样 + LLM抽取 + 导入Neo4j）
python -m src.kg.build_graph --sample 500 --clear --delay 0.3

# 构建向量索引
python -m src.retrieval.build_index
```

### 启动

**方式一：一键启动**
```bash
# Windows 双击 start.bat
```

**方式二：手动启动**
```bash
# 终端1：启动 Neo4j（如未运行）
neo4j console

# 终端2：启动后端 (http://localhost:8000)
python -m src.api.main

# 终端3：启动前端 (http://localhost:3000)
cd frontend && npx vite
```

浏览器打开 `http://localhost:3000`，即可使用对话界面。

### 知识图谱移植

```bash
# 导出（从 Neo4j 导出到 JSON 文件）
# 系统已内置导出功能，直接复制 data/knowledge_graph.json

# 导入（从 JSON 导入到 Neo4j）
python -m src.kg.neo4j_importer data/knowledge_graph.json

# 清空后重新导入
python -m src.kg.neo4j_importer data/knowledge_graph.json --clear
```

JSON 文件格式：
```json
{
  "entities": [{"name": "感冒", "type": "disease"}, ...],
  "triples": [{"head": "感冒", "relation": "has_symptom", "tail": "咳嗽", "confidence": 0.8, "evidence": "..."}, ...]
}
```

## API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/chat` | POST | 标准问答 |
| `/api/chat/stream` | POST | 流式问答 (SSE) |
| `/api/trace` | POST | 推理链路追踪 |
| `/api/health` | GET | 健康检查 |
| `/docs` | GET | Swagger API 文档 |

请求示例：
```json
POST /api/chat
{
    "question": "糖尿病患者出现手脚麻木应该做什么检查？",
    "graph_hops": 2,
    "api_key": "sk-xxx"
}
```

响应包含 `answer`、`sources`（引用的文档片段）、`graph_data`（图谱子图节点和边）、`reasoning_steps`（推理步骤）。

## 技术栈

| 组件 | 选型 |
|------|------|
| 向量数据库 | ChromaDB |
| 图数据库 | Neo4j 5.26 |
| LLM 框架 | LangChain |
| LLM 模型 | qwen3.7-max (DashScope，MODEL_LIST 可配置回退) |
| Embedding | BAAI/bge-small-zh-v1.5 (512维，中文优化) |
| 分词 | jieba |
| 后端 | FastAPI + Uvicorn |
| 前端 | Vue 3 + Vite + vis-network |

## 配置

所有配置通过 `.env` 文件管理，参考 `.env.example`。关键配置项：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DASHSCOPE_API_KEY` | 阿里云 DashScope API Key | — |
| `LLM_MODEL_NAME` | LLM 模型（被 MODEL_LIST 覆盖） | qwen3.7-max |
| `EMBEDDING_MODEL_NAME` | Embedding 模型 | BAAI/bge-small-zh-v1.5 |
| `EMBEDDING_DIMENSION` | Embedding 向量维度 | 512 |
| `NEO4J_PASSWORD` | Neo4j 密码 | — |
| `CHROMA_PERSIST_DIR` | ChromaDB 持久化目录 | ./data/chroma |
