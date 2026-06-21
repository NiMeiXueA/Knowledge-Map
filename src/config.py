from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
import os

load_dotenv()

# 基础目录配置
BASE_DIR = Path(__file__).resolve().parent.parent  # 项目根目录
DATA_DIR = BASE_DIR / "src" / "data"  # 数据目录
ANALYSIS_DIR = DATA_DIR / "analysis"  # 分析结果目录
PAPERS_JSON_PATH = DATA_DIR / "papers.json"  # 论文集合JSON文件路径
UPLOADS_DIR = BASE_DIR / "uploads"  # 上传文件暂存目录
PAPER_DIR = BASE_DIR / "paper"  # 论文PDF存放目录
ENV_PATH = BASE_DIR / ".env"  # 环境变量文件路径


@dataclass(frozen=True)
class CategoryDefinition:
    """论文分类定义数据类"""
    id: str  # 分类ID
    name: str  # 分类名称
    folder: str  # 对应的文件夹名称
    why: str  # 为什么需要这个分类
    advantages: str  # 该分类的优势
    disadvantages: str  # 该分类的劣势


# 论文分类定义列表，定义了联邦学习领域的9个主要研究方向
CATEGORY_DEFINITIONS: list[CategoryDefinition] = [
    CategoryDefinition(
        id="optimization",
        name="基础联邦优化",
        folder="01_基础联邦优化",
        why="关注联邦训练最核心的聚合、收敛和通信效率问题，是后续绝大多数联邦方法的出发点。",
        advantages="概念清晰、方法成熟、适合作为统一比较基线。",
        disadvantages="对异构分布、个性化需求和复杂系统约束的处理有限。",
    ),
    CategoryDefinition(
        id="personalization",
        name="个性化联邦学习",
        folder="02_个性化联邦学习",
        why="面向客户端数据分布差异显著的场景，让每个参与方获得更适合自身的数据模型。",
        advantages="能显著缓解 non-IID 带来的性能退化。",
        disadvantages="统一评价更难，部署与维护成本更高。",
    ),
    CategoryDefinition(
        id="distillation",
        name="知识蒸馏与异构联邦",
        folder="03_知识蒸馏与异构联邦",
        why="解决模型结构不一致、通信预算有限或需要更细粒度知识传递的场景。",
        advantages="更灵活地支持异构模型和轻量知识交换。",
        disadvantages="蒸馏效果依赖知识载体设计，稳定性和解释性较难保证。",
    ),
    CategoryDefinition(
        id="graph",
        name="图联邦学习",
        folder="04_图联邦学习",
        why="面向社交、生物、推荐等图结构数据，把图建模和隐私协同结合起来。",
        advantages="适合复杂关系建模，能保留结构性知识。",
        disadvantages="跨客户端图结构差异大，训练和聚合都更复杂。",
    ),
    CategoryDefinition(
        id="generative",
        name="生成式与扩散联邦",
        folder="05_生成式与扩散联邦",
        why="探索联邦场景中的生成模型、扩散模型与 one-shot 协同训练等新范式。",
        advantages="适合高隐私和低通信场景，也能支持数据合成与增强。",
        disadvantages="训练成本高，评价标准和稳定性仍在发展。",
    ),
    CategoryDefinition(
        id="prompt",
        name="联邦提示学习与基础模型",
        folder="06_联邦提示学习与基础模型",
        why="关注基础模型时代下，如何通过提示、轻量参数和协同适配实现联邦优化。",
        advantages="参数高效，适配大模型场景更自然。",
        disadvantages="受底座模型约束较强，实验成本通常较高。",
    ),
    CategoryDefinition(
        id="system",
        name="系统优化与应用部署",
        folder="07_系统优化与应用部署",
        why="强调资源调度、服务编排、边缘部署和工程落地，是研究走向生产的重要环节。",
        advantages="更贴近真实业务系统与部署约束。",
        disadvantages="系统因素多，实验复现和公平比较更难。",
    ),
    CategoryDefinition(
        id="survey",
        name="综述、公平性与背景理论",
        folder="08_综述_公平性_背景理论",
        why="提供路线整理、背景搭建和公平性等横向问题视角，适合作为阅读地图的地基。",
        advantages="帮助快速建立全局认知和比较框架。",
        disadvantages="通常不直接给出可复用训练算法。",
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
    for category in CATEGORY_DEFINITIONS:
        (PAPER_DIR / category.folder).mkdir(parents=True, exist_ok=True)


def get_env(name: str, default: Any = None) -> Any:
    """获取环境变量，支持默认值"""
    return os.getenv(name, default)


def get_bool_env(name: str, default: bool = False) -> bool:
    """获取布尔类型的环境变量，支持多种真值格式"""
    value = str(os.getenv(name, str(default))).strip().lower()
    return value in {"1", "true", "yes", "on"}
