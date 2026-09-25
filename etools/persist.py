# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""Crash-safe, versioned persistence for application state.

A thin manager over the filesystem, for any program that has to remember
something across runs -- settings, session state, a cache, a document index.
It knows nothing about what it is storing.

A port of gBASIC's ``stdlib/persist.bas`` under the translation law
(``docs/porting-plan.md`` §1.1). Two properties carry the whole module:

**Write is atomic.** The text goes to a temporary sibling and is swapped in
with a single ``rename(2)``, so a crash mid-write never leaves a truncated
file -- a reader sees either the whole old file or the whole new one.

**Read never raises.** Reads report one of three states as a *value*:
missing, corrupt (with the parser's reason and position), or loaded. The
caller owns the recovery policy -- keep, rebuild, or refuse to start.

    from etools import persist

    persist.ensure_dir(home)
    persist.write_atomic(home / "settings.json", {"schema_version": 1, "theme": "dark"})

    st = persist.read_status(home / "settings.json")
    if st.is_ok:
        settings = st.value

**One deviation from the translation law, and it is deliberate.**
``read_status`` returns a :class:`tervalue.Outcome` rather than gBASIC's
``{status, value, message}`` record, so the three states are spelled in the
family's shared vocabulary instead of this module's private one:

======================  ==================  =================
gBASIC                  here                ask it with
======================  ==================  =================
``status = "loaded"``   ``status = "ok"``   ``st.is_ok``
``status = "missing"``  ``"unknown"``       ``st.is_unknown``
``status = "corrupt"``  ``"invalid"``       ``st.is_invalid``
``message``             ``reason``
======================  ==================  =================

The structure is identical -- three states, a value, a reason, and never a
raise -- and only the three words differ. They differ because the distinction
``read_status`` draws *is* axiom 7: a missing store is **unknown**, a corrupt
one is **invalid**, and collapsing them is the mistake the kernel exists to
prevent (``packaging.md`` §9.3: a per-library duplicate of a kernel type means
every boundary converts). Outcome also *enforces* what gBASIC only does by
convention -- an invalid must carry a reason -- and keeps the unparseable text
on ``raw``, which gBASIC discards.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from tervalue import Outcome

__all__ = ["ensure_dir", "read_status", "write_atomic", "write_text_atomic"]


def ensure_dir(path) -> None:
    """Create *path* and any missing parents. Idempotent."""
    os.makedirs(path, exist_ok=True)


def write_atomic(path, record) -> None:
    """Atomically persist *record* to *path* as strict JSON.

    Strict is the operative word. ``json.dumps`` accepts ``NaN`` and
    ``Infinity`` by default and emits them as bare words, which **is not
    JSON** -- RFC 8259 has no such literals, and a store other tools may read
    must be real JSON. ``allow_nan=False`` turns that back off, which is the
    Python spelling of gBASIC choosing ``json_encode`` over the lenient
    ``encode`` dialect.
    """
    try:
        text = json.dumps(record, allow_nan=False)
    except (TypeError, ValueError) as e:
        raise ValueError(
            f"persist: value is not JSON-encodable for {path}") from e
    write_text_atomic(path, text)


def write_text_atomic(path, text: str) -> None:
    """Atomically persist raw *text* through the same temp-then-rename dance.

    For artifacts that are source files rather than stores, where encoding to
    JSON would be exactly wrong. Crash-safety matters for the same reason: a
    reader must see the whole file or none of it, never a half-written one.
    """
    path = Path(path)
    # A UNIQUE temp name, where gBASIC uses a fixed `path + ".tmp"`. Two
    # processes writing one store both open that same fixed name, and the
    # loser's rename moves the winner's half-written bytes into place -- which
    # is the exact failure the temp-then-rename dance exists to prevent. A
    # crashed run also leaves the fixed name behind forever. Third upstream
    # defect found by this port; the fix belongs in persist.bas.
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")

    # A store someone chmod 600'd because it holds a credential must not come
    # back 644 just because it was rewritten. rename(2) replaces the inode, so
    # the mode travels with the temp file, not with the destination.
    try:
        mode = os.stat(path).st_mode & 0o7777
    except FileNotFoundError:
        mode = None

    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(text)
        finally:
            if mode is not None:
                os.chmod(tmp, mode)
        # Atomic VISIBILITY, not durability: rename(2) guarantees a reader
        # sees one whole file or the other, which covers a process crash.
        # Surviving a power loss would additionally need fsync of the file and
        # of its directory, and gBASIC's atomic_replace scopes that out in so
        # many words. Matched here rather than quietly diverging.
        os.replace(tmp, path)
    except BaseException:
        # On any failure rename() has left the destination untouched, so the
        # only thing to undo is the temp file.
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_status(path) -> Outcome:
    """Read *path* and report one of three states. Never raises.

    * **ok** -- present and well-formed; ``value`` holds the decoded document.
    * **unknown** -- no file there, or it could not be read; ``reason`` says
      which. A store that is absent is not a store that is wrong (axiom 7).
    * **invalid** -- present and unparseable; ``reason`` carries the parser's
      complaint and position, and ``raw`` the text that failed.

    ``raw`` is carried on the invalid case only. Axiom 1 says preserve the
    source, and for an *invalid* that is load-bearing -- the text is what you
    show a person, and it is the one case where re-reading the file may not
    give it back. For a good read the file on disk is still the source, so a
    second copy in memory would buy nothing and cost a document index.

    The reader is lenient where the writer is strict, exactly as gBASIC's is:
    ``json.loads`` accepts ``NaN``/``Infinity``, so what the parser can read,
    it reads. Only :func:`write_atomic` insists on the standard.
    """
    try:
        text = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return Outcome.unknown(reason=f"no file at {path}")
    except OSError as e:
        # "Read never raises" is the contract, and a store you are not allowed
        # to open is still a store whose contents you do not know.
        return Outcome.unknown(reason=f"cannot read {path}: {e.strerror}")

    try:
        value = json.loads(text)
    except UnicodeDecodeError as e:                 # pragma: no cover - rare
        return Outcome.invalid(f"not valid UTF-8: {e}", raw=text)
    except json.JSONDecodeError as e:
        return Outcome.invalid(
            f"{e.msg} (line {e.lineno}, column {e.colno})", raw=text)
    return Outcome.ok(value)
