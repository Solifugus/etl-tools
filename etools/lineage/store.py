# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""The side-car lineage graph: always on, sqlite-backed, OpenLineage-shaped.

Four node kinds -- Run, Dataset, Field, Edge -- stored in stdlib ``sqlite3``
so the always-on path costs no dependency. Nothing here is called by user
code directly; sources and sinks register themselves through the ambient
:class:`~etools.core.run.Run`.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DEFAULT_DB = Path(".etools/lineage.db")

SCHEMA = """
create table if not exists runs (
    run_id       text primary key,
    job          text not null,
    started      text not null,
    finished     text,
    status       text not null,
    code_version text
);
create table if not exists datasets (
    dataset_id text primary key,
    namespace  text not null,
    name       text not null,
    unique (namespace, name)
);
create table if not exists run_datasets (
    run_id     text not null references runs(run_id),
    dataset_id text not null references datasets(dataset_id),
    direction  text not null check (direction in ('input','output')),
    rows       integer,
    primary key (run_id, dataset_id, direction)
);
create table if not exists fields (
    dataset_id text not null references datasets(dataset_id),
    name       text not null,
    primary key (dataset_id, name)
);
create table if not exists edges (
    run_id     text not null references runs(run_id),
    src_ds     text not null,
    src_field  text,
    dst_ds     text not null,
    dst_field  text,
    transform  text not null,
    primary key (run_id, src_ds, src_field, dst_ds, dst_field, transform)
);
"""


class LineageStore:
    def __init__(self, path: Path | str = DEFAULT_DB):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # -- writes -------------------------------------------------------
    def start_run(self, run_id: str, job: str, started: str, code_version: str | None):
        self.conn.execute(
            "insert into runs (run_id, job, started, status, code_version)"
            " values (?,?,?,'started',?)",
            (run_id, job, started, code_version),
        )
        self.conn.commit()

    def finish_run(self, run_id: str, finished: str, status: str):
        self.conn.execute(
            "update runs set finished=?, status=? where run_id=?",
            (finished, status, run_id),
        )
        self.conn.commit()

    def dataset(self, namespace: str, name: str) -> str:
        dsid = f"{namespace}#{name}"
        self.conn.execute(
            "insert or ignore into datasets (dataset_id, namespace, name) values (?,?,?)",
            (dsid, namespace, name),
        )
        self.conn.commit()
        return dsid

    def record_fields(self, dataset_id: str, names):
        self.conn.executemany(
            "insert or ignore into fields (dataset_id, name) values (?,?)",
            [(dataset_id, n) for n in names],
        )
        self.conn.commit()

    def link(self, run_id: str, dataset_id: str, direction: str, rows: int | None):
        self.conn.execute(
            "insert into run_datasets (run_id, dataset_id, direction, rows)"
            " values (?,?,?,?)"
            " on conflict (run_id, dataset_id, direction) do update set rows=excluded.rows",
            (run_id, dataset_id, direction, rows),
        )
        self.conn.commit()

    def edge(self, run_id, src_ds, src_field, dst_ds, dst_field, transform):
        self.conn.execute(
            "insert or ignore into edges"
            " (run_id, src_ds, src_field, dst_ds, dst_field, transform)"
            " values (?,?,?,?,?,?)",
            (run_id, src_ds, src_field or "", dst_ds, dst_field or "", transform),
        )
        self.conn.commit()

    # -- reads --------------------------------------------------------
    def runs(self, limit: int = 20):
        cur = self.conn.execute(
            "select run_id, job, started, finished, status from runs"
            " order by started desc limit ?", (limit,))
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    def run_detail(self, run_id: str):
        cur = self.conn.execute(
            "select d.namespace, d.name, rd.direction, rd.rows"
            " from run_datasets rd join datasets d using (dataset_id)"
            " where rd.run_id=? order by rd.direction desc, d.name", (run_id,))
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    def close(self):
        self.conn.close()
