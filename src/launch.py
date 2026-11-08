"""Getting a save's word list and queue ready at start-up (main's set-up, run on the progress window's worker thread).

Each stage is named once, together with the work that does it: `stages` decides which stages this start needs and
returns them as (step names, work) pairs. `set_up` logs every stage's step names first (constants.plan_line: the
progress window's "Step i of n" corner), then runs the work in order. Before this module, main() worked out the steps
in one if / elif chain and then ran a second copy of the same chain, which could drift apart.

The step names a stage gives come from wordsource.wiktionary_steps / queue_steps, which predict the stage lines
build_wiktionary and prepare_queue log as they go: those two must still be kept in step with the work they predict.

No tkinter here: this runs on a worker thread (startup.run_with_progress).
"""
from constants import plan_line
from problems import SetupError
from wordsource import build_word_list, build_wiktionary, prepare_queue, queue_steps, wiktionary_steps


def builds_wiktionary(current, wordlist=None, source="wiktionary"):
    """True when this start builds (or upgrades to) the full Wiktionary list: no --wordlist, not a custom list,
    Wiktionary asked for and not built yet. `current`: the save's meta "source" ("wordnet" for an older save
    with words but no source)."""
    return not wordlist and current != "custom" and source == "wiktionary" and current != "wiktionary"


def stages(store, existing, current, wordlist=None, source="wiktionary", wiktionary_file=None, keep_download=False,
           seed=None):
    """The stages this start needs, in order: [(step names for the plan line, work(log))]. `existing`: words in the
    save before this start; `current`: its source (see builds_wiktionary). A custom list is never replaced."""
    out = []
    wiki = builds_wiktionary(current, wordlist, source)
    adds = False
    if wordlist:
        adds = existing == 0
        if adds:
            def from_file(log):
                store.insert_words(build_word_list(wordlist))
                store.set_meta("source", "custom")
            out.append(([], from_file))
    elif current == "custom":
        pass
    elif wiki:
        adds = True

        def from_wiktionary(log):
            if existing:
                log(f"Upgrading your {existing:,}-word list to the full Wiktionary list. Your progress is kept.")
            try:
                build_wiktionary(store, wiktionary_file, keep_download, log=log)
            except (RuntimeError, OSError) as exc:
                raise SetupError(f"Could not build the Wiktionary word list: {exc}\n\n"
                                 "Try again (downloads resume), download the file yourself and pass "
                                 "--wiktionary-file, or use --source wordnet.") from exc
        out.append((wiktionary_steps(store, wiktionary_file), from_wiktionary))
    elif source == "wordnet" and existing == 0:
        adds = True

        def from_wordnet(log):
            log("First run: building the word list (about 10-30 seconds)...")
            store.insert_words(build_word_list())
            store.set_meta("source", "wordnet")
        out.append((["First run: building the word list"], from_wordnet))
    # the queue: flag compounds, mark obscene words and shuffle (cheap when already done)
    out.append((queue_steps(store, adds_words=adds, by_wiktionary=wiki), lambda log: prepare_queue(store, log=log)))
    if seed is not None and seed != store.queue_settings()["seed"]:
        def reshuffle(log):
            if seed != store.queue_settings()["seed"]:        # (asked again after the queue's own shuffle)
                log(f"Reshuffling the queue with seed {seed}...")
                store.reshuffle(seed=seed)
        out.append((["Reshuffling the queue"], reshuffle))
    return out


def set_up(store, log, existing, current, **options):
    """Get the save ready: log the plan (every stage's step names), then run each stage. `options`: stages'."""
    todo = stages(store, existing, current, **options)
    log(plan_line([name for names, _ in todo for name in names]))
    for _, work in todo:
        work(log)
