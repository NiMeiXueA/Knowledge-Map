from __future__ import annotations

import html
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import quote_plus, urlparse

import httpx

from src.config import get_env

USER_AGENT = "Knowledge-Map/1.0 (+paper metadata lookup)"


@dataclass(frozen=True)
class ReferenceHint:
    raw: str
    title: str = ""
    doi: str | None = None
    arxiv_id: str | None = None
    source_url: str | None = None


async def lookup_paper_candidates(
    local_metadata: dict[str, Any],
    raw_text: str,
    reference_hint: str | None = None,
) -> list[dict[str, Any]]:
    title = str(local_metadata.get("title") or "").strip()
    hint = parse_reference_hint(reference_hint or "")
    doi = str(local_metadata.get("doi") or "").strip() or hint.doi or _extract_doi(raw_text) or None
    arxiv_id = str(local_metadata.get("arxiv_id") or "").strip() or hint.arxiv_id or _extract_arxiv_id(raw_text) or None
    title_query = title or hint.title

    async with httpx.AsyncClient(timeout=30, headers={"User-Agent": USER_AGENT}) as client:
        candidates: list[dict[str, Any]] = []

        if doi:
            crossref_by_doi = await _lookup_crossref_by_doi(client, doi)
            if crossref_by_doi:
                candidates.append(crossref_by_doi)
            semanticscholar_by_doi = await _lookup_semantic_scholar_by_doi(client, doi)
            if semanticscholar_by_doi:
                candidates.append(semanticscholar_by_doi)

        if arxiv_id:
            arxiv_by_id = await _lookup_arxiv_by_id(client, arxiv_id)
            if arxiv_by_id:
                candidates.append(arxiv_by_id)

        if title_query:
            max_results = int(get_env("PAPER_SEARCH_MAX_CANDIDATES", 3) or 3)
            candidates.extend(await _lookup_crossref_by_title(client, title_query, max_results))
            candidates.extend(await _lookup_semantic_scholar_by_title(client, title_query, max_results))
            candidates.extend(await _lookup_arxiv_by_title(client, title_query, max_results))

        normalized = _deduplicate_candidates(candidates)
        for item in normalized:
            if not item.get("citations"):
                item["citations"] = await _enrich_candidate_citations(client, item)
            item["confidence"] = _score_candidate(local_metadata, raw_text, item, hint)
            item["reason"] = _build_match_reason(local_metadata, item, hint)

    normalized = _filter_low_quality_candidates(local_metadata, normalized, hint)
    normalized.sort(key=lambda item: item.get("confidence", 0.0), reverse=True)
    return normalized[: int(get_env("PAPER_SEARCH_MAX_CANDIDATES", 5) or 5)]


def parse_reference_hint(reference: str) -> ReferenceHint:
    raw = str(reference or "").strip()
    if not raw:
        return ReferenceHint(raw="")

    doi = _extract_doi(raw)
    arxiv_id = _extract_arxiv_id(raw) or _extract_arxiv_id_from_url(raw) or _extract_bare_arxiv_id(raw)
    source_url = raw if _is_valid_http_url(raw) else None
    title = ""
    if not doi and not arxiv_id and not source_url:
        title = raw
    return ReferenceHint(raw=raw, title=title, doi=doi, arxiv_id=arxiv_id, source_url=source_url)


def fallback_source_result(
    local_metadata: dict[str, Any],
    raw_text: str,
    reference_hint: str | None = None,
) -> dict[str, Any]:
    hint = parse_reference_hint(reference_hint or "")
    doi = str(local_metadata.get("doi") or "").strip() or hint.doi or _extract_doi(raw_text)
    arxiv_id = str(local_metadata.get("arxiv_id") or "").strip() or hint.arxiv_id or _extract_arxiv_id(raw_text)
    title = str(local_metadata.get("title") or "").strip() or hint.title
    year = _extract_year(raw_text[:5000]) or None
    citation = _format_citation(
        title=title,
        authors=list(local_metadata.get("authors") or []),
        year=year,
        venue=None,
    )
    return {
        "title": title,
        "authors": list(local_metadata.get("authors") or []),
        "abstract": str(local_metadata.get("abstract") or "").strip(),
        "year": year,
        "venue": None,
        "source": "local_pdf" if str(local_metadata.get("metadata_source_method") or "") == "local_pdf" else "reference_lookup",
        "doi": doi,
        "arxiv_id": arxiv_id,
        "source_url": hint.source_url,
        "citation_text": citation,
        "bibtex": _build_simple_bibtex(
            title=title,
            authors=list(local_metadata.get("authors") or []),
            year=year,
            venue=None,
            doi=doi,
            arxiv_id=arxiv_id,
        ),
        "citations": [],
        "confidence": float(local_metadata.get("metadata_confidence") or 0.35),
        "reason": "未命中可靠联网结果，回退到本地 PDF / 输入参考信息。",
    }


def merge_citations(local_citations: list[dict[str, Any]], remote_citations: list[dict[str, Any]], limit: int = 60) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for item in [*local_citations, *remote_citations]:
        normalized = _normalize_citation_item(item)
        if not normalized:
            continue
        key = (
            str(normalized.get("doi") or "").lower()
            or re.sub(r"[^a-z0-9]+", "", str(normalized.get("title") or "").lower())
        )
        existing = merged.get(key)
        if existing is None or _citation_score(normalized) > _citation_score(existing):
            merged[key] = normalized
    items = list(merged.values())
    items.sort(key=lambda item: (item.get("year") or 9999, item.get("title") or ""))
    return items[:limit]


async def _lookup_crossref_by_doi(client: httpx.AsyncClient, doi: str) -> dict[str, Any] | None:
    response = await client.get(f"https://api.crossref.org/works/{quote_plus(doi)}")
    if response.status_code != 200:
        return None
    item = response.json().get("message", {})
    return _candidate_from_crossref(item, "crossref_doi")


async def _lookup_crossref_by_title(client: httpx.AsyncClient, title: str, rows: int) -> list[dict[str, Any]]:
    response = await client.get(f"https://api.crossref.org/works?query.title={quote_plus(title)}&rows={rows}")
    if response.status_code != 200:
        return []
    items = response.json().get("message", {}).get("items", [])
    return [candidate for item in items if (candidate := _candidate_from_crossref(item, "crossref_title"))]


def _candidate_from_crossref(item: dict[str, Any], provider: str) -> dict[str, Any] | None:
    title = " ".join(item.get("title") or []).strip()
    if not title:
        return None
    authors = [
        " ".join(part for part in [author.get("given"), author.get("family")] if part).strip()
        for author in item.get("author", []) or []
        if isinstance(author, dict)
    ]
    year = _extract_crossref_year(item)
    venue = ((item.get("container-title") or [None])[0]) if isinstance(item.get("container-title"), list) else None
    doi = item.get("DOI")
    abstract = _strip_jats_tags(item.get("abstract") or "")
    return {
        "provider": provider,
        "title": title,
        "authors": [author for author in authors if author],
        "abstract": abstract,
        "year": year,
        "venue": venue,
        "doi": doi,
        "arxiv_id": None,
        "source_url": item.get("URL"),
        "citation_text": _format_citation(title, authors, year, venue),
        "bibtex": _build_simple_bibtex(title, authors, year, venue, doi, None),
        "citations": _citations_from_crossref(item.get("reference") or []),
        "paper_id": None,
        "confidence": 0.0,
        "reason": "",
    }


async def _lookup_semantic_scholar_by_doi(client: httpx.AsyncClient, doi: str) -> dict[str, Any] | None:
    response = await client.get(
        f"https://api.semanticscholar.org/graph/v1/paper/DOI:{quote_plus(doi)}"
        "?fields=title,abstract,authors,year,venue,url,externalIds,paperId,"
        "references.title,references.authors,references.year,references.venue,references.externalIds"
    )
    if response.status_code != 200:
        return None
    return _candidate_from_semantic_scholar(response.json(), "semantic_scholar_doi")


async def _lookup_semantic_scholar_by_title(client: httpx.AsyncClient, title: str, limit: int) -> list[dict[str, Any]]:
    response = await client.get(
        "https://api.semanticscholar.org/graph/v1/paper/search"
        f"?query={quote_plus(title)}&limit={limit}&fields=paperId,title,abstract,authors,year,venue,url,externalIds"
    )
    if response.status_code != 200:
        return []
    return [
        candidate
        for item in response.json().get("data", [])
        if (candidate := _candidate_from_semantic_scholar(item, "semantic_scholar_title"))
    ]


def _candidate_from_semantic_scholar(item: dict[str, Any], provider: str) -> dict[str, Any] | None:
    title = str(item.get("title") or "").strip()
    if not title:
        return None
    authors = [author.get("name", "").strip() for author in item.get("authors", []) if isinstance(author, dict)]
    external_ids = item.get("externalIds") or {}
    year = item.get("year")
    venue = item.get("venue")
    doi = external_ids.get("DOI")
    arxiv_id = external_ids.get("ArXiv")
    references = _citations_from_semantic_scholar(item.get("references") or [])
    return {
        "provider": provider,
        "title": title,
        "authors": [author for author in authors if author],
        "abstract": str(item.get("abstract") or "").strip(),
        "year": year if isinstance(year, int) else None,
        "venue": venue,
        "doi": doi,
        "arxiv_id": arxiv_id,
        "source_url": item.get("url"),
        "citation_text": _format_citation(title, authors, year if isinstance(year, int) else None, venue),
        "bibtex": _build_simple_bibtex(title, authors, year if isinstance(year, int) else None, venue, doi, arxiv_id),
        "citations": references,
        "paper_id": item.get("paperId"),
        "confidence": 0.0,
        "reason": "",
    }


async def _lookup_arxiv_by_id(client: httpx.AsyncClient, arxiv_id: str) -> dict[str, Any] | None:
    response = await client.get(f"https://export.arxiv.org/api/query?id_list={quote_plus(arxiv_id)}")
    if response.status_code != 200:
        return None
    return _candidate_from_arxiv_feed(response.text, "arxiv_id")


async def _lookup_arxiv_by_title(client: httpx.AsyncClient, title: str, limit: int) -> list[dict[str, Any]]:
    response = await client.get(
        f"https://export.arxiv.org/api/query?search_query=all:{quote_plus(title)}&start=0&max_results={limit}"
    )
    if response.status_code != 200:
        return []
    entries = re.findall(r"<entry>(.*?)</entry>", response.text, flags=re.DOTALL)
    return [candidate for entry in entries if (candidate := _candidate_from_arxiv_entry(entry, "arxiv_title"))]


def _candidate_from_arxiv_feed(xml_text: str, provider: str) -> dict[str, Any] | None:
    match = re.search(r"<entry>(.*?)</entry>", xml_text, flags=re.DOTALL)
    if not match:
        return None
    return _candidate_from_arxiv_entry(match.group(1), provider)


def _candidate_from_arxiv_entry(entry_xml: str, provider: str) -> dict[str, Any] | None:
    title_match = re.search(r"<title>(.*?)</title>", entry_xml, flags=re.DOTALL)
    if not title_match:
        return None
    title = _strip_xml(title_match.group(1))
    author_matches = re.findall(r"<name>(.*?)</name>", entry_xml, flags=re.DOTALL)
    abstract_match = re.search(r"<summary>(.*?)</summary>", entry_xml, flags=re.DOTALL)
    id_match = re.search(r"<id>https?://arxiv.org/abs/([^<]+)</id>", entry_xml)
    year_match = re.search(r"<published>(\d{4})-", entry_xml)
    doi_match = re.search(r'<arxiv:doi[^>]*>(.*?)</arxiv:doi>', entry_xml, flags=re.DOTALL)
    authors = _normalize_arxiv_authors([_strip_xml(author) for author in author_matches])
    year = int(year_match.group(1)) if year_match else None
    arxiv_id = id_match.group(1) if id_match else None
    doi = _strip_xml(doi_match.group(1)) if doi_match else None
    return {
        "provider": provider,
        "title": title,
        "authors": [author for author in authors if author],
        "abstract": _strip_xml(abstract_match.group(1)) if abstract_match else "",
        "year": year,
        "venue": "arXiv",
        "doi": doi,
        "arxiv_id": arxiv_id,
        "source_url": f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else None,
        "citation_text": _format_citation(title, authors, year, "arXiv"),
        "bibtex": _build_simple_bibtex(title, authors, year, "arXiv", doi, arxiv_id),
        "citations": [],
        "paper_id": None,
        "confidence": 0.0,
        "reason": "",
    }


async def _enrich_candidate_citations(client: httpx.AsyncClient, candidate: dict[str, Any]) -> list[dict[str, Any]]:
    if candidate.get("citations"):
        return merge_citations([], candidate.get("citations", []))

    paper_id = str(candidate.get("paper_id") or "").strip()
    if paper_id:
        response = await client.get(
            "https://api.semanticscholar.org/graph/v1/paper/"
            f"{quote_plus(paper_id)}?fields=references.title,references.authors,references.year,references.venue,references.externalIds"
        )
        if response.status_code == 200:
            return _citations_from_semantic_scholar(response.json().get("references") or [])

    doi = str(candidate.get("doi") or "").strip()
    if doi:
        response = await client.get(
            f"https://api.semanticscholar.org/graph/v1/paper/DOI:{quote_plus(doi)}"
            "?fields=references.title,references.authors,references.year,references.venue,references.externalIds"
        )
        if response.status_code == 200:
            return _citations_from_semantic_scholar(response.json().get("references") or [])

    return []


def _deduplicate_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for item in candidates:
        key = (
            str(item.get("doi") or "").lower()
            or str(item.get("arxiv_id") or "").lower()
            or re.sub(r"[^a-z0-9]+", "", str(item.get("title") or "").lower())
        )
        if not key:
            continue
        existing = deduped.get(key)
        if existing is None or _candidate_quality(item) > _candidate_quality(existing):
            deduped[key] = item
    return list(deduped.values())


def _candidate_quality(item: dict[str, Any]) -> tuple[int, int, int]:
    return (
        len(str(item.get("abstract") or "")),
        len(item.get("citations") or []),
        1 if item.get("doi") else 0,
    )


def _score_candidate(
    local_metadata: dict[str, Any],
    raw_text: str,
    candidate: dict[str, Any],
    hint: ReferenceHint,
) -> float:
    local_title = str(local_metadata.get("title") or hint.title or "")
    candidate_title = str(candidate.get("title") or "")
    title_score = (
        SequenceMatcher(None, local_title.lower(), candidate_title.lower()).ratio()
        if local_title and candidate_title
        else 0.0
    )

    local_authors = {author.lower() for author in local_metadata.get("authors", []) if isinstance(author, str)}
    candidate_authors = {author.lower() for author in candidate.get("authors", []) if isinstance(author, str)}
    author_score = len(local_authors & candidate_authors) / max(len(local_authors), 1) if candidate_authors and local_authors else 0.0

    doi = str(candidate.get("doi") or "").lower()
    arxiv_id = str(candidate.get("arxiv_id") or "").lower()
    local_doi = str(local_metadata.get("doi") or hint.doi or "").lower()
    local_arxiv = str(local_metadata.get("arxiv_id") or hint.arxiv_id or "").lower()
    doi_bonus = 0.3 if doi and local_doi and doi == local_doi else 0.2 if doi and doi in raw_text.lower() else 0.0
    arxiv_bonus = 0.3 if arxiv_id and local_arxiv and _arxiv_ids_match(arxiv_id, local_arxiv) else 0.15 if arxiv_id and arxiv_id in raw_text.lower() else 0.0
    abstract_score = 0.1 if str(candidate.get("abstract") or "").strip() else 0.0
    citation_bonus = min(0.08, 0.02 * len(candidate.get("citations") or []))
    provider_bonus = 0.18 if "doi" in str(candidate.get("provider")) else 0.08 if "crossref" in str(candidate.get("provider")) else 0.05
    cited_penalty = 0.18 if _candidate_looks_like_reference_target(local_metadata, candidate) else 0.0

    if not local_title and (doi_bonus or arxiv_bonus):
        title_score = 1.0

    score = (
        0.45 * title_score
        + 0.2 * author_score
        + doi_bonus
        + arxiv_bonus
        + abstract_score
        + citation_bonus
        + provider_bonus
        - cited_penalty
    )
    return round(max(0.0, min(score, 0.99)), 4)


def _build_match_reason(local_metadata: dict[str, Any], candidate: dict[str, Any], hint: ReferenceHint) -> str:
    reasons: list[str] = []
    reference_title = str(local_metadata.get("title") or hint.title or "")
    if reference_title and candidate.get("title"):
        similarity = SequenceMatcher(None, reference_title.lower(), str(candidate.get("title")).lower()).ratio()
        reasons.append(f"标题相似度 {similarity:.2f}")
    if candidate.get("doi"):
        reasons.append("包含 DOI")
    if candidate.get("arxiv_id"):
        reasons.append("包含 arXiv ID")
    if candidate.get("authors"):
        reasons.append(f"作者数 {len(candidate.get('authors', []))}")
    if candidate.get("citations"):
        reasons.append(f"参考文献 {len(candidate.get('citations', []))} 条")
    if _candidate_looks_like_reference_target(local_metadata, candidate):
        reasons.append("疑似被引论文，已降权")
    return "，".join(reasons) or "基于标题和作者匹配。"


def _filter_low_quality_candidates(
    local_metadata: dict[str, Any],
    candidates: list[dict[str, Any]],
    hint: ReferenceHint,
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    local_doi = str(local_metadata.get("doi") or hint.doi or "").lower()
    local_title = str(local_metadata.get("title") or hint.title or "")
    for candidate in candidates:
        candidate_doi = str(candidate.get("doi") or "").lower()
        if local_doi and candidate_doi == local_doi:
            filtered.append(candidate)
            continue
        local_arxiv = str(local_metadata.get("arxiv_id") or hint.arxiv_id or "").lower()
        candidate_arxiv = str(candidate.get("arxiv_id") or "").lower()
        if local_arxiv and candidate_arxiv and _arxiv_ids_match(candidate_arxiv, local_arxiv):
            filtered.append(candidate)
            continue
        title_score = SequenceMatcher(
            None,
            local_title.lower(),
            str(candidate.get("title") or "").lower(),
        ).ratio() if local_title else 0.0
        local_authors = {author.lower() for author in local_metadata.get("authors", []) if isinstance(author, str)}
        candidate_authors = {author.lower() for author in candidate.get("authors", []) if isinstance(author, str)}
        author_overlap = bool(local_authors & candidate_authors) if local_authors and candidate_authors else False
        if title_score >= 0.88 and (author_overlap or not local_authors):
            filtered.append(candidate)
            continue
        if float(candidate.get("confidence") or 0.0) >= 0.55 and not _candidate_looks_like_reference_target(local_metadata, candidate):
            filtered.append(candidate)
    return filtered or candidates[:1]


def _candidate_looks_like_reference_target(local_metadata: dict[str, Any], candidate: dict[str, Any]) -> bool:
    """识别候选是否其实是“被引论文”却被误当成正本——标题相似度过低却仍被纳入候选时降权。"""
    local_title = str(local_metadata.get("title") or "").lower()
    candidate_title = str(candidate.get("title") or "").lower()
    if not local_title or not candidate_title:
        return False
    if candidate_title in local_title or local_title in candidate_title:
        return False
    similarity = SequenceMatcher(None, local_title, candidate_title).ratio()
    return similarity < 0.6


def _extract_crossref_year(item: dict[str, Any]) -> int | None:
    for key in ("published-print", "published-online", "issued", "created"):
        value = item.get(key) or {}
        date_parts = value.get("date-parts") or []
        if date_parts and date_parts[0]:
            year = date_parts[0][0]
            if isinstance(year, int):
                return year
    return None


def _extract_year(text: str) -> int | None:
    match = re.search(r"(19|20)\d{2}", text)
    return int(match.group(0)) if match else None


def _extract_doi(raw_text: str) -> str | None:
    match = re.search(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", raw_text, flags=re.IGNORECASE)
    return match.group(0).rstrip(").,;") if match else None


def _extract_arxiv_id(raw_text: str) -> str | None:
    match = re.search(r"\barxiv[:\s]*([0-9]{4}[.-][0-9]{4,5}(?:v\d+)?)\b", raw_text, flags=re.IGNORECASE)
    return _normalize_arxiv_id(match.group(1)) if match else None


def _extract_arxiv_id_from_url(raw_text: str) -> str | None:
    match = re.search(r"arxiv\.org/(?:abs|pdf)/([0-9]{4}[.-][0-9]{4,5}(?:v\d+)?)", raw_text, flags=re.IGNORECASE)
    return _normalize_arxiv_id(match.group(1)) if match else None


def _extract_bare_arxiv_id(raw_text: str) -> str | None:
    match = re.fullmatch(r"\s*([0-9]{4}[.-][0-9]{4,5}(?:v\d+)?)\s*", raw_text, flags=re.IGNORECASE)
    return _normalize_arxiv_id(match.group(1)) if match else None


def _normalize_arxiv_id(value: str) -> str:
    return value.strip().replace("-", ".")


def _arxiv_ids_match(left: str, right: str) -> bool:
    return _strip_arxiv_version(left) == _strip_arxiv_version(right)


def _strip_arxiv_version(value: str) -> str:
    return re.sub(r"v\d+$", "", _normalize_arxiv_id(value).lower())


def _is_valid_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _strip_jats_tags(text: str) -> str:
    if not text:
        return ""
    return _normalize_whitespace(html.unescape(re.sub(r"<[^>]+>", " ", text)))


def _strip_xml(text: str) -> str:
    return _normalize_whitespace(html.unescape(re.sub(r"<[^>]+>", " ", text)))


def _normalize_arxiv_authors(authors: list[str]) -> list[str]:
    normalized: list[str] = []
    index = 0
    while index < len(authors):
        current = authors[index].strip()
        next_author = authors[index + 1].strip() if index + 1 < len(authors) else ""
        if _looks_like_single_name(current) and _looks_like_single_name(next_author):
            normalized.append(f"{current} {next_author}")
            index += 2
            continue
        if current:
            normalized.append(current)
        index += 1
    return normalized


def _looks_like_single_name(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Z][A-Za-z'`-]+", value.strip()))


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _format_citation(title: str, authors: list[str], year: int | None, venue: str | None) -> str | None:
    if not title:
        return None
    author_part = ", ".join(authors[:4]) if authors else "Unknown authors"
    year_part = str(year) if year else "n.d."
    venue_part = f" {venue}." if venue else ""
    return f"{author_part} ({year_part}). {title}.{venue_part}".strip()


def _build_simple_bibtex(
    title: str,
    authors: list[str],
    year: int | None,
    venue: str | None,
    doi: str | None,
    arxiv_id: str | None,
) -> str | None:
    if not title:
        return None
    key_base = re.sub(r"[^a-z0-9]+", "", (authors[0] if authors else "paper").lower())[:12] or "paper"
    key = f"{key_base}{year or 'nd'}"
    fields = [
        f"  title = {{{title}}}",
        f"  author = {{{' and '.join(authors)}}}" if authors else None,
        f"  year = {{{year}}}" if year else None,
        f"  journal = {{{venue}}}" if venue else None,
        f"  doi = {{{doi}}}" if doi else None,
        f"  eprint = {{{arxiv_id}}}" if arxiv_id else None,
    ]
    rendered = ",\n".join(field for field in fields if field)
    return f"@article{{{key},\n{rendered}\n}}"


def _citations_from_crossref(references: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in references:
        if not isinstance(item, dict):
            continue
        title = _normalize_whitespace(
            str(item.get("article-title") or item.get("series-title") or item.get("volume-title") or "")
        )
        authors = _split_reference_author_string(str(item.get("author") or ""))
        year = _to_int(item.get("year"))
        venue = _normalize_whitespace(str(item.get("journal-title") or item.get("container-title") or "")) or None
        doi = str(item.get("DOI") or "").strip() or None
        if not title and not doi:
            continue
        normalized.append(
            {
                "title": title or (doi or "Untitled reference"),
                "authors": authors,
                "year": year,
                "venue": venue,
                "doi": doi,
            }
        )
    return merge_citations([], normalized)


def _citations_from_semantic_scholar(references: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in references:
        if not isinstance(item, dict):
            continue
        external_ids = item.get("externalIds") or {}
        authors = [
            str(author.get("name") or "").strip()
            for author in item.get("authors", [])
            if isinstance(author, dict) and str(author.get("name") or "").strip()
        ]
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        year = item.get("year") if isinstance(item.get("year"), int) else None
        normalized.append(
            {
                "title": title,
                "authors": authors,
                "year": year,
                "venue": str(item.get("venue") or "").strip() or None,
                "doi": str(external_ids.get("DOI") or "").strip() or None,
            }
        )
    return merge_citations([], normalized)


def _split_reference_author_string(value: str) -> list[str]:
    if not value:
        return []
    separators = re.split(r";| and ", value)
    authors = [_normalize_whitespace(part.strip(" ,.")) for part in separators if part.strip(" ,.")] 
    return authors[:16]


def _normalize_citation_item(item: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    title = _normalize_whitespace(str(item.get("title") or ""))
    doi = str(item.get("doi") or "").strip() or None
    if not title and not doi:
        return None
    authors = [
        _normalize_whitespace(str(author))
        for author in item.get("authors", [])
        if _normalize_whitespace(str(author))
    ]
    year = _to_int(item.get("year"))
    venue = _normalize_whitespace(str(item.get("venue") or "")) or None
    return {
        "title": title or doi or "Untitled reference",
        "authors": authors[:16],
        "year": year,
        "venue": venue,
        "doi": doi,
    }


def _citation_score(item: dict[str, Any]) -> tuple[int, int, int, int]:
    return (
        1 if item.get("doi") else 0,
        1 if item.get("venue") else 0,
        len(item.get("authors") or []),
        1 if item.get("year") else 0,
    )


def _to_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    try:
        number = int(str(value).strip())
    except Exception:
        return None
    return number if 1800 <= number <= 2100 else None
