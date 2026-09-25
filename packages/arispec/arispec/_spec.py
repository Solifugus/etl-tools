# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""The spec language: an indentation-defined declarative document.

Deliberately small. A spec is a short document and a heavyweight parser here
would be the tail wagging the dog.

    page:
        break: formfeed
        drop: 2

    type usd_trailing:
        /\\$?\\s*([\\d,]+\\.\\d{2})-/   -> negate as decimal
        /\\$?\\s*([\\d,]+\\.\\d{2})/    -> as decimal
        output: money

    section report:
        using money: usd_trailing
        field branch: right of "Branch:" as integer

        section tellers repeats starts(/^Teller: /):
            field name: between "Teller:" and "Teller #:"
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field as _field

from ._pattern import indent_of, is_blank
from ._recognize import BUILTIN_TYPES, TYPE_DIALECTS

__all__ = ["Field", "Page", "Section", "SpecError", "TypeDecl", "TypeRule",
           "parse_spec"]


class SpecError(Exception):
    """A spec that cannot be read. Reported as a value by :func:`arispec.parse`."""


@dataclass(frozen=True, slots=True)
class Field:
    name: str
    locator: str
    type: str = ""


@dataclass(frozen=True, slots=True)
class TypeRule:
    pattern: str
    replacement: str = ""
    negate: bool = False
    dialect: str = ""


@dataclass(frozen=True, slots=True)
class TypeDecl:
    name: str
    rules: tuple
    base: str = "text"


@dataclass(frozen=True, slots=True)
class Page:
    kind: str = "none"          # none | formfeed | regex
    pattern: str = ""
    drop: int = 0


@dataclass(slots=True)
class Section:
    name: str
    repeats: bool = False
    starts: str = ""
    ends: str = ""
    fields: list = _field(default_factory=list)
    sections: list = _field(default_factory=list)
    rows: list = _field(default_factory=list)
    has_rows: bool = False
    row_continue: str = ""
    usings: dict = _field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Spec:
    page: Page
    types: dict
    root: Section


def split_rule(text: str):
    """Split a type rule into its slash-delimited parts and its action.

        /re/ -> as decimal        ->  ["re"],        "as decimal"
        /re/repl/ -> as date      ->  ["re","repl"], "as date"

    Hand-scanned rather than matched with a regex because a rule's own regex
    routinely contains ESCAPED SLASHES -- a date pattern always does -- and a
    pattern like ``/(.*)/([^/]*)/`` cannot tell a delimiter from a ``\\/``
    inside the body. Upstream it silently mis-split a date rule into a
    transform whose pattern ended in a lone backslash, which the engine then
    rejected.
    """
    if not text.startswith("/"):
        return None
    parts, cur, i = [], [], 1
    while i < len(text):
        c = text[i]
        if c == "\\" and i + 1 < len(text):
            cur.append(c)
            cur.append(text[i + 1])
            i += 2
            continue
        if c == "/":
            parts.append("".join(cur))
            cur = []
            rest = text[i + 1:]
            if rest.lstrip().startswith("->"):
                return parts, rest.lstrip()[2:].strip()
            i += 1
            continue
        cur.append(c)
        i += 1
    return (parts, "") if parts else None


def _make_rule(parts, action, base):
    negate = action.startswith("negate")
    dialect = ""
    am = re.search(r"\bas\s+([A-Za-z_][A-Za-z0-9_]*)\s*$", action)
    word = am.group(1) if am else action.replace("negate", "").strip()
    if word in TYPE_DIALECTS.get(base, ()):
        dialect = word
    return TypeRule(pattern=parts[0],
                    replacement=parts[1] if len(parts) > 1 else "",
                    negate=negate, dialect=dialect)


def _parse_field(body: str) -> Field | None:
    """``<name>: <locator> [as <type>]``"""
    c = body.find(":")
    if c < 0:
        return None
    rest = body[c + 1:].strip()
    ty = ""
    am = re.search(r"\s+as\s+([A-Za-z_][A-Za-z0-9_]*)\s*$", rest)
    if am:
        ty = am.group(1)
        rest = rest[:am.start()].strip()
    return Field(name=body[:c].strip(), locator=rest, type=ty)


def _parse_section_header(body: str) -> Section | None:
    """``section <name> [repeats] [starts(<pat>)] [ends(<pat>)]:``"""
    nm = re.match(r"^section\s+([A-Za-z_][A-Za-z0-9_]*)", body)
    if not nm:
        return None
    sec = Section(name=nm.group(1))
    sec.repeats = bool(re.search(r"\srepeats(\s|:|$)", body))
    sm = re.search(r"starts\(([^)]*)\)", body)
    if sm:
        sec.starts = sm.group(1).strip()
    em = re.search(r"ends\(([^)]*)\)", body)
    if em:
        sec.ends = em.group(1).strip()
    return sec


def _block_end(lines, i, indent, stop):
    """How far the block opened at *i* runs, skipping blank lines."""
    j = i + 1
    while j < stop:
        if is_blank(lines[j]):
            j += 1
            continue
        if indent_of(lines[j]) <= indent:
            break
        j += 1
    return j


def _parse_block(sec: Section, lines, start_at, stop_at, base_indent) -> Section:
    i = start_at
    while i < stop_at:
        line = lines[i]
        if is_blank(line) or line.strip().startswith("'"):
            i += 1
            continue
        t = line.strip()
        ind = indent_of(line)
        if ind < base_indent:
            return sec
        child_end = _block_end(lines, i, ind, stop_at)

        if t.startswith("section "):
            child = _parse_section_header(t)
            if child is not None:
                sec.sections.append(_parse_block(child, lines, i + 1, child_end, ind + 1))
            i = child_end
            continue

        if t.startswith("rows"):
            rm = re.match(r"^rows\s*(continue\(([^)]*)\))?\s*:", t)
            if rm:
                holder = _parse_block(Section("rows"), lines, i + 1, child_end, ind + 1)
                sec.rows = holder.fields
                sec.has_rows = True
                # `rows continue(<pat>):` -- a line matching <pat> continues the
                # record above it rather than starting a new one. Wrapped fields
                # are ordinary in these reports.
                if rm.group(2) is not None:
                    sec.row_continue = rm.group(2).strip()
                i = child_end
                continue

        if t.startswith("field "):
            f = _parse_field(t[6:].strip())
            if f is not None:
                sec.fields.append(f)
            i += 1
            continue

        if t.startswith("using "):
            um = re.match(r"^using\s+([A-Za-z_]+)\s*:\s*([A-Za-z_][A-Za-z0-9_]*)", t)
            if um:
                sec.usings[um.group(1)] = um.group(2)
            i += 1
            continue

        i += 1
    return sec


def _parse_page(lines, start_at, stop_at) -> Page:
    kind, pattern, drop = "none", "", 0
    for i in range(start_at, stop_at):
        t = lines[i].strip()
        if not t or t.startswith("'"):
            continue
        if t.startswith("break:"):
            body = t[6:].strip()
            if body == "formfeed":
                kind = "formfeed"
            elif body.startswith("/") and body.endswith("/"):
                kind, pattern = "regex", body[1:-1]
        elif t.startswith("drop:"):
            body = t[5:].strip()
            if body.isdigit():
                drop = int(body)
    return Page(kind=kind, pattern=pattern, drop=drop)


def _parse_type(lines, start_at, stop_at, name) -> TypeDecl:
    base, raw = "text", []
    for i in range(start_at, stop_at):
        t = lines[i].strip()
        if not t or t.startswith("'"):
            continue
        if t.startswith("output:"):
            base = t[7:].strip()
            continue
        split = split_rule(t)
        if split is not None:
            raw.append(split)
    return TypeDecl(name=name, rules=tuple(_make_rule(p, a, base) for p, a in raw),
                    base=base)


def _check_usings(sec: Section, types: dict, path: str) -> None:
    """A ``using`` that names neither a declared type nor a dialect is refused.

    It used to fall through silently and hand the field back the raw line as
    text -- and ``inspect``'s own hint for an ambiguous date told authors to
    write exactly the binding that did it. The remedy for one silent wrong
    answer was itself a silent wrong answer, which is the worst place for a
    defect to live.
    """
    for builtin, bound in sec.usings.items():
        if builtin not in BUILTIN_TYPES:
            raise SpecError(
                f"{path}: `using {builtin}:` is not a builtin type "
                f"(known: {', '.join(BUILTIN_TYPES)})")
        if bound in types or bound in TYPE_DIALECTS.get(builtin, ()):
            continue
        dialects = TYPE_DIALECTS.get(builtin, ())
        raise SpecError(
            f"{path}: `using {builtin}: {bound}` names neither a declared type "
            f"nor a dialect of {builtin} "
            f"(dialects: {', '.join(dialects) if dialects else 'none'}; "
            f"declared types: {', '.join(sorted(types)) if types else 'none'})")
    for child in sec.sections:
        _check_usings(child, types, f"{path}.{child.name}")


def parse_spec(spec_text: str) -> Spec:
    """Read a spec into its model, or raise :class:`SpecError`."""
    lines = spec_text.split("\n")
    page, types, roots = Page(), {}, []

    i = 0
    while i < len(lines):
        line = lines[i]
        if is_blank(line) or line.strip().startswith("'"):
            i += 1
            continue
        t = line.strip()
        ind = indent_of(line)
        end = _block_end(lines, i, ind, len(lines))

        if t.startswith("page:"):
            page = _parse_page(lines, i + 1, end)
            i = end
            continue
        tm = re.match(r"^type\s+([A-Za-z_][A-Za-z0-9_]*)\s*:", t)
        if tm:
            types[tm.group(1)] = _parse_type(lines, i + 1, end, tm.group(1))
            i = end
            continue
        if t.startswith("section "):
            sec = _parse_section_header(t)
            if sec is not None:
                roots.append(_parse_block(sec, lines, i + 1, end, ind + 1))
            i = end
            continue
        if t.startswith("using "):
            # There is no file scope for a binding to attach to, so one written
            # above the first section is refused rather than ignored.
            raise SpecError("`using` must be written inside a section")
        i = end if end > i else i + 1

    if not roots:
        raise SpecError("spec declares no section")
    # One top-level section is the overwhelmingly common shape and its record
    # IS the result. Several are wrapped in a nameless root so the value still
    # has one shape whatever the spec did.
    root = roots[0] if len(roots) == 1 else Section("", sections=roots)
    for sec in roots:
        _check_usings(sec, types, sec.name)
    return Spec(page=page, types=types, root=root)
