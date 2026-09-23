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
' Columns: expr, ccy, amount, operand, expect, name -- tab separated. The
' format is not JSON on purpose: crypto.json_decode is flat, so a nested file
' would be readable by one side only, and a harness whose halves disagree
' about how to read the questions cannot arbitrate the answers.
'
' A case whose name begins with "gbasic-defect:" is one Python passes and this
' tree is known to fail. It is reported here and tolerated; it is a hard
' failure on the Python side. The fix belongs in gBASIC.

program main(args)
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

            expr    = cols[0]
            ccy     = cols[1]
            amount  = cols[2]
            operand = cols[3]
            expect  = cols[4]
            name    = cols[5]

            got = _run(expr, ccy, amount, operand)
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
function _run(expr, ccy, amount, operand)
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
