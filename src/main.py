from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from src.agents.graph import run_analysis
from src.config import UPLOADS_DIR, ensure_runtime_dirs
from src.database.json_store import (
    add_category,
    delete_category,
    ensure_data_files,
    list_categories,
    load_collection,
    patch_paper,
    update_category,
)
from src.database.kv import KVRepository
from src.llm.provider import LLMConfigurationError, LLMJSONParseError
from src.llm.settings import get_model_settings_summary, save_model_settings
from src.schemas import CategoryCreateIn, CategoryModel, CategoryUpdateIn, GraphPayload, MineruSettingsIn, MineruSettingsSummary, ModelSettingsIn, PaperAnalysisPatch, UploadResponse
from src.services.mineru_settings import get_mineru_settings_summary, save_mineru_settings
from src.services.paper_graph_builder import build_graph_payload

# 创建FastAPI应用实例
app = FastAPI(title="Knowledge Map API")

# 配置CORS中间件，允许前端跨域访问
# - http://localhost:\d+   开发模式（Vite 5173 / 8000 等）
# - http://127.0.0.1:\d+   桌面模式或本地直连
# - tauri://localhost      macOS / Linux Tauri WebView 的 origin
# - http://tauri.localhost  Windows Tauri WebView 的 origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "tauri://localhost",
        "http://tauri.localhost",
    ],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Redis键值存储仓库实例
kv = KVRepository()


@app.on_event("startup")
async def startup_event() -> None:
    """应用启动事件：确保运行时目录和数据文件存在"""
    ensure_runtime_dirs()
    ensure_data_files()


@app.get("/api/health")
async def health() -> dict:
    """健康检查接口"""
    return {"status": "ok"}


@app.get("/api/papers")
async def list_papers() -> dict:
    """获取所有论文列表"""
    return load_collection().model_dump(mode="json")


@app.get("/api/papers/{paper_id}")
async def get_paper(paper_id: str) -> dict:
    """根据论文ID获取单篇论文详情"""
    collection = load_collection()
    for paper in collection.papers:
        if paper.id == paper_id:
            return paper.model_dump(mode="json")
    raise HTTPException(status_code=404, detail="Paper not found")


async def _run_task(task_id: str, paper_inputs: list[tuple[str, str]]) -> None:
    """后台任务：逐个处理上传的PDF文件"""
    for pdf_path, reference in paper_inputs:
        try:
            await run_analysis(task_id, pdf_path, reference=reference)
        except LLMConfigurationError as exc:
            # LLM配置错误（如未配置API Key）
            kv.set_task(task_id, status="failed", stage="metadata", message=str(exc), error=str(exc))
            return
        except LLMJSONParseError as exc:
            # LLM返回的JSON无法解析
            kv.set_task(
                task_id,
                status="failed",
                stage="llm_json_parse",
                message=f"论文分析失败：{exc}",
                error=str(exc),
            )
            return
        except Exception as exc:
            # 其他未预期的异常
            kv.set_task(
                task_id,
                status="failed",
                stage="processing",
                message=f"论文分析失败：{exc}",
                error=str(exc),
            )
            return


@app.post("/api/papers/upload", response_model=UploadResponse)
async def upload_papers(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    references: list[str] = Form(...),
) -> UploadResponse:
    """论文上传接口：每篇 PDF 必须同时提供 DOI / arXiv / 论文链接"""
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")
    cleaned_references = [item.strip() for item in references if item and item.strip()]
    if not cleaned_references:
        raise HTTPException(status_code=400, detail="请同时提供 DOI / arXiv / 论文链接")
    if len(cleaned_references) != len(files):
        raise HTTPException(status_code=400, detail="PDF 数量必须和 DOI / arXiv / 论文链接数量一致")
    
    # 检查是否已配置API密钥
    summary = get_model_settings_summary()
    if not summary.api_key_configured:
        raise HTTPException(status_code=400, detail="请先配置 API / 模型")

    # 创建上传目录并保存文件
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    task_id = uuid.uuid4().hex  # 生成唯一任务ID
    paper_inputs: list[tuple[str, str]] = []

    for file, reference in zip(files, cleaned_references):
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="仅支持 PDF 文件上传")
        # 使用UUID重命名文件，避免重名冲突
        target = UPLOADS_DIR / f"{uuid.uuid4().hex}-{Path(file.filename).name}"
        with target.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        paper_inputs.append((str(target), reference))

    # 创建任务状态并启动后台分析
    kv.set_task(task_id, status="processing", stage="queued", message="任务已创建，等待分析")
    background_tasks.add_task(_run_task, task_id, paper_inputs)
    return UploadResponse(task_id=task_id, status="processing")


@app.get("/api/papers/tasks/{task_id}")
async def get_task(task_id: str) -> dict:
    """查询任务状态"""
    task = kv.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.post("/api/settings/model")
async def save_settings(payload: ModelSettingsIn) -> dict:
    """保存LLM模型设置（API Key、模型名称等）"""
    return save_model_settings(payload).model_dump()


@app.get("/api/settings/model")
async def get_settings() -> dict:
    """获取当前模型设置摘要（不包含API Key明文）"""
    return get_model_settings_summary().model_dump()


@app.get("/api/settings/mineru", response_model=MineruSettingsSummary)
async def get_mineru_settings() -> MineruSettingsSummary:
    """获取 MinerU 远程解析配置摘要（不含 token 明文）"""
    return get_mineru_settings_summary()


@app.post("/api/settings/mineru", response_model=MineruSettingsSummary)
async def save_mineru_settings_api(payload: MineruSettingsIn) -> MineruSettingsSummary:
    """保存 MinerU 远程解析配置到 .env，配置后所有 PDF 自动走云端解析"""
    return save_mineru_settings(payload)


@app.get("/api/graph", response_model=GraphPayload)
async def get_graph() -> GraphPayload:
    """获取论文关系图数据（节点和边）"""
    return build_graph_payload()


@app.get("/api/categories", response_model=list[CategoryModel])
async def get_categories() -> list[CategoryModel]:
    """获取分类列表"""
    return list_categories()


@app.post("/api/categories", response_model=list[CategoryModel])
async def create_category(payload: CategoryCreateIn) -> list[CategoryModel]:
    """创建分类"""
    try:
        return add_category(CategoryModel(**payload.model_dump()))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.put("/api/categories/{category_id}", response_model=CategoryModel)
async def save_category(category_id: str, payload: CategoryUpdateIn) -> CategoryModel:
    """更新分类"""
    try:
        updated = update_category(category_id, CategoryModel(**payload.model_dump()))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if updated is None:
        raise HTTPException(status_code=404, detail="Category not found")
    return updated


@app.delete("/api/categories/{category_id}")
async def remove_category(category_id: str) -> dict:
    """删除分类"""
    removed = delete_category(category_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Category not found")
    return {"ok": True}


@app.patch("/api/papers/{paper_id}/analysis")
async def patch_paper_analysis(paper_id: str, payload: PaperAnalysisPatch) -> dict:
    """部分更新论文分析结果（如手动修正摘要、创新点等）"""
    updated = patch_paper(paper_id, payload.model_dump(exclude_none=True))
    if updated is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    return updated.model_dump(mode="json")
