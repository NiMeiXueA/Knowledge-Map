from __future__ import annotations

from src.services.paper_metadata_pipeline import build_verified_metadata, build_verified_metadata_from_reference


async def analyze_source(raw_text: str, reference: str | None = None) -> dict:
    if reference and not raw_text.strip():
        return await build_verified_metadata_from_reference(reference)
    return await build_verified_metadata(raw_text, reference)
