# CLAUDE.md — 医疗GraphRAG问答系统

## 项目概述

基于"大模型+知识图谱"的增强型医疗RAG问答系统。核心思路是用医学知识图谱的结构化推理能力弥补传统向量检索RAG在多跳推理问题上的不足。项目分为四个模块：数据/图谱构建 → 混合检索引擎 → 问答生成 → Web展示。

## 技术栈

| 组件 | 选型 | 版本 |
|------|------|------|
| 向量数据库 | ChromaDB | 1.5.8 |
| 图数据库 | Neo4j | 6.1.0 |
| LLM框架 | LangChain | 1.2.17 |
| LLM供应商 | 通义千问 (DashScope) | `qwen-turbo` / `qwen2-7b-instruct` |
| Embedding | sentence-transformers `all-MiniLM-L6-v2` | 本地部署，维度384 |
| 后端API | FastAPI | 0.136.1 |
| 前端 | Vue (待搭建) | — |
| Python | 3.13 | — |

## 项目结构

```
.
├── Data_original/              # 原始数据（976,693条医患问答）
│   ├── Andriatria_男科/       # 110,515条
│   ├── IM_内科/               # 293,178条
│   ├── OAGD_妇产科/           # 222,557条
│   ├── Oncology_肿瘤科/        # 92,479条
│   ├── Pediatric_儿科/         # 114,343条
│   └── Surgical_外科/          # 143,621条
├── data/                       # 处理后数据
│   ├── raw/                    # 待处理的数据副本
│   ├── processed/              # 清洗后数据
│   └── chroma/                 # ChromaDB持久化目录
├── models/
│   └── embedding/              # 本地Embedding模型
│       └── models--sentence-transformers--all-MiniLM-L6-v2/
├── src/                        # 源代码（待构建）
├── .env                        # 环境变量配置
├── requirements.txt            # Python依赖
├── project_demo.txt            # 项目需求文档
└── DATASET_README.md           # 数据集说明
```

## 四个模块及开发计划

### 模块一：数据处理与知识图谱构建（基础层）

**全部待构建**：
1. 数据获取与清洗：
   - 从 `Data_original/` 中抽样至少500条医学非结构化文本
   - 编写清洗脚本：去噪、分句、标准化医学术语
2. 知识抽取（核心）：
   - 使用通义千问设计Prompt进行医学实体识别（NER）和关系抽取（RE）
   - 医学实体类型：疾病、症状、药物、检查、治疗方法、科室、医生等
   - 医学关系类型：症状-疾病、疾病-药物、药物-禁忌症、疾病-检查、疾病-科室等
   - 输出标准三元组格式：`(头实体, 关系, 尾实体, 置信度)`
3. 图谱存储：
   - 使用Neo4j图数据库存储抽取的医学三元组
   - 创建节点索引（疾病名、药物名等），确保查询效率
   - **进阶**：实体对齐，合并重复实体（如"感冒"与"上呼吸道感染"）

### 模块二：混合检索引擎（核心层）

**全部待构建**：
1. 向量检索：
   - 使用 `all-MiniLM-L6-v2`（维度384）将医学文本块向量化，存入ChromaDB
   - 实现基于余弦相似度的Top-K医学文本块检索
2. 图谱检索：
   - 实体链接：将用户问题中的关键医学实体映射到Neo4j图谱节点
   - 多跳查询：编写Cypher查询语句，检索医学实体周围的一跳或多跳邻居节点
3. 检索融合：
   - 设计算法将"检索到的医学文本片段"与"图谱医学三元组信息"合并，作为大模型的上下文

### 模块三：问答生成与逻辑推理（应用层）

**全部待构建**：
1. Prompt工程：
   - 设计医学系统提示词，要求模型仅基于提供的医学图谱知识和检索文本回答问题，避免幻觉
   - 格式示例：`你是一个专业的医疗助手。已知医学知识图谱信息：[三元组...]，相关医学文本：[片段...]。请回答用户问题...`
2. 多跳推理支持：
   - 系统需能回答至少包含一个推理步骤的医疗问题
   - 测试案例：问"糖尿病患者出现手脚麻木症状应该做什么检查？"，系统需先查到"糖尿病"与"手脚麻木"的关系，再查"手脚麻木"相关的检查项目
3. 上下文记忆：
   - 实现对话上下文记忆压缩，支持多轮医疗问答

### 模块四：用户交互界面（展示层）

**全部待构建**：
1. FastAPI后端：对话API、检索API、溯源API
2. Vue前端：输入框、对话历史记录、答案输出
3. 知识可视化溯源（亮点功能）：
   - 答案下方展示引用的原始医学文档片段
   - 展示检索到的医学知识图谱子图（可视化节点与连线），让用户看到模型推理过程

## 环境配置要点

- `.env` 文件包含所有关键配置，**不要提交到版本控制**
- Neo4j连接：`bolt://localhost:7687`，密码见 `.env`
- DashScope API Key 在 `.env` 中已配置
- Embedding模型路径：`./models/embedding`，维度384
- ChromaDB持久化目录：`./data/chroma`
- 原始数据位于 `Data_original/`，共6个科室、约97.7万条问答记录，每条含 `department, title, ask, answer` 四个字段

## 开发约定

- 新模块放在 `src/` 下，按功能分子目录：
  - `src/kg/` — 知识图谱构建（数据清洗、NER/RE、Neo4j导入）
  - `src/retrieval/` — 混合检索（向量检索、图检索、检索融合）
  - `src/qa/` — 问答生成（Prompt模板、LangChain Pipeline、记忆管理）
  - `src/api/` — FastAPI后端路由与服务
- 前端代码放在独立目录（如 `frontend/`），与后端分离
- 数据文件放在 `data/` 下，不要直接操作 `Data_original/`
- 使用 `conda` 管理Python环境（见 `.vscode/settings.json`）
- CSV文件编码统一使用 UTF-8 BOM（`utf-8-sig`）
- 医学实体用书面语全称，避免符号和英文缩写

## 关键技术决策

1. **为什么用 all-MiniLM-L6-v2？** 轻量级（~22M参数）、维度低（384），适合本地快速推理，满足中文医学文本的基础语义匹配
2. **为什么用 Neo4j + ChromaDB 双存储？** 向量库处理语义相似度，图库处理结构化关系推理，各取所长
3. **为什么用通义千问？** 中文医学理解能力强，DashScope API稳定，LangChain有原生集成 `ChatTongyi`
4. **关系抽取应采用结构化输出**：通过Pydantic schema + `with_structured_output` 约束LLM输出格式，保证三元组质量。建议定义16种医学关系（`has_symptom`、`treated_with`、`caused_by`、`located_in`、`has_complication`、`has_treatment`、`has_diagnosis`、`has_side_effect`、`belongs_to` 等）
