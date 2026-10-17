"""tools/check_release.py catches what it should: undeclared packages, undocumented modules, unlisted tests,
stray files, files in the wrong folder; and its zip keeps the folder layout (R-1)."""
import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
import os, shutil, subprocess, sys, tempfile, zipfile

tmp = tempfile.mkdtemp()
work = os.path.join(tmp, "proj")
shutil.copytree(_paths.ROOT, work, ignore=shutil.ignore_patterns(".git", ".venv", "venv", "__pycache__", "*.db",
                                                                  "*.db-*", "*.log", "*.pyc", "*.part"))

def run(*args):
    r = subprocess.run([sys.executable, os.path.join("tools", "check_release.py"), *args], cwd=work,
                       capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr

def put(rel, text="x"):
    path = os.path.join(work, rel)
    open(path, "w").write(text)
    return path

code, out = run()
assert code == 0 and "static checks: OK" in out, out                       # the real project passes

p = put(os.path.join("src", "newmod.py"), "import requests\nimport numpy\n")
code, out = run()
assert code == 1 and "'requests' is imported by src/newmod.py but is not in requirements.txt" in out, out
assert "not in deps.PACKAGES" in out and "src/newmod.py is not in the README file map" in out, out
os.remove(p)

p = put(os.path.join("tests", "_selftest_new.py"), "print('x')\n")
code, out = run(); assert code == 1 and "tests/_selftest_new.py is not run by tests/run_tests.sh" in out, out
os.remove(p)

p = put("helper.py", "x = 1\n")                                            # modules belong in src/
code, out = run(); assert code == 1 and "helper.py is at the top of the project" in out, out
os.remove(p)

p = put(os.path.join("src", "debug.log"))                                  # a stray file inside a code folder
code, out = run(); assert code == 1 and "stray file" in out and "debug.log" in out, out
os.remove(p)

# your save, its log and an export sit next to tierlist.py: fine, and never shipped
for f in ("tierlist.db", "tierlist.log", "tierlist.txt"):
    put(f)
code, out = run(); assert code == 0, out

req = open(os.path.join(work, "requirements.txt")).read()
open(os.path.join(work, "requirements.txt"), "w").write(req.replace("wordfreq>=3.0", ""))
code, out = run(); assert code == 1 and "'wordfreq'" in out, out
open(os.path.join(work, "requirements.txt"), "w").write(req)

code, out = run("--zip", os.path.join(tmp, "out.zip"))
assert code == 0 and "zip:" in out, out
names = zipfile.ZipFile(os.path.join(tmp, "out.zip")).namelist()
for need in ("tierlist.py", "requirements.txt", "README.md", "LICENSE", "src/app.py", "src/widgets.py",
             "tests/run_tests.sh", "tests/_selftest.py", "tests/_paths.py", "tools/check_release.py",
             ".claude/CLAUDE.md", ".claude/CHECKLIST.md"):
    assert "word-tierlist/" + need in names, (need, names)
assert not [n for n in names if n.endswith((".db", ".log", ".pyc")) or n.endswith("/tierlist.txt")], names
assert not [n for n in names if "__pycache__" in n or "/.git/" in n]
shutil.rmtree(tmp)
print("RELEASE OK")
