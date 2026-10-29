"""Geometry and text normalisation for the CAC 篩選標準一覽表 PNG (no OCR here)."""
from __future__ import annotations

import io
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Protocol

import numpy as np
from PIL import Image

LINE_DARK = 160   # gray below this counts as part of a grid line
INK_DARK = 110    # gray below this counts as text ink

_SIMPLIFIED = {
    "数": "數", "国": "國", "测": "測", "筛": "篩", "顺": "順", "标": "標", "级": "級",
    "额": "額", "别": "別", "顶": "頂", "会": "會", "听": "聽", "学": "學", "组": "組",
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
    if t in _MISSING:
        return None
    # noise may precede the level (丁頂標), and 標 itself is often misread: key on the level character
    first = next((c for c in t if c in "頂前均後底"), None)
    return first + "標" if first else None


def parse_listening(s: str) -> str | None:
    t = normalize_text(s).upper()
    return t if t in ("A", "B", "C") else None


def parse_multiplier(s: str) -> Decimal | None:
    try:
        d = Decimal(normalize_text(s).rstrip("."))  # a trailing "." is border noise
    except InvalidOperation:
        return None
    return d if d.is_finite() else None


def parse_quota(s: str) -> int:
    return int(normalize_text(s).rstrip("."))


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


# ------------------------------------------------------------------------ OCR

class OcrEngine(Protocol):
    def recognize(self, line: np.ndarray) -> str: ...


class RapidOcrEngine:
    """Per-line recognition only (use_det=False); whole-image detection misreads this table."""

    TARGET_HEIGHT = 40

    def __init__(self) -> None:
        from rapidocr_onnxruntime import RapidOCR  # lazy: model load is slow

        self._engine = RapidOCR()

    def recognize(self, line: np.ndarray) -> str:
        h = line.shape[0]
        if h < self.TARGET_HEIGHT:
            w = max(1, round(line.shape[1] * self.TARGET_HEIGHT / h))
            line = np.asarray(Image.fromarray(line).resize((w, self.TARGET_HEIGHT), Image.LANCZOS))
        img = np.ascontiguousarray(np.stack([line] * 3, axis=-1))
        result, _ = self._engine(img, use_det=False, use_cls=False)
        if not result:
            return ""
        first = result[0]
        return str(first[0] if len(first) == 2 else first[1])


# -------------------------------------------------------------- header mapping

_SUBJECT_HEADERS = ("國文", "英文", "數學A", "數學B", "社會", "自然", "英聽")
KNOWN_HEADERS: dict[str, str] = {
    "校系代碼": "code", "性別要求": "gender", "校系名稱": "name", "招生名額": "quota",
    **{h: h for h in _SUBJECT_HEADERS},
    "學測科目組合": "學測科目組合",
    **{f"篩選順序{n}": f"sieve{i}" for i, n in enumerate("一二三四五六", 1)},
    "同級分超額篩選": "overflow",
}
# merged header cells are cut by the column grid, so labels often arrive truncated
_HEADER_ALIASES = {
    "校系名": "name", "招生名": "quota", "超額": "overflow", "可力超": "overflow",
    **{f"順序{n}": f"sieve{i}" for i, n in enumerate("一二三四五六", 1)},
}
_HEADER_KEYS = sorted(KNOWN_HEADERS, key=len, reverse=True)
_ALIAS_KEYS = sorted(_HEADER_ALIASES, key=len, reverse=True)
_BASE_KEYS = ("code", "gender", "name", "quota", "overflow")
THRESHOLD_KEYS = ("國文", "英文", "數學A", "數學B", "社會", "自然", "英聽")
MULTIPLIER_KEYS = ("國文", "英文", "數學A", "數學B", "社會", "自然", "學測科目組合")


def map_headers(header_texts: list[str]) -> dict[int, tuple[str, str]] | None:
    seen: set[str] = set()
    mapping: dict[int, tuple[str, str]] = {}
    for i, raw in enumerate(header_texts):
        text = normalize_text(raw)
        key = next((KNOWN_HEADERS[k] for k in _HEADER_KEYS if k in text), None)
        if key is None:
            key = next((_HEADER_ALIASES[k] for k in _ALIAS_KEYS if k in text), None)
        if key is None and text == "英":  # 英聽 header is cut to its first character
            key = "英聽"
        if key is None or "APCS" in text.upper():  # APCS columns stack several values per cell
            mapping[i] = ("extra", text)
        elif key in _BASE_KEYS:
            mapping[i] = ("base", key)
        elif key.startswith("sieve"):
            mapping[i] = ("sieve", key)
        elif key == "學測科目組合":
            mapping[i] = ("multipliers", key)
        elif key in seen and key != "英聽":
            mapping[i] = ("multipliers", key)
        else:
            seen.add(key)
            mapping[i] = ("thresholds", key)
    present = {k for block, k in mapping.values() if block == "base"}
    if not {"code", "name", "quota"} <= present:
        return None
    return mapping


# ------------------------------------------------------------------ row parsing

@dataclass
class SieveRow:
    school_code: str
    cac_code: str
    gender: str | None
    name: str
    quota: int
    group: str
    thresholds: dict[str, str | None]
    multipliers: dict[str, Decimal | None]
    extra: dict[str, str]
    sieve: list[SieveLevel]
    overflow_tiebreak: bool
    raw_cells: list[str]


@dataclass
class SieveParseResult:
    rows: list[SieveRow]
    rows_skipped: int
    warnings: list[str]
    groups: list[str]


_DEFAULT_GROUP = "一般校系"
_NO_GENDER = {"", "無", "浦"}  # the stylised 無 is consistently read as 浦
_STARS = {"*", "＊", "水", "米", "×", "x"}  # the small asterisk is consistently read as 水
_MAX_HEADER_ROWS = 3


def _ocr_cell(gray: np.ndarray, y0: int, y1: int, x0: int, x1: int, ocr: OcrEngine) -> str:
    return normalize_text("".join(ocr.recognize(ln) for ln in cell_lines(gray, y0, y1, x0, x1)))


def _group_name(gray: np.ndarray, above: tuple[int, int] | None, ocr: OcrEngine) -> str:
    if above is None:
        return _DEFAULT_GROUP
    lines = cell_lines(gray, above[0], above[1], 0, gray.shape[1])
    if not lines:
        return _DEFAULT_GROUP
    text = normalize_text(ocr.recognize(lines[-1]))  # the marker is the line right above the table
    m = re.search(r"[【\[]([^】\]]+)", text)
    return m.group(1) if m else _DEFAULT_GROUP


def _repair_name(name: str) -> str:
    # the OCR model cannot read 戲 and drops it
    return "戲" + name if name.startswith("劇學系") else name


def _is_missing(text: str) -> bool:
    return text in _MISSING


def _build_row(cells: list[str], mapping: dict[int, tuple[str, str]], school_code: str,
               group: str) -> SieveRow:
    """Raise ValueError when the cells do not form a valid row."""
    base: dict[str, str] = {}
    thresholds: dict[str, str | None] = dict.fromkeys(THRESHOLD_KEYS)
    multipliers: dict[str, Decimal | None] = dict.fromkeys(MULTIPLIER_KEYS)
    extra: dict[str, str] = {}
    sieve_cells: dict[str, str] = {}
    for i, text in enumerate(cells):
        block, key = mapping.get(i, ("extra", ""))
        if block == "base":
            base[key] = text
        elif block == "sieve":
            sieve_cells[key] = text
        elif block == "extra":
            extra[key] = text
        elif block == "thresholds":
            value = parse_listening(text) if key == "英聽" else (parse_level(text) if text else None)
            if text and not _is_missing(text) and value is None:
                raise ValueError(f"bad {key} {text!r}")
            thresholds[key] = value
        else:
            value = parse_multiplier(text) if text else None
            if text and not _is_missing(text) and value is None:
                raise ValueError(f"bad multiplier {text!r}")
            multipliers[key] = value
    code = base.get("code", "")
    if not re.fullmatch(r"\d{6}", code) or code[:3] != school_code:
        raise ValueError(f"bad code {code!r}")
    gender = base.get("gender", "")
    if gender not in _NO_GENDER and gender not in ("男", "女"):
        raise ValueError(f"bad gender {gender!r}")
    gender = gender if gender in ("男", "女") else None
    if not base.get("name"):
        raise ValueError("empty name")
    quota = parse_quota(base["quota"])
    levels = []
    for key in (f"sieve{n}" for n in range(1, 7)):
        level = parse_sieve_cell(sieve_cells.get(key, ""))
        if level is not None:
            level.order = len(levels) + 1
            levels.append(level)
    return SieveRow(
        school_code=school_code, cac_code=code, gender=gender,
        name=normalize_program_name(_repair_name(base["name"]), gender), quota=quota, group=group,
        thresholds=thresholds, multipliers=multipliers, extra=extra, sieve=levels,
        overflow_tiebreak=base.get("overflow", "") in _STARS, raw_cells=cells,
    )


def _parse_table(gray: np.ndarray, table: Table, rows: list[tuple[int, int, bool]],
                 school_code: str, ocr: OcrEngine, result: SieveParseResult) -> None:
    xs = detect_vlines(gray, table.y0, table.y1)
    cols = list(zip(xs, xs[1:]))
    trows = [(y0, y1) for y0, y1, g in rows if g and y0 >= table.y0 and y1 <= table.y1]
    group = _group_name(gray, table.above, ocr)
    header_texts = [""] * len(cols)
    n_header = 0
    for y0, y1 in trows[:_MAX_HEADER_ROWS]:
        if re.fullmatch(r"\d{6}", _ocr_cell(gray, y0, y1, *cols[0], ocr)):
            break
        for i, (x0, x1) in enumerate(cols):
            header_texts[i] += _ocr_cell(gray, y0, y1, x0, x1, ocr)
        n_header += 1
    mapping = map_headers(header_texts)
    if mapping is None:
        result.warnings.append(f"skip table: unrecognised headers {header_texts}")
        return
    result.groups.append(group)
    for y0, y1 in trows[n_header:]:
        cells = [_ocr_cell(gray, y0, y1, x0, x1, ocr) for x0, x1 in cols]
        try:
            result.rows.append(_build_row(cells, mapping, school_code, group))
        except ValueError:
            result.rows_skipped += 1
            result.warnings.append(f"skip row: {cells}")


def parse_sieve_image(png: bytes, school_code: str, ocr: OcrEngine | None = None) -> SieveParseResult:
    ocr = ocr or RapidOcrEngine()
    gray = to_gray(png)
    rows = grid_rows(gray, detect_hlines(gray))
    result = SieveParseResult(rows=[], rows_skipped=0, warnings=[], groups=[])
    for table in split_tables(rows):
        _parse_table(gray, table, rows, school_code, ocr, result)
    return result
