import httpx

from collegedata.countries import SUPPORTED
from collegedata.sources import ensure_source

HIPO_URL = "http://universities.hipolabs.com/search"
HIPO_COUNTRY_NAMES = {"TW": "Taiwan, Province of China", "US": "United States"}

UPSERT_SQL = """
insert into institution (country_code, name_en, domain, web_url, source_id, source_url, fetched_at)
values (%s, %s, %s, %s, %s, %s, now())
on conflict (country_code, domain) do update set
    name_en = excluded.name_en,
    web_url = excluded.web_url,
    source_id = excluded.source_id,
    source_url = excluded.source_url,
    fetched_at = excluded.fetched_at
where institution.source_id = excluded.source_id
"""


def upsert_institutions(conn, records: list[dict], source_id: int, source_url: str) -> int:
    count = 0
    for rec in records:
        domains = rec.get("domains") or []
        if not domains:
            continue
        web_pages = rec.get("web_pages") or []
        conn.execute(
            UPSERT_SQL,
            (
                rec["alpha_two_code"],
                rec["name"],
                domains[0],
                web_pages[0] if web_pages else None,
                source_id,
                source_url,
            ),
        )
        count += 1
    return count


class HipoJob:
    name = "hipo"

    def __init__(self, client: httpx.Client | None = None):
        self.client = client

    def run(self, conn) -> int:
        client = self.client or httpx.Client(timeout=30)
        source_id = ensure_source(conn, "hipo")
        total = 0
        for code in SUPPORTED:
            resp = client.get(HIPO_URL, params={"country": HIPO_COUNTRY_NAMES[code]})
            resp.raise_for_status()
            total += upsert_institutions(conn, resp.json(), source_id, str(resp.request.url))
        return total
