' SPDX-License-Identifier: Apache-2.0
' Copyright 2026 Matthew C. Tedder
'
' run_parity.bas -- the gBASIC half of the parity harness.
'
' Reads the SAME tab-separated case files as parity/run_parity.py and runs
' them against gBASIC. A case that disagrees fails in whichever tree is wrong;
' the case file arbitrates, so neither implementation is right merely by being
' the one that was asked.
'
'   gbasic parity/run_parity.bas parity/cases/money.tsv
'
' Columns: expr, a, b, c, expect, name -- tab separated. What the middle three
' mean depends on the expression. The format is not JSON on purpose:
' crypto.json_decode is flat, so a nested file would be readable by one side
' only, and a harness whose halves disagree about how to read the questions
' cannot arbitrate the answers.
'
' Calendars, specs and series bounds are NAMED in the case files, and the two
' runners build the named thing identically -- so a case that disagrees is a
' disagreement about behaviour, never about which calendar was meant.
'
' The dates cases need stdlib/dates.bas, loaded relative to this file as
' ../../gbasic/stdlib/dates.bas. That assumes the gbasic and etl-tools
' checkouts are siblings, which is the same assumption running the harness in
' both trees already makes.
'
' A case whose name begins with "gbasic-defect:" is one Python passes and this
' tree is known to fail. It is reported here and tolerated; it is a hard
' failure on the Python side. The fix belongs in gBASIC.

program main(args)
    load dates from "../../gbasic/stdlib/dates.bas"
    load persist from "../../gbasic/stdlib/persist.bas"

    ' Shared with run_parity.py on purpose: an identical scratch path makes
    ' the path inside an error message comparable verbatim rather than through
    ' a filter. absent.json is never written, by anyone.
    persist.ensure_dir("/tmp/parity_persist")
    persist.write_atomic("/tmp/parity_persist/good.json", { schema_version: 1, theme: "dark", recent: 10 })
    bk{file} = "/tmp/parity_persist/broken.json"
    write(bk, "{ this is not json ]")
    ek{file} = "/tmp/parity_persist/empty.json"
    write(ek, "")

    if len(args) < 1 then
        print "usage: gbasic run_parity.bas <cases.tsv> [...]"
        return
    end if

    passed = 0
    failed = 0
    skipped = 0
    known = 0

    for each path in args
        f {file}= path
        text = read(f)
        for each line in split(text, "\n")
            if len(line) = 0 then
                continue
            end if
            if mid(line, 0, 1) = "#" then
                continue
            end if
            cols = split(line, "\t")
            if len(cols) != 6 then
                continue
            end if
            if cols[0] = "expr" then
                continue
            end if

            expr   = cols[0]
            a      = cols[1]
            b      = cols[2]
            c      = cols[3]
            expect = cols[4]
            name   = cols[5]

            got = _run(expr, a, b, c)
            if got = "?" then
                skipped = skipped + 1
            else if got = expect then
                passed = passed + 1
            else if mid(name, 0, 14) = "gbasic-defect:" then
                known = known + 1
                print "  KNOWN " + name
                print "        want " + expect
                print "        got  " + got
            else
                failed = failed + 1
                print "  FAIL " + name
                print "       want " + expect
                print "       got  " + got
            end if
        end for
    end for

    print ""
    print "gbasic: " + string(passed) + " passed, " + string(failed) + " failed, " + string(known) + " known divergence, " + string(skipped) + " skipped"
end program

' Evaluate one case. Returns the display string, "!"+message on a refusal,
' or "?" when this tree has no evaluator for the expression.
function _run(expr, a, b, c)
    if _is_money(expr) then
        return _run_money(expr, a, b, c)
    end if
    if _is_persist(expr) then
        return _run_persist(expr, a, b, c)
    end if
    return _run_dates(expr, a, b, c)
end function

function _is_persist(expr)
    if expr = "status" or expr = "reports" or expr = "value" then
        return true
    end if
    if expr = "text_roundtrip" or expr = "encode_refuses" then
        return true
    end if
    return false
end function

function _is_money(expr)
    if expr = "show" or expr = "text" or expr = "text2" then
        return true
    end if
    if expr = "mul" or expr = "div" or expr = "divmul" or expr = "accum" then
        return true
    end if
    return false
end function

function _run_money(expr, ccy, amount, operand)
    on error goto next
    m = money.of(ccy, amount)
    if error then
        msg = error.message
        error.clear()
        return "!" + msg
    end if
    on error stop

    if expr = "show" then
        return string(m)
    end if
    if expr = "text" then
        return money.text(m)
    end if
    if expr = "text2" then
        return money.text(m, 2)
    end if
    if expr = "mul" then
        return string(m * number(operand))
    end if
    if expr = "div" then
        return string(m / number(operand))
    end if
    if expr = "divmul" then
        return string((m / number(operand)) * number(operand))
    end if
    if expr = "accum" then
        total = money.of(ccy, "0")
        i = 0
        while i < number(operand)
            total = total + m
            i = i + 1
        end while
        return string(total)
    end if
    return "?"
end function

' ------------------------------------------------------------------
' The dates half.
'
' Named calendars, specs and bounds, built here exactly as run_parity.py
' builds them. Keeping them out of the case file is what lets a flat
' six-column format carry a question as structured as "the third Thursday of
' every month at 14:00, rolled off this calendar's holidays".

function _run_dates(expr, a, b, c)
    on error goto next
    r = _dates(expr, a, b, c)
    if error then
        msg = error.message
        error.clear()
        return "!" + msg
    end if
    on error stop
    return r
end function

' unknown is an ANSWER here, not a failure: a spec no day satisfies (a fifth
' Tuesday) yields it, and a malformed spec raises instead. The two failure
' modes mean different things and the case file distinguishes them.
function _sh(v)
    if is_unknown(v) then
        return "unknown"
    end if
    return string(v)
end function

function _dcal(name)
    if name = "plain" then
        return dates.calendar({})
    end if
    if name = "xmas" then
        h {date}= "2026-12-25"
        return dates.calendar({ holidays: [h] })
    end if
    if name = "feb13" then
        h {date}= "2026-02-13"
        return dates.calendar({ holidays: [h] })
    end if
    if name = "hours" then
        return dates.calendar({ hours: { open: "9:00", close: "17:00" } })
    end if
    if name = "xmashours" then
        h {date}= "2026-12-25"
        return dates.calendar({ holidays: [h], hours: { open: "9:00", close: "17:00" } })
    end if
    if name = "july4" then
        h {date}= "2026-07-04"
        return dates.calendar({ holidays: [h], observe: "nearest" })
    end if
    if name = "july4f" then
        h {date}= "2026-07-04"
        return dates.calendar({ holidays: [h], observe: "forward" })
    end if
    if name = "never" then
        return dates.calendar({ weekend: ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"] })
    end if
    if name = "badobserve" then
        h {date}= "2026-07-04"
        return dates.calendar({ holidays: [h], observe: "sideways" })
    end if
    error "parity: unknown calendar '" + name + "'"
end function

function _dspec(name)
    if name = "thu3" then
        return { nth: 3, weekday: "thursday", within: "month" }
    end if
    if name = "wedlast" then
        return { nth: "last", weekday: "wednesday", within: "month" }
    end if
    if name = "wedneg1" then
        return { nth: 0 - 1, weekday: "wednesday", within: "month" }
    end if
    if name = "tue5" then
        return { nth: 5, weekday: "tuesday", within: "month" }
    end if
    if name = "mon1q" then
        return { nth: 1, weekday: "monday", within: "quarter" }
    end if
    if name = "fri1y" then
        return { nth: 1, weekday: "friday", within: "year" }
    end if
    if name = "blastwk" then
        return { nth: 0 - 1, kind: "business", within: "week" }
    end if
    if name = "tueafter15" then
        return { nth: 1, weekday: "tuesday", after: { day: 15 } }
    end if
    if name = "bbefore28" then
        d {date}= "2026-12-28"
        return { nth: 1, kind: "business", before: d }
    end if
    if name = "monoa" then
        d {date}= "2026-08-17"
        return { nth: 1, weekday: "monday", on_or_after: d }
    end if
    if name = "monafter" then
        d {date}= "2026-08-17"
        return { weekday: "monday", after: d }
    end if
    if name = "barefri" then
        return { weekday: "friday" }
    end if
    if name = "d31mod" then
        return { nth: 1, day: 31, within: "month", roll: "modified" }
    end if
    if name = "d31fwd" then
        return { nth: 1, day: 31, within: "month", roll: "forward" }
    end if
    if name = "business" then
        return { kind: "business" }
    end if
    if name = "d15m7" then
        return { day: 15, month: 7 }
    end if
    if name = "board" then
        return { every: "month", when: { nth: 3, weekday: "thursday" }, at: "14:00" }
    end if
    if name = "boardx" then
        d {date}= "2026-03-19"
        return { every: "month", when: { nth: 3, weekday: "thursday" }, except: [d] }
    end if
    if name = "payroll" then
        return { every: 2 weeks, roll: "backward" }
    end if
    if name = "monthly" then
        return { every: "month" }
    end if
    if name = "standup" then
        return { every: "week", when: { weekday: ["monday", "wednesday", "friday"] } }
    end if
    if name = "bymonth" then
        return { every: "month", when: { day: 15, month: [1, 7] } }
    end if
    if name = "bdays" then
        return { every: "business day" }
    end if
    if name = "badroll" then
        return { nth: 1, day: 31, within: "month", roll: "sideways" }
    end if
    if name = "badwithin" then
        return { nth: 1, weekday: "monday", within: "fortnight" }
    end if
    if name = "nthneg" then
        d {date}= "2026-08-17"
        return { nth: 0 - 1, weekday: "monday", after: d }
    end if
    if name = "nonth" then
        return { weekday: "monday", within: "month" }
    end if
    if name = "badwhen" then
        return { every: "day", when: { weekday: "monday" } }
    end if
    if name = "noevery" then
        return { weekday: "monday" }
    end if
    if name = "badevery" then
        return { every: "fortnight" }
    end if
    ' The two upstream defects. gBASIC answers both of these instead of
    ' refusing: badfield becomes "the third day of the month" and nthfirst
    ' becomes "last". Reported as known divergence, tolerated here, and a
    ' hard failure on the Python side.
    if name = "badfield" then
        return { nth: 3, weekdy: "thursday", within: "month" }
    end if
    if name = "nthfirst" then
        return { nth: "first", weekday: "thursday", within: "month" }
    end if
    error "parity: unknown spec '" + name + "'"
end function

function _dbounds(name)
    if name = "h1" then
        f {date}= "2026-01-01"
        t {date}= "2026-06-30"
        return { from: f, through: t }
    end if
    if name = "c6from0102" then
        f {date}= "2026-01-02"
        return { from: f, count: 6 }
    end if
    if name = "c4from0131" then
        f {date}= "2026-01-31"
        return { from: f, count: 4 }
    end if
    if name = "c6from0817" then
        f {date}= "2026-08-17"
        return { from: f, count: 6 }
    end if
    if name = "y2026" then
        f {date}= "2026-01-01"
        t {date}= "2026-12-31"
        return { from: f, through: t }
    end if
    if name = "c3from1223" then
        f {date}= "2026-12-23"
        return { from: f, count: 3 }
    end if
    if name = "c3from0101" then
        f {date}= "2026-01-01"
        return { from: f, count: 3 }
    end if
    if name = "nobound" then
        f {date}= "2026-01-01"
        return { from: f }
    end if
    error "parity: unknown bounds '" + name + "'"
end function

function _series_index(expr)
    if expr = "series_0" then
        return 0
    end if
    if expr = "series_1" then
        return 1
    end if
    if expr = "series_2" then
        return 2
    end if
    if expr = "series_3" then
        return 3
    end if
    if expr = "series_4" then
        return 4
    end if
    return 0 - 1
end function

function _dates(expr, a, b, c)
    if expr = "dayname" then
        d {date}= a
        return dates.dayname(d)
    end if
    if expr = "days_between" then
        x {date}= a
        y {date}= b
        return string(dates.days_between(x, y))
    end if
    if expr = "between" then
        x {date}= a
        y {date}= b
        return string(dates.between(x, y, c))
    end if
    if expr = "end_of_month" then
        d {end of month}= a
        return string(d)
    end if
    if expr = "start_of_month" then
        d {start of month}= a
        return string(d)
    end if
    if expr = "next_weekday" then
        d {date}= a
        return string(_named_weekday(d, b, 1))
    end if
    if expr = "previous_weekday" then
        d {date}= a
        return string(_named_weekday(d, b, 0 - 1))
    end if
    if expr = "at" then
        d {date}= a
        return string(dates.at(d, b))
    end if
    if expr = "is_business_day" then
        d {date}= a
        return string(dates.is_business_day(d, _dcal(b)))
    end if
    if expr = "next_business_day" then
        d {date}= a
        return string(dates.next_business_day(d, _dcal(b)))
    end if
    if expr = "previous_business_day" then
        d {date}= a
        return string(dates.previous_business_day(d, _dcal(b)))
    end if
    if expr = "add_business_days" then
        d {date}= a
        return string(dates.add_business_days(d, number(b), _dcal(c)))
    end if
    if expr = "business_days_between" then
        x {date}= a
        y {date}= b
        return string(dates.business_days_between(x, y, _dcal(c)))
    end if
    if expr = "holiday_count" then
        return string(len(_dcal(a).holidays))
    end if
    if expr = "select" then
        d {date}= b
        return _sh(dates.select(_dspec(a), d, _dcal(c)))
    end if
    if expr = "matches" then
        d {date}= b
        return string(dates.matches(d, _dspec(a), _dcal(c)))
    end if
    ' `on error goto next` continues to the NEXT statement, so a raising
    ' dates.series followed by len() in one expression reports len's own
    ' complaint and buries the real refusal. Check before touching the result.
    if expr = "series_count" then
        rows = dates.series(_dspec(a), _dbounds(b), _dcal(c))
        if error then
            return ""
        end if
        return string(len(rows))
    end if
    idx = _series_index(expr)
    if idx >= 0 then
        rows = dates.series(_dspec(a), _dbounds(b), _dcal(c))
        if error then
            return ""
        end if
        return string(rows[idx])
    end if
    if expr = "add_bhours" then
        d {date}= a
        return string(dates.add_business_hours(d, (1 minute) * number(b), _dcal(c)))
    end if
    if expr = "bhours_between" then
        x {date}= a
        y {date}= b
        dur = dates.business_hours_between(x, y, _dcal(c))
        return string(floor(dur.total_seconds / 60))
    end if
    if expr = "is_business_time" then
        d {date}= a
        return string(dates.is_business_time(d, _dcal(b)))
    end if
    return "?"
end function

' gBASIC spells "the next Friday" as fourteen modifiers, not a function, so
' the runner dispatches the name here. Python has one function taking the
' name, which is the same translation the modifier-to-function port makes.
function _named_weekday(d, name, direction)
    if direction > 0 then
        if name = "monday" then
            x {next monday}= d
            return x
        end if
        if name = "tuesday" then
            x {next tuesday}= d
            return x
        end if
        if name = "wednesday" then
            x {next wednesday}= d
            return x
        end if
        if name = "thursday" then
            x {next thursday}= d
            return x
        end if
        if name = "friday" then
            x {next friday}= d
            return x
        end if
        if name = "saturday" then
            x {next saturday}= d
            return x
        end if
        x {next sunday}= d
        return x
    end if
    if name = "monday" then
        x {previous monday}= d
        return x
    end if
    if name = "tuesday" then
        x {previous tuesday}= d
        return x
    end if
    if name = "wednesday" then
        x {previous wednesday}= d
        return x
    end if
    if name = "thursday" then
        x {previous thursday}= d
        return x
    end if
    if name = "friday" then
        x {previous friday}= d
        return x
    end if
    if name = "saturday" then
        x {previous saturday}= d
        return x
    end if
    x {previous sunday}= d
    return x
end function


' ------------------------------------------------------------------
' The persist half.
'
' read_status answers loaded/missing/corrupt here and an Outcome answering
' ok/unknown/invalid in the Python tree -- a deliberate deviation documented
' in etools/persist.py. The case file uses THESE words and the Python runner
' maps into them, so what the cases compare is the classification: that the
' same file lands in the same one of three buckets in both trees.

function _run_persist(expr, a, b, c)
    on error goto next
    r = _persist(expr, a, b, c)
    if error then
        msg = error.message
        error.clear()
        return "!" + msg
    end if
    on error stop
    return r
end function

function _persist(expr, a, b, c)
    if expr = "status" then
        st = persist.read_status("/tmp/parity_persist/" + a + ".json")
        return st.status
    end if
    if expr = "reports" then
        st = persist.read_status("/tmp/parity_persist/" + a + ".json")
        return string(st.message != "")
    end if
    if expr = "value" then
        st = persist.read_status("/tmp/parity_persist/" + a + ".json")
        return string(st.value[b])
    end if
    if expr = "text_roundtrip" then
        persist.write_text_atomic("/tmp/parity_persist/notes.txt", a)
        nf{file} = "/tmp/parity_persist/notes.txt"
        back = read(nf)
        return back
    end if
    if expr = "encode_refuses" then
        ' `unknown` is part of the dialect the decoder accepts and has no JSON
        ' form at all, so it is the one value both trees must refuse to write.
        persist.write_atomic("/tmp/parity_persist/bad.json", { x: unknown })
        return "wrote it"
    end if
    return "?"
end function
