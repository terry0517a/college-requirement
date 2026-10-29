"""Geometry and text normalisation for the CAC 篩選標準一覽表 PNG (no OCR here)."""
from __future__ import annotations

import io
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

import numpy as np
from PIL import Image

LINE_DARK = 160   # gray below this counts as part of a grid line
INK_DARK = 110    # gray below this counts as text ink

_SIMPLIFIED = {
    "数": "數", "国": "國", "测": "測", "筛": "篩", "顺": "順", "标": "標", "级": "級",
    "额": "額", "顶": "頂", "会": "會", "听": "聽", "学": "學", "组": "組",
}
_TRANS = str.maketrans({**_SIMPLIFIED, "（": "(", "）": ")"})
_MISSING = {"", "--", "-", "—", "－－", "－"}


def to_gray(png: bytes) -> np.ndarray:
    return np.asarray(Image.open(io.BytesIO(png)).convert("L"), dtype=np.uint8)


def _longest_run(mask: np.ndarray) -> int:
    """Length of the longest contiguous True run in a 1-D bool array."""
    padded = np.concatenate(([False], mask, [False]))
    edges = np.flatnonzero(padded[1:] != padded[:-1])
    return int((edges[1::2] - edges[0::2]).max()) if len(edges) else 0


def _merge(positions: list[int], max_gap: int = 2) -> list[int]:
    """Merge positions whose neighbours are within max_gap; return midpoints."""
    out: list[int] = []
    group: list[int] = []
    for p in positions:
        if group and p - group[-1] > max_gap:
            out.append((group[0] + group[-1]) // 2)
            group = []
        group.append(p)
    if group:
        out.append((group[0] + group[-1]) // 2)
    return out


def detect_hlines(gray: np.ndarray) -> list[int]:
    dark = gray < LINE_DARK
    limit = gray.shape[1] * 0.3
    return _merge([y for y in range(gray.shape[0]) if _longest_run(dark[y]) > limit])


def grid_rows(gray: np.ndarray, hlines: list[int]) -> list[tuple[int, int, bool]]:
    # the image top/bottom bound the title and notes areas, which have no lines of their own
    bounds = sorted({0, gray.shape[0], *hlines})
    rows = []
    for y0, y1 in zip(bounds, bounds[1:]):
        frac = (gray[y0:y1 + 1] < LINE_DARK).mean(axis=0)
        xs = _merge([int(x) for x in np.flatnonzero(frac >= 0.9)])
        rows.append((y0, y1, len(xs) >= 3))
    return rows


@dataclass
class Table:
    y0: int
    y1: int
    above: tuple[int, int] | None


def split_tables(rows: list[tuple[int, int, bool]]) -> list[Table]:
    tables: list[Table] = []
    current: Table | None = None
    last_plain: tuple[int, int] | None = None
    for y0, y1, is_grid in rows:
        if is_grid:
            if current is None:
                current = Table(y0, y1, last_plain)
                tables.append(current)
            else:
                current.y1 = y1
        else:
            current = None
            last_plain = (y0, y1)
    return tables


def detect_vlines(gray: np.ndarray, y0: int, y1: int) -> list[int]:
    dark = gray[y0:y1 + 1] < LINE_DARK
    limit = (y1 - y0) * 0.6
    return _merge([x for x in range(gray.shape[1]) if _longest_run(dark[:, x]) > limit])


def cell_lines(gray: np.ndarray, y0: int, y1: int, x0: int, x1: int) -> list[np.ndarray]:
    """Crop the cell (inset 2 px) and split it into text-line images."""
    cell = gray[y0 + 2:y1 - 1, x0 + 2:x1 - 1]
    ink = cell < INK_DARK
    if ink.sum() < 4:
        return []
    ys = np.flatnonzero(ink.any(axis=1))
    bands: list[list[int]] = []
    for y in ys:
        if bands and y - bands[-1][1] <= 3:
            bands[-1][1] = int(y)
        else:
            bands.append([int(y), int(y)])
    lines = []
    for a, b in bands:
        if b - a + 1 < 6:
            continue
        xs = np.flatnonzero(ink[a:b + 1].any(axis=0))
        left = max(int(xs[0]) - 6, 0)
        right = min(int(xs[-1]) + 7, cell.shape[1])
        lines.append(cell[a:b + 1, left:right])
    return lines


# ---------------------------------------------------------------- text values

def normalize_text(s: str) -> str:
    return re.sub(r"\s+", "", s.translate(_TRANS))


def parse_level(s: str) -> str | None:
    t = normalize_text(s)
    if t in _MISSING or t[0] not in "頂前均後底":
        return None
    return t[0] + "標"


def parse_listening(s: str) -> str | None:
    t = normalize_text(s).upper()
    return t if t in ("A", "B", "C") else None


def parse_multiplier(s: str) -> Decimal | None:
    try:
        d = Decimal(normalize_text(s))
    except InvalidOperation:
        return None
    return d if d.is_finite() else None


def parse_quota(s: str) -> int:
    return int(normalize_text(s))


@dataclass
class SieveLevel:
    order: int
    label: str
    subjects: list[str]
    min_score: Decimal


# longest token first: 英聽 before 英, 數學A/數A before 數
_ABBREV = {
    "國文": "國文", "英文": "英文", "英聽": "英聽", "數學A": "數學A", "數學B": "數學B",
    "數A": "數學A", "數B": "數學B", "社會": "社會", "自然": "自然",
    "國": "國文", "英": "英文", "社": "社會", "自": "自然",
}
_TOKENS = sorted(_ABBREV, key=len, reverse=True)


def expand_subjects(s: str) -> list[str]:
    t = normalize_text(s)
    if not t:
        return []
    if "+" in t:
        return t.split("+")
    out: list[str] = []
    i = 0
    while i < len(t):
        tok = next((k for k in _TOKENS if t.startswith(k, i)), None)
        if tok is None:
            return []
        out.append(_ABBREV[tok])
        i += len(tok)
    return out


_CELL = re.compile(r"^\(?(.+?)\)?\s*(\d+(?:\.\d+)?)$")


def parse_sieve_cell(s: str) -> SieveLevel | None:
    t = normalize_text(s)
    if t in _MISSING:
        return None
    m = _CELL.match(t)
    if not m or re.fullmatch(r"[\d.]+", m.group(1)):  # bare number: the lazy group swallowed a digit
        return None
    return SieveLevel(order=0, label=t, subjects=expand_subjects(m.group(1)),
                      min_score=Decimal(m.group(2)))


def normalize_program_name(name: str, gender: str | None) -> str:
    n = re.sub(r"\s+", "", unicodedata.normalize("NFKC", name))  # NFKC also maps （） to ()
    g = normalize_text(gender or "")
    return f"{n}({g})" if g in ("男", "女") else n
