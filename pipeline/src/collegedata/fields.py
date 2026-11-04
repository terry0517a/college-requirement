"""Taiwan institution control (public/private) and program field classification."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import yaml

KEYWORDS_PATH = Path(__file__).resolve().parents[2] / "config" / "tw_field_keywords.yaml"
DEPT_RE = re.compile(r"^(.+?(學系|學位學程|學士班|學程|系))")
PUBLIC_RE = re.compile(r"^(國立|市立|臺北市立|台北市立|高雄市立|臺中市立|新北市立|桃園市立|臺南市立)")


@lru_cache(maxsize=1)
def load_tw_field_rules() -> list[tuple[str, list[str]]]:
    data = yaml.safe_load(KEYWORDS_PATH.read_text(encoding="utf-8"))
    return [(r["field"], list(r["keywords"])) for r in data]


def _match(text: str) -> str | None:
    for field, keywords in load_tw_field_rules():
        if any(k in text for k in keywords):
            return field
    return None


def classify_tw_program(name_zh: str) -> str | None:
    m = DEPT_RE.match(name_zh)
    if m:
        hit = _match(m.group(1))
        if hit:
            return hit
    return _match(name_zh)


def tw_control(name_zh: str) -> str:
    return "public" if PUBLIC_RE.match(name_zh) else "private"
