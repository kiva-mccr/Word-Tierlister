#!/bin/sh
# Run every self-test, stopping at the first failure. From the top of the project:  sh tests/run_tests.sh
#
# Core tests need only python3 (+ wordfreq). Window tests need tkinter and a display; with no
# display (CI, a server) they run under xvfb-run, on a desktop they simply run.
# Some Linux Pythons ship without tkinter: point TK_PYTHON at one that has it, e.g.
#     TK_PYTHON=/usr/bin/python3.12 sh tests/run_tests.sh
# KEEP_GOING=1 runs every test and lists all the failures at the end (the macOS workflow uses it).
# A test that runs longer than TEST_TIMEOUT seconds (default 600) is stopped and counts as failed.
# SHARD=k/n runs only part k of n, the parts about equally long (_shard.py; the macOS workflow runs them at once).
cd "$(dirname "$0")" || exit 1
PY=${PY:-python3}
TK_PYTHON=${TK_PYTHON:-$PY}
OUT=$(mktemp)
FAILED=""
CORE="_selftest _selftest_wikt _selftest_queue _selftest_resume _selftest_install _selftest_keymap _selftest_obscene _selftest_appdir _selftest_folders _selftest_bundle _selftest_rudeness _selftest_nextreview _selftest_updates"
WINDOW="_selftest_ui _selftest_ui2 _selftest_zoom _selftest_veil _selftest_tidy _selftest_fonts _selftest_style _selftest_motion _selftest_smooth _selftest_startup _selftest_sizing _selftest_errors _selftest_health _selftest_widgets _selftest_widgets2 _selftest_backmenu _selftest_fullscreen _selftest_filepicker _selftest_shortcuts _selftest_review _selftest_devtools _selftest_tune _selftest_looks _selftest_icon _selftest_lookup _selftest_defsize _selftest_drawer _selftest_tabswitch _selftest_freeze _selftest_dealing _selftest_sources _selftest_selfupdate _selftest_nightly _selftest_smoke _selftest_chart _selftest_deps _selftest_build _selftest_release"
PICK=" $CORE $WINDOW "
if [ -n "$SHARD" ]; then
    PICK=$($PY _shard.py "$SHARD" $CORE $WINDOW) || exit 1
    PICK=" $(echo $PICK) "
    echo "part $SHARD:$PICK"
fi

run() {  # run <label> <command...>: show the last line of output, abort if the test failed
    label=$1; shift
    case "$PICK" in *" $label "*) ;; *) return 0 ;; esac          # (not in this part)
    if perl -e 'alarm shift; exec @ARGV or die "cannot start $ARGV[0]\n"' "${TEST_TIMEOUT:-600}" "$@" >"$OUT" 2>&1; then
        echo "ok   $label: $(tail -1 "$OUT")"
    else
        echo "FAIL $label"; tail -40 "$OUT"
        if [ -n "$KEEP_GOING" ]; then FAILED="$FAILED $label"; else rm -f "$OUT"; exit 1; fi
    fi
}

for t in $CORE; do
    run $t $PY $t.py
done
for t in _selftest_ui _selftest_ui2 _selftest_sync _selftest_zoom _selftest_veil _selftest_tidy _selftest_fonts _selftest_style _selftest_motion _selftest_smooth _selftest_startup _selftest_sizing _selftest_errors _selftest_health _selftest_widgets _selftest_widgets2 _selftest_backmenu _selftest_fullscreen _selftest_filepicker _selftest_shortcuts _selftest_review _selftest_devtools _selftest_tune _selftest_looks _selftest_icon _selftest_lookup _selftest_defsize _selftest_drawer _selftest_tabswitch _selftest_freeze _selftest_dealing _selftest_sources _selftest_selfupdate _selftest_nightly _selftest_smoke _selftest_chart _selftest_deps _selftest_build _selftest_release; do
    if [ -z "$DISPLAY" ] && command -v xvfb-run >/dev/null 2>&1; then
        run $t xvfb-run -a -s "-screen 0 1920x1200x24" $TK_PYTHON $t.py
    else
        run $t $TK_PYTHON $t.py
    fi
done
rm -f "$OUT"
if [ -n "$FAILED" ]; then echo "FAILED:$FAILED"; exit 1; fi
echo "ALL TESTS PASSED"
