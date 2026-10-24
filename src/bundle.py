"""What a built program carries besides its code (T-2), for build.py (T-3) to hand to PyInstaller.

PyInstaller follows the imports and takes the code (and compiled parts such as msgpack's and regex's) by itself;
data files it only takes when told. wordfreq ships 60 MB of word lists in 40 languages; the program reads only the
English ones, so only those go in (about 1.6 MB):

    datas()        [(source file, folder inside the program)] for --add-data
    EXCLUDE        modules never to bundle (wordfreq's Chinese / Japanese / Korean tokenizers, tests ...)
    size_mb()      how much data that is

WordNet (nltk's dictionary, ~30 MB) is not bundled: as from source, it stays an optional download the first time
offline definitions or the WordNet word list are wanted (nltk puts it in ~/nltk_data).

    python tools/bundle.py          lists the files and their size
"""
import importlib.util
import os

# (package, data files inside it): what the program reads at run time
DATA = (
    ("wordfreq", ("data/large_en.msgpack.gz", "data/small_en.msgpack.gz")),   # word frequencies (English only)
    ("langcodes", ("data/language-subtag-registry.txt",)),                   # wordfreq looks "en" up in it
    ("nltk", ("VERSION",)),                                                  # read as nltk is imported
)
# never bundled: wordfreq's tokenizers for Chinese / Japanese / Korean (it imports them only for those
# languages), nltk's own tests, and the tkinter test suite; and packages the program never uses that nltk only
# mentions (its charts, its maths), which PyInstaller would otherwise pack if they are on the computer. A broken
# one stopped the build (reported: matplotlib installed without Pillow, "No module named 'PIL'")
UNUSED = ("matplotlib", "PIL", "numpy", "scipy", "pandas", "sklearn", "IPython", "pytest", "datasets",
          "huggingface_hub", "networkx", "requests", "twython", "pygame", "pycrfsuite", "bllipparser", "svgling",
          "yaml")
EXCLUDE = ("jieba", "MeCab", "ipadic", "mecab_ko_dic", "nltk.test", "tkinter.test", "test") + UNUSED


def package_dir(name):
    """The folder of an installed package, or None if it is not installed."""
    spec = importlib.util.find_spec(name)
    return os.path.dirname(spec.origin) if spec and spec.origin else None


def datas(optional=("nltk",)):
    """[(absolute source path, destination folder inside the program)]. A package in `optional` that is not
    installed is left out (nltk); a required one missing, or a missing file, raises FileNotFoundError."""
    out = []
    for pkg, files in DATA:
        root = package_dir(pkg)
        if root is None:
            if pkg in optional:
                continue
            raise FileNotFoundError(f"{pkg} is not installed (pip install -r requirements.txt)")
        for rel in files:
            src = os.path.join(root, rel)
            if not os.path.isfile(src):
                raise FileNotFoundError(f"{src} is missing: is {pkg} installed completely?")
            out.append((src, os.path.normpath(os.path.join(pkg, os.path.dirname(rel)))))
    return out


def size_mb(pairs=None):
    return sum(os.path.getsize(src) for src, _ in (pairs if pairs is not None else datas())) / 1e6


if __name__ == "__main__":
    for src, dest in datas():
        print(f"{os.path.getsize(src) / 1e6:7.2f} MB  {dest}/{os.path.basename(src)}")
    print(f"{size_mb():7.2f} MB in all")
