from __future__ import annotations

import re
from pathlib import Path

from src.config import PAPER_DIR


def slugify_paper_id(title: str, fallback: str = "paper") -> str:
    lowered = title.lower()
    slug = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", lowered).strip("-")
    return slug[:80] or fallback


def ensure_unique_paper_id(candidate: str, existing_ids: set[str]) -> str:
    if candidate not in existing_ids:
        return candidate
    index = 2
    while f"{candidate}-{index}" in existing_ids:
        index += 1
    return f"{candidate}-{index}"


def move_pdf_to_category(source_path: Path, target_folder: str, paper_id: str) -> Path:
    destination_dir = PAPER_DIR / target_folder
    destination_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9\u4e00-\u9fff._-]+", "_", f"{paper_id}.pdf")
    destination = destination_dir / safe_name
    counter = 2
    while destination.exists():
        destination = destination_dir / re.sub(r"\.pdf$", f"-{counter}.pdf", safe_name, flags=re.IGNORECASE)
        counter += 1
    source_path.replace(destination)
    return destination

