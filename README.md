# Knowledge Map — 论文知识地图 + 多 Agent 论文分析系统

基于 **FastAPI + LangGraph + React** 构建的前后端分离论文分析平台。上传 PDF 后，系统自动完成元数据提取、联网校验、分类、创新点/局限性分析、反思修复、关系图构建等全流程，并以知识地图的形式可视化展示。

## 项目介绍视频

[![项目介绍视频](https://img.shields.io/badge/Bilibili-视频介绍-blue)](https://www.bilibili.com/video/BV1cd7w6sEB9/)

> **桌面版**：除下文介绍的 Web 开发模式外，本项目还支持 **Tauri + React + FastAPI sidecar** 桌面应用，双击 exe 即可运行，无需手动装 Redis / 启动后端。桌面版的打包流程、stdout 启动协议、数据目录重定向等说明详见 [`desktop/README_DESKTOP.md`](./desktop/README_DESKTOP.md)。

## 目录

- [功能特性](#功能特性)
- [项目介绍视频](#项目介绍视频)
- [技术栈](#技术栈)
- [项目架构](#项目架构)
- [环境要求](#环境要求)
- [快速启动](#快速启动)
- [环境变量配置](#环境变量配置)
- [数据结构手册](#数据结构手册)
  - [papers.json 字段说明](#papersjson-字段说明)
  - [analysis JSON 字段说明](#analysis-json-字段说明)
  - [论文存储位置](#论文存储位置)
- [自定义分类](#自定义分类)
  - [为什么可以自定义](#为什么可以自定义)
  - [需要修改哪些文件](#需要修改哪些文件)
  - [修改分类定义](#修改分类定义)
  - [分类 Agent 提示词](#分类-agent-提示词)
  - [创建对应的论文文件夹](#创建对应的论文文件夹)
  - [完整示例：计算机视觉领域](#完整示例计算机视觉领域)
  - [适配检查清单](#适配检查清单)
- [LangGraph 工作流](#langgraph-工作流)
- [元数据校验链路](#元数据校验链路)
- [PDF 解析降级链](#pdf-解析降级链)
- [论文关系图构建](#论文关系图构建)
- [API 端点参考](#api-端点参考)
- [前端使用说明](#前端使用说明)
- [常见问题](#常见问题)

---

## 功能特性

- **PDF 自动解析**：支持 MinerU / PyMuPDF / pypdf，扫描版 PDF 可启用 Tesseract OCR
- **多源元数据校验**：本地 PDF 提取 → Crossref / Semantic Scholar / arXiv 联网检索 → LLM 比对校验
- **智能分类**：基于 LLM 将论文自动归入预定义研究方向
- **创新点 & 局限性分析**：多 Agent 协作，自动生成结构化分析结果
- **反思 & 修复机制**：分析结果经 LLM 自检，不合格自动重试（最多 2 次）
- **论文关系图**：自动构建引用关系和同类别演进关系，可视化展示
- **可配置 LLM**：支持 OpenAI 和 Anthropic，通过前端界面设置 API Key
- **Redis 任务队列**：异步处理上传任务，实时查询进度

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 18 + TypeScript + Vite 5 + React Router 6 |
| 后端 | FastAPI + LangGraph + Pydantic v2 |
| 存储 | Redis 7（任务队列/缓存）+ 本地 JSON（论文数据） |
| 文档处理 | MinerU / PyMuPDF / pypdf / Tesseract OCR |
| LLM | OpenAI API / Anthropic API（通过统一 Provider 调用） |
| 外部检索 | arXiv API / Crossref API / Semantic Scholar API |

---

## 项目架构

```text
Knowledge-Map/
├── front/                          # React 前端
│   ├── src/
│   │   ├── api/                    # API 调用封装（client.ts + config.ts）
│   │   ├── components/             # UI 组件
│   │   │   ├── ApiModelSettings.tsx     # 模型/分类设置弹窗
│   │   │   ├── CategoryTimeline.tsx     # 分类时间线（按年份分组）
│   │   │   ├── PaperCard.tsx            # 论文卡片
│   │   │   ├── PaperNetworkGraph.tsx    # SVG 关系图（拖拽/缩放/筛选）
│   │   │   ├── PaperSearchPanel.tsx     # 关键词搜索
│   │   │   ├── PaperUploadButton.tsx    # 上传入口按钮
│   │   │   ├── PaperUploadModal.tsx     # 上传弹窗 + 任务轮询
│   │   │   └── TaskProgressPanel.tsx    # 任务进度条
│   │   ├── pages/                  # 路由页面
│   │   │   ├── KnowledgeMapPage.tsx     # 首页：分类时间线
│   │   │   ├── NetworkPage.tsx          # /network：关系图
│   │   │   └── PaperDetailPage.tsx      # /paper/:id：论文详情
│   │   ├── styles/                 # 样式文件
│   │   ├── types/                  # TypeScript 类型定义（与后端 schemas.py 对应）
│   │   ├── App.tsx                 # 路由 + 顶层状态
│   │   └── main.tsx                # React 入口
│   ├── package.json
│   └── vite.config.ts
├── src/                            # FastAPI 后端
│   ├── main.py                     # FastAPI 应用入口
│   ├── config.py                   # 全局配置（路径、分类定义）★ 领域适配核心文件
│   ├── schemas.py                  # Pydantic 数据模型
│   ├── agents/                     # LangGraph Agent 定义
│   │   ├── graph.py                # 工作流编排
│   │   ├── classify_agent.py       # 论文分类 Agent ★ 领域适配需修改提示词
│   │   ├── innovation_agent.py     # 创新点分析 Agent
│   │   ├── limitation_agent.py     # 局限性分析 Agent
│   │   ├── reflection_agent.py     # 反思校验 Agent
│   │   └── source_agent.py         # 来源检索 Agent
│   ├── llm/                        # LLM 调用层
│   │   ├── provider.py             # 统一 LLM Provider（OpenAI/Anthropic）
│   │   └── settings.py             # 模型配置管理
│   ├── services/                   # 业务逻辑
│   │   ├── pdf_loader.py           # PDF 文本提取（MinerU/PyMuPDF/pypdf + OCR）
│   │   ├── metadata_extractor.py   # 本地 PDF 元数据提取（正则启发式）
│   │   ├── paper_metadata_pipeline.py  # 三级元数据校验链路（本地→联网→LLM）
│   │   ├── external_paper_lookup.py    # Crossref/Semantic Scholar/arXiv 联网检索
│   │   ├── paper_file_manager.py       # 论文 ID slug + 文件移动
│   │   ├── paper_graph_builder.py      # 关系图构建（同类演进+引用匹配）
│   │   └── paper_record_cleaner.py     # paper.short 生成 + idea 清洗
│   ├── database/                   # 数据存储层
│   │   ├── json_store.py           # JSON 文件读写（papers.json + analysis/）
│   │   ├── kv.py                   # Redis 键值存储封装（KVRepository）
│   │   └── redis_client.py         # Redis 客户端（含本地文件降级）
│   ├── tools/                      # 辅助工具
│   │   └── repair_metadata_records.py
│   └── data/                       # 运行时数据
│       ├── papers.json             # 论文集合索引
│       └── analysis/               # 每篇论文的分析结果
├── src-tauri/                      # Tauri 桌面壳（Rust）
│   ├── src/main.rs                 # Tauri 主进程：启动 sidecar + 健康检查 + API URL 注入
│   ├── tauri.conf.json             # 桌面配置（externalBin/窗口/CSP）
│   ├── binaries/                   # PyInstaller 产物（knowledge-map-backend-*.exe）
│   └── Cargo.toml
├── desktop/                        # 桌面后端打包支持
│   ├── backend/run_backend.py      # sidecar 入口：端口探测 + stdout 协议
│   ├── backend/build_backend.ps1   # PyInstaller 打包脚本
│   └── README_DESKTOP.md           # 桌面版完整说明
├── paper/                          # 论文 PDF 存储（按分类组织）
├── uploads/                        # 上传暂存目录
├── docker-compose.yml              # Redis 编排
├── requirements.txt                # Python 依赖
├── .env.example                    # 环境变量示例
└── README.md
```

---

## 环境要求

- **Python** >= 3.10
- **Node.js** >= 18
- **Docker**（用于运行 Redis，可选）
- **Tesseract OCR**（可选，用于扫描版 PDF）

---

## 快速启动

### 1. 启动 Redis

```bash
docker compose up -d
```

### 2. 启动后端

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API Key 等配置

# 启动服务
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. 启动前端

```bash
cd front
npm install
npm run dev
```

默认访问地址：
- 前端：`http://localhost:5173`
- 后端 API：`http://localhost:8000`
- API 文档：`http://localhost:8000/docs`

---

## 环境变量配置

复制 `.env.example` 为 `.env` 并填写：

```bash
# LLM 配置
OPENAI_API_KEY=sk-xxx              # OpenAI API Key（二选一）
ANTHROPIC_API_KEY=sk-ant-xxx       # Anthropic API Key（二选一）
LLM_PROVIDER=openai                # openai 或 anthropic
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=4096

# Redis
REDIS_URL=redis://localhost:6379/0

# OCR（可选）
OCR_ENABLED=true
OCR_MIN_TEXT_LENGTH=500
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe

# PDF 解析器
PDF_PARSER_BACKEND=auto            # auto / mineru / pymupdf
MINERU_CLI_COMMAND=mineru
MINERU_METHOD=auto
MINERU_BACKEND=pipeline
MINERU_EFFORT=medium
MINERU_LANG=ch

# MinerU 远程 API（可选）
MINERU_API_BASE_URL=https://mineru.net
MINERU_API_TOKEN=
MINERU_API_TIMEOUT=600
```

---

## 数据结构手册

### papers.json 字段说明

`src/data/papers.json` 是论文集合的主索引文件，顶层结构：

```json
{
  "categories": [...],
  "papers": [...]
}
```

#### categories 数组元素

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 分类唯一标识，如 `optimization`、`personalization` |
| `name` | string | 分类中文名称，如"核心方法" |
| `folder` | string | 对应 `paper/` 下的子文件夹名，如 `01_核心方法` |
| `why` | string | 该分类的研究动机 |
| `advantages` | string | 该方向的优势 |
| `disadvantages` | string | 该方向的劣势 |

#### papers 数组元素

| 字段 | 类型 | 必有 | 说明 |
|------|------|------|------|
| `id` | string | 是 | 论文唯一标识，由文件名自动生成（如 `fedavg`、`a93e13033a934717852c1182b8d6fd88-fedprox`） |
| `short` | string | 是 | 论文简称/缩写（如 `BERT`、`ResNet`），用于图谱节点展示 |
| `title` | string | 是 | 论文完整标题 |
| `year` | int \| null | 否 | 发表年份 |
| `authors` | string[] | 是 | 作者列表 |
| `first_author` | string | 是 | 第一作者 |
| `venue` | string \| null | 否 | 发表会议/期刊（如 `AISTATS 2017`、`arXiv`） |
| `abstract` | string | 是 | 论文摘要 |
| `summary` | string | 是 | 系统生成的中文总结（1-3 句话概括论文贡献） |
| `idea` | string | 是 | 核心思想/方法（1-2 句，**仅描述机制，不含结果性表述**，详见下方约束） |

> **`idea` 字段硬约束**：`idea` 只能写论文的核心方法机制，1-2 句。提示词与后处理 `normalize_idea_text` 双重保险剔除"实验表明"、"优于其他方法"、"更快收敛"、"性能更好"、"显著提升"等结果性表述，最多保留前 2 句、180 字符。修改 innovation_agent 提示词时不要放松这条约束。
| `categories` | string[] | 是 | 所属分类 ID 列表（通常只有一个） |
| `source_path` | string | 是 | 论文 PDF 的存储路径（绝对路径或相对路径） |
| `innovation` | string | 是 | 创新点总结描述 |
| `innovation_points` | InnovationPoint[] | 是 | 结构化创新点列表（见下方子表） |
| `flow_steps` | string[] | 是 | 方法流程步骤（有序列表） |
| `applications` | string | 是 | 应用场景描述 |
| `limitations` | string | 是 | 局限性总结描述 |
| `limitation_points` | LimitationPoint[] | 是 | 结构化局限性列表（见下方子表） |
| `citations` | CitationItem[] | 是 | 引用列表（见下方子表） |
| `relationships` | RelationshipItem[] | 是 | 与其他论文的关系（见下方子表） |
| `analysis_json_path` | string | 是 | 对应分析结果 JSON 文件路径（如 `src/data/analysis/fedavg.json`） |
| `needs_human_review` | bool | 是 | 是否需要人工审核（反思重试 2 次仍未通过时为 `true`） |
| `created_at` | datetime | 是 | 创建时间（ISO 8601） |
| `updated_at` | datetime | 是 | 最后更新时间（ISO 8601） |
| `venue_source` | string \| null | 否 | 元数据来源类型：`conference`、`journal`、`arxiv_id`、`crossref` 等 |
| `doi` | string \| null | 否 | DOI 标识符 |
| `arxiv_id` | string \| null | 否 | arXiv ID |
| `source_url` | string \| null | 否 | 论文来源 URL |
| `citation_text` | string \| null | 否 | 标准化引用文本 |
| `bibtex` | string \| null | 否 | BibTeX 格式引用 |
| `metadata_confidence` | float | 是 | 元数据置信度（0-1），越高表示元数据越可信 |
| `metadata_source_method` | string \| null | 否 | 元数据获取方法（如 `crossref`、`arxiv_id`、`local_pdf`） |
| `metadata_verification_notes` | string \| null | 否 | 元数据验证说明（如"标题、作者与 DOI 已按 Crossref 结果校正"） |
| `source_candidates` | PaperSourceCandidate[] | 是 | 来源候选列表（见下方子表） |

##### InnovationPoint（创新点）

| 字段 | 类型 | 说明 |
|------|------|------|
| `point` | string | 创新点描述 |
| `evidence` | string | 支持证据（来自论文原文的引用或描述） |
| `confidence` | float | 置信度（0-1） |

##### LimitationPoint（局限性点）

| 字段 | 类型 | 说明 |
|------|------|------|
| `point` | string | 局限性描述 |
| `evidence` | string | 支持证据 |
| `type` | string | 类型：`paper_claimed`（论文自述）或 `inferred`（系统推断） |
| `severity` | string | 严重程度：`low` / `medium` / `high` |

##### CitationItem（引用项）

| 字段 | 类型 | 说明 |
|------|------|------|
| `title` | string | 被引论文标题 |
| `authors` | string[] | 被引论文作者列表 |
| `year` | int \| null | 被引论文年份 |
| `venue` | string \| null | 被引论文会议/期刊 |
| `doi` | string \| null | 被引论文 DOI |

##### RelationshipItem（关系项）

| 字段 | 类型 | 说明 |
|------|------|------|
| `source` | string | 源论文 ID |
| `target` | string | 目标论文 ID |
| `type` | string | 关系类型：`citation`（引用关系）或 `same_category_evolution`（同类别时间演进） |
| `reason` | string | 关系原因说明 |

##### PaperSourceCandidate（来源候选）

| 字段 | 类型 | 说明 |
|------|------|------|
| `provider` | string | 数据来源：`local_pdf`（本地 PDF 提取）、`crossref_title`（Crossref 标题检索）、`arxiv_id`（arXiv 检索）、`reference_lookup`（用户输入引用）等 |
| `title` | string | 候选论文标题 |
| `authors` | string[] | 候选论文作者 |
| `abstract` | string | 候选论文摘要 |
| `year` | int \| null | 候选论文年份 |
| `venue` | string \| null | 候选论文会议/期刊 |
| `doi` | string \| null | 候选论文 DOI |
| `arxiv_id` | string \| null | 候选论文 arXiv ID |
| `source_url` | string \| null | 候选论文来源 URL |
| `citation_text` | string \| null | 标准化引用文本 |
| `bibtex` | string \| null | BibTeX 格式 |
| `confidence` | float | 候选匹配置信度（0-1） |
| `reason` | string | 匹配原因说明（如"标题相似度 0.99，包含 DOI，作者数 3"） |

---

### analysis JSON 字段说明

`src/data/analysis/{paper_id}.json` 是每篇论文的独立分析结果文件。其字段与 `papers.json` 中 `papers` 数组元素基本一致，但有以下差异：

| 差异点 | 说明 |
|--------|------|
| 不包含 `relationships` 字段 | 关系数据仅维护在 `papers.json` 主索引中 |
| 不包含 `source_candidates` 中的部分字段 | 部分精简版可能缺少 `citation_text`、`bibtex` |
| `updated_at` 可能更早 | 分析 JSON 在保存时生成，后续通过 `PATCH` 更新的是 `papers.json` |

完整的 analysis JSON 字段列表：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 论文唯一标识 |
| `short` | string | 论文简称 |
| `title` | string | 论文标题 |
| `year` | int \| null | 发表年份 |
| `authors` | string[] | 作者列表 |
| `first_author` | string | 第一作者 |
| `venue` | string \| null | 会议/期刊 |
| `abstract` | string | 摘要 |
| `summary` | string | 中文总结 |
| `idea` | string | 核心思想 |
| `categories` | string[] | 分类 ID 列表 |
| `source_path` | string | PDF 路径 |
| `innovation` | string | 创新点描述 |
| `innovation_points` | InnovationPoint[] | 结构化创新点 |
| `flow_steps` | string[] | 方法流程 |
| `applications` | string | 应用场景 |
| `limitations` | string | 局限性描述 |
| `limitation_points` | LimitationPoint[] | 结构化局限性 |
| `citations` | CitationItem[] | 引用列表 |
| `analysis_json_path` | string | 自身文件路径 |
| `needs_human_review` | bool | 是否需要人工审核 |
| `created_at` | datetime | 创建时间 |
| `updated_at` | datetime | 更新时间 |
| `venue_source` | string \| null | 元数据来源类型 |
| `doi` | string \| null | DOI |
| `arxiv_id` | string \| null | arXiv ID |
| `source_url` | string \| null | 来源 URL |

---

### 论文存储位置

论文 PDF 文件按分类存储在 `paper/` 目录下：

```text
paper/
├── 01_核心方法/
│   └── {paper_id}.pdf
├── 02_改进与扩展/
├── 03_理论与分析/
├── 04_应用与系统/
├── 05_数据与评测/
├── 06_综述与展望/
└── 其他/
```

- 上传的 PDF 先暂存在 `uploads/` 目录
- 分类完成后自动移动到 `paper/{分类文件夹}/` 下
- 文件名格式：`{paper_id}.pdf`（paper_id 由系统自动生成）
- `source_path` 字段记录了论文 PDF 的最终存储路径

---

## 自定义分类

本项目默认提供一套**面向任意研究领域的通用分类**（核心方法 / 改进与扩展 / 理论与分析 / 应用与系统 / 数据与评测 / 综述与展望 / 其他），按“研究贡献类型”而非具体领域划分，适合把任何方向的论文组织成技术发展脉络。

如果你希望按自己的研究方向（如计算机视觉、自然语言处理、强化学习等）重新组织分类，只需修改以下内容。

### 为什么可以自定义

系统的分类完全由数据驱动：

1. **分类定义**（`src/config.py`）：`CATEGORY_DEFINITIONS` 列表定义了默认的通用分类，分类 Agent 会把论文归入这些方向
2. **分类 Agent 提示词**（`src/agents/classify_agent.py`）：系统提示词是通用的“论文分类助手”，会严格按照给定的可选大类做归类

修改分类定义后，分类 Agent 会以新分类视角理解论文；无需改动其他逻辑。

### 需要修改哪些文件

| 文件 | 修改内容 | 优先级 |
|------|----------|--------|
| `src/config.py` | 修改 `CATEGORY_DEFINITIONS` 列表 | 必须 |
| `src/agents/classify_agent.py` | 修改系统提示词中的领域描述 | 必须 |
| `paper/` 目录 | 创建与新分类对应的子文件夹 | 必须（系统会自动创建，但建议提前规划） |

### 修改分类定义

打开 `src/config.py`，找到 `CATEGORY_DEFINITIONS` 列表（约第 34-107 行），将其中的 `CategoryDefinition` 替换为你所在领域的研究方向。

每个分类需要填写 6 个字段：

```python
CategoryDefinition(
    id="detection",                    # 英文标识，用于 JSON 和 URL
    name="目标检测",                    # 中文名称，用于前端显示
    folder="01_目标检测",               # 文件夹名，paper/ 下的子目录
    why="目标检测是计算机视觉的基础任务...",  # 为什么这个方向重要
    advantages="...",                   # 该方向的优势
    disadvantages="...",                # 该方向的劣势
),
```

**注意事项**：
- `id` 必须是英文小写，用下划线分隔（如 `object_detection`、`image_segmentation`）
- `folder` 建议用数字前缀排序（如 `01_目标检测`、`02_图像分割`）
- 保留 `other` 分类作为兜底，用于无法归类的论文
- `why`、`advantages`、`disadvantages` 会被 LLM 用于理解分类逻辑，尽量写清楚

### 分类 Agent 提示词

`src/agents/classify_agent.py` 的系统提示词默认是通用的“论文分类助手”，会严格按给定的可选大类归类，默认无需修改。如果你希望分类时带有特定领域视角（例如更贴合计算机视觉的语义），可以在系统提示词中补充领域描述：

```python
"你是计算机视觉论文分类助手，只能返回 JSON，不要解释。..."
```

这个提示词会影响分类 Agent 对论文的理解视角。

### 创建对应的论文文件夹

系统启动时会根据 `CATEGORY_DEFINITIONS` 中的 `folder` 字段自动创建文件夹。但建议提前在 `paper/` 下手动创建，以便整理已有论文。

### 完整示例：计算机视觉领域

以下是一个将系统适配为**计算机视觉**领域的完整示例。

**修改 `src/config.py`**：

```python
CATEGORY_DEFINITIONS: list[CategoryDefinition] = [
    CategoryDefinition(
        id="detection",
        name="目标检测",
        folder="01_目标检测",
        why="目标检测是视觉感知的核心任务，广泛应用于自动驾驶、安防监控、工业质检等场景。",
        advantages="端到端训练成熟，工业落地案例丰富。",
        disadvantages="小目标和密集场景下性能仍有瓶颈。",
    ),
    CategoryDefinition(
        id="segmentation",
        name="图像分割",
        folder="02_图像分割",
        why="像素级理解是精细化视觉任务的基础，包括语义分割、实例分割和全景分割。",
        advantages="提供最细粒度的空间理解能力。",
        disadvantages="标注成本极高，计算开销大。",
    ),
    CategoryDefinition(
        id="generation",
        name="图像生成与编辑",
        folder="03_图像生成与编辑",
        why="生成式模型（GAN、Diffusion）推动了图像合成、超分辨率、风格迁移等方向。",
        advantages="创造力强，应用场景广泛。",
        disadvantages="评估标准主观性强，训练不稳定。",
    ),
    CategoryDefinition(
        id="3d",
        name="三维视觉",
        folder="04_三维视觉",
        why="从2D到3D的跨越是机器人、AR/VR、数字孪生等应用的关键。",
        advantages="空间信息更丰富，适合物理世界建模。",
        disadvantages="数据采集和标注难度大。",
    ),
    CategoryDefinition(
        id="video",
        name="视频理解",
        folder="05_视频理解",
        why="时序建模是理解动态场景的核心，涵盖动作识别、视频描述、时序定位等。",
        advantages="信息更丰富，能捕捉时空关系。",
        disadvantages="计算量大，长视频建模困难。",
    ),
    CategoryDefinition(
        id="multimodal",
        name="多模态学习",
        folder="06_多模态学习",
        why="视觉-语言、视觉-音频等跨模态融合是通用人工智能的重要方向。",
        advantages="能利用多种信息源，泛化能力更强。",
        advantages="能利用多种信息源，泛化能力更强。",
        disadvantages="模态对齐和融合策略复杂。",
    ),
    CategoryDefinition(
        id="efficient",
        name="高效网络与部署",
        folder="07_高效网络与部署",
        why="模型轻量化、量化、蒸馏是落地的关键环节。",
        advantages="直接决定工程可行性。",
        disadvantages="精度与效率的权衡难以兼顾。",
    ),
    CategoryDefinition(
        id="survey",
        name="综述与基准",
        folder="08_综述与基准",
        why="提供领域全景图和统一评估框架。",
        advantages="帮助快速建立领域认知。",
        disadvantages="不直接提出新方法。",
    ),
    CategoryDefinition(
        id="other",
        name="其他",
        folder="其他",
        why="用于暂时无法稳定归类的论文。",
        advantages="避免误分，便于后续复审。",
        disadvantages="可解释性略弱。",
    ),
]
```

**修改 `src/agents/classify_agent.py`**：

```python
"你是计算机视觉论文分类助手。只能返回 JSON，不要解释。",
```

**创建文件夹**：

```bash
mkdir -p paper/01_目标检测 paper/02_图像分割 paper/03_图像生成与编辑 \
         paper/04_三维视觉 paper/05_视频理解 paper/06_多模态学习 \
         paper/07_高效网络与部署 paper/08_综述与基准 paper/其他
```

### 适配检查清单

修改完成后，按以下清单逐项确认：

- [ ] `src/config.py` 中的 `CATEGORY_DEFINITIONS` 已替换为你的领域分类
- [ ] `src/agents/classify_agent.py` 中的系统提示词已修改领域描述
- [ ] `paper/` 下的子文件夹已创建（或确认系统启动时能自动创建）
- [ ] `papers.json` 中的 `categories` 数组已更新（如果已有历史数据）
- [ ] 重启后端服务使修改生效
- [ ] 上传一篇测试论文，确认分类结果符合预期

---

## LangGraph 工作流

论文上传后，系统通过 LangGraph 编排以下 13 个节点的有向图工作流：

```
parse_pdf → extract_metadata → source_agent → save_metadata_to_kv → classify_paper
    → move_pdf_to_category → innovation_agent → limitation_agent → reflection_agent
    → [repair ↔ reflection_agent]（最多重试 2 次）
    → save_final_json → build_relationship → finish
```

| 节点 | 功能 |
|------|------|
| `parse_pdf` | 调用 PDF 解析器提取文本内容 |
| `extract_metadata` | 从 PDF 文本中本地提取标题、作者、摘要等 |
| `source_agent` | 联网检索（Crossref/Semantic Scholar/arXiv）并用 LLM 校验 |
| `save_metadata_to_kv` | 将元数据缓存到 Redis |
| `classify_paper` | LLM 将论文分类到预定义方向之一 |
| `move_pdf_to_category` | 将 PDF 移动到对应分类文件夹 |
| `innovation_agent` | LLM 分析创新点、核心思想、方法流程、应用场景 |
| `limitation_agent` | LLM 分析局限性和不足 |
| `reflection_agent` | LLM 检查分析结果质量，决定是否需要修复 |
| `repair` | 根据反思反馈重新运行对应 Agent |
| `save_final_json` | 保存分析结果到 `analysis/{paper_id}.json` 并更新 `papers.json` |
| `build_relationship` | 构建论文间引用关系和演进关系 |
| `finish` | 标记任务完成 |

---

## 元数据校验链路

`source_agent` 节点实际调用 `src/services/paper_metadata_pipeline.py`，论文标题/作者/年份/DOI 的获取走**三级校验**，保证结果可信：

```text
本地 PDF 提取 ─┐
              ├─→ 联网检索候选（Crossref/Semantic Scholar/arXiv）
              │        ↓
              │   候选评分（标题相似度 + 作者重合 + DOI/arXiv 匹配 + 渠道加成）
              │        ↓
              └─→ LLM 比对：选最可信的标题、作者、年份、来源
                       ↓ 失败时
                  按最高分候选自动对齐（fallback）
```

| 来源 | 实现 | 置信度估算 |
|------|------|-----------|
| 本地 PDF | `metadata_extractor.py` 用正则从首页 24 行提取标题/作者/摘要/引用 | 基础 0.25 + 标题长度 ≥ 20（+0.2）+ 有作者（+0.15）+ 摘要 ≥ 120 字（+0.2）+ 有 DOI（+0.15）+ 有 arXiv ID（+0.05），封顶 0.95 |
| 联网检索 | `external_paper_lookup.py` 按 DOI / arXiv ID / 标题分别查询三个数据源 | 见下方评分公式 |
| LLM 比对 | `_reconcile_with_llm` 把本地结果 + 候选 + PDF 摘要交给 LLM 选最可信 | LLM 失败时降级到 `_fallback_reconcile`（取候选分最高） |

**候选评分公式**（`_score_candidate`，0-0.99）：

```
score = 0.45 × 标题相似度（SequenceMatcher）
      + 0.20 × 作者重合比例
      + DOI 加成（本地 DOI 精确匹配 +0.30 / 候选 DOI 出现在原文 +0.20）
      + arXiv 加成（本地 arXiv 精确匹配 +0.30 / 候选 arXiv 出现在原文 +0.15）
      + 摘要存在（+0.10）
      + 引用列表加成（每条 +0.02，上限 +0.08）
      + 渠道加成（DOI 渠道 +0.18 / Crossref 渠道 +0.08 / 其他 +0.05）
      − 被引嫌疑扣分（疑似被引论文被误识别为正本时 −0.18）
```

候选数受 `PAPER_SEARCH_MAX_CANDIDATES` 控制（默认 5）。低质量候选（标题相似度 < 0.88 且无 DOI/arXiv 匹配且置信度 < 0.55）会被过滤。

特殊保护：`_candidate_looks_like_reference_target` 识别**被引论文被错误识别为正本**的情况并扣 0.18 分。如果改评分逻辑，不要破坏这个保护。

---

## PDF 解析降级链

`src/services/pdf_loader.py::extract_pdf_text` 按 `PDF_PARSER_BACKEND` 配置降级：

| `PDF_PARSER_BACKEND` | 解析路径 |
|---------------------|---------|
| `mineru` | 仅 MinerU（远程 API 优先，无 token 时走本地 CLI），失败抛错 |
| `auto`（默认） | MinerU → 失败回退 PyMuPDF → 失败回退 pypdf |
| 其他值 | 直接 PyMuPDF → 失败回退 pypdf |

**MinerU 自身两种模式**（看 `MINERU_API_TOKEN` 是否配置）：

- **远程 API**（推荐用于扫描版/复杂公式 PDF）：申请上传链接 → PUT 上传 PDF → 轮询 `extract-results/batch/{batch_id}` 直到 `state=done` → 下载 `full_zip_url` → 解压读 `full.md`。详见常见问题 Q5。
- **本地 CLI**：调用 `mineru` 命令行，从 `output/{stem}/{method|vlm|hybrid_method}/` 读 `.md` / `_content_list.json` / `_middle.json`。

**扫描版检测 + OCR**：文本长度 < `OCR_MIN_TEXT_LENGTH`（默认 500）触发 OCR。流程：PyMuPDF 渲染页面为 PNG（matrix 2x）→ pytesseract 识别（`chi_sim+eng`）。`OCR_ENABLED=false` 时跳过 OCR，只用常规文本抽取。

返回结构：

```python
{
  "raw_text": "...",          # 提取到的纯文本
  "page_count": 12,
  "possibly_scanned_pdf": false,
  "used_ocr": false,
  "parser_backend": "pymupdf",  # mineru / pymupdf / pypdf
  "warning": None               # 警告信息（如 OCR 不可用、扫描件检测等）
}
```

---

## 论文关系图构建

`src/services/paper_graph_builder.py` 生成两类关系边：

### `same_category_evolution`（同类别时间演进）

同分类下的论文按 `(year ASC, short.lower())` 排序，**只连相邻两篇**（不跨年跳跃），表达该方向的时间演进：

```
论文A(2017) → 论文B(2018) → 论文C(2021) → ...
```

### `citation`（引用关系）

当论文 A 的本地 `citations` 列表中某条引用的标题能**精确匹配**到论文库中已有论文 B 的标题时，连一条 `B → A` 的边（被引方 → 引用方）：

```
匹配条件：citation.title.lower() == paper.title.lower()
边方向：被引论文 → 引用论文
```

边按 `(source, target, type)` 三元组去重。`sync_relationships_into_papers()` 把关系反向写回 `papers.json` 中每篇论文的 `relationships` 字段——**analysis JSON 中不存 relationships**，只在 `papers.json` 主索引中维护。

前端 `PaperNetworkGraph.tsx` 在 SVG 渲染时会**再次按论文年份调整边的方向**（早 → 晚），并支持节点拖拽、画布平移、分类筛选。9 个分类各自有固定颜色映射（`categoryColors`），新增分类需要补颜色。

---

## API 端点参考

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/health` | 健康检查（Tauri 启动时轮询） |
| GET | `/api/papers` | 获取所有论文 + 分类（返回 `PaperCollection`） |
| GET | `/api/papers/{paper_id}` | 获取单篇论文详情 |
| POST | `/api/papers/upload` | 上传 PDF（multipart/form-data，`files[]` + `references[]` 数量必须一致） |
| GET | `/api/papers/tasks/{task_id}` | 查询上传任务进度（前端每 1800ms 轮询） |
| GET | `/api/graph` | 获取关系图数据（`nodes[]` + `links[]`） |
| GET | `/api/categories` | 获取分类列表 |
| POST | `/api/categories` | 新增分类 |
| PUT | `/api/categories/{category_id}` | 更新分类（改 ID 时会同步修正所有论文的 `categories` 字段） |
| DELETE | `/api/categories/{category_id}` | 删除分类（论文归入 `other`） |
| GET | `/api/settings/model` | 获取模型设置摘要（不返回 API Key 明文） |
| POST | `/api/settings/model` | 保存模型设置（写入 `.env`） |
| PATCH | `/api/papers/{paper_id}/analysis` | 部分更新论文分析结果（用于人工修正） |

**CORS**：放行 `http://localhost:5173`、`tauri://localhost`、`http://tauri.localhost` 以及 `http://(localhost|127\.0\.0\.1):\d+` 正则匹配的来源。

---

## 前端使用说明

1. **配置 API**：点击首页"设置"按钮，选择 OpenAI 或 Anthropic，填入 API Key。设置弹窗同时支持分类管理（新增/编辑/删除分类）
2. **上传论文**：点击"添加论文"，拖拽或选择 PDF 文件，**每个 PDF 必须同时配一行 DOI / arXiv ID / 论文链接**（用作元数据检索 hint，数量必须与文件数一致）
3. **查看进度**：上传后页面顶部显示当前处理阶段（前端每 1800ms 轮询任务状态）
4. **浏览分析结果**：首页以**分类时间线**形式展示论文（每个分类 → 年份分组 → 论文卡片），支持关键词搜索（按简称、标题、作者、年份、会议、方向实时筛选）
5. **查看关系图**：点击右上角"论文关系网"进入 `/network` 页面，可视化论文间的引用和演进关系，支持节点拖拽、画布平移、分类筛选
6. **论文详情**：点击任意论文卡片进入 `/paper/{id}` 详情页，展示创新点、主要流程图（按步骤可视化）、应用场景、缺陷与局限

前端 API 地址解析（`front/src/api/config.ts`）按优先级：

1. `VITE_API_BASE_URL`（Vite 构建期环境变量，开发模式可用）
2. `window.__KNOWLEDGE_MAP_API_URL__`（Tauri 桌面模式运行时注入）
3. 兜底 `http://127.0.0.1:8000`

---

## 常见问题

### 上传时报"请先配置 API / 模型"

分类、创新点、局限性和反思节点都依赖 LLM。需先在首页设置模型配置。

### 来源查询失败但任务没有完全失败

来源查询设计为可降级节点。联网失败时自动回退到 PDF 本地提取结果。

### 论文被放进"其他"

当分类 Agent 置信度不足或内容跨方向过强时，会避免误分类并落入"其他"。如果想按自己的研究方向重新组织分类，参考[自定义分类](#自定义分类)。

### 扫描版 PDF 抽取效果不好

两种改进路径：
1. 启用 Tesseract OCR：`OCR_ENABLED=true`，配置 `TESSERACT_CMD` 路径
2. 切换 MinerU：`PDF_PARSER_BACKEND=mineru`，配置 MinerU CLI 或远程 API

### 如何使用 MinerU 远程精准解析 API

```bash
PDF_PARSER_BACKEND=mineru
MINERU_API_BASE_URL=https://mineru.net
MINERU_API_TOKEN=你的token
MINERU_BACKEND=vlm
MINERU_LANG=ch
MINERU_API_TIMEOUT=600
```

调用流程：申请上传链接 → PUT 上传 PDF → 轮询结果 → 下载 zip 包。

> **注意**：`MINERU_API_URL` / `MINERU_API_BASE_URL` 必须是 `http://` 或 `https://` 开头的服务地址；`MINERU_API_TOKEN` 才是 Bearer Token，不要把 token 填到 URL 字段里。

### 如何使用 MinerU 本地 CLI

```bash
PDF_PARSER_BACKEND=auto    # 或 mineru
MINERU_CLI_COMMAND=mineru  # 默认值；如装在其他路径请指定完整路径
MINERU_METHOD=auto
MINERU_BACKEND=pipeline    # pipeline / vlm / hybrid
MINERU_EFFORT=medium       # low / medium / high
MINERU_LANG=ch
```

未配置 `MINERU_API_TOKEN` 时自动走 CLI 模式，会在项目根的临时目录下生成 `output/{stem}/{method或vlm}/`，依次尝试读取 `{stem}.md` → `{stem}_content_list.json` → `{stem}_middle.json`。

### 候选论文检索结果不准怎么办

候选评分公式见 [元数据校验链路](#元数据校验链路)。常见调优方向：

- **标题不准**：本地 PDF 提取的标题过短或过长会影响评分。可以调高 `PAPER_SEARCH_MAX_CANDIDATES`（默认 5）让更多候选参与比对
- **DOI / arXiv 强匹配**：在上传时尽量提供 DOI 或 arXiv ID，命中精确匹配（+0.30）比纯标题匹配更可靠
- **被引论文被错误匹配为正本**：`_candidate_looks_like_reference_target` 已经做了保护，但特定场景仍可能误判，可以调整该函数的关键词规则

### 上传的论文被分到"其他"

分类 Agent 不确定时强制输出 `other`，避免误分类。检查：

1. 默认通用分类是否满足需求，或参考[自定义分类](#自定义分类)按研究方向调整
2. 论文是否跨方向过强，提示词中可以适当放低 `other` 阈值
3. 反思 Agent 可能在 `repair_targets` 中要求重新分类，看 `reflection_feedback` 中的 `issues`

---

## License

MIT
