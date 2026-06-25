from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


def _resolve_data_root() -> Path:
    """
    解析数据根目录。

    优先级：
    1. 环境变量 KNOWLEDGE_MAP_DATA_DIR（桌面模式由 Tauri 注入，或用户手动指定）
    2. 项目根目录下的 src/data（开发模式保持原有行为）

    桌面模式下数据写入用户目录而非安装目录，可以避免权限问题和卸载时丢失数据。
    """
    override = os.getenv("KNOWLEDGE_MAP_DATA_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return Path(__file__).resolve().parent.parent / "src" / "data"


def _resolve_env_path() -> Path:
    """
    解析 .env 文件位置。

    - 如果用户显式指定了 KNOWLEDGE_MAP_ENV_PATH，使用该路径
    - 否则优先使用项目根目录下的 .env（开发模式常见）
    - 桌面模式下，Tauri 会通过 KNOWLEDGE_MAP_DATA_DIR 指向用户数据目录，
      此时 .env 也会落在该目录下
    """
    explicit = os.getenv("KNOWLEDGE_MAP_ENV_PATH", "").strip()
    if explicit:
        return Path(explicit).expanduser().resolve()

    data_dir_env = DATA_DIR / ".env"
    project_env = BASE_DIR / ".env"
    if data_dir_env.exists():
        return data_dir_env
    if project_env.exists():
        return project_env
    # 默认落点：跟随 DATA_DIR，桌面模式下会写入用户数据目录
    return data_dir_env


# 基础目录配置
BASE_DIR = Path(__file__).resolve().parent.parent  # 项目根目录
DATA_DIR = _resolve_data_root()  # 数据根目录（可在桌面模式下重定向）
ANALYSIS_DIR = DATA_DIR / "analysis"  # 分析结果目录
PAPERS_JSON_PATH = DATA_DIR / "papers.json"  # 论文集合JSON文件路径
UPLOADS_DIR = DATA_DIR / "uploads"  # 上传文件暂存目录
PAPER_DIR = DATA_DIR / "paper"  # 论文PDF存放目录

ENV_PATH = _resolve_env_path()  # 环境变量文件路径

# 加载 .env：必须在 ENV_PATH 计算完成之后调用
#（dotenv 默认只读，不会写入；用户通过 API 修改模型设置时由 settings.py 写回）
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
else:
    load_dotenv()


@dataclass(frozen=True)
class CategoryDefinition:
    """论文分类定义数据类"""
    id: str  # 分类ID
    name: str  # 分类名称
    folder: str  # 对应的文件夹名称
    why: str  # 为什么需要这个分类
    advantages: str  # 该分类的优势
    disadvantages: str  # 该分类的劣势


# 论文分类定义列表：面向任意研究领域的通用论文技术路线图分类。
# 按“研究贡献类型”而非具体领域划分，便于把任何方向的论文组织成发展脉络。
CATEGORY_DEFINITIONS: list[CategoryDefinition] = [
    CategoryDefinition(
        id="core_method",
        name="核心方法",
        folder="01_核心方法",
        why="提出新的核心方法、模型、算法或框架，通常是该方向后续工作的出发点。",
        advantages="贡献清晰，适合作为技术路线图的主干与统一比较基线。",
        disadvantages="往往只解决最核心的问题，对边缘场景和约束考虑有限。",
    ),
    CategoryDefinition(
        id="improvement",
        name="改进与扩展",
        folder="02_改进与扩展",
        why="在已有方法上做改进、优化、变体或扩展，体现技术演进路线。",
        advantages="能针对已有方法的不足进行针对性提升，衔接性强。",
        disadvantages="依赖前序工作作为背景，独立性较弱。",
    ),
    CategoryDefinition(
        id="theory",
        name="理论与分析",
        folder="03_理论与分析",
        why="侧重理论推导、复杂度分析、收敛性或机理证明，为方法提供基础支撑。",
        advantages="结论严谨，能解释方法为何有效。",
        disadvantages="通常不直接给出可复用的工程实现。",
    ),
    CategoryDefinition(
        id="application",
        name="应用与系统",
        folder="04_应用与系统",
        why="面向实际场景或系统的工程实现、部署与落地，是研究走向应用的关键。",
        advantages="贴近真实需求，可直接复用或迁移。",
        disadvantages="受具体场景约束，泛化性与公平比较较难保证。",
    ),
    CategoryDefinition(
        id="benchmark",
        name="数据与评测",
        folder="05_数据与评测",
        why="提供数据集、评测方法、基准测试或系统性的实验分析，规范领域评价。",
        advantages="帮助建立统一的评测框架和可比较结论。",
        disadvantages="结论受数据与指标选取影响，时效性可能受限。",
    ),
    CategoryDefinition(
        id="survey",
        name="综述与展望",
        folder="06_综述与展望",
        why="梳理研究脉络、背景与发展方向，适合作为阅读地图的地基与入口。",
        advantages="帮助快速建立全局认知和比较框架。",
        disadvantages="通常不直接给出可复用的具体算法。",
    ),
    CategoryDefinition(
        id="other",
        name="其他",
        folder="其他",
        why="用于暂时无法稳定归类、信息不足或方向交叉过强的论文。",
        advantages="避免误分，便于后续人工复审。",
        disadvantages="自动路线图的可解释性会略弱。",
    ),
]

CATEGORY_MAP = {item.id: item for item in CATEGORY_DEFINITIONS}  # 分类ID到定义的映射字典


def ensure_runtime_dirs() -> None:
    """确保所有运行时必要的目录存在"""
    for path in (DATA_DIR, ANALYSIS_DIR, UPLOADS_DIR, PAPER_DIR):
        path.mkdir(parents=True, exist_ok=True)
    # paper/ 下的分类子目录以 papers.json 中实际 categories 为准；
    # papers.json 不存在时退回到 CATEGORY_DEFINITIONS（首次启动的初始化路径）
    folders = _collect_category_folders()
    for folder in folders:
        (PAPER_DIR / folder).mkdir(parents=True, exist_ok=True)


def _collect_category_folders() -> list[str]:
    """收集当前应当存在的分类文件夹名"""
    import json

    if PAPERS_JSON_PATH.exists():
        try:
            data = json.loads(PAPERS_JSON_PATH.read_text(encoding="utf-8"))
            folders = [item.get("folder") for item in data.get("categories", [])]
            return [item for item in folders if item]
        except (OSError, ValueError, KeyError):
            pass
    return [item.folder for item in CATEGORY_DEFINITIONS]


def get_env(name: str, default: Any = None) -> Any:
    """获取环境变量，支持默认值"""
    return os.getenv(name, default)


def get_bool_env(name: str, default: bool = False) -> bool:
    """获取布尔类型的环境变量，支持多种真值格式"""
    value = str(os.getenv(name, str(default))).strip().lower()
    return value in {"1", "true", "yes", "on"}
