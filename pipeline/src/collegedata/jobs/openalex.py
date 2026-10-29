import logging
import os
import time

import httpx

from collegedata.sources import ensure_source

OPENALEX_URL = "https://api.openalex.org/institutions"
MIN_WORKS = 100
TOP_N = 10

log = logging.getLogger(__name__)

PENDING_SQL = """
select id, country_code, name_en from institution
where name_en is not null
  and (openalex_id is null
       or not exists (select 1 from strength s where s.institution_id = institution.id))
order by id
"""

UPSERT_STRENGTH_SQL = """
insert into strength (institution_id, topic_id, topic_name, field_name, works_count,
                      cited_by_count, rank, source_id, source_url, fetched_at)
values (%s, %s, %s, %s, %s, 0, %s, %s, %s, now())
on conflict (institution_id, topic_id) do update set
    topic_name = excluded.topic_name,
    field_name = excluded.field_name,
    works_count = excluded.works_count,
    cited_by_count = excluded.cited_by_count,
    rank = excluded.rank,
    source_id = excluded.source_id,
    source_url = excluded.source_url,
    fetched_at = excluded.fetched_at
"""


class OpenAlexJob:
    name = "openalex"

    def __init__(self, client: httpx.Client | None = None, api_key: str | None = None,
                 limit: int | None = None):
        self.client = client
        self.api_key = api_key if api_key is not None else os.environ.get("OPENALEX_API_KEY")
        self.limit = limit

    def run(self, conn) -> int:
        client = self.client or httpx.Client(timeout=30)
        source_id = ensure_source(conn, "openalex")
        rows = conn.execute(PENDING_SQL).fetchall()
        if self.limit is not None:
            rows = rows[: self.limit]
        total = 0
        for i, (inst_id, cc, name_en) in enumerate(rows):
            params = {
                "search": name_en,
                "filter": f"country_code:{cc},type:education",
                "per-page": 1,
                "select": "id,display_name,ror,works_count,cited_by_count,topics",
            }
            if self.api_key:
                params["api_key"] = self.api_key
            resp = client.get(OPENALEX_URL, params=params)
            resp.raise_for_status()
            results = resp.json().get("results") or []
            if not results or (results[0].get("works_count") or 0) < MIN_WORKS:
                log.warning("OpenAlex: no confident match for %s", name_en)
            else:
                total += self._write(conn, inst_id, results[0], source_id, str(resp.request.url))
            if i < len(rows) - 1:
                time.sleep(1)
        return total

    @staticmethod
    def _write(conn, inst_id: int, match: dict, source_id: int, url: str) -> int:
        conn.execute(
            "update institution set openalex_id = %s, ror_id = %s where id = %s",
            (match["id"], match.get("ror"), inst_id),
        )
        topics = sorted(match.get("topics") or [], key=lambda t: t["count"], reverse=True)[:TOP_N]
        for rank, t in enumerate(topics, start=1):
            conn.execute(
                UPSERT_STRENGTH_SQL,
                (inst_id, t["id"], t["display_name"], (t.get("field") or {}).get("display_name"),
                 t["count"], rank, source_id, url),
            )
        return len(topics)
