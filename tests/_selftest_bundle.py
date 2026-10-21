import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""T-2: what a built program carries besides its code (tools/bundle.py). Without PyInstaller here, a folder is put
together the way it would be: each package's code (and compiled parts) but none of its data files, then only the
data tools/bundle.py names. A Python that sees nothing else (no site-packages) must then rank English words with
wordfreq and import nltk. The packages it needs are found by trying (each "No module named" adds one)."""
import importlib.util, os, shutil, subprocess, sys, tempfile
sys.path.insert(0, os.path.join(_paths.ROOT, "tools"))
import bundle

pairs = bundle.datas()
names = {os.path.join(dest, os.path.basename(src)) for src, dest in pairs}
assert {"wordfreq/data/large_en.msgpack.gz", "wordfreq/data/small_en.msgpack.gz",
        "langcodes/data/language-subtag-registry.txt"} <= names, names
assert not any("_fr." in n or "jieba" in n for n in names)            # only English: not the other 39 languages
assert 1 < bundle.size_mb(pairs) < 5, bundle.size_mb(pairs)
CODE = (".py", ".so", ".pyd", ".dylib")


def copy_code(name, into):
    """Copy an installed module or package's code (no data files) into the folder."""
    spec = importlib.util.find_spec(name)
    if spec is None or spec.origin in (None, "built-in", "frozen"):
        raise RuntimeError(f"{name} is not installed")
    if spec.submodule_search_locations:
        root = list(spec.submodule_search_locations)[0]
        for folder, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for f in files:
                if f.endswith(CODE):
                    dest = os.path.join(into, name, os.path.relpath(folder, root))
                    os.makedirs(dest, exist_ok=True)
                    shutil.copy2(os.path.join(folder, f), dest)
    else:
        shutil.copy2(spec.origin, into)


app = tempfile.mkdtemp(prefix="bundle-")
for src, dest in pairs:
    os.makedirs(os.path.join(app, dest), exist_ok=True)
    shutil.copy2(src, os.path.join(app, dest))
probe = f"""
import sys; sys.path.insert(0, {app!r})
from wordfreq import get_frequency_dict, zipf_frequency, top_n_list
assert zipf_frequency("the", "en") > 7 and len(get_frequency_dict("en")) > 100000
assert top_n_list("en", 3) == ["the", "to", "and"] or len(top_n_list("en", 3)) == 3
import nltk
if getattr(nltk, "__file__", None) is None:                      # (only its VERSION file so far)
    raise ImportError("cannot import name '__version__' from 'nltk' (unknown location)")
print("BUNDLE RUNS", nltk.__version__)
"""
copied = []
for _ in range(40):
    run = subprocess.run([sys.executable, "-I", "-S", "-c", probe], capture_output=True, text=True, timeout=120)
    if run.returncode == 0:
        break
    missing = run.stderr.strip().splitlines()[-1]
    if "(unknown location)" in missing:                            # a folder with only its data: add its code
        name = missing.split(" from ")[1].split()[0].strip("'\"").split(".")[0]
    else:
        assert "No module named" in missing, run.stderr             # (anything else: data the list lacks)
        name = missing.split("No module named ")[1].strip("'\"").split(".")[0]
    assert name not in copied, run.stderr
    copy_code(name, app)
    copied.append(name)
assert run.returncode == 0 and "BUNDLE RUNS" in run.stdout, run.stderr
assert sorted(os.listdir(os.path.join(app, "wordfreq", "data"))) == ["large_en.msgpack.gz", "small_en.msgpack.gz"]
print(f"BUNDLE OK ({', '.join(copied)}; {bundle.size_mb(pairs):.1f} MB of data)")
