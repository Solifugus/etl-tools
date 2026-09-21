"""The daily rates table: an upsert, not an append.

These series are **revised**. Treasury and FRED both restate published values,
and a daily job re-reads days it has already stored. An append-only log would
double-count on a re-run and hold two disagreeing values after a revision, so
the table is keyed by ``(series, obs_date)`` and the load is an upsert.

The load reports ``inserted`` / ``revised`` / ``unchanged`` separately, because
"a value I already had changed underneath me" is the interesting event and an
upsert that merely succeeds hides it.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from ..core.run import current

TABLE = "rates_daily"

DDL = {
    "sqlite": """
        create table if not exists {t} (
            series       text    not null,
            obs_date     text    not null,
            value        text    not null,
            source       text    not null,
            retrieved_at text    not null,
            primary key (series, obs_date)
        )""",
    "postgres": """
        create table if not exists {t} (
            series       text          not null,
            obs_date     date          not null,
            value        numeric(9,4)  not null,
            source       text          not null,
            retrieved_at timestamptz   not null,
            primary key (series, obs_date)
        )""",
}

UPSERT = """
    insert into {t} (series, obs_date, value, source, retrieved_at)
    values ({p},{p},{p},{p},{p})
    on conflict (series, obs_date) do update set
        value        = excluded.value,
        source       = excluded.source,
        retrieved_at = excluded.retrieved_at
"""


@dataclass
class DB:
    conn: Any
    dialect: str
    namespace: str

    @property
    def ph(self) -> str:
        return "?" if self.dialect == "sqlite" else "%s"


def connect_sqlite(path: str | Any) -> DB:
    conn = sqlite3.connect(str(path))
    sqlite3.register_adapter(Decimal, str)
    sqlite3.register_adapter(date, lambda d: d.isoformat())
    return DB(conn, "sqlite", f"file://{path}")


def connect_postgres(dsn: str) -> DB:
    try:
        import psycopg
    except ImportError as e:  # pragma: no cover - depends on install
        raise ImportError(
            "Postgres support needs psycopg: pip install etools-etl[postgres]"
        ) from e
    conn = psycopg.connect(dsn)
    info = conn.info
    return DB(conn, "postgres", f"postgres://{info.host}:{info.port}/{info.dbname}")


def ensure_table(db: DB, table: str = TABLE) -> None:
    db.conn.execute(DDL[db.dialect].format(t=table))
    db.conn.commit()


@dataclass(frozen=True)
class LoadReport:
    inserted: int
    revised: int
    unchanged: int
    revisions: tuple  # (series, obs_date, old, new)

    @property
    def total(self) -> int:
        return self.inserted + self.revised + self.unchanged


def upsert_observations(db: DB, observations, *, table: str = TABLE) -> LoadReport:
    """Upsert ``observations``, reporting what actually changed."""
    if not observations:
        return LoadReport(0, 0, 0, ())

    ensure_table(db, table)
    cur = db.conn.cursor()

    keys = {(o.series, o.obs_date) for o in observations}
    existing: dict[tuple, Decimal] = {}
    series_list = sorted({s for s, _ in keys})
    ph = db.ph
    placeholders = ",".join([ph] * len(series_list))
    cur.execute(
        f"select series, obs_date, value from {table} where series in ({placeholders})",
        series_list,
    )
    for s, d, v in cur.fetchall():
        d = date.fromisoformat(d) if isinstance(d, str) else d
        existing[(s, d)] = Decimal(str(v))

    inserted = revised = unchanged = 0
    revisions = []
    now = datetime.now(timezone.utc)
    now_param = now.isoformat() if db.dialect == "sqlite" else now

    rows = []
    for o in observations:
        prev = existing.get((o.series, o.obs_date))
        if prev is None:
            inserted += 1
        elif prev != o.value:
            revised += 1
            revisions.append((o.series, o.obs_date, prev, o.value))
        else:
            unchanged += 1
        rows.append((o.series, o.obs_date, o.value, o.source, now_param))

    cur.executemany(UPSERT.format(t=table, p=ph), rows)
    db.conn.commit()

    r = current()
    if r is not None:
        dsid = r.output(db.namespace, table,
                        fields=["series", "obs_date", "value", "source", "retrieved_at"],
                        rows=len(rows))
        for ns in sorted({o.source for o in observations}):
            r.edge(ns, dsid, transform="upsert_observations")

    return LoadReport(inserted, revised, unchanged, tuple(revisions))
