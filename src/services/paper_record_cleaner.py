from __future__ import annotations

import re
from collections import Counter


def build_paper_short(title: str, abstract: str = "", raw_text: str = "") -> str:
    cleaned_title = _clean_title(title)
    explicit = _extract_explicit_alias(cleaned_title, abstract, raw_text)
    if explicit:
        return explicit

    acronym = _extract_acronym_candidate(cleaned_title, raw_text)
    if acronym:
        return acronym

    return _truncate_title(cleaned_title)


def normalize_short(value: object, fallback: str = "") -> str:
    """归一化 AI 返回的论文缩写（short）。

    AI 在分类时一并给出的缩写质量最高，但需要做防御性清洗：
    去掉首尾标点/引号/空白、合并多余空白、去掉换行、限制长度 2-24 字符。
    清洗后过短或过长则回退到 fallback（通常是启发式 build_paper_short 的结果）。
    """
    text = str(value or "").strip()
    if not text:
        return fallback
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[\r\n]+", " ", text)
    text = re.sub(r'^["“”\'`\-:;,. ]+|["“”\'`\-:;,. ]+$', "", text).strip()
    text = text.split("。")[0].strip()
    if len(text) < 2:
        return fallback
    if len(text) > 24:
        # 超长时按词截断，避免生硬切断单词；仍超长再硬截断
        words = text.split()
        truncated = ""
        for word in words:
            candidate = f"{truncated} {word}".strip()
            if len(candidate) > 24:
                break
            truncated = candidate
        text = truncated or text[:24]
    return text or fallback


def normalize_idea_text(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"(实验表明|结果表明|实验结果表明|优于其他方法|优于现有方法|更快收敛|性能更好|显著提升)[，,。；;]?", "", text)
    text = re.sub(r"(本文|该方法|该工作)(提出|设计|采用)", r"\1通过", text)
    sentences = re.split(r"(?<=[。！？])", text)
    compact = "".join(sentence for sentence in sentences[:2] if sentence.strip()).strip()
    compact = compact or text
    return compact[:180].strip(" ，,;；")


def _clean_title(value: str) -> str:
    cleaned = re.sub(r"^[#*`\-:;,. ]+", "", value or "").strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def _extract_explicit_alias(title: str, abstract: str, raw_text: str) -> str | None:
    combined = " ".join(part for part in [title, abstract, raw_text[:2000]] if part)
    patterns = [
        r"\(([A-Z][A-Z0-9-]{2,})\)",
        r"\b([A-Z][A-Z0-9-]{2,})\s+algorithm\b",
        r"\bcalled\s+([A-Z][A-Z0-9-]{2,})\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, combined)
        if match:
            return match.group(1)
    return None


def _extract_acronym_candidate(title: str, raw_text: str) -> str | None:
    words = re.findall(r"[A-Za-z][A-Za-z-]+", title)
    if len(words) >= 2:
        acronym = "".join(word[0] for word in words if word[0].isalpha()).upper()
        if 3 <= len(acronym) <= 10 and re.search(rf"\b{re.escape(acronym)}\b", raw_text):
            return acronym

    matches = re.findall(r"\b[A-Z][A-Za-z0-9]{2,}(?:[A-Z][A-Za-z0-9]*)*\b", raw_text[:3000])
    filtered = [
        item
        for item in matches
        if len(item) <= 16 and not item.isdigit() and item.lower() not in {"abstract", "introduction"}
    ]
    if not filtered:
        return None
    candidate, count = Counter(filtered).most_common(1)[0]
    return candidate if count >= 2 else None


def _truncate_title(title: str) -> str:
    words = title.split()
    if len(words) <= 5:
        return title
    candidate = " ".join(words[:5]).strip()
    return candidate[:48].strip()
