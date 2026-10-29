import logging
import os
import time

import httpx

from collegedata.sources import ensure_source

OPENALEX_URL = "https://api.openalex.org/institutions"
MIN_WORKS = 100
TOP_N = 10
DEFAULT_BATCH_SIZE = 800

log = logging.getLogger(__name__)

# Unlinked institutions first (by id), then the ones whose topics are oldest,
# so successive runs cycle through every institution within the daily budget.
SELECT_SQL = """
select i.id, i.country_code, i.name_en
from institution i
left join (select institution_id, max(fetched_at) as last_fetched
           from strength group by institution_id) s on s.institution_id = i.id
where i.name_en is not null
order by (i.openalex_id is null) desc,
         case when i.openalex_id is null then i.id end,
         s.last_fetched asc nulls first,
         i.id
limit %s
"""

INSERT_STRENGTH_SQL = """
insert into strength (institution_id, topic_id, topic_name, field_name, works_count,
                      cited_by_count, rank, source_id, source_url, fetched_at)
values (%s, %s, %s, %s, %s, 0, %s, %s, %s, now())
"""


class OpenAlexJob:
    name = "openalex"
    # Each run only covers one batch, so its row count is not comparable to the last run.
    row_count_guard = False

    def __init__(self, client: httpx.Client | None = None, api_key: str | None = None,
                 limit: int | None = None, batch_size: int | None = None):
        self.client = client
        self.api_key = api_key if api_key is not None else os.environ.get("OPENALEX_API_KEY")
        if batch_size is None:
            batch_size = int(os.environ.get("OPENALEX_BATCH_SIZE") or DEFAULT_BATCH_SIZE)
        self.batch_size = min(batch_size, limit) if limit is not None else batch_size

    def run(self, conn) -> int:
        client = self.client or httpx.Client(timeout=30)
        source_id = ensure_source(conn, "openalex")
        rows = conn.execute(SELECT_SQL, (self.batch_size,)).fetchall()
        total = 0
        for i, (inst_id, cc, name_en) in enumerate(rows):
            try:
                with conn.transaction():
                    total += self._process(conn, client, inst_id, cc, name_en, source_id)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429:
                    log.warning("OpenAlex: rate limit / budget exhausted at %s; stopping, next run continues",
                                name_en)
                    break
                log.warning("OpenAlex: HTTP %s for %s; skipping", exc.response.status_code, name_en)
            except httpx.TransportError as exc:
                log.warning("OpenAlex: transport error for %s (%s); skipping", name_en, exc)
            if i < len(rows) - 1:
                time.sleep(1)
        return total

    def _process(self, conn, client, inst_id: int, cc: str, name_en: str, source_id: int) -> int:
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
            return 0
        match = results[0]
        owner = conn.execute(
            "select id from institution where openalex_id = %s and id <> %s", (match["id"], inst_id)
        ).fetchone()
        if owner:
            log.warning("OpenAlex: %s already linked to institution %s; skipping %s",
                        match["id"], owner[0], name_en)
            return 0
        url = str(resp.request.url.copy_remove_param("api_key"))
        return self._write(conn, inst_id, match, source_id, url)

    @staticmethod
    def _write(conn, inst_id: int, match: dict, source_id: int, url: str) -> int:
        conn.execute(
            "update institution set openalex_id = %s, ror_id = %s where id = %s",
            (match["id"], match.get("ror"), inst_id),
        )
        conn.execute("delete from strength where institution_id = %s", (inst_id,))
        topics = sorted(match.get("topics") or [], key=lambda t: t["count"], reverse=True)[:TOP_N]
        for rank, t in enumerate(topics, start=1):
            conn.execute(
                INSERT_STRENGTH_SQL,
                (inst_id, t["id"], t["display_name"],
                 (t.get("field") or {}).get("display_name") or "Unknown",
                 t["count"], rank, source_id, url),
            )
        return len(topics)
