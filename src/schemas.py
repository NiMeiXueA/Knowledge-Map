from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CategoryModel(BaseModel):
    """论文分类模型"""
    id: str  # 分类ID
    name: str  # 分类名称
    folder: str  # 对应的文件夹名称
    why: str  # 为什么需要这个分类
    advantages: str  # 该分类的优势
    disadvantages: str  # 该分类的劣势


class CategoryCreateIn(BaseModel):
    """创建分类输入模型"""
    id: str
    name: str
    folder: str
    why: str = ""
    advantages: str = ""
    disadvantages: str = ""


class CategoryUpdateIn(BaseModel):
    """更新分类输入模型"""
    id: str
    name: str
    folder: str
    why: str = ""
    advantages: str = ""
    disadvantages: str = ""


class InnovationPoint(BaseModel):
    """创新点模型"""
    point: str  # 创新点描述
    evidence: str = ""  # 支持证据
    confidence: float = 0.0  # 置信度（0-1）


class LimitationPoint(BaseModel):
    """局限性点模型"""
    point: str  # 局限性描述
    evidence: str = ""  # 支持证据
    type: Literal["paper_claimed", "inferred"] = "inferred"  # 类型：论文自述或推断
    severity: Literal["low", "medium", "high"] = "medium"  # 严重程度


class CitationItem(BaseModel):
    """引用项模型"""
    title: str  # 引用论文标题
    authors: list[str] = Field(default_factory=list)  # 作者列表
    year: int | None = None  # 发表年份
    venue: str | None = None  # 发表会议/期刊
    doi: str | None = None  # DOI标识符


class PaperSourceCandidate(BaseModel):
    """论文来源候选模型"""
    provider: str  # 数据提供者（如crossref_doi, semantic_scholar_title等）
    title: str = ""  # 论文标题
    authors: list[str] = Field(default_factory=list)  # 作者列表
    abstract: str = ""  # 摘要
    year: int | None = None  # 发表年份
    venue: str | None = None  # 发表会议/期刊
    doi: str | None = None  # DOI标识符
    arxiv_id: str | None = None  # arXiv ID
    source_url: str | None = None  # 来源URL
    citation_text: str | None = None  # 引用文本
    bibtex: str | None = None  # BibTeX格式引用
    confidence: float = 0.0  # 置信度分数（0-1）
    reason: str = ""  # 匹配原因说明


class RelationshipItem(BaseModel):
    """论文关系项模型"""
    source: str  # 源论文ID
    target: str  # 目标论文ID
    type: str  # 关系类型（如citation, same_category_evolution）
    reason: str  # 关系原因说明


class PaperModel(BaseModel):
    """论文完整模型"""
    id: str  # 论文唯一标识符
    short: str  # 论文简称/缩写
    title: str  # 论文标题
    year: int | None = None  # 发表年份
    authors: list[str] = Field(default_factory=list)  # 作者列表
    first_author: str = ""  # 第一作者
    venue: str | None = None  # 发表会议/期刊
    abstract: str = ""  # 摘要
    summary: str = ""  # 论文总结
    idea: str = ""  # 核心思想/方法
    categories: list[str] = Field(default_factory=list)  # 所属分类ID列表
    source_path: str = ""  # 原始PDF文件路径
    innovation: str = ""  # 创新点描述
    innovation_points: list[InnovationPoint] = Field(default_factory=list)  # 创新点列表
    flow_steps: list[str] = Field(default_factory=list)  # 方法流程步骤
    applications: str = ""  # 应用场景描述
    limitations: str = ""  # 局限性描述
    limitation_points: list[LimitationPoint] = Field(default_factory=list)  # 局限性点列表
    citations: list[CitationItem] = Field(default_factory=list)  # 引用列表
    relationships: list[RelationshipItem] = Field(default_factory=list)  # 与其他论文的关系
    analysis_json_path: str = ""  # 分析结果JSON文件路径
    needs_human_review: bool = False  # 是否需要人工审核
    created_at: datetime  # 创建时间
    updated_at: datetime  # 更新时间
    venue_source: str | None = None  # 会议/期刊来源
    doi: str | None = None  # DOI标识符
    arxiv_id: str | None = None  # arXiv ID
    source_url: str | None = None  # 来源URL
    citation_text: str | None = None  # 引用文本
    bibtex: str | None = None  # BibTeX格式引用
    metadata_confidence: float = 0.0  # 元数据置信度（0-1）
    metadata_source_method: str | None = None  # 元数据获取方法
    metadata_verification_notes: str | None = None  # 元数据验证说明
    source_candidates: list[PaperSourceCandidate] = Field(default_factory=list)  # 来源候选列表


class PaperCollection(BaseModel):
    """论文集合模型"""
    categories: list[CategoryModel]  # 分类列表
    papers: list[PaperModel]  # 论文列表


class TaskStatusModel(BaseModel):
    """任务状态模型"""
    task_id: str  # 任务ID
    status: Literal["processing", "completed", "failed"] = "processing"  # 任务状态
    stage: str  # 当前阶段
    message: str  # 状态消息
    paper_id: str | None = None  # 关联的论文ID
    error: str | None = None  # 错误信息
    created_at: datetime  # 创建时间
    updated_at: datetime  # 更新时间


class UploadResponse(BaseModel):
    """上传响应模型"""
    task_id: str  # 任务ID
    status: str  # 任务状态


class ModelSettingsIn(BaseModel):
    """模型设置输入模型"""
    provider: Literal["openai", "anthropic"]  # LLM提供商
    api_key: str = Field(min_length=1)  # API密钥
    base_url: str  # API基础URL
    model: str  # 模型名称
    temperature: float = 0.2  # 温度参数
    max_tokens: int = 4096  # 最大token数


class ModelSettingsSummary(BaseModel):
    """模型设置摘要模型"""
    provider: Literal["openai", "anthropic"]  # LLM提供商
    base_url: str  # API基础URL
    model: str  # 模型名称
    temperature: float  # 温度参数
    max_tokens: int  # 最大token数
    api_key_configured: bool  # API密钥是否已配置


class PaperAnalysisPatch(BaseModel):
    """论文分析补丁模型（用于部分更新）"""
    abstract: str | None = None  # 摘要
    summary: str | None = None  # 总结
    idea: str | None = None  # 核心思想
    innovation: str | None = None  # 创新点描述
    innovation_points: list[InnovationPoint] | None = None  # 创新点列表
    applications: str | None = None  # 应用场景
    flow_steps: list[str] | None = None  # 方法流程步骤
    limitations: str | None = None  # 局限性描述
    limitation_points: list[LimitationPoint] | None = None  # 局限性点列表


class GraphNode(BaseModel):
    """图节点模型（用于关系图）"""
    id: str  # 论文ID
    title: str  # 论文标题
    short: str  # 论文简称
    year: int | None = None  # 发表年份
    category_id: str  # 所属分类ID


class GraphLink(BaseModel):
    """图边模型（用于关系图）"""
    source: str  # 源论文ID
    target: str  # 目标论文ID
    type: str  # 关系类型
    reason: str  # 关系原因说明


class GraphPayload(BaseModel):
    """图数据载荷模型"""
    nodes: list[GraphNode]  # 节点列表
    links: list[GraphLink]  # 边列表
