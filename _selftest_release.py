"""check_release.py catches what it should: undeclared packages, undocumented modules, unlisted tests."""
import os, shutil, subprocess, sys, tempfile, zipfile

here = os.path.dirname(os.path.abspath(__file__))
tmp = tempfile.mkdtemp()
work = os.path.join(tmp, "proj")
os.makedirs(work)
for f in os.listdir(here):
    if f.endswith((".py", ".md", ".txt", ".sh")):
        shutil.copy(os.path.join(here, f), work)

def run(*args):
    r = subprocess.run([sys.executable, "check_release.py", *args], cwd=work, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr

code, out = run()
assert code == 0 and "static checks: OK" in out, out                       # the real project passes

open(os.path.join(work, "newmod.py"), "w").write("import requests\nimport numpy\n")
code, out = run()
assert code == 1 and "'requests' is imported by newmod.py but is not in requirements.txt" in out, out
assert "not in deps.PACKAGES" in out and "newmod.py is not in the README file map" in out, out
os.remove(os.path.join(work, "newmod.py"))

open(os.path.join(work, "_selftest_new.py"), "w").write("print('x')\n")
code, out = run(); assert code == 1 and "_selftest_new.py is not run by run_tests.sh" in out, out
os.remove(os.path.join(work, "_selftest_new.py"))

open(os.path.join(work, "tierlist.db"), "w").write("x")
code, out = run(); assert code == 1 and "stray file" in out and "tierlist.db" in out, out
os.remove(os.path.join(work, "tierlist.db"))

req = open(os.path.join(work, "requirements.txt")).read()
open(os.path.join(work, "requirements.txt"), "w").write(req.replace("wordfreq>=3.0", ""))
code, out = run(); assert code == 1 and "'wordfreq'" in out, out
open(os.path.join(work, "requirements.txt"), "w").write(req)

code, out = run("--zip", os.path.join(tmp, "out.zip"))
assert code == 0 and "zip:" in out, out
names = zipfile.ZipFile(os.path.join(tmp, "out.zip")).namelist()
assert "word-tierlist/tierlist.py" in names and "word-tierlist/requirements.txt" in names
assert "word-tierlist/CLAUDE.md" in names and "word-tierlist/CHECKLIST.md" in names
assert not [n for n in names if n.endswith((".db", ".log", ".pyc"))]
shutil.rmtree(tmp)
print("RELEASE OK")
