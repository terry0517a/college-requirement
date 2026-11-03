"""Parser for the Taiwan UAC distribution-admission result PDF."""
from __future__ import annotations

import pathlib
import re
from dataclasses import dataclass

import pdfplumber

KNOWN_SUBJECTS = {"國", "英", "公", "數甲", "物", "歷", "化", "生", "地",
                  "數B", "數乙", "社", "數A", "自", "術"}
_TOKEN = re.compile(r"^(.+?)x([\d.]+)$")
_MISSING = {"", "-----"}


@dataclass
class UacRow:
    code: str
    school_zh: str
    program_zh: str
    subjects: list[tuple[str, float]]
    admitted_count: int
    min_score: float | None
    tiebreak: str | None


def parse_subjects(text: str) -> list[tuple[str, float]]:
    result: list[tuple[str, float]] = []
    for token in text.split():
        m = _TOKEN.match(token)
        if not m or m.group(1) not in KNOWN_SUBJECTS:
            raise ValueError(f"unknown subject token: {token!r}")
        result.append((m.group(1), float(m.group(2))))
    return result


def _clean(cell: str | None) -> str | None:
    s = (cell or "").strip()
    return None if s in _MISSING else s


def row_from_cells(cells: list[str]) -> UacRow:
    c = [_clean(x) for x in cells]
    score = c[5]
    return UacRow(
        code=c[0] or "",
        school_zh=c[1] or "",
        program_zh=c[2] or "",
        subjects=parse_subjects(c[3] or ""),
        admitted_count=int(c[4] or 0),
        min_score=float(score) if score is not None else None,
        tiebreak=c[6],
    )


def parse_uac_pdf(path: str | pathlib.Path) -> list[UacRow]:
    rows: list[UacRow] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for cells in table:
                    first = (cells[0] or "").strip()
                    if re.fullmatch(r"\d{4}", first):
                        rows.append(row_from_cells(cells))
    return rows
