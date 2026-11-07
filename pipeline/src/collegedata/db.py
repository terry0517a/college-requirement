import os

import psycopg

# Jobs hold one transaction open while downloading and parsing files, so the
# connection can sit idle for minutes; keepalives stop the pooler or a NAT from
# dropping it.
KEEPALIVES = {"keepalives": 1, "keepalives_idle": 30, "keepalives_interval": 10, "keepalives_count": 5}


def connect(url: str | None = None) -> psycopg.Connection:
    return psycopg.connect(url or os.environ["DATABASE_URL"], **KEEPALIVES)
