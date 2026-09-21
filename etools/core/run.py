"""The ambient run context.

Lineage recording must not be the caller's job -- if it needs bookkeeping at
every call site it will be wrong within a month. So a :class:`Run` lives in a
``ContextVar`` and sources and sinks find it themselves::

    with run("daily-rates"):
        obs = treasury.yields(["DGS5", "DGS10"])   # registers an input
        db.upsert_observations(conn, obs)          # registers an output

Nothing in that snippet mentions lineage. That is the design.

A run that dies mid-pipeline is left ``started`` with no ``finished``. That is
honest: we do not know that it completed, so we do not say so.
"""

from __future__ import annotations

import os
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone

from ..lineage.store import DEFAULT_DB, LineageStore

_current: ContextVar["Run | None"] = ContextVar("etools_run", default=None)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Run:
    def __init__(self, job: str, store: LineageStore, code_version: str | None):
        self.job = job
        self.run_id = str(uuid.uuid4())
        self.store = store
        self.store.start_run(self.run_id, job, _now(), code_version)

    def input(self, namespace: str, name: str, fields=(), rows: int | None = None) -> str:
        dsid = self.store.dataset(namespace, name)
        if fields:
            self.store.record_fields(dsid, fields)
        self.store.link(self.run_id, dsid, "input", rows)
        return dsid

    def output(self, namespace: str, name: str, fields=(), rows: int | None = None) -> str:
        dsid = self.store.dataset(namespace, name)
        if fields:
            self.store.record_fields(dsid, fields)
        self.store.link(self.run_id, dsid, "output", rows)
        return dsid

    def edge(self, src_ds, dst_ds, transform, src_field=None, dst_field=None):
        self.store.edge(self.run_id, src_ds, src_field, dst_ds, dst_field, transform)


def current() -> Run | None:
    """The run in scope, or ``None``. Sources and sinks call this."""
    return _current.get()


@contextmanager
def run(job: str, *, db=DEFAULT_DB, code_version: str | None = None):
    store = LineageStore(db)
    r = Run(job, store, code_version or os.environ.get("ETOOLS_CODE_VERSION"))
    token = _current.set(r)
    status = "failed"
    try:
        yield r
        status = "completed"
    finally:
        _current.reset(token)
        store.finish_run(r.run_id, _now(), status)
        store.close()
