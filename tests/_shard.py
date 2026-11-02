"""Split the self-tests into SHARD=k/n parts of about equal length, for running them on several machines at once
(the macOS workflow). Usage: python _shard.py k/n test...   prints the tests of part k (1..n), one per line.

Each test is weighed by how long it took on GitHub's Intel Mac (seconds; a new test counts as 15) and given, longest
first, to the part that is shortest so far, so the parts end at about the same time. Re-measure from a run's log
(the "Self-tests" step's timestamps) when the parts drift apart."""
import sys

SECONDS = {
    "_selftest_ui": 96, "_selftest_zoom": 86, "_selftest_queue": 73, "_selftest_build": 63, "_selftest_smoke": 54,
    "_selftest_sources": 48, "_selftest_looks": 45, "_selftest_drawer": 34, "_selftest_startup": 34,
    "_selftest_dealing": 27, "_selftest_sizing": 26, "_selftest_ui2": 24, "_selftest_release": 21,
    "_selftest_selfupdate": 19, "_selftest_freeze": 19, "_selftest_widgets2": 17, "_selftest_health": 17,
    "_selftest_lookup": 15, "_selftest_wikt": 15, "_selftest_shortcuts": 13, "_selftest_filepicker": 13,
    "_selftest_tabswitch": 13, "_selftest": 11, "_selftest_defsize": 11, "_selftest_rudeness": 6,
    "_selftest_obscene": 6, "_selftest_motion": 5, "_selftest_deps": 4, "_selftest_bundle": 4, "_selftest_tidy": 4,
    "_selftest_install": 4, "_selftest_fonts": 2, "_selftest_resume": 2, "_selftest_widgets": 2,
    "_selftest_errors": 1, "_selftest_smooth": 1, "_selftest_style": 1, "_selftest_chart": 1, "_selftest_icon": 1,
    "_selftest_keymap": 0, "_selftest_appdir": 0, "_selftest_updates": 0,
}
NEW = 15


def split(tests, n):
    """The tests in n parts of about equal length, each in the given order."""
    parts, totals = [[] for _ in range(n)], [0] * n
    for t in sorted(tests, key=lambda t: -SECONDS.get(t, NEW)):       # (sorted is stable: ties keep their order)
        i = totals.index(min(totals))
        parts[i].append(t)
        totals[i] += SECONDS.get(t, NEW)
    return [[t for t in tests if t in part] for part in parts]


if __name__ == "__main__":
    k, n = (int(x) for x in sys.argv[1].split("/"))
    print("\n".join(split(sys.argv[2:], n)[k - 1]))
