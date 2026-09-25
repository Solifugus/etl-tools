# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""Tests for etools.persist.

The four behaviours gBASIC's examples/persist_test.bas asserts -- loaded,
missing, corrupt, text round-trip -- plus the ones that only matter when
something goes wrong, which is the entire point of the module.
"""

import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from tervalue import UNKNOWN

from etools import persist


class PersistCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def temps(self):
        return [p.name for p in self.home.iterdir() if p.name.endswith(".tmp")]


class TestEnsureDir(PersistCase):
    def test_creates_parents_and_is_idempotent(self):
        deep = self.home / "a" / "b" / "c"
        persist.ensure_dir(deep)
        self.assertTrue(deep.is_dir())
        persist.ensure_dir(deep)            # must not raise the second time
        self.assertTrue(deep.is_dir())


class TestReadStatus(PersistCase):
    def test_loaded(self):
        persist.write_atomic(self.home / "settings.json",
                             {"schema_version": 1, "theme": "dark", "recent": 10})
        st = persist.read_status(self.home / "settings.json")
        self.assertTrue(st.is_ok)
        self.assertEqual(st.value, {"schema_version": 1, "theme": "dark", "recent": 10})

    def test_missing_is_unknown_not_invalid(self):
        # Axiom 7. A store that is absent is not a store that is wrong, and a
        # caller that cannot tell them apart will rebuild a good file or trust
        # a broken one.
        st = persist.read_status(self.home / "absent.json")
        self.assertTrue(st.is_unknown)
        self.assertFalse(st.is_invalid)
        self.assertIn("no file at", st.reason)
        self.assertIs(st.value, UNKNOWN)

    def test_corrupt_is_invalid_and_says_why(self):
        (self.home / "broken.json").write_text("{ this is not json ]")
        st = persist.read_status(self.home / "broken.json")
        self.assertTrue(st.is_invalid)
        self.assertIn("line 1", st.reason)
        self.assertIn("column", st.reason)
        # Axiom 1: the text that failed is what you show a person.
        self.assertEqual(st.raw, "{ this is not json ]")

    def test_read_never_raises(self):
        # The contract is unconditional, so a directory and an unreadable file
        # are states too, not exceptions.
        persist.ensure_dir(self.home / "adir")
        self.assertTrue(persist.read_status(self.home / "adir").is_unknown)

        locked = self.home / "locked.json"
        locked.write_text("{}")
        os.chmod(locked, 0o000)
        self.addCleanup(os.chmod, locked, 0o644)
        if os.geteuid() != 0:               # root reads it regardless
            st = persist.read_status(locked)
            self.assertTrue(st.is_unknown)
            self.assertIn("cannot read", st.reason)

    def test_an_empty_file_is_corrupt_not_missing(self):
        # A zero-byte store is the classic aftermath of a non-atomic write by
        # some other tool. It is present and unparseable, so it is invalid.
        (self.home / "empty.json").write_text("")
        self.assertTrue(persist.read_status(self.home / "empty.json").is_invalid)

    def test_the_reader_is_lenient_where_the_writer_is_strict(self):
        # Exactly as gBASIC's is: what the parser can read, it reads. Only
        # write_atomic insists on the standard, so this is reachable only by
        # hand-editing a store.
        (self.home / "nan.json").write_text('{"x": NaN}')
        st = persist.read_status(self.home / "nan.json")
        self.assertTrue(st.is_ok)


class TestWriteAtomic(PersistCase):
    def test_round_trip(self):
        value = {"a": [1, 2, {"b": None}], "c": "é", "d": True}
        persist.write_atomic(self.home / "s.json", value)
        self.assertEqual(persist.read_status(self.home / "s.json").value, value)

    def test_nan_is_refused_because_it_is_not_json(self):
        # json.dumps emits bare NaN by default, which no other language's
        # parser is obliged to accept. A store other tools may read must be
        # real JSON.
        with self.assertRaises(ValueError) as cm:
            persist.write_atomic(self.home / "s.json", {"x": float("nan")})
        self.assertIn("persist: value is not JSON-encodable for", str(cm.exception))
        # The default we turned off: bare Infinity, which RFC 8259 has no
        # literal for and another language's parser need not accept.
        self.assertEqual(json.dumps(float("inf")), "Infinity")

    def test_unencodable_object_is_refused_with_the_path(self):
        with self.assertRaises(ValueError) as cm:
            persist.write_atomic(self.home / "s.json", {"x": object()})
        self.assertEqual(str(cm.exception),
                         f"persist: value is not JSON-encodable for {self.home / 's.json'}")

    def test_a_refused_write_leaves_nothing_behind(self):
        persist.write_atomic(self.home / "s.json", {"good": 1})
        with self.assertRaises(ValueError):
            persist.write_atomic(self.home / "s.json", {"x": float("nan")})
        self.assertEqual(persist.read_status(self.home / "s.json").value, {"good": 1})
        self.assertEqual(self.temps(), [])

    def test_a_failed_replace_leaves_the_old_file_intact(self):
        # The property the whole module exists for. rename(2) leaves both
        # sides untouched on failure, so a crash at the worst moment costs the
        # new content, never the old.
        target = self.home / "s.json"
        persist.write_atomic(target, {"version": 1})
        with mock.patch("os.replace", side_effect=OSError(28, "No space left")):
            with self.assertRaises(OSError):
                persist.write_atomic(target, {"version": 2})
        self.assertEqual(persist.read_status(target).value, {"version": 1})
        self.assertEqual(self.temps(), [], "a failed write orphaned its temp file")

    def test_a_failed_write_leaves_no_temp_file(self):
        target = self.home / "s.json"
        with mock.patch("os.fdopen", side_effect=OSError("disk on fire")):
            with self.assertRaises(OSError):
                persist.write_atomic(target, {"version": 1})
        self.assertEqual(self.temps(), [])
        self.assertFalse(target.exists())

    def test_mode_survives_a_rewrite(self):
        # A store chmod 600'd because it holds a credential must not come back
        # world-readable just because it was rewritten. rename(2) replaces the
        # inode, so the mode has to be carried across deliberately.
        target = self.home / "secret.json"
        persist.write_atomic(target, {"token": "x"})
        os.chmod(target, 0o600)
        persist.write_atomic(target, {"token": "y"})
        self.assertEqual(os.stat(target).st_mode & 0o777, 0o600)

    def test_concurrent_writers_never_interleave(self):
        # gBASIC's fixed `path + ".tmp"` makes two writers share one temp
        # file, so the loser's rename publishes the winner's half-written
        # bytes. With unique temp names each writer renames its own whole
        # file, and the reader sees one document or the other -- never a mix,
        # never a partial, never a JSONDecodeError.
        target = self.home / "hot.json"
        a = {"who": "a", "pad": "a" * 20000}
        b = {"who": "b", "pad": "b" * 20000}
        persist.write_atomic(target, a)

        stop = threading.Event()
        seen, errors = [], []

        def writer(value):
            while not stop.is_set():
                persist.write_atomic(target, value)

        def reader():
            while not stop.is_set():
                st = persist.read_status(target)
                if st.is_ok:
                    seen.append(st.value["who"])
                else:
                    errors.append(st.reason)

        threads = [threading.Thread(target=writer, args=(a,)),
                   threading.Thread(target=writer, args=(b,)),
                   threading.Thread(target=reader)]
        for t in threads:
            t.start()
        while len(seen) < 200 and not errors:
            pass
        stop.set()
        for t in threads:
            t.join()

        self.assertEqual(errors, [], "a reader saw a torn file")
        self.assertTrue(set(seen) <= {"a", "b"})
        self.assertEqual(self.temps(), [])


class TestWriteTextAtomic(PersistCase):
    def test_round_trip(self):
        persist.write_text_atomic(self.home / "notes.txt", "line one\n")
        self.assertEqual((self.home / "notes.txt").read_text(), "line one\n")

    def test_utf8_survives(self):
        persist.write_text_atomic(self.home / "u.txt", "café — 日本\n")
        self.assertEqual((self.home / "u.txt").read_text(encoding="utf-8"),
                         "café — 日本\n")

    def test_it_does_not_encode_to_json(self):
        # The reason this exists beside write_atomic: for a materialized
        # source file, json_encode would be exactly wrong.
        persist.write_text_atomic(self.home / "p.bas", 'print "hi"')
        self.assertEqual((self.home / "p.bas").read_text(), 'print "hi"')


if __name__ == "__main__":
    unittest.main()
