# Replaces PyInstaller's own hook for nltk (T-3), which packs every nltk_data folder on the build machine (WordNet
# alone is ~30 MB) into the program. WordNet stays an optional download, as from source; the one file nltk needs
# to import (its VERSION) comes from tools/bundle.py.
datas = []
