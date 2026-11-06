import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""Start-up's stages (launch.py): each step is named once with its work, so the plan line ("Step i of n") lists
exactly the stages that then run, in order; a custom list is never replaced; --seed reshuffles only when it differs."""
import os, tempfile
import launch
from constants import parse_plan
from store import Store

tmp = tempfile.mkdtemp()
words = os.path.join(tmp, "words.txt")
open(words, "w", encoding="utf-8").write("".join(f"word{i}\n" for i in range(50)))


def run(store, **options):
    lines = []
    existing = store.count_words()
    current = store.get_meta("source") or ("wordnet" if existing else None)
    launch.set_up(store, lines.append, existing, current, **options)
    return [step for step in parse_plan(lines[0]) or [] if step], lines[1:]


assert launch.builds_wiktionary(None) and launch.builds_wiktionary("wordnet")
assert not launch.builds_wiktionary("wiktionary") and not launch.builds_wiktionary("custom")
assert not launch.builds_wiktionary(None, wordlist=words) and not launch.builds_wiktionary(None, source="wordnet")

# a first start from a word list: the words go in, then the queue's own steps, each logged as planned
s = Store(os.path.join(tmp, "a.db"))
plan, said = run(s, wordlist=words)
assert s.count_words() == 50 and s.get_meta("source") == "custom"
assert plan, plan                                                    # (the queue is made: its steps were named)
for step in plan:
    assert any(line.startswith(step) for line in said), (step, said)
# a later start: nothing to do, no steps; a custom list is never replaced, even when Wiktionary is asked for
assert run(s) == ([], [])
assert run(s, source="wiktionary") == ([], []) and s.get_meta("source") == "custom"
# --seed: a step of its own only when it is not the seed already
plan, said = run(s, seed=7)
assert plan == ["Reshuffling the queue"] and s.queue_settings()["seed"] == 7, plan
assert run(s, seed=7) == ([], [])
# the stages themselves: (names, work) in order, nothing done until the work runs
t = Store(os.path.join(tmp, "b.db"))
todo = launch.stages(t, 0, None, wordlist=words, seed=3)
assert [names for names, _ in todo][-1] == ["Reshuffling the queue"] and t.count_words() == 0
s.close(); t.close()

# main() calls launch.set_up from inside start(): a function or name of its own called "launch" (start's window part
# was) hides the module there and every start failed with UnboundLocalError. No name inside main() may hide a
# module tierlist.py imports.
import ast
tree = ast.parse(open(os.path.join(_paths.ROOT, "tierlist.py"), encoding="utf-8").read())
modules = {(a.asname or a.name).split(".")[0] for n in tree.body if isinstance(n, ast.Import) for a in n.names}
main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
bound = {n.name for n in ast.walk(main) if isinstance(n, (ast.FunctionDef, ast.ClassDef))} | \
        {n.id for n in ast.walk(main) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
assert "launch" in modules and not bound & modules, bound & modules
print("LAUNCH OK")
