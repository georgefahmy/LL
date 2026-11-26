from __future__ import annotations

import base64
import io
import shutil

import pytest
from PIL import Image, ImageDraw

from backend.core.ocr import (
    decode_image_base64,
    extract_text_from_image_bytes,
    parse_category_stats_text,
)


def test_parse_category_stats_text_clean_and_noisy_lines() -> None:
    sample = """
    Category    Record    Pct
    AMER HIST   15-20     .750
    ART         8-16      .500
    BUS ECON    12/20     60%
    CLASS MUSIC 5-10      .500
    CURR EVENTS 14 - 20   .700
    GAMESISPORT 9-12      .750
    SCIENCE     72.5%
    WORLD HIST  0.650
    PARTICIPATION 10-20   .500
    """
    parsed = parse_category_stats_text(sample)
    metrics = parsed["category_metrics"]

    assert parsed["matched_count"] == 8
    assert metrics["AMER HIST"] == {"correct": 15, "total": 20, "percent": 0.75}
    assert metrics["ART"] == {"correct": 8, "total": 16, "percent": 0.5}
    assert metrics["BUS/ECON"] == {"correct": 12, "total": 20, "percent": 0.6}
    assert metrics["CLASS MUSIC"] == {"correct": 5, "total": 10, "percent": 0.5}
    assert metrics["CURR EVENTS"] == {"correct": 14, "total": 20, "percent": 0.7}
    assert metrics["GAMES/SPORT"] == {"correct": 9, "total": 12, "percent": 0.75}
    assert metrics["SCIENCE"] == {"correct": 0, "total": 0, "percent": 0.725}
    assert metrics["WORLD HIST"] == {"correct": 0, "total": 0, "percent": 0.65}
    assert "PARTICIPATION" not in metrics
    assert len(parsed["missing_categories"]) == 10


def test_decode_image_base64_validation() -> None:
    raw = b"\x89PNG\r\n\x1a\nfake"
    encoded = "data:image/png;base64," + base64.b64encode(raw).decode("ascii")
    assert decode_image_base64(encoded) == raw

    with pytest.raises(ValueError, match="empty"):
        decode_image_base64("data:image/png;base64,")

    with pytest.raises(ValueError, match="Invalid base64"):
        decode_image_base64("not-valid-base64!!!")

    with pytest.raises(ValueError, match="maximum"):
        decode_image_base64(base64.b64encode(b"x" * 64).decode("ascii"), max_bytes=16)


def test_extract_text_from_synthetic_stats_image() -> None:
    if shutil.which("tesseract") is None:
        pytest.skip("tesseract binary not installed")

    img = Image.new("RGB", (640, 260), color=(20, 24, 34))
    draw = ImageDraw.Draw(img)
    lines = [
        "AMER HIST    15-20    .750",
        "ART          8-16     .500",
        "SCIENCE      18-20    .900",
        "WORLD HIST   6-15     .400",
    ]
    y = 25
    for line in lines:
        draw.text((25, y), line, fill=(240, 244, 248))
        y += 50

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    ocr_text = extract_text_from_image_bytes(buf.getvalue())
    parsed = parse_category_stats_text(ocr_text)
    assert parsed["matched_count"] >= 2
    assert "AMER HIST" in parsed["category_metrics"] or "SCIENCE" in parsed["category_metrics"]
