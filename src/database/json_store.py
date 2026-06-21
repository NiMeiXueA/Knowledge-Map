from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.config import ANALYSIS_DIR, CATEGORY_DEFINITIONS, PAPERS_JSON_PATH, ensure_runtime_dirs
from src.schemas import CategoryModel, PaperCollection, PaperModel


def _seed_collection() -> PaperCollection:
    """创建初始论文集合（包含预定义分类）"""
    return PaperCollection(
        categories=[
            CategoryModel(
                id=item.id,
                name=item.name,
                folder=item.folder,
                why=item.why,
                advantages=item.advantages,
                disadvantages=item.disadvantages,
            )
            for item in CATEGORY_DEFINITIONS
        ],
        papers=[],
    )


def ensure_data_files() -> None:
    """确保数据文件存在（如不存在则创建初始集合）"""
    ensure_runtime_dirs()
    if not PAPERS_JSON_PATH.exists():
        save_collection(_seed_collection())


def load_collection() -> PaperCollection:
    """加载论文集合"""
    ensure_data_files()
    data = json.loads(PAPERS_JSON_PATH.read_text(encoding="utf-8"))
    return PaperCollection.model_validate(data)


def save_collection(collection: PaperCollection) -> None:
    """保存论文集合到JSON文件"""
    ensure_runtime_dirs()
    PAPERS_JSON_PATH.write_text(
        json.dumps(collection.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def upsert_paper(paper: PaperModel) -> None:
    """
    插入或更新论文
    
    如果论文ID已存在则更新，否则插入新论文
    保存后按年份和简称排序
    """
    collection = load_collection()
    remaining = [item for item in collection.papers if item.id != paper.id]
    remaining.append(paper)
    remaining.sort(key=lambda item: ((item.year or 9999), item.short.lower()))
    collection.papers = remaining
    save_collection(collection)


def patch_paper(paper_id: str, fields: dict) -> PaperModel | None:
    """
    部分更新论文字段
    
    Args:
        paper_id: 论文ID
        fields: 要更新的字段字典
        
    Returns:
        更新后的论文模型，或None（如果未找到）
    """
    collection = load_collection()
    for index, paper in enumerate(collection.papers):
        if paper.id != paper_id:
            continue
        payload = paper.model_dump()
        payload.update({key: value for key, value in fields.items() if value is not None})
        payload["updated_at"] = datetime.now(timezone.utc)
        updated = PaperModel.model_validate(payload)
        collection.papers[index] = updated
        save_collection(collection)
        save_analysis_json(updated)
        return updated
    return None


def save_analysis_json(paper: PaperModel) -> Path:
    """
    保存论文分析结果到单独的JSON文件
    
    文件路径：src/data/analysis/{paper_id}.json
    
    Args:
        paper: 论文模型
        
    Returns:
        保存的文件路径
    """
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    target = ANALYSIS_DIR / f"{paper.id}.json"
    target.write_text(
        json.dumps(paper.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return target


def list_categories() -> list[CategoryModel]:
    """获取当前分类列表"""
    return load_collection().categories


def add_category(category: CategoryModel) -> list[CategoryModel]:
    """新增分类"""
    collection = load_collection()
    if any(item.id == category.id for item in collection.categories):
        raise ValueError("分类 ID 已存在")
    collection.categories.append(category)
    collection.categories.sort(key=lambda item: item.name)
    save_collection(collection)
    return collection.categories


def update_category(category_id: str, next_category: CategoryModel) -> CategoryModel | None:
    """更新分类，并同步修正论文上的分类 ID"""
    collection = load_collection()
    target_index: int | None = None

    for index, category in enumerate(collection.categories):
        if category.id == category_id:
            target_index = index
            continue
        if category.id == next_category.id:
            raise ValueError("新的分类 ID 已存在")

    if target_index is None:
        return None

    collection.categories[target_index] = next_category

    if category_id != next_category.id:
        for paper in collection.papers:
            paper.categories = [next_category.id if item == category_id else item for item in paper.categories]
            save_analysis_json(paper)

    save_collection(collection)
    return next_category


def delete_category(category_id: str) -> bool:
    """删除分类，并同步从论文分类中移除"""
    collection = load_collection()
    remaining = [item for item in collection.categories if item.id != category_id]
    if len(remaining) == len(collection.categories):
        return False

    fallback_category = next((item.id for item in remaining if item.id == "other"), None)
    for paper in collection.papers:
        updated_categories = [item for item in paper.categories if item != category_id]
        if not updated_categories and fallback_category:
            updated_categories = [fallback_category]
        paper.categories = updated_categories
        save_analysis_json(paper)

    collection.categories = remaining
    save_collection(collection)
    return True
