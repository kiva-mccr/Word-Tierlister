import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""tools/classify_obscene.py (OB-3): which words go, the prompt, reading Claude's answers, and a whole run against a
stand-in for the API (the tests never go online)."""
import json
import os
import sys
import tempfile
from types import SimpleNamespace as NS

sys.path.insert(0, os.path.join(_paths.ROOT, "tools"))
import classify_obscene as C  # noqa: E402
import tierlist as T  # noqa: E402

tmp = tempfile.mkdtemp()
db = os.path.join(tmp, "tierlist.db")
s = T.Store(db)
s.insert_words(["table", "fuck", "fucking", "box", "penis", "idiot", "run", "bitches", "bitch"])
s.set_def("table", "• (noun) A flat surface with legs.")
s.set_def("fuck", "• (verb) (vulgar) To have sexual intercourse.\n• (interjection) (vulgar) Used as an oath.")
s.set_def("fucking", "• (verb) present participle of fuck")
s.set_def("box", "• (noun) A container.\n• (noun) (vulgar) The vagina.")
s.set_def("penis", "• (noun) The male organ of copulation.")
s.set_def("idiot", "• (noun) A stupid person.")
s.set_def("run", "• (verb) To move swiftly.")
s.set_def("bitch", "• (noun) A female dog.\n• (noun) (offensive) A spiteful woman.")
s.set_def("bitches", "• (noun) plural of bitch")
s.db.close()

# ---- which words go: rude labels, telling meanings, the hand list; forms follow their word
save = C.read_save(db)
cands, forms = C.candidates(save)
assert set(cands) == {"fuck", "box", "penis", "idiot", "bitch"}, cands
assert forms == {"fucking": "fuck", "bitches": "bitch"}, forms
assert "labelled" in cands["fuck"] and "meaning" in cands["penis"] and "meaning" in cands["idiot"]
assert list(cands)[0] == "fuck"                                             # commonest first (insert order = rank)
assert C.candidates(save, {"hurtlex": {"table"}})[0]["table"] == ["hurtlex"]
p = C.prompt_for(["box"], save)
assert "WORD: box" in p and "1. (noun) A container." in p and "2. (noun) (vulgar) The vagina." in p
assert "no meanings stored" in C.prompt_for(["zzz"], {})
params = C.request_params(["box"], save, C.MODEL)
assert params["model"] == "claude-opus-5-5" and params["output_config"]["effort"] == "low"
assert params["output_config"]["format"]["schema"] is C.SCHEMA and "thinking" not in params
assert [len(g) for g in C.groups(range(45))] == [20, 20, 5]


# ---- reading answers
def message(items, stop="end_turn"):
    return NS(stop_reason=stop, content=[NS(type="text", text=json.dumps({"words": items}))])


ans = C.read_answer(message([{"word": "box", "meanings": ["clean", "sexual"], "kind": "double", "confidence": 93,
                              "note": "rude only\tin slang"},
                             {"word": "penis", "meanings": ["clinical"], "kind": "nonsense", "confidence": 99,
                              "note": ""}]), ["box", "penis", "idiot"])
assert ans["box"] == ("double", 93, ["clean", "sexual"], "rude only in slang", ""), ans["box"]
assert ans["penis"][1] == 0 and ans["idiot"][1] == 0                        # a bad kind or no answer: to check
assert all(v[1] == 0 for v in C.read_answer(message([], stop="refusal"), ["box"]).values())
assert "refusal" in C.read_answer(message([], stop="refusal"), ["box"])["box"][3]

# ---- the estimate (offline: guessed from the text)
t_in, t_out, cost = C.estimate(C.groups(cands), save, C.MODEL)
assert t_in > 300 and t_out == 5 * C.OUT_PER_WORD and 0 < cost < 1, (t_in, t_out, cost)
assert C.estimate([], save, C.MODEL) == (0, 0, 0.0)


# ---- a whole run against a stand-in for the API
class FakeBatches:
    def __init__(self):
        self.made, self.polls = {}, 0

    def create(self, requests):
        bid = f"msgbatch_{len(self.made)}"
        self.made[bid] = requests
        return NS(id=bid)

    def retrieve(self, bid):
        self.polls += 1
        status = "ended" if self.polls > 1 else "in_progress"
        return NS(processing_status=status, request_counts=NS(succeeded=0, errored=0, processing=1))

    def results(self, bid):
        for req in self.made[bid]:
            words = [ln[6:] for ln in req["params"]["messages"][0]["content"].splitlines() if ln.startswith("WORD: ")]
            if "idiot" in words:                                           # this request fails: sent again later
                yield NS(custom_id=req["custom_id"], result=NS(type="errored"))
                continue
            cheap = req["params"]["model"] == "claude-haiku-5-5"            # (Haiku is unsure of bitch)
            items = [{"word": w, "meanings": ["sexual"], "kind": {"box": "double", "penis": "clinical"}.get(w, "swear"),
                      "confidence": 60 if w == "bitch" and cheap else 95, "note": ""} for w in words]
            yield NS(custom_id=req["custom_id"], result=NS(type="succeeded", message=message(items)))


fake = NS(messages=NS(batches=FakeBatches(), create=None, count_tokens=lambda **k: NS(input_tokens=900)))
logs = []
C.time.sleep = lambda s: None
C.GROUP = 1                                                     # one word a request: only idiot's request fails
args = ["run", "--db", db, "--no-lists", "--model", "claude-haiku-5-5"]
assert C.main(args, client_factory=lambda: fake, log=logs.append, ask=lambda q: "n") == 1
assert not fake.messages.batches.made and "Nothing sent." in logs                 # asked first; "n" sends nothing
assert C.main(args, client_factory=lambda: fake, log=logs.append, ask=lambda q: "y") == 0
out, state, _ = C.paths(db)
got = C.read_results(out)
assert got["box"][:2] == ("double", 95) and got["penis"][0] == "clinical" and got["fuck"][0] == "swear"
assert got["fucking"] == ("swear", 95, [], "form of fuck", "claude-haiku-5-5")      # forms follow their word
assert got["bitches"][1] == 60 and got["box"][4] == "claude-haiku-5-5"
assert "idiot" not in got and not os.path.exists(state)
assert any("1 words got no answer" in m for m in logs) and any("1 to check by hand" in m for m in logs), logs
with open(out, encoding="utf-8") as f:
    lines = f.read().splitlines()
assert lines[0].startswith("# word") and lines[1].startswith("fuck\tswear\t95") and lines[1].endswith("\tclaude-haiku-5-5")

# the next run sends only what is left (idiot), keeping the earlier answers
fake.messages.batches.polls = 0
before = len(fake.messages.batches.made)
logs.clear()
C.main(args + ["--yes"], client_factory=lambda: fake, log=logs.append)
sent = fake.messages.batches.made[f"msgbatch_{before}"]
assert len(sent) == 1 and "WORD: idiot" in sent[0]["params"]["messages"][0]["content"]
assert C.read_results(out)["box"][0] == "double"

# --recheck: only the words answered below --review go again, to the stronger model, and their answers replace
before = len(fake.messages.batches.made)
fake.messages.batches.polls = 0
logs.clear()
C.main(["run", "--db", db, "--no-lists", "--recheck", "--yes"], client_factory=lambda: fake, log=logs.append)
sent = fake.messages.batches.made[f"msgbatch_{before}"]
assert [r["params"]["messages"][0]["content"].split("WORD: ")[1].split("\n")[0] for r in sent] == ["bitch"], sent
assert sent[0]["params"]["model"] == "claude-opus-5-5" and "1 to send again" in logs[0]
got = C.read_results(out)
assert got["bitch"][1:2] == (95,) and got["bitch"][4] == "claude-opus-5-5"
assert got["bitches"][1] == 95 and got["bitches"][4] == "claude-opus-5-5"            # its form follows
assert got["box"][4] == "claude-haiku-5-5"                                              # sure answers stay
logs.clear()
assert C.main(["status", "--db", db], log=logs.append) == 0 and "to check by hand" in logs[0]
assert any("claude-opus-5-5: 2 words, 0 below" in m for m in logs) and any("claude-haiku-5-5:" in m for m in logs), logs
assert C.main(["run", "--db", db, "--no-lists", "--recheck", "--yes"], client_factory=lambda: fake,
              log=logs.append) == 0 and "Nothing to send." in logs                     # all sure now
logs.clear()
assert C.main(["estimate", "--db", os.path.join(tmp, "none.db")], log=logs.append) == 1 and "No save" in logs[0]
logs.clear()
assert C.main(["estimate", "--db", db, "--no-lists"], log=logs.append) == 0
assert "1 to send" in logs[0] and "$" in logs[1]                                   # (only idiot is left)
print("classify tool OK")
