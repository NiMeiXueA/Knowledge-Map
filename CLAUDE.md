# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Knowledge Map 是一个论文知识地图系统，支持两种运行模式：
- **Web 模式**：FastAPI（`src/`）+ React（`front/`）+ Redis，前后端分离开发
- **桌面模式**：Tauri（`src-tauri/`）+ React + FastAPI sidecar（PyInstaller 单文件 exe），双击 exe 即用

后端通过 LangGraph 编排 13 个节点完成 PDF 上传到关系图构建的全流程：解析 PDF → 提取元数据 → 联网校验 → 分类 → 创新点/局限性分析 → 反思自检 → 保存 → 关系图。

## 常用命令

### Web 模式开发

```bash
# 后端（二选一）
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
python desktop/backend/run_backend.py    # 桌面后端启动脚本，含端口探测

# 前端
cd front && npm install && npm run dev    # http://localhost:5173

# Redis（可选，不可用时自动降级到 src/data/runtime_kv.json）
docker compose up -d
```

### Tauri 桌面模式

```bash
# 首次或后端代码变更后，先打包 sidecar（PyInstaller → src-tauri/binaries/）
powershell -ExecutionPolicy Bypass -File desktop/backend/build_backend.ps1

# 桌面开发（自动拉起 Vite dev server）
npm run tauri:dev

# 桌面打包（MSI / NSIS 安装包）
npm run tauri:build
```

仓库未配置测试框架与 linter，没有 `npm test` / `pytest` 流程。

## 架构要点

### 桌面模式启动协议（关键设计）

`src-tauri/src/main.rs` 与 `desktop/backend/run_backend.py` 之间通过 **stdout 协议行** 通信，不是 IPC：

1. Tauri 启动时把 `%APPDATA%\Knowledge-Map` 通过 `KNOWLEDGE_MAP_DATA_DIR` 注入给 sidecar
2. Sidecar 探测可用端口（默认 8000，被占用则尝试 8001-8003），输出 `KNOWLEDGE_MAP_LISTENING_ON http://127.0.0.1:PORT`
3. Sidecar 自检 `/api/health` 通过后输出 `KNOWLEDGE_MAP_READY`
4. Tauri 收到 LISTENING 后做健康检查（最长 90s），通过后用 `window.eval` 注入 `window.__KNOWLEDGE_MAP_API_URL__`
5. 前端 `front/src/api/config.ts` 按优先级解析 API 地址：`VITE_API_BASE_URL` → `window.__KNOWLEDGE_MAP_API_URL__` → `http://127.0.0.1:8000`

修改 sidecar 启动逻辑时，**不要破坏这三个 stdout 协议行**，否则 Tauri 会一直等待后端就绪。

### 数据目录重定向

`src/config.py` 的 `_resolve_data_root()` 通过 `KNOWLEDGE_MAP_DATA_DIR` 决定 papers.json / analysis / uploads / paper / runtime_kv.json 的落点。开发模式默认走 `src/data/`，桌面模式由 Tauri 注入到用户目录。**所有路径必须从 `config.py` 的常量取**（`DATA_DIR`、`ANALYSIS_DIR`、`PAPER_DIR`、`UPLOADS_DIR`、`PAPERS_JSON_PATH`、`ENV_PATH`），不要硬编码 `src/data/...`。

`.env` 文件位置同样可重定向（`_resolve_env_path()`）：桌面模式落在 `KNOWLEDGE_MAP_DATA_DIR/.env`，API Key 通过 `/api/settings/model` 接口由 `src/llm/settings.py` 用 `python-dotenv` 的 `set_key` 写回。

### Redis 降级链路

`src/database/redis_client.py::RedisBackedStore` 在 Redis 不可用时自动降级到**内存 + 文件**（`runtime_kv.json`，原子写：先写 `.tmp` 再 rename），所有读写都做 try/except 兜底。任务状态、元数据缓存等都要能在纯文件模式下工作——不要把 Redis 当强依赖。`KVRepository` 的键命名约定：`task:{id}` / `paper:{id}:{suffix}` / `settings:model`。

### LangGraph 工作流

`src/agents/graph.py` 是后端核心，13 个节点用 `StateGraph` 串联：

```
parse_pdf → extract_metadata → source_agent → save_metadata_to_kv → classify_paper
  → move_pdf_to_category → innovation_agent → limitation_agent → reflection_agent
  → [repair ↔ reflection_agent]（最多重试 2 次）
  → save_final_json → build_relationship → finish
```

关键设计：
- 反思节点（`reflection_agent`）后用条件边 `_route_after_reflection` 分流：通过 → 保存；未通过且 `retry_count < 2` → `repair` → 回到反思；超过重试上限 → 保存但置 `needs_human_review=True`
- LLM 调用统一走 `src/llm/provider.py::UnifiedLLMProvider.complete_json`，自带 JSON 解析重试（`_parse_json_content` 支持 ```json 代码块、裸 `{...}`、`[...]` 等多种格式）
- 状态归一化集中在 `_normalize_state_for_save` 和 `_normalize_innovation_points` / `_normalize_limitation_points`，**Agent 节点本身不要重复归一化逻辑**
- `repair` 节点支持 4 个修复目标：`innovation_agent` / `limitation_agent` / `source_agent` / `classify_agent`，由反思 Agent 返回的 `repair_targets` 数组驱动

### Agent 层职责

各 Agent（`src/agents/*.py`）只负责构造提示词并调用 provider，返回 dict 给 graph 编排器。每个 Agent 用独立 `trace_label` 标识（`innovation_agent` / `limitation_agent` / `reflection_agent` / `source_agent.metadata_reconcile`）。**不要在 Agent 里写状态持久化、字段归一化、异常兜底**——那些都在 `graph.py` 的节点包装函数里处理。

特别约束：**`idea` 字段只能写论文的核心方法机制 1-2 句，禁止结果性表述**（"实验表明"、"优于其他方法"、"更快收敛"、"性能更好"、"显著提升"）。提示词里强制 + `paper_record_cleaner.normalize_idea_text` 后处理双重保险。修改 innovation_agent 提示词时不要放松这条约束。

### 元数据校验三级链路（核心架构）

论文标题/作者/年份的获取走 `src/services/paper_metadata_pipeline.py`，三级来源：

1. **本地 PDF 提取**（`metadata_extractor.py`）：正则启发式，从首页 24 行提取标题/作者、`abstract` / `summary` 关键字后取摘要、`references` 部分按 `[1]`/`1.` 分割最多 40 条引用。本地置信度 = 0.25 基础分 + 标题≥20字(+0.2) + 有作者(+0.15) + 摘要≥120字(+0.2) + 有DOI(+0.15) + 有arXiv ID(+0.05)，封顶 0.95。
2. **联网检索**（`external_paper_lookup.py`）：按 DOI / arXiv ID / 标题分别查询 Crossref、Semantic Scholar、arXiv，返回最多 `PAPER_SEARCH_MAX_CANDIDATES` 条（默认 5）。
3. **LLM 比对**（`_reconcile_with_llm`）：把本地结果 + 联网候选 + PDF 摘要交给 LLM 选最可信的，失败时降级到 `_fallback_reconcile`（按最高分候选对齐）。

**候选评分公式**（`_score_candidate`）必须读懂再改：

```
score = 0.45 * title_similarity(SequenceMatcher)
      + 0.2  * author_overlap_ratio
      + doi_bonus      (本地DOI 匹配 +0.3 / 候选DOI 出现在原文 +0.2)
      + arxiv_bonus    (本地arXiv 匹配 +0.3 / 候选arXiv 出现在原文 +0.15)
      + abstract_score (有摘要 +0.1)
      + citation_bonus (每条引用 +0.02, 上限 +0.08)
      + provider_bonus (DOI 渠道 +0.18 / Crossref 渠道 +0.08 / 其他 +0.05)
      - cited_penalty  (疑似被引论文 -0.18)
```

特殊坑：`_candidate_looks_like_reference_target` 识别**被引论文被错误识别为正本**的情况，会扣 0.18 分。修改评分逻辑时不要破坏这个保护。

**引用提取（关系图命脉）**：关系图只由引用构建，所以引用必须准。`_finalize_metadata` 在 PDF 模式（`allow_llm=True`）下额外调一次 `_extract_citations_with_llm`——把 `metadata_extractor.extract_references_text` 截出的 References 原文（≤12000 字符）交给 LLM（`trace_label=source_agent.citation_extract`）切出结构化 `title/authors/year`，再与本地正则 + 联网候选用 `merge_citations` 三层合并去重。LLM 失败 / References 缺失时返回空，自动回退到本地+联网结果。`reference` 纯输入模式（`allow_llm=False`）跳过此步。修改引用相关逻辑时，确保 `_extract_citations_with_llm` 产出的 title 与 `paper_graph_builder._title_variants` 的归一化对齐，否则边连不上。

### PDF 解析四级降级

`src/services/pdf_loader.py::extract_pdf_text` 按 `PDF_PARSER_BACKEND` 配置降级：

| 配置 | 路径 |
|------|------|
| `mineru` | 仅 MinerU，失败抛错 |
| `auto`（默认） | MinerU → 失败回退 PyMuPDF → 失败回退 pypdf |
| 其他 | 直接 PyMuPDF → pypdf |

**MinerU 自身两种模式**（看 `MINERU_API_TOKEN` 是否配置）：
- **远程 API**：申请上传链接 → PUT 上传 → 轮询 `extract-results/batch/{batch_id}` 直到 `state=done` → 下载 `full_zip_url` → 解压读 `full.md`
- **本地 CLI**：调用 `mineru` 命令行，从 `output/{stem}/{method|vlm|hybrid_method}/` 读 `.md` / `_content_list.json` / `_middle.json`

扫描版检测：文本长度 < `OCR_MIN_TEXT_LENGTH`（默认 500）→ 触发 OCR。OCR 流程：PyMuPDF 渲染页面为 PNG（matrix 2x）→ pytesseract 识别（`chi_sim+eng`）。`OCR_ENABLED=false` 时跳过。

### 论文 ID 与文件命名

`src/services/paper_file_manager.py`：

- `slugify_paper_id(title)`：标题转小写 → 非 `[a-z0-9一-鿿]` 替换为 `-` → 截断到 80 字符
- `ensure_unique_paper_id`：冲突时追加 `-2` / `-3`（注意 graph.py 调用时传入了 `existing_ids - {self}` 避免把自己当冲突）
- `move_pdf_to_category(source, folder, paper_id)`：移到 `paper/{folder}/{paper_id}.pdf`，文件名只保留 `[A-Za-z0-9一-鿿._-]`，其他替换为 `_`，文件已存在时追加 `-2.pdf`

`paper/short` 字段（图谱节点显示名）**优先由分类 Agent 在 `classify_paper` 时一并产出**（LLM 已读标题/摘要/正文，取学界常用缩写最准，如 BERT / FedAvg）。提示词约束长度 2-24 字符，`graph.py::save_final_json_node` 用 `paper_record_cleaner.normalize_short` 做清洗（去引号/句号、限长），清洗失败或 Agent 未给时**回退**到启发式 `build_paper_short`：括号显式缩写 `(BERT)` → `called XXX` 模式 → 标题首字母缩写（3-10 字母，需在原文出现 ≥ 2 次）→ 截断到 5 词 48 字符。修改 `classify_agent.py` 提示词时不要丢掉 `short` 输出字段。

### 关系图构建

`src/services/paper_graph_builder.py` **只生成引用边**（不再人为串联同分类论文）：

- **`citation`**：论文 `citations` 列表中的标题（经 `_title_variants` 归一化：小写 + 去尾标点 + 合并空白）能匹配到库内已有论文标题时，连 `被引论文 → 引用方` 的边；匹配命中自己则跳过。

没有真实引用关系的论文之间不出现任何边。因此**引用提取的准确性直接决定关系图质量**——见下文「元数据校验」中的 LLM 引用提取。

边按 `(source, target, type)` 去重。`sync_relationships_into_papers` 把关系反向写回 papers.json，存到每篇论文的 `relationships` 字段（注意：analysis JSON 里**不存 relationships**，只在 papers.json 主索引中维护）。

前端 `PaperNetworkGraph.tsx`（SVG, viewBox 1120×680）会再次按论文年份调整边的方向（早 → 晚），并支持节点拖拽 / 画布平移 / 分类筛选 / 分类配色（9 个分类有固定颜色映射）。`isCoreLink` 把 `citation` 视为主线边。

### JSON 存储约定

`src/database/json_store.py`：

- `upsert_paper` 保存后自动按 `(year ASC, short.lower())` 排序，新论文插入位置由排序决定
- `update_category` 改分类 ID 时会**同步修正所有论文的 `categories` 数组**
- `delete_category` 时该分类下的论文会归入 `other`（找不到 other 则清空分类）
- `save_analysis_json` 落到 `ANALYSIS_DIR/{paper_id}.json`
- `ensure_data_files` 在 papers.json 不存在时用 `_seed_collection` 创建包含 `CATEGORY_DEFINITIONS` 的初始集合

### 前端结构

`front/src/App.tsx` 用 `BrowserRouter` 注册三条路由：

| 路径 | 组件 | 作用 |
|------|------|------|
| `/` | `KnowledgeMapPage` | 首页路线图：分类时间线 + 论文搜索 + 上传 + 设置 |
| `/network` | `NetworkPage` | 论文关系图（PaperNetworkGraph） |
| `/paper/:paperId` | `PaperDetailPage` | 单篇论文详情 |

`App` 组件在顶层拉一次 `/api/papers` 缓存到 state，并通过 `refresh` 回调下放给 KnowledgeMapPage。上传流程在 `PaperUploadModal.tsx` 里**每 1800ms 轮询** `/api/papers/tasks/{task_id}`，直到 status 变为 `completed` 或 `failed`。

前端类型定义在 `front/src/types/paper.ts`，与后端 `src/schemas.py` 一一对应。

### 自定义分类

仓库默认提供一套**面向任意领域的通用分类**（核心方法 / 改进与扩展 / 理论与分析 / 应用与系统 / 数据与评测 / 综述与展望 / 其他），按“研究贡献类型”而非具体领域划分。改成自己研究方向的分类只需改一处：
1. `src/config.py` 的 `CATEGORY_DEFINITIONS`（id / name / folder / why / advantages / disadvantages）

`src/agents/classify_agent.py` 的分类提示词已是通用的“论文分类助手”，会严格按 `CATEGORY_DEFINITIONS` 归类，无需随领域改动。`paper/` 下的分类文件夹会在启动时由 `ensure_runtime_dirs()` 按 `folder` 字段自动创建。前端 `PaperNetworkGraph.tsx` 里的 `categoryColors` 覆盖了默认分类 ID；新增分类若不在映射里会走 `FALLBACK_PALETTE` 按 hash 取色兜底（不会无色）。

## 打包排障

### 体积控制（重要）

sidecar exe 体积直接由「打包用的 Python 环境」决定——在装了一堆无关库的全局环境里跑 PyInstaller，numpy/pandas/matplotlib/pytest 等会被一起打进去，exe 轻松上百 MB。正确做法：**只在干净 venv 里打包**。

```powershell
# 1. 建干净虚拟环境（只装 requirements.txt + pyinstaller）
powershell -ExecutionPolicy Bypass -File scripts/setup_clean_env.ps1

# 2. 让 build_backend.ps1 用这个环境打包
$env:BUILD_PYTHON = ".\.venv-build\Scripts\python.exe"
powershell -ExecutionPolicy Bypass -File desktop/backend/build_backend.ps1
```

`requirements.txt` 刻意保持精简（无 uvloop/httptools/websockets/watchfiles——桌面模式用裸 `uvicorn`，不开 reload、不用 WebSocket）。`build_backend.ps1` 还预设了 `--exclude-module`（tkinter / pytest / sphinx / matplotlib / IPython / jupyter 等），即便环境略脏也兜底排除。`PIL._tkinter_finder` 不要加回 hidden imports——它会把 tkinter 拉进来。若未来真引入了被排除的库（例如用 matplotlib 画图），记得同步从 `excludeModules` 移除。

### hidden imports

PyInstaller 容易漏 hidden imports，`desktop/backend/build_backend.ps1` 已预设 `langgraph / pydantic / fastapi / uvicorn / redis` 的 `--collect-submodules`。新增 Python 依赖后报 `ModuleNotFoundError` 时，用环境变量追加：

```powershell
$env:PYINSTALLER_HIDDEN_IMPORTS = "新模块名"
powershell -ExecutionPolicy Bypass -File desktop/backend/build_backend.ps1
```

打包后的 sidecar 必须命名为 `knowledge-map-backend-<target-triple>.exe`（如 `knowledge-map-backend-x86_64-pc-windows-msvc.exe`）放在 `src-tauri/binaries/`，Tauri 通过 `tauri.conf.json` 的 `externalBin` 加载——这个命名约定由 `resolve_sidecar()` 在 Rust 端拼出来，不要随意改名。

## 关键约束清单

修改代码前必须知道的几条"看不见的约定"：

- **CORS** 已放行 `http://localhost:5173`、`tauri://localhost`、`http://tauri.localhost` 以及 `http://(localhost|127\.0\.0\.1):\d+` 正则——新增前端 origin 通常不需要改
- **上传接口**强制要求每个 PDF 配一行 DOI / arXiv / 论文链接（`references` 数组长度必须等于 `files`），用作元数据检索 hint
- **LLM Provider URL 构造**（`_build_openai_chat_url`）：base_url 已含 `/chat/completions` 直接用 / 以 `/v1` 结尾追加 / 空路径追加 `/v1/chat/completions` / 其他追加 `/chat/completions`
- **OpenAI 调用固定带 `response_format: {"type": "json_object"}`**——若换成不支持该参数的 OpenAI 兼容服务，需要改 provider.py
- **Anthropic 调用**走固定 `https://api.anthropic.com/v1/messages`，base_url 配置对它无效
