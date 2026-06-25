from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from src.schemas import CitationItem

# DOI正则表达式模式：匹配10.xxxx/xxxxx格式
DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", flags=re.IGNORECASE)
# arXiv ID正则表达式模式：匹配2106.09685或arXiv:2106.09685v2格式
ARXIV_PATTERN = re.compile(r"\barxiv[:\s]*([0-9]{4}\.[0-9]{4,5}(?:v\d+)?)\b", flags=re.IGNORECASE)
# 年份正则表达式模式：匹配19xx或20xx格式
YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")
# 参考文献分割模式：匹配[1]、1.等编号格式
REFERENCE_SPLIT_PATTERN = re.compile(r"(?m)^\s*(?:\[\d+\]|\(\d+\)|\d+\.)\s+")


def _clean_lines(raw_text: str) -> list[str]:
    """清理文本：去除空白行并strip每行"""
    return [line.strip() for line in raw_text.splitlines() if line.strip()]


def _normalize_whitespace(value: str) -> str:
    """将多个空白字符合并为单个空格"""
    return re.sub(r"\s+", " ", value).strip()


def extract_metadata(raw_text: str) -> dict[str, Any]:
    """
    从PDF原始文本中提取元数据（标题、作者、摘要、引用、DOI、arXiv ID等）
    
    这是论文标题获取的第一步：本地PDF解析
    
    Args:
        raw_text: PDF提取的原始文本
        
    Returns:
        包含所有元数据的字典
    """
    lines = _clean_lines(raw_text)
    front_lines = lines[:24]  # 取前24行作为首页内容
    front_text = "\n".join(front_lines)
    
    # 提取各项元数据
    title = _extract_title(front_lines)  # 提取标题
    authors = _extract_authors(front_lines)  # 提取作者
    abstract = _extract_abstract(raw_text)  # 提取摘要
    citations = _extract_citations(raw_text)  # 提取引用列表
    doi = _extract_doi(front_text) or _extract_doi(raw_text[:4000])  # 提取DOI
    arxiv_id = _extract_arxiv_id(front_text)  # 提取arXiv ID
    year = _extract_year(front_text) or _extract_year(raw_text[:4000])  # 提取年份
    
    # 估算本地提取的置信度
    confidence = _estimate_local_confidence(title, authors, abstract, doi, arxiv_id)
    
    return {
        "title": title,  # 论文标题
        "authors": authors,  # 作者列表
        "abstract": abstract,  # 摘要
        "citations": citations,  # 引用列表
        "doi": doi,  # DOI标识符
        "arxiv_id": arxiv_id,  # arXiv ID
        "metadata_confidence": confidence,  # 元数据置信度
        "metadata_source_method": "local_pdf",  # 元数据来源方法
        "metadata_verification_notes": "从 PDF 首页文本启发式提取，并对标题、作者、引用做了规则清洗。",
        "source_candidates": [
            {
                "provider": "local_pdf",  # 数据提供者
                "title": title,  # 论文标题
                "authors": authors,  # 作者列表
                "abstract": abstract,  # 摘要
                "year": year,  # 发表年份
                "venue": None,  # 发表会议/期刊（本地提取暂无）
                "doi": doi,  # DOI标识符
                "arxiv_id": arxiv_id,  # arXiv ID
                "source_url": None,  # 来源URL（本地提取暂无）
                "citation_text": None,  # 引用文本
                "bibtex": None,  # BibTeX格式
                "confidence": confidence,  # 置信度
                "reason": "来自本地 PDF 首页与摘要区域提取。",
            }
        ],
    }


def _extract_title(lines: list[str]) -> str:
    """
    从PDF文本的前12行中提取论文标题
    
    这是论文标题获取的核心函数，使用启发式规则：
    1. 遍历前12行
    2. 过滤掉太短（<12字符）或太长（>220字符）的行
    3. 过滤掉以"abstract"、"keywords"、"introduction"开头的行
    4. 过滤掉包含@符号的行（邮箱）
    5. 过滤掉字母数量少于8个的行
    6. 返回第一个满足条件的行作为标题
    
    Args:
        lines: PDF文本的行列表
        
    Returns:
        提取的论文标题
    """
    for line in lines[:12]:
        normalized = _clean_title_candidate(line)
        if len(normalized) < 12 or len(normalized) > 220:
            continue
        lowered = normalized.lower()
        if lowered.startswith(("abstract", "keywords", "introduction")):
            continue
        if "@" in normalized:
            continue
        if sum(1 for char in normalized if char.isalpha()) < 8:
            continue
        return normalized
    # 如果没有找到合适的标题，返回第一行或默认标题
    fallback = _clean_title_candidate(lines[0]) if lines else "Untitled Paper"
    return fallback or "Untitled Paper"


def _clean_title_candidate(line: str) -> str:
    """清理标题候选行：去除特殊字符和多余空格"""
    normalized = _normalize_whitespace(line)
    normalized = re.sub(r"^[#*`\-:;,. ]+", "", normalized)  # 去除开头特殊字符
    normalized = re.sub(r"\$[^$]*\$", " ", normalized)  # 去除LaTeX公式
    normalized = re.sub(r"\{|\}", "", normalized)  # 去除花括号
    normalized = re.sub(r"\s{2,}", " ", normalized)  # 合并多余空格
    return normalized.strip(" -:;,.")


def _extract_authors(lines: list[str]) -> list[str]:
    """
    从PDF文本的前10行中提取作者列表
    
    启发式规则：
    1. 遍历第2-10行（跳过标题行）
    2. 过滤掉包含"abstract"、"keywords"、"introduction"的行
    3. 过滤掉包含机构名称的行（university, institute等）
    4. 按逗号、"and"、分号分割
    5. 验证每个名字是否像人名
    6. 最多返回16位作者
    
    Args:
        lines: PDF文本的行列表
        
    Returns:
        作者姓名列表
    """
    for line in lines[1:10]:
        normalized = _clean_author_line(line)
        if not normalized:
            continue
        lowered = normalized.lower()
        if any(token in lowered for token in ["abstract", "keywords", "introduction"]):
            continue
        if re.search(r"\b(university|institute|department|school|laboratory|college|research)\b", lowered):
            continue
        parts = re.split(r",| and |;", normalized)
        authors = [_clean_author_name(item) for item in parts]
        authors = [item for item in authors if _looks_like_person_name(item)]
        if authors:
            return authors[:16]
    return []


def _clean_author_line(line: str) -> str:
    """清理作者行：去除LaTeX标记、脚注符号、邮箱、数字等"""
    normalized = _normalize_whitespace(line)
    normalized = re.sub(r"\$[^$]*\$", " ", normalized)  # 去除LaTeX公式
    normalized = re.sub(r"\^\{[^}]*\}", " ", normalized)  # 去除上标
    normalized = re.sub(r"\[[^\]]*\]", " ", normalized)  # 去除方括号内容
    normalized = re.sub(r"[\*†‡§¶]+", " ", normalized)  # 去除脚注符号
    normalized = re.sub(r"\b\w+@\w[\w.-]*\.\w+\b", " ", normalized)  # 去除邮箱
    normalized = re.sub(r"\d+", " ", normalized)  # 去除数字
    normalized = re.sub(r"\s{2,}", " ", normalized)  # 合并多余空格
    return normalized.strip(" ,;")


def _clean_author_name(value: str) -> str:
    """清理单个作者姓名"""
    cleaned = _normalize_whitespace(value)
    cleaned = re.sub(r"^[^\w\u4e00-\u9fff]+|[^\w\u4e00-\u9fff.-]+$", "", cleaned)  # 去除首尾非字母字符
    cleaned = re.sub(r"\s{2,}", " ", cleaned)  # 合并多余空格
    return cleaned.strip()


def _looks_like_person_name(value: str) -> bool:
    """
    判断字符串是否像人名
    
    启发式规则：
    1. 长度在2-80之间
    2. 不包含特定关键词（abstract, keywords等）
    3. 不是纯标点符号
    4. 词数不超过5个
    5. 单个词必须是中文或包含大写字母
    """
    if len(value) < 2 or len(value) > 80:
        return False
    lowered = value.lower()
    if any(
        token in lowered
        for token in [
            "abstract",
            "keywords",
            "introduction",
            "email",
            "framework",
            "theoretically",
            "practically",
            "demonstrate",
            "significant",
            "heterogeneity",
        ]
    ):
        return False
    if re.fullmatch(r"[\W_]+", value):
        return False
    tokens = [token for token in re.split(r"\s+", value) if token]
    if len(tokens) > 5:
        return False
    if len(tokens) == 1 and not re.search(r"[\u4e00-\u9fff]", tokens[0]):
        return False
    alpha_tokens = [token for token in tokens if re.search(r"[A-Za-z\u4e00-\u9fff]", token)]
    if not alpha_tokens:
        return False
    titled = 0
    for token in alpha_tokens:
        cleaned = token.strip(".-")
        if re.fullmatch(r"[A-Z]\.?", cleaned):
            titled += 1
        elif re.match(r"[A-Z\u4e00-\u9fff]", cleaned):
            titled += 1
    return titled >= max(1, len(alpha_tokens) - 1)


def _extract_abstract(raw_text: str) -> str:
    """
    从PDF原始文本中提取摘要
    
    使用两种模式匹配：
    1. "abstract"关键字后的内容
    2. "summary"关键字后的内容
    
    提取到第一个空行、"keywords"或"introduction"为止
    
    Args:
        raw_text: PDF原始文本
        
    Returns:
        提取的摘要文本（最多4000字符）
    """
    patterns = [
        r"(?is)\babstract\b[:\s\-–—]*(.+?)(?:\n\s*\n|\bkeywords\b|\b1\.?\s+introduction\b|\bi\.\s+introduction\b)",
        r"(?is)\bsummary\b[:\s]*(.+?)(?:\n\s*\n|\bkeywords\b|\b1\.?\s+introduction\b)",
    ]
    for pattern in patterns:
        match = re.search(pattern, raw_text)
        if match:
            return _normalize_whitespace(match.group(1))[:4000]
    # 如果没有找到摘要模式，返回文本开头部分
    return _normalize_whitespace(raw_text[:1600])


def _extract_citations(raw_text: str) -> list[dict]:
    """
    从PDF原始文本中提取引用列表

    查找"references"部分，然后分割和解析每个引用项

    Args:
        raw_text: PDF原始文本

    Returns:
        引用项列表（最多40个）
    """
    references_text = extract_references_text(raw_text)
    if not references_text:
        return []
    chunks = _split_reference_chunks(references_text)
    citations: list[CitationItem] = []
    for chunk in chunks[:40]:
        citation = _parse_reference_chunk(chunk)
        if citation:
            citations.append(citation)
    return _deduplicate_citations([item.model_dump() for item in citations])


def extract_references_text(raw_text: str) -> str:
    """从 PDF 原始文本中截取 References / Bibliography 段落（完整、不截断）。

    正则引用提取（_extract_citations）和 LLM 引用提取都复用它。
    LLM 路径自行在外层做长度截断以控制输入体积。
    找不到该段落时返回空串。
    """
    if not raw_text:
        return ""
    refs_match = re.search(r"(?is)\b(references|bibliography)\b(.+)$", raw_text)
    if not refs_match:
        return ""
    return refs_match.group(2).strip()


def _split_reference_chunks(references_text: str) -> list[str]:
    """将参考文献文本分割成单个引用项"""
    text = references_text.strip()
    # 尝试按编号分割
    numbered_parts = REFERENCE_SPLIT_PATTERN.split(text)
    chunks = [_normalize_whitespace(part) for part in numbered_parts if _normalize_whitespace(part)]
    if len(chunks) >= 3:
        return chunks

    # 如果编号分割失败，按行合并
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    merged: list[str] = []
    current = ""
    for line in lines:
        if current and re.match(r"^[A-Z][^:]{0,80}\b(?:,| and )", line):
            merged.append(_normalize_whitespace(current))
            current = line
            continue
        current = f"{current} {line}".strip() if current else line
    if current:
        merged.append(_normalize_whitespace(current))
    return merged


def _parse_reference_chunk(chunk: str) -> CitationItem | None:
    """解析单个引用项文本"""
    cleaned = _normalize_whitespace(re.sub(r"^[\[\(]?\d+[\]\)]?\.?\s*", "", chunk))
    if len(cleaned) < 12:
        return None

    doi_match = DOI_PATTERN.search(cleaned)
    year = _extract_reference_year(cleaned)
    authors, remainder = _split_reference_authors(cleaned)
    title, tail = _split_reference_title(remainder)
    venue = _extract_reference_venue(tail or remainder)

    if not title:
        title = _fallback_reference_title(cleaned)
    if not title:
        return None

    return CitationItem(
        title=title[:240],
        authors=authors[:16],
        year=year,
        venue=venue[:180] if venue else None,
        doi=doi_match.group(0) if doi_match else None,
    )


def _split_reference_authors(text: str) -> tuple[list[str], str]:
    """从引用文本中分割作者和剩余部分"""
    year_match = re.search(r"(?<!:)\b(19|20)\d{2}\b", text)
    split_index = year_match.start() if year_match else None
    prefix = text[:split_index].strip(" .,;") if split_index is not None else text
    suffix = text[split_index:].strip() if split_index is not None else ""

    if not prefix:
        return [], text

    semicolon_chunks = [chunk.strip(" .,;") for chunk in prefix.split(";") if chunk.strip(" .,;")]
    if len(semicolon_chunks) >= 2:
        authors = [_normalize_reference_author_chunk(chunk) for chunk in semicolon_chunks]
        authors = [author for author in authors if _looks_like_person_name(author)]
        if authors:
            remainder = text[len(prefix):].lstrip(" .,;")
            return authors, remainder

    prefix = prefix.replace(" and ", ", ")
    parts = [part.strip(" .,;") for part in prefix.split(",") if part.strip(" .,;")]
    if len(parts) <= 1:
        return [], text

    authors = _build_reference_author_list(parts)
    authors = [author for author in authors if _looks_like_person_name(author)]
    if not authors:
        return [], text
    remainder = text[len(prefix):].lstrip(" .,;")
    return authors, remainder


def _build_reference_author_list(parts: list[str]) -> list[str]:
    """构建作者列表，尝试识别姓-名配对模式"""
    if len(parts) == 2 and _looks_like_surname_fragment(parts[0]) and _looks_like_initials_fragment(parts[1]):
        return [_clean_author_name(f"{parts[0]} {parts[1]}")]
    alternating_pairs = []
    if len(parts) >= 4:
        alternating_pairs = [
            _clean_author_name(f"{parts[index]} {parts[index + 1]}")
            for index in range(0, len(parts) - 1, 2)
            if _looks_like_surname_fragment(parts[index]) and _looks_like_initials_fragment(parts[index + 1])
        ]
    if alternating_pairs and len(alternating_pairs) >= max(2, len(parts) // 3):
        return alternating_pairs
    return [_clean_author_name(part) for part in parts]


def _looks_like_surname_fragment(value: str) -> bool:
    """判断字符串是否像姓氏片段"""
    cleaned = value.strip()
    return 1 <= len(cleaned.split()) <= 3 and bool(re.fullmatch(r"[A-Z][A-Za-z'`\-]+(?:\s+[A-Z][A-Za-z'`\-]+){0,2}", cleaned))


def _looks_like_initials_fragment(value: str) -> bool:
    """判断字符串是否像名字缩写片段"""
    cleaned = value.strip()
    return bool(re.fullmatch(r"(?:[A-Z]\.?)(?:\s*[A-Z]\.?)*", cleaned))


def _split_reference_title(text: str) -> tuple[str, str]:
    """从引用文本中分割标题和剩余部分"""
    if not text:
        return "", ""
    working = text
    year_match = re.search(r"(?:^|[\s,(])(\d{4}[a-z]?)\)?[.,]?\s*", working, flags=re.IGNORECASE)
    if year_match:
        working = working[year_match.end():].strip()
    quoted_match = re.search(r"[\"“](.+?)[\"”]", working)
    if quoted_match:
        title = _clean_reference_title(quoted_match.group(1))
        tail = working[quoted_match.end():].strip(" .,;")
        return title, tail

    parts = re.split(r"\.\s+", working, maxsplit=2)
    if len(parts) >= 2:
        candidate = _clean_reference_title(parts[0])
        if _looks_like_reference_title(candidate):
            tail = parts[1] if len(parts) > 1 else ""
            return candidate, tail
    comma_match = re.search(r",\s*(In\s+.+)$", working)
    if comma_match:
        candidate = _clean_reference_title(working[:comma_match.start()])
        if _looks_like_reference_title(candidate):
            return candidate, comma_match.group(1)
    return "", working


def _clean_reference_title(value: str) -> str:
    """清理引用标题"""
    cleaned = _normalize_whitespace(value)
    cleaned = re.sub(r"^[\"“'`]+|[\"”'`]+$", "", cleaned)
    return cleaned.strip(" .,;")


def _looks_like_reference_title(value: str) -> bool:
    """判断字符串是否像引用标题"""
    if len(value) < 6 or len(value) > 240:
        return False
    lowered = value.lower()
    if lowered.startswith(("in ", "pp.", "vol.", "pages ")):
        return False
    return bool(re.search(r"[A-Za-z\u4e00-\u9fff]", value))


def _fallback_reference_title(text: str) -> str:
    """备用标题提取方法"""
    parts = re.split(r"\.\s+", text)
    for part in parts[1:4]:
        candidate = _clean_reference_title(part)
        if _looks_like_reference_title(candidate):
            return candidate
    cleaned = _clean_reference_title(text)
    return cleaned[:240]


def _extract_reference_venue(text: str) -> str | None:
    """从引用文本中提取会议/期刊名称"""
    if not text:
        return None
    working = _normalize_whitespace(text)
    patterns = [
        r"\bIn\s+([^.,]+(?:Conference|Symposium|Workshop|Congress|Proceedings|Meeting)[^.,]*)",
        r"\b(arXiv preprint [^.,]+)",
        r"\b([A-Z][A-Za-z&/\- ]+(?:Journal|Transactions|Letters|Review|Magazine|Conference|Proceedings)[^.,]*)",
    ]
    for pattern in patterns:
        match = re.search(pattern, working, flags=re.IGNORECASE)
        if match:
            return _normalize_whitespace(match.group(1)).strip(" .,;")
    return None


def _normalize_reference_author_chunk(value: str) -> str:
    parts = [part.strip(" .,;") for part in value.split(",") if part.strip(" .,;")]
    if len(parts) == 2 and _looks_like_surname_fragment(parts[0]) and _looks_like_initials_fragment(parts[1]):
        return _clean_author_name(f"{parts[0]} {parts[1]}")
    return _clean_author_name(value)


def _deduplicate_citations(citations: list[dict]) -> list[dict]:
    deduped: dict[str, dict] = {}
    for item in citations:
        doi = str(item.get("doi") or "").strip().lower()
        title = _normalize_whitespace(str(item.get("title") or "")).lower()
        key = doi or re.sub(r"[^a-z0-9]+", "", title)
        if not key:
            continue
        existing = deduped.get(key)
        if existing is None or _citation_richness(item) > _citation_richness(existing):
            deduped[key] = item
    return list(deduped.values())


def _citation_richness(item: dict) -> tuple[int, int, int, int]:
    return (
        1 if item.get("doi") else 0,
        1 if item.get("venue") else 0,
        len(item.get("authors") or []),
        1 if item.get("year") else 0,
    )


def _extract_doi(raw_text: str) -> str | None:
    """从文本中提取DOI标识符"""
    match = DOI_PATTERN.search(raw_text)
    return match.group(0) if match else None


def _extract_arxiv_id(raw_text: str) -> str | None:
    """从文本中提取arXiv ID"""
    match = ARXIV_PATTERN.search(raw_text)
    return match.group(1) if match else None


def _extract_year(text: str) -> int | None:
    """从文本中提取年份（1990年至今）"""
    current_year = datetime.now().year + 1
    years = [int(match.group(0)) for match in YEAR_PATTERN.finditer(text)]
    for year in years:
        if 1990 <= year <= current_year:
            return year
    return None


def _extract_reference_year(text: str) -> int | None:
    """从引用文本中提取年份（排除arXiv预印本年份）"""
    current_year = datetime.now().year + 1
    sanitized = re.sub(r"arXiv:\d{4}\.\d{4,5}(?:v\d+)?", "", text, flags=re.IGNORECASE)
    years = [int(match.group(0)) for match in YEAR_PATTERN.finditer(sanitized)]
    valid_years = [year for year in years if 1990 <= year <= current_year]
    return valid_years[0] if valid_years else None


def _estimate_local_confidence(
    title: str,
    authors: list[str],
    abstract: str,
    doi: str | None,
    arxiv_id: str | None,
) -> float:
    """
    估算本地提取元数据的置信度（0-0.95）
    
    评分维度：
    - 标题长度 >= 20字符：+0.2
    - 有作者信息：+0.15
    - 摘要长度 >= 120字符：+0.2
    - 有DOI：+0.15
    - 有arXiv ID：+0.05
    - 基础分：0.25
    
    Args:
        title: 论文标题
        authors: 作者列表
        abstract: 摘要
        doi: DOI标识符
        arxiv_id: arXiv ID
        
    Returns:
        置信度分数（0-0.95）
    """
    score = 0.25
    if len(title) >= 20:
        score += 0.2
    if authors:
        score += 0.15
    if len(abstract) >= 120:
        score += 0.2
    if doi:
        score += 0.15
    if arxiv_id:
        score += 0.05
    return min(score, 0.95)
