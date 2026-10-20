"""Imported first by every self-test: puts the program's folders on the import path, so the tests run from
anywhere (`python tests/_selftest.py`, or `sh tests/run_tests.sh`). ROOT is the top of the project. The tests
never ask Wiktionary for anything (OFFLINE_ENV; the ones about it fake its answers)."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
for p in (SRC, ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)
os.environ["WORD_TIERLIST_OFFLINE"] = "1"         # (wordsource.OFFLINE_ENV; also seen by the program the tests start)
