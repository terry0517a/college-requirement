from pathlib import Path

import yaml

SOURCES_PATH = Path(__file__).resolve().parents[2] / "config" / "sources.yaml"


def ensure_source(conn, code: str) -> int:
    entry = yaml.safe_load(SOURCES_PATH.read_text(encoding="utf-8"))[code]
    row = conn.execute(
        """
        insert into source(code, name, url, license) values (%s, %s, %s, %s)
        on conflict (code) do update
            set name = excluded.name, url = excluded.url, license = excluded.license
        returning id
        """,
        (code, entry["name"], entry["url"], entry.get("license")),
    ).fetchone()
    return row[0]
