"""Geometry, per-cell OCR and row parsing for the CAC 篩選標準一覽表 PNG."""
from __future__ import annotations

import hashlib
import io
import logging
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from decimal import Decimal, InvalidOperation
from typing import Protocol

import numpy as np
from PIL import Image

log = logging.getLogger(__name__)

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
    t = normalize_text(s)
    t = OCR_CONFUSIONS["listening"].get(t, t).upper()
    return t if t in ("A", "B", "C") else None


def collapse_dots(s: str) -> str:
    """The v5 model doubles the decimal point (2..5); see OCR_CONFUSIONS["number_dots"]."""
    return re.sub(r"\.{2,}", ".", s)


def parse_multiplier(s: str) -> Decimal | None:
    try:
        t = collapse_dots(normalize_text(s))
        t = OCR_CONFUSIONS["multiplier_glyphs"].get(t, t)
        d = Decimal(t.rstrip("."))  # a trailing "." is border noise
    except InvalidOperation:
        return None
    return d if d.is_finite() else None


def parse_quota(s: str) -> int:
    # a quota is an integer: any dot is noise (115 台大 001052 quota 11 read as 1.1 by the v5 model)
    return int(normalize_text(s).replace(".", ""))


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
SUBJECT_NAMES = frozenset(_ABBREV.values())
MAX_SUBJECT_SCORE = 15


def expand_subjects(s: str) -> list[str]:
    t = normalize_text(s)
    if not t:
        return []
    if "+" in t:
        parts = t.split("+")
        return parts if all(p in SUBJECT_NAMES for p in parts) else []
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
    t = collapse_dots(normalize_text(s))
    for wrong, right in OCR_CONFUSIONS["sieve_text"].items():
        t = t.replace(wrong, right)
    if t in _MISSING:
        return None
    m = _CELL.match(t)
    if not m or re.fullmatch(r"[\d.]+", m.group(1)):  # bare number: the lazy group swallowed a digit
        return None
    return SieveLevel(order=0, label=t, subjects=expand_subjects(m.group(1)),
                      min_score=Decimal(m.group(2)))


def normalize_program_name(name: str, gender: str | None) -> str:
    """NFKC, no whitespace, half-width parens; a 男/女 gender adds a (男)/(女) suffix once."""
    n = re.sub(r"\s+", "", unicodedata.normalize("NFKC", name))  # NFKC also maps （） to ()
    g = normalize_text(gender or "")
    if g not in ("男", "女") or n.endswith(f"({g})"):
        return n
    return f"{n}({g})"


# ------------------------------------------------------------------------ OCR

class OcrEngine(Protocol):
    def recognize(self, line: np.ndarray) -> str: ...


MODEL_DIR = Path(__file__).resolve().parents[3] / "models" / "ocr"  # pipeline/models/ocr


class RapidOcrEngine:
    """Per-line recognition only (use_det=False); whole-image detection misreads this table.

    Uses the PP-OCRv5 mobile recognition model shipped in pipeline/models/ocr (see its README):
    rapidocr's default model is simplified-Chinese only and misreads the traditional text.
    """

    TARGET_HEIGHT = 48
    MAX_WIDTH = 1600  # rapidocr raises ResizeImgError on very wide inputs
    MODEL_PATH = MODEL_DIR / "ch_PP-OCRv5_rec_mobile.onnx"
    KEYS_PATH = MODEL_DIR / "ppocrv5_dict.txt"
    MODEL_SHA256 = "5825fc7ebf84ae7a412be049820b4d86d77620f204a041697b0494669b1742c5"

    def __init__(self) -> None:
        digest = hashlib.sha256(self.MODEL_PATH.read_bytes()).hexdigest()
        if digest != self.MODEL_SHA256:
            raise RuntimeError(f"OCR model checksum mismatch for {self.MODEL_PATH}: {digest}")
        from rapidocr_onnxruntime import RapidOCR  # lazy: model load is slow

        self._engine = RapidOCR(rec_model_path=str(self.MODEL_PATH), rec_keys_path=str(self.KEYS_PATH))

    def recognize(self, line: np.ndarray) -> str:
        h = line.shape[0]
        if h < self.TARGET_HEIGHT:
            w = max(1, round(line.shape[1] * self.TARGET_HEIGHT / h))
            line = np.asarray(Image.fromarray(line).resize((w, self.TARGET_HEIGHT), Image.LANCZOS))
        if line.shape[1] > self.MAX_WIDTH:
            # the only case where we downscale: a very wide line (page title/notes) would crash the engine
            h2 = max(1, round(line.shape[0] * self.MAX_WIDTH / line.shape[1]))
            line = np.asarray(Image.fromarray(line).resize((self.MAX_WIDTH, h2), Image.LANCZOS))
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
# Every OCR-confusion workaround lives in this one table. All entries were observed on
# tests/fixtures/cac/115_001_crop.png and 115_001_apcs_crop.png (rapidocr, per-cell recognition).
OCR_CONFUSIONS = {
    # merged header cells are cut by the column grid, so labels arrive truncated
    "header_aliases": {
        "校系名": "name", "招生名": "quota", "超額": "overflow", "可力超": "overflow",
        **{f"順序{n}": f"sieve{i}" for i, n in enumerate("一二三四五六", 1)},
    },
    # the stylised 無 in the gender column is consistently read as 浦
    "no_gender": {"無", "浦", "海"},  # 海: v5 model, 113 台大
    # the small asterisk in the overflow column is consistently read as 水 (米/×/x are look-alikes)
    "star": {"*", "＊", "水", "米", "×", "x"},
    # the OCR model cannot read 戲 and drops it (prefix match)
    "name_repairs": {"劇學系": "戲劇學系"},
    # --- observed with the PP-OCRv5 model on the full 113 and 114 台大 (001) images ---
    # header text only (never data cells): 會 read as 曾
    "header_text": {"社曾": "社會"},
    # the 【】 of the group marker above a table are read as ( ) or [ ]
    "marker_open": "【([（",
    "marker_close": "】)]）",
    # quota_dots: an integer quota read with a dot (11 -> 1.1) -> dots dropped (parse_quota)
    # --- observed with the PP-OCRv5 model on the 113 台大 image only (single glyphs, own column only) ---
    # sieve cells: the 會 of 社會 read as 曾 (applied to sieve-cell labels, not other data cells)
    "sieve_text": {"社曾": "社會"},
    # 英聽 A read as 合
    "listening": {"合": "A"},
    # a lone multiplier 5 read as u
    "multiplier_glyphs": {"u": "5"},
    # 歷 (歷史學系) read as the Japanese form 歴
    "name_chars": {"歴": "歷"},
    # 114 台大: the overflow star read as "-"; a lone ink blob no wider than this x its height is a star
    "star_max_aspect": 1.3,
    # number_dots: a multiplier / min score 2.5 read as 2..5 -> repeated dots collapse (collapse_dots)
}
# the overflow star is also read as ÷ by the v5 model
OCR_CONFUSIONS["star"].update({"÷", "r"})  # r: 113 台大
_HEADER_ALIASES = OCR_CONFUSIONS["header_aliases"]
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
        for wrong, right in OCR_CONFUSIONS["header_text"].items():
            text = text.replace(wrong, right)
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
    name: str  # normalised, without the gender suffix (the job adds it)
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
UNREADABLE = "?"
CORE_SUBJECTS = ("國文", "英文", "數學A", "數學B", "社會", "自然")

_MAX_HEADER_ROWS = 3


def _recognize(ocr: OcrEngine, line: np.ndarray, warnings: list[str]) -> str:
    try:
        return ocr.recognize(line)
    except Exception as exc:  # an engine failure must not abort the whole image
        warnings.append(f"ocr failed on line {line.shape}: {exc!r}")
        return ""


def _ocr_cell(gray: np.ndarray, y0: int, y1: int, x0: int, x1: int, ocr: OcrEngine,
              warnings: list[str]) -> str:
    lines = cell_lines(gray, y0, y1, x0, x1)
    text = normalize_text("".join(_recognize(ocr, ln, warnings) for ln in lines))
    # ink the engine could not read must never pass as an empty cell ("no requirement")
    return UNREADABLE if lines and not text else text


def _group_name(gray: np.ndarray, above: tuple[int, int] | None, ocr: OcrEngine,
                warnings: list[str], previous: str | None) -> str:
    """The 【…】 marker right above the table; without one, a table continues the previous group."""
    lines = cell_lines(gray, above[0], above[1], 0, gray.shape[1]) if above else []
    # the marker is the line right above the table
    text = normalize_text(_recognize(ocr, lines[-1], warnings)) if lines else ""
    opens = re.escape(OCR_CONFUSIONS["marker_open"])
    closes = re.escape(OCR_CONFUSIONS["marker_close"])
    m = re.search(f"[{opens}]([^{closes}]+)", text)
    if m:
        return m.group(1)
    if previous is not None:
        warnings.append(f"no group marker above table ({text!r}), continuing {previous}")
        return previous
    if text:
        warnings.append(f"group marker not recognised ({text!r}), using {_DEFAULT_GROUP}")
    return _DEFAULT_GROUP


def _repair_name(name: str) -> str:
    name = name.translate(str.maketrans(OCR_CONFUSIONS["name_chars"]))
    for prefix, fixed in OCR_CONFUSIONS["name_repairs"].items():
        if name.startswith(prefix):
            repaired = fixed + name[len(prefix):]
            log.warning("name repaired: %r -> %r", name, repaired)
            return repaired
    return name


def _is_star_blob(gray: np.ndarray, y0: int, y1: int, x0: int, x1: int) -> bool:
    """The overflow star is one small, roughly square blob of ink (the "--" is too light to count as ink).

    The v5 model reads it as -, which would otherwise pass as "no tie-break" (114 台大 001012).
    """
    lines = cell_lines(gray, y0, y1, x0, x1)
    if len(lines) != 1:
        return False
    ink = lines[0] < INK_DARK
    h = int(ink.any(axis=1).sum())
    xs = np.flatnonzero(ink.any(axis=0))
    w = int(xs[-1] - xs[0] + 1)
    return w <= OCR_CONFUSIONS["star_max_aspect"] * h


def _parse_overflow(text: str) -> bool:
    if not text or _is_missing(text):
        return False
    if text in OCR_CONFUSIONS["star"]:
        return True
    raise ValueError(f"bad overflow {text!r}")


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
            if value is not None and text.endswith("."):
                log.warning("multiplier %r read with trailing dot, treated as %s", text, value)
            if text and not _is_missing(text) and value is None:
                raise ValueError(f"bad multiplier {text!r}")
            multipliers[key] = value
    code = base.get("code", "")
    if not re.fullmatch(r"\d{6}", code) or code[:3] != school_code:
        raise ValueError(f"bad code {code!r}")
    gender = base.get("gender", "")
    if gender and gender not in OCR_CONFUSIONS["no_gender"] and gender not in ("男", "女"):
        raise ValueError(f"bad gender {gender!r}")
    gender = gender if gender in ("男", "女") else None
    if base.get("name", "") in ("", UNREADABLE):
        raise ValueError("empty name")
    quota = parse_quota(base["quota"])
    levels = []
    for key in (f"sieve{n}" for n in range(1, 7)):
        text = sieve_cells.get(key, "")
        level = parse_sieve_cell(text)
        if level is None and not _is_missing(text):
            raise ValueError(f"bad {key} {text!r}")
        if level is not None:
            if level.subjects and level.min_score > MAX_SUBJECT_SCORE * len(level.subjects):
                raise ValueError(f"{key} score above maximum: {text!r}")
            level.order = len(levels) + 1
            levels.append(level)
    return SieveRow(
        school_code=school_code, cac_code=code, gender=gender,
        name=normalize_program_name(_repair_name(base["name"]), None), quota=quota, group=group,
        thresholds=thresholds, multipliers=multipliers, extra=extra, sieve=levels,
        overflow_tiebreak=_parse_overflow(base.get("overflow", "")), raw_cells=cells,
    )


def _missing_core(mapping: dict[int, tuple[str, str]]) -> list[str]:
    """Core subjects absent from the thresholds or the multipliers block."""
    present = set(mapping.values())
    return [f"{block}.{s}" for block in ("thresholds", "multipliers") for s in CORE_SUBJECTS
            if (block, s) not in present]


def _parse_table(gray: np.ndarray, table: Table, rows: list[tuple[int, int, bool]],
                 school_code: str, ocr: OcrEngine, result: SieveParseResult,
                 previous_group: str | None) -> str:
    """Parse one table into result; return its group (the next table may continue it)."""
    xs = detect_vlines(gray, table.y0, table.y1)
    cols = list(zip(xs, xs[1:]))
    trows = [(y0, y1) for y0, y1, g in rows if g and y0 >= table.y0 and y1 <= table.y1]
    group = _group_name(gray, table.above, ocr, result.warnings, previous_group)
    header_texts = [""] * len(cols)
    n_header = 0
    for y0, y1 in trows[:_MAX_HEADER_ROWS]:
        first = _ocr_cell(gray, y0, y1, *cols[0], ocr, result.warnings)
        if re.search(r"\d", first):  # a data row (possibly with a misread code)
            break
        header_texts[0] += first
        for i, (x0, x1) in enumerate(cols[1:], 1):
            header_texts[i] += _ocr_cell(gray, y0, y1, x0, x1, ocr, result.warnings)
        n_header += 1
    mapping = map_headers(header_texts)
    missing = _missing_core(mapping) if mapping is not None and group == _DEFAULT_GROUP else []
    if mapping is None or missing:
        # every data row of a skipped table counts as skipped, so the skip-ratio guard sees it
        result.rows_skipped += len(trows) - n_header
        reason = f"missing core subjects {missing}" if missing else "unrecognised headers"
        result.warnings.append(f"skip table ({group}): {reason}: {header_texts}")
        return group
    result.groups.append(group)
    for y0, y1 in trows[n_header:]:
        cells = [_ocr_cell(gray, y0, y1, x0, x1, ocr, result.warnings) for x0, x1 in cols]
        for i, (x0, x1) in enumerate(cols):
            if mapping.get(i) == ("base", "overflow") and _is_star_blob(gray, y0, y1, x0, x1):
                cells[i] = "*"
        log.debug("%s raw cells: %s", school_code, cells)
        try:
            result.rows.append(_build_row(cells, mapping, school_code, group))
        except ValueError:
            result.rows_skipped += 1
            result.warnings.append(f"skip row: {cells}")
    return group


def parse_sieve_image(png: bytes, school_code: str, ocr: OcrEngine | None = None) -> SieveParseResult:
    ocr = ocr or RapidOcrEngine()
    gray = to_gray(png)
    rows = grid_rows(gray, detect_hlines(gray))
    result = SieveParseResult(rows=[], rows_skipped=0, warnings=[], groups=[])
    group: str | None = None
    for table in split_tables(rows):
        group = _parse_table(gray, table, rows, school_code, ocr, result, group)
    return result
