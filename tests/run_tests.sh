#!/bin/sh
# Run every self-test, stopping at the first failure. From the top of the project:  sh tests/run_tests.sh
#
# Core tests need only python3 (+ wordfreq). Window tests need tkinter and a display; with no
# display (CI, a server) they run under xvfb-run, on a desktop they simply run.
# Some Linux Pythons ship without tkinter: point TK_PYTHON at one that has it, e.g.
#     TK_PYTHON=/usr/bin/python3.12 sh tests/run_tests.sh
cd "$(dirname "$0")" || exit 1
PY=${PY:-python3}
TK_PYTHON=${TK_PYTHON:-$PY}
OUT=$(mktemp)

run() {  # run <label> <command...>: show the last line of output, abort if the test failed
    label=$1; shift
    if "$@" >"$OUT" 2>&1; then
        echo "ok   $label: $(tail -1 "$OUT")"
    else
        echo "FAIL $label"; tail -15 "$OUT"; rm -f "$OUT"; exit 1
    fi
}

for t in _selftest _selftest_wikt _selftest_queue _selftest_resume _selftest_install; do
    run $t $PY $t.py
done
for t in _selftest_ui _selftest_ui2 _selftest_zoom _selftest_tidy _selftest_fonts _selftest_style _selftest_motion _selftest_startup _selftest_sizing _selftest_errors _selftest_widgets _selftest_widgets2 _selftest_chart _selftest_deps _selftest_release; do
    if [ -z "$DISPLAY" ] && command -v xvfb-run >/dev/null 2>&1; then
        run $t xvfb-run -a -s "-screen 0 1920x1200x24" $TK_PYTHON $t.py
    else
        run $t $TK_PYTHON $t.py
    fi
done
rm -f "$OUT"
echo "ALL TESTS PASSED"
