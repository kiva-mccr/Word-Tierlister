"""Imported first by every self-test: puts the program's folders on the import path, so the tests run from
anywhere (`python tests/_selftest.py`, or `sh tests/run_tests.sh`). ROOT is the top of the project. The tests
never go online: no Wiktionary, no online definitions (OFFLINE_ENV; the ones about it fake its answers). Every
temporary folder a test makes goes in one folder of its own, removed when the test ends (they once filled the
disk: 30 GB of saves and builds)."""
import atexit
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
for p in (SRC, ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)
os.environ["WORD_TIERLIST_OFFLINE"] = "1"         # (constants.OFFLINE_ENV; also seen by the program the tests start)

TMP = tempfile.mkdtemp(prefix="wtl-test-")
tempfile.tempdir = TMP                             # (every mkdtemp / NamedTemporaryFile from here on goes inside)
atexit.register(shutil.rmtree, TMP, True)
