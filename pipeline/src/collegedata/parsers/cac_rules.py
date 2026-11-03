"""Parsers for the CAC 校系分則查詢系統 pages (discovery, code lists, department detail)."""
from __future__ import annotations

import html as htmllib
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from urllib.parse import urljoin

SUBJECTS = ("國文", "英文", "數學A", "數學B", "社會", "自然", "英聽")
_NUMERALS = "一二三四五六七八九十"


@dataclass
class Stage2Item:
    name: str
    threshold: str | None
    pct: int | None


@dataclass
class RulesPage:
    cac_code: str
    school: str
    name: str
    quota: int
    gender: str | None
    expected_candidates: int | None
    fee: int | None
    thresholds: dict[str, str | None]
    multipliers: dict[str, Decimal | None]
    gsat_weights: dict[str, Decimal]
    stage1_pct: int | None
    items: list[Stage2Item]
    tiebreak_order: list[str]
    review_items: str | None
    exam_date: str | None
    website: str | None
    overflow_rule: str | None


def find_system_url(query_html: str, roc: int) -> str | None:
    m = re.search(r'href="\./system/(ColQry_[^/"]+)/', query_html)
    if not m:
        return None
    return urljoin(f"https://www.cac.edu.tw/apply{roc}/query.php", f"./system/{m.group(1)}/")


def parse_total_gsd(html: str) -> list[tuple[str, str, int]]:
    return [(c, n.strip(), int(k)) for c, n, k in re.findall(r"\((\d{3})\)([^<\-]+?)\s*-(\d+)系", html)]


def parse_code_list(html: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"html/\d{3}_(\d{6})\.htm", html)))


class _Cells(HTMLParser):
    """Collects every <td> as (class tokens, inner HTML); tolerant of sloppy markup."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.cells: list[tuple[set[str], str]] = []
        self._classes: set[str] = set()
        self._buf: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "td":
            self._flush()
            self._classes = set(dict(attrs).get("class", "").split())
            self._buf = []
        elif self._buf is not None:
            self._buf.append(self.get_starttag_text())

    def handle_startendtag(self, tag, attrs):
        if self._buf is not None:
            self._buf.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        if tag in ("td", "tr", "table"):
            self._flush()
        elif self._buf is not None:
            self._buf.append(f"</{tag}>")

    def handle_data(self, data):
        if self._buf is not None:
            self._buf.append(data)

    def handle_entityref(self, name):
        if self._buf is not None:
            self._buf.append(f"&{name};")

    def handle_charref(self, name):
        if self._buf is not None:
            self._buf.append(f"&#{name};")

    def _flush(self):
        if self._buf is not None:
            self.cells.append((self._classes, "".join(self._buf)))
            self._buf = None

    def close(self):
        super().close()
        self._flush()


def _text(inner: str) -> str:
    return htmllib.unescape(re.sub(r"<[^>]+>", "", inner)).strip()


def _lines(inner: str, keep_blank: bool = False) -> list[str]:
    """Split on <br>. keep_blank preserves blank lines (positional zips); trailing blanks are dropped."""
    parts = re.split(r"<br\s*/?>", inner, flags=re.I)
    out = [re.sub(r"\s+", " ", _text(p)) for p in parts]
    if keep_blank:
        while out and not out[-1]:
            out.pop()
        return out
    return [t for t in out if t]


def _multiline(inner: str) -> str:
    return "\n".join(_lines(inner))


def _compact(inner: str) -> str:
    return re.sub(r"\s+", "", _text(inner))


def _int(s: str | None) -> int | None:
    m = re.search(r"\d+", (s or "").replace(",", ""))
    return int(m.group()) if m else None


def _dec(s: str) -> Decimal | None:
    try:
        return Decimal(s.lstrip("*").strip())
    except InvalidOperation:
        return None


def _div_text(html: str, cls: str) -> str:
    m = re.search(rf'<div class="?{cls}"?[^>]*>(.*?)</div>', html, re.S)
    return _text(m.group(1)) if m else ""


def _labeled(cells: list[tuple[set[str], str]]) -> dict[str, str]:
    """Label cell (class Lb) text -> inner HTML of the next cell."""
    out: dict[str, str] = {}
    for i, (cls, inner) in enumerate(cells[:-1]):
        if "Lb" in cls:
            out.setdefault(_compact(inner), cells[i + 1][1])
    return out


def parse_rules_page(html: str) -> RulesPage:
    p = _Cells()
    p.feed(html)
    p.close()
    labeled = _labeled(p.cells)
    if "校系代碼" not in labeled:
        raise ValueError("not a rules page")

    def val(label: str) -> str | None:
        return _text(labeled[label]) if label in labeled else None

    if "招生名額" not in labeled:
        raise ValueError("not a rules page")
    raw_quota = _text(labeled["招生名額"]).replace(",", "")
    if not raw_quota.isdigit():
        raise ValueError(f"quota not numeric: {raw_quota!r}")
    quota = int(raw_quota)
    gender = val("性別要求")
    if gender in (None, "", "無"):
        gender = None

    g3 = [(i, inner) for i, (cls, inner) in enumerate(p.cells) if "g3" in cls]
    if g3 and len(g3) != 8:
        raise ValueError(f"unexpected g3 cell count: {len(g3)}")

    thresholds: dict[str, str | None] = {s: None for s in SUBJECTS}
    multipliers: dict[str, Decimal | None] = {s: None for s in SUBJECTS}
    gsat_weights: dict[str, Decimal] = {}
    items: list[Stage2Item] = []
    tiebreak: list[str] = []
    stage1_pct = None
    if g3:
        subjects, thr_lines, mul_lines, wts, pct_cell, names, item_thr, item_pct = (
            _lines(inner, keep_blank=True) for _, inner in g3
        )
        if not (len(subjects) == len(thr_lines) == len(mul_lines) == len(wts)):
            raise ValueError("misaligned first-stage cells")
        for k, subj in enumerate(subjects):
            if subj not in thresholds:
                continue
            if thr_lines[k] not in ("", "--"):
                thresholds[subj] = thr_lines[k]
            multipliers[subj] = _dec(mul_lines[k]) if mul_lines[k] not in ("", "--") else None
            if wts[k].startswith("*"):
                w = _dec(wts[k])
                if w is not None:
                    gsat_weights[subj] = w
        stage1_pct = _int(" ".join(pct_cell))
        if names:
            if not (len(names) == len(item_thr) == len(item_pct)):
                raise ValueError("misaligned second-stage cells")
            items = [
                Stage2Item(name=n, threshold=item_thr[k] if item_thr[k] not in ("", "--") else None,
                           pct=_int(item_pct[k]))
                for k, n in enumerate(names)
            ]
        if g3[7][0] + 1 < len(p.cells):
            tiebreak = [re.sub(rf"^[{_NUMERALS}]、\s*", "", ln) for ln in _lines(p.cells[g3[7][0] + 1][1])]

    review = None
    for i, (cls, inner) in enumerate(p.cells[:-1]):
        if "g3" not in cls and _compact(inner) == "審查資料":
            m = re.search(r"項目：(.*)", p.cells[i + 1][1], re.S)
            if m:
                review = re.split(r"※|說明：", _text(m.group(1)))[0].strip() or None
            break

    exam = " ".join(_lines(labeled["指定項目甄試日期"])) if "指定項目甄試日期" in labeled else None
    website = None
    for line in _lines(labeled.get("備註", "")):
        wm = re.search(r"https?://\S+", line)
        if wm:
            website = wm.group().rstrip("。")
            break
    school, dept = _div_text(html, "colname"), _div_text(html, "gsdname")
    if not school or not dept:
        raise ValueError("not a rules page")

    return RulesPage(
        cac_code=_text(labeled["校系代碼"]),
        school=school,
        name=dept,
        quota=quota,
        gender=gender,
        expected_candidates=_int(val("預計甄試人數")),
        fee=_int(val("指定項目甄試費")),
        thresholds=thresholds,
        multipliers=multipliers,
        gsat_weights=gsat_weights,
        stage1_pct=stage1_pct,
        items=items,
        tiebreak_order=tiebreak,
        review_items=review,
        exam_date=exam or None,
        website=website,
        overflow_rule=_multiline(labeled["同級分(分數)超額篩選方式"]) or None if "同級分(分數)超額篩選方式" in labeled else None,
    )
