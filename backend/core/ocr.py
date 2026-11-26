from __future__ import annotations

import base64
import binascii
import io
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps, ImageStat, UnidentifiedImageError
from rapidfuzz import fuzz

from .constants import CATEGORIES

_MAX_IMAGE_BYTES = 10 * 1024 * 1024
_RECORD_PAIR_RE = re.compile(r"(\d+)\s*[-–—/]\s*(\d+)")
_PERCENT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_DECIMAL_RE = re.compile(r"(?<!\d)(?:0?\.\d{2,4}|1\.0{1,3})(?!\d)")
_DATA_URL_PREFIX_RE = re.compile(r"^data:image/[a-zA-Z0-9.+-]+;base64,", re.IGNORECASE)


def _find_tesseract() -> str:
    """Locate the system tesseract binary or raise an informative error."""
    found = shutil.which("tesseract")
    if found:
        return found
    for candidate in ("/opt/homebrew/bin/tesseract", "/usr/local/bin/tesseract"):
        if Path(candidate).is_file() and os.access(candidate, os.X_OK):
            return candidate
    raise RuntimeError(
        "Tesseract OCR binary not found. Install tesseract (e.g. `brew install tesseract`) "
        "or paste the stats table text directly."
    )


def decode_image_base64(
    image_base64: str,
    max_bytes: int = _MAX_IMAGE_BYTES,
) -> bytes:
    """Decode a base64 image string (with optional data URL prefix) with size checks."""
    cleaned = image_base64.strip()
    if not cleaned:
        raise ValueError("Image payload is empty.")
    cleaned = _DATA_URL_PREFIX_RE.sub("", cleaned, count=1).strip()
    if not cleaned:
        raise ValueError("Image payload is empty.")
    try:
        raw = base64.b64decode(cleaned, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Invalid base64 image encoding.") from exc
    if not raw:
        raise ValueError("Decoded image is empty.")
    if len(raw) > max_bytes:
        raise ValueError(
            f"Image exceeds maximum allowed size ({max_bytes // (1024 * 1024)} MB)."
        )
    return raw


def extract_text_from_image_bytes(image_bytes: bytes) -> str:
    """Preprocess screenshot image (invert dark mode, upscale, autocontrast) and run Tesseract."""
    tesseract_bin = _find_tesseract()
    try:
        with Image.open(io.BytesIO(image_bytes)) as opened:
            if opened.mode in ("RGBA", "LA") or (
                opened.mode == "P" and "transparency" in opened.info
            ):
                rgba = opened.convert("RGBA")
                bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
                composed = Image.alpha_composite(bg, rgba)
                gray = composed.convert("L")
            else:
                gray = opened.convert("L")
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError("Could not read image data as a supported screenshot.") from exc

    mean_brightness = ImageStat.Stat(gray).mean[0]
    if mean_brightness < 128.0:
        gray = ImageOps.invert(gray)

    if gray.width < 1800:
        gray = gray.resize(
            (gray.width * 2, gray.height * 2),
            Image.Resampling.LANCZOS,
        )

    gray = ImageOps.autocontrast(gray, cutoff=1)

    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name
        gray.save(tmp_path, format="PNG")
        proc = subprocess.run(
            [tesseract_bin, tmp_path, "stdout", "--psm", "6"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Tesseract OCR timed out while processing screenshot.") from exc
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)

    if proc.returncode != 0:
        err = proc.stderr.strip() or f"exit code {proc.returncode}"
        raise RuntimeError(f"Tesseract OCR failed: {err}")

    return proc.stdout


def _normalize_for_match(text: str) -> str:
    cleaned = re.sub(r"[/\\|_:\-]+", " ", text.upper())
    return re.sub(r"\s+", " ", cleaned).strip()


def _match_category_on_line(line: str) -> tuple[str | None, str]:
    """Identify the LearnedLeague category at the start of a line and return trailing text."""
    norm_line = _normalize_for_match(line)
    if not norm_line:
        return None, ""

    # Separate leading text prefix before first numeric record/percentage
    prefix_match = re.match(r"^([^\d%]+?)(?=\s*\d|\s*\.|\s*$)", line.strip())
    prefix_raw = prefix_match.group(1).strip() if prefix_match else line.strip()
    norm_prefix = _normalize_for_match(prefix_raw)
    tail = line.strip()[len(prefix_raw) :].strip() if prefix_match else line.strip()

    # 1. Exact word-boundary match of normalized category name
    for cat in CATEGORIES:
        norm_cat = _normalize_for_match(cat)
        if re.search(rf"\b{re.escape(norm_cat)}\b", norm_line):
            return cat, tail

    # 2. Fuzzy match against leading non-digit prefix (handles OCR slash -> 'I' glitches)
    if len(norm_prefix) < 2:
        return None, ""

    best_cat: str | None = None
    best_score = 0.0
    compact_prefix = norm_prefix.replace(" ", "")
    for cat in CATEGORIES:
        norm_cat = _normalize_for_match(cat)
        compact_cat = norm_cat.replace(" ", "")
        if len(norm_cat) <= 4:
            score = float(fuzz.ratio(norm_cat, norm_prefix))
        else:
            score = max(
                float(fuzz.partial_ratio(norm_cat, norm_prefix)),
                float(fuzz.ratio(compact_cat, compact_prefix)),
            )
        if score > best_score:
            best_score = score
            best_cat = cat

    if best_cat is not None and best_score >= 80.0:
        return best_cat, tail
    return None, ""


def _extract_metric_from_tail(tail: str) -> dict[str, Any] | None:
    """Parse (correct, total, percent) or fallback percent from the remainder of a stats row."""
    for m in _RECORD_PAIR_RE.finditer(tail):
        correct = int(m.group(1))
        total = int(m.group(2))
        if total > 0 and 0 <= correct <= total:
            return {
                "correct": correct,
                "total": total,
                "percent": round(correct / total, 6),
            }

    pct_match = _PERCENT_RE.search(tail)
    if pct_match:
        val = float(pct_match.group(1)) / 100.0
        if 0.0 <= val <= 1.0:
            return {"correct": 0, "total": 0, "percent": round(val, 6)}

    dec_match = _DECIMAL_RE.search(tail)
    if dec_match:
        val = float(dec_match.group(0))
        if 0.0 <= val <= 1.0:
            return {"correct": 0, "total": 0, "percent": round(val, 6)}

    return None


def parse_category_stats_text(text: str) -> dict[str, Any]:
    """Parse LearnedLeague category performance text into structured category_metrics."""
    category_metrics: dict[str, dict[str, Any]] = {}

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        cat, tail = _match_category_on_line(line)
        if cat is None:
            continue
        metric = _extract_metric_from_tail(tail) or _extract_metric_from_tail(line)
        if metric is None:
            continue
        existing = category_metrics.get(cat)
        if existing is None or (existing["total"] == 0 and metric["total"] > 0):
            category_metrics[cat] = metric

    missing = [cat for cat in CATEGORIES if cat not in category_metrics]
    return {
        "category_metrics": category_metrics,
        "matched_count": len(category_metrics),
        "missing_categories": missing,
        "raw_text": text,
    }
