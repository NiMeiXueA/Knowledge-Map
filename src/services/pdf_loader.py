from __future__ import annotations

from pathlib import Path
from io import BytesIO
import logging
import json
import shutil
import subprocess
import tempfile
import time
import zipfile
from io import BytesIO
from urllib.parse import urlparse

import fitz
import httpx
from pypdf import PdfReader
from PIL import Image

from src.config import BASE_DIR, get_bool_env, get_env

try:
    import pytesseract
except Exception:  # pragma: no cover - optional dependency fallback
    pytesseract = None

logger = logging.getLogger(__name__)


def _extract_text_with_pymupdf(pdf_path: Path) -> tuple[list[str], int]:
    doc = fitz.open(pdf_path)
    return [page.get_text("text") for page in doc], doc.page_count


def _extract_text_with_pypdf(pdf_path: Path) -> tuple[list[str], int]:
    reader = PdfReader(str(pdf_path))
    return [page.extract_text() or "" for page in reader.pages], len(reader.pages)


def _is_ocr_available() -> bool:
    if pytesseract is None:
        return False
    tesseract_cmd = str(get_env("TESSERACT_CMD", "") or "").strip()
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _ocr_pdf_with_pymupdf(pdf_path: Path) -> tuple[str, list[str]]:
    warnings: list[str] = []
    if not _is_ocr_available():
        warnings.append("OCR 依赖未就绪：请安装 Tesseract 并配置 TESSERACT_CMD。")
        return "", warnings

    doc = fitz.open(pdf_path)
    text_parts: list[str] = []
    for page_index, page in enumerate(doc):
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        image = Image.open(BytesIO(pix.tobytes("png")))
        page_text = pytesseract.image_to_string(image, lang="chi_sim+eng")
        if page_text.strip():
            text_parts.append(page_text.strip())
        else:
            warnings.append(f"第 {page_index + 1} 页 OCR 未提取到有效文本。")
    return "\n".join(text_parts).strip(), warnings


def _resolve_mineru_parse_dir(output_dir: Path, stem: str, backend: str, method: str) -> Path:
    if backend.startswith("pipeline"):
        return output_dir / stem / method
    if backend.startswith("vlm"):
        return output_dir / stem / "vlm"
    if backend.startswith("hybrid"):
        return output_dir / stem / f"hybrid_{method}"
    return output_dir / stem


def _extract_text_from_mineru_outputs(parse_dir: Path, stem: str) -> str:
    markdown_path = parse_dir / f"{stem}.md"
    if markdown_path.exists():
        return markdown_path.read_text(encoding="utf-8", errors="ignore").strip()

    content_list_path = parse_dir / f"{stem}_content_list.json"
    if content_list_path.exists():
        data = json.loads(content_list_path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            texts: list[str] = []
            for item in data:
                if isinstance(item, dict):
                    for key in ("text", "content", "latex"):
                        value = item.get(key)
                        if isinstance(value, str) and value.strip():
                            texts.append(value.strip())
                            break
            return "\n".join(texts).strip()

    middle_json_path = parse_dir / f"{stem}_middle.json"
    if middle_json_path.exists():
        data = json.loads(middle_json_path.read_text(encoding="utf-8"))
        texts: list[str] = []
        for page in data.get("pdf_info", []) if isinstance(data, dict) else []:
            if not isinstance(page, dict):
                continue
            for block in page.get("para_blocks", []) or []:
                if not isinstance(block, dict):
                    continue
                text = block.get("text") or block.get("content")
                if isinstance(text, str) and text.strip():
                    texts.append(text.strip())
        return "\n".join(texts).strip()

    return ""


def _extract_text_from_mineru_zip(content: bytes, stem: str) -> str:
    with zipfile.ZipFile(BytesIO(content)) as archive:
        names = archive.namelist()

        full_md_candidates = [name for name in names if name.endswith("full.md")]
        if full_md_candidates:
            best = min(full_md_candidates, key=len)
            return archive.read(best).decode("utf-8", errors="ignore").strip()

        stem_md_candidates = [name for name in names if name.endswith(f"{stem}.md")]
        if stem_md_candidates:
            best = min(stem_md_candidates, key=len)
            return archive.read(best).decode("utf-8", errors="ignore").strip()

        content_list_candidates = [name for name in names if name.endswith("_content_list.json")]
        for name in content_list_candidates:
            data = json.loads(archive.read(name).decode("utf-8", errors="ignore"))
            if isinstance(data, list):
                texts: list[str] = []
                for item in data:
                    if isinstance(item, dict):
                        for key in ("text", "content", "latex"):
                            value = item.get(key)
                            if isinstance(value, str) and value.strip():
                                texts.append(value.strip())
                                break
                if texts:
                    return "\n".join(texts).strip()
    return ""


def _get_mineru_remote_base_url() -> str:
    raw_url = str(get_env("MINERU_API_URL", "") or "").strip()
    raw_base = str(get_env("MINERU_API_BASE_URL", "https://mineru.net") or "https://mineru.net").strip()
    candidate = raw_url if raw_url.startswith(("http://", "https://")) else raw_base
    parsed = urlparse(candidate)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return candidate.rstrip("/")


def _is_valid_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _extract_text_with_mineru_remote(pdf_path: Path) -> tuple[str, int, list[str]]:
    warnings: list[str] = []
    token = str(get_env("MINERU_API_TOKEN", "") or "").strip()
    if not token:
        raise ValueError("未配置 MINERU_API_TOKEN，无法使用远程 MinerU 服务。")

    base_url = _get_mineru_remote_base_url()
    if not _is_valid_http_url(base_url):
        raise ValueError("MINERU_API_URL / MINERU_API_BASE_URL 不是合法的 http(s) 地址。")

    model_version = "vlm" if str(get_env("MINERU_BACKEND", "pipeline") or "pipeline").strip() == "vlm" else "pipeline"
    language = str(get_env("MINERU_LANG", "ch") or "ch").strip()
    is_ocr = get_bool_env("OCR_ENABLED", True)
    enable_formula = True
    enable_table = True
    timeout_seconds = int(get_env("MINERU_API_TIMEOUT", 600) or 600)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    try:
        _, page_count = _extract_text_with_pypdf(pdf_path)
    except Exception:
        page_count = 0

    with httpx.Client(timeout=120) as client:
        create_resp = client.post(
            f"{base_url}/api/v4/file-urls/batch",
            headers=headers,
            json={
                "files": [{"name": pdf_path.name, "is_ocr": is_ocr}],
                "model_version": model_version,
                "language": language,
                "enable_formula": enable_formula,
                "enable_table": enable_table,
            },
        )
        create_resp.raise_for_status()
        create_data = create_resp.json()
        if create_data.get("code") != 0:
            raise RuntimeError(f"MinerU 申请上传链接失败：{create_data.get('msg')}")

        batch_id = create_data["data"]["batch_id"]
        upload_urls = create_data["data"]["file_urls"]
        if not upload_urls:
            raise RuntimeError("MinerU 未返回文件上传地址。")

        with pdf_path.open("rb") as file_obj:
            upload_resp = client.put(upload_urls[0], content=file_obj.read(), headers={})
        if upload_resp.status_code not in {200, 201}:
            raise RuntimeError(f"MinerU 文件上传失败：HTTP {upload_resp.status_code}")

        deadline = time.time() + timeout_seconds
        last_state = "waiting-file"
        while time.time() < deadline:
            poll_resp = client.get(f"{base_url}/api/v4/extract-results/batch/{batch_id}", headers=headers)
            poll_resp.raise_for_status()
            poll_data = poll_resp.json()
            if poll_data.get("code") != 0:
                raise RuntimeError(f"MinerU 轮询失败：{poll_data.get('msg')}")

            results = poll_data.get("data", {}).get("extract_result", [])
            if not results:
                time.sleep(2)
                continue

            item = results[0]
            state = item.get("state", "")
            last_state = state
            if state == "done":
                full_zip_url = item.get("full_zip_url")
                if not full_zip_url:
                    raise RuntimeError("MinerU 已完成解析，但未返回 full_zip_url。")
                zip_resp = client.get(full_zip_url)
                zip_resp.raise_for_status()
                text = _extract_text_from_mineru_zip(zip_resp.content, pdf_path.stem)
                if not text:
                    raise RuntimeError("MinerU 结果包已下载，但未提取到可读文本。")
                return text, page_count, warnings
            if state == "failed":
                raise RuntimeError(f"MinerU 远程解析失败：{item.get('err_msg') or '未知错误'}")
            time.sleep(2)

    raise TimeoutError(f"MinerU 远程解析超时，最后状态为：{last_state}")


def _extract_text_with_mineru(pdf_path: Path) -> tuple[str, int, list[str]]:
    warnings: list[str] = []
    if str(get_env("MINERU_API_TOKEN", "") or "").strip():
        return _extract_text_with_mineru_remote(pdf_path)

    cli_command = str(get_env("MINERU_CLI_COMMAND", "mineru") or "mineru").strip()
    cli_path = shutil.which(cli_command) or (cli_command if Path(cli_command).exists() else None)
    if not cli_path:
        raise FileNotFoundError("未找到 MinerU CLI，可通过 MINERU_CLI_COMMAND 指定可执行文件路径。")

    method = str(get_env("MINERU_METHOD", "auto") or "auto").strip()
    backend = str(get_env("MINERU_BACKEND", "pipeline") or "pipeline").strip()
    effort = str(get_env("MINERU_EFFORT", "medium") or "medium").strip()
    lang = str(get_env("MINERU_LANG", "ch") or "ch").strip()
    api_url = str(get_env("MINERU_API_URL", "") or "").strip()
    parsed_api_url = urlparse(api_url) if api_url else None

    with tempfile.TemporaryDirectory(prefix="mineru-", dir=str(BASE_DIR)) as temp_dir:
        output_dir = Path(temp_dir) / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        command = [
            cli_path,
            "-p",
            str(pdf_path),
            "-o",
            str(output_dir),
            "-m",
            method,
            "-b",
            backend,
            "-l",
            lang,
            "--effort",
            effort,
        ]
        if api_url and parsed_api_url and parsed_api_url.scheme in {"http", "https"}:
            command.extend(["--api-url", api_url])
        elif api_url:
            warnings.append("MINERU_API_URL 不是合法的 http(s) 地址，已忽略该配置并改用 MinerU 默认行为。")

        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"MinerU 解析失败（exit={result.returncode}）：{(result.stderr or result.stdout).strip()[:800]}"
            )

        parse_dir = _resolve_mineru_parse_dir(output_dir, pdf_path.stem, backend, method)
        text = _extract_text_from_mineru_outputs(parse_dir, pdf_path.stem)
        if not text:
            warnings.append("MinerU 已执行，但未在预期输出目录中找到可读文本，已回退。")
        _, page_count = _extract_text_with_pypdf(pdf_path)
        return text, page_count, warnings


def extract_pdf_text(pdf_path: Path) -> dict:
    parser_backend = str(get_env("PDF_PARSER_BACKEND", "auto") or "auto").strip().lower()
    text_parts: list[str] = []
    page_count = 0
    parser_used = "pymupdf"
    warning_messages: list[str] = []

    if parser_backend in {"mineru", "auto"}:
        try:
            mineru_text, mineru_page_count, mineru_warnings = _extract_text_with_mineru(pdf_path)
            if mineru_text:
                raw_text = mineru_text
                page_count = mineru_page_count
                parser_used = "mineru"
                warning_messages.extend(mineru_warnings)
            else:
                raise ValueError("MinerU 未返回可用文本。")
        except Exception as exc:
            if parser_backend == "mineru":
                raise
            warning_messages.append(f"MinerU 不可用，已回退到本地 PDF 文本抽取：{exc}")
        else:
            min_text_length = int(get_env("OCR_MIN_TEXT_LENGTH", 500) or 500)
            possibly_scanned = len(raw_text) < min_text_length
            return {
                "raw_text": raw_text,
                "page_count": page_count,
                "possibly_scanned_pdf": possibly_scanned,
                "used_ocr": True,
                "parser_backend": parser_used,
                "warning": " ".join(dict.fromkeys(message for message in warning_messages if message)) or None,
            }

    try:
        text_parts, page_count = _extract_text_with_pymupdf(pdf_path)
    except Exception as exc:
        logger.warning("PyMuPDF extraction failed for %s: %s", pdf_path, exc)
        text_parts, page_count = _extract_text_with_pypdf(pdf_path)
        parser_used = "pypdf"

    raw_text = "\n".join(part.strip() for part in text_parts if part).strip()
    min_text_length = int(get_env("OCR_MIN_TEXT_LENGTH", 500) or 500)
    possibly_scanned = len(raw_text) < min_text_length
    used_ocr = False

    if possibly_scanned:
        warning_messages.append("检测到文本较短，疑似扫描版 PDF。")
        if get_bool_env("OCR_ENABLED", True):
            ocr_text, ocr_warnings = _ocr_pdf_with_pymupdf(pdf_path)
            warning_messages.extend(ocr_warnings)
            if len(ocr_text) > len(raw_text):
                raw_text = ocr_text
                used_ocr = True
                possibly_scanned = len(raw_text) < min_text_length
                if raw_text:
                    warning_messages.append("已自动切换 OCR 并使用 OCR 结果继续分析。")
        else:
            warning_messages.append("OCR 已关闭，当前仅使用常规文本抽取。")

    return {
        "raw_text": raw_text,
        "page_count": page_count,
        "possibly_scanned_pdf": possibly_scanned,
        "used_ocr": used_ocr,
        "parser_backend": parser_used,
        "warning": " ".join(dict.fromkeys(message for message in warning_messages if message)) or None,
    }
