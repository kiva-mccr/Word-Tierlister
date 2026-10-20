import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""ST-6: how words are dealt. The store (kinds, obscene words, the words left out, Most common first), the smear
on the word card and the duel cards (un-smearing under the pointer), the masked text elsewhere, the settings
page and the first start's three steps."""
import os, tempfile, time, types
os.environ["HOME"] = tempfile.mkdtemp()
import tkinter as tk
import tierlist as T
from fonts import font
from constants import mask_word

assert mask_word("bastard") == "b•••••d" and mask_word("ok") == "••" and mask_word("shit") == "s••t"

# ---- the store ---------------------------------------------------------------------------------------------
WORDS = ["bastard", "table", "serendipity", "luminous", "gristle", "moist", "bureaucracy", "shit", "run", "quickly",
         "of"] + [f"w{i:04d}" for i in range(200)]
s = T.Store(os.path.join(tempfile.mkdtemp(), "deal.db"))
s.insert_words(WORDS)
s.set_kinds([(w, 1) for w in WORDS] + [("run", 3), ("luminous", 4), ("moist", 4), ("quickly", 8), ("of", 16)])
s.set_obscene(["bastard", "shit", "notinthelist"])
assert s.obscene_words() == {"bastard", "shit"}
assert s.deal_settings() == {"kinds": 31, "obscene": True, "censor": False}
c = s.kind_counts()
assert c == {"noun": len(WORDS) - 6, "verb": 1, "adj": 2, "adv": 1, "other": 1, "obscene": 2}, c   # (run: noun + verb)
s.set_deal(kinds=4, obscene=False)                                   # adjectives only
dealt = [r[0] for r in s.db.execute("SELECT word FROM words WHERE out=0")]
assert sorted(dealt) == ["luminous", "moist"] and s.next_unplaced()["word"] in dealt and s.left_out() == len(WORDS) - 2
s.set_deal(kinds=0, obscene=True)                                    # "untick the rest to sort only obscene words"
assert s.next_unplaced()["word"] in ("bastard", "shit")
s.place("bastard", 2); s.place("shit", 3)
assert s.next_unplaced() is None and s.get_word("table")["tier"] is None      # left out, never deleted
s.set_deal(kinds=31, obscene=True)
assert s.next_unplaced() is not None and s.left_out() == 0
s.add_word("zorpish"); assert s.get_word("zorpish")["out"] == 0               # (UI-51: an added word is dealt)
# Most common first: strictly by rank, no randomness
s.reshuffle(shape="rank")
order = [r[0] for r in s.db.execute("SELECT word FROM words WHERE tier IS NULL ORDER BY skips, qkey LIMIT 5")]
assert order == [w for w in WORDS if w not in ("bastard", "shit")][:5], order
assert s.queue_settings()["shape"] == "rank"
s.reshuffle(shape="exp")
# Browse's Show: placed words of a kind, and the obscene ones
s.place("run", 1); s.place("table", 1)
assert [r["word"] for r in s.list_words("", "Verbs")[0]] == ["run"]
assert {r["word"] for r in s.list_words("", "Obscene words")[0]} == {"bastard", "shit"}
assert {r["word"] for r in s.list_words("", "Nouns")[0]} == {"run", "table", "bastard", "shit"}
assert not s.censored("bastard")
s.set_censor(True)
assert s.censored("bastard") and not s.censored("table") and not s.censored("")

# ---- the window ----------------------------------------------------------------------------------------------
s.set_anchors(["serendipity", "luminous", "table", "bureaucracy", "gristle", "moist"])
s.unplace("shit")                                                    # (comes up next: unplace puts it in front)
root = tk.Tk(); root.geometry("1100x760+0+0")
app = T.App(root, s, T.Definitions(s))


def pump(n=6):
    for _ in range(n):
        root.update(); time.sleep(0.02)


pump(12)
card = app.word_card
assert app.cur_word == "shit" and card.censored
assert card.find_withtag("smear") and card.itemcget("word", "state") == "hidden"   # the smear, not the letters
assert app.shown("shit") == "s••t" and app.shown("table") == "table"
# the pointer over the word un-smears it, easing; away again, it smears again
app.anim.reduce_motion = False
x0, y0, x1, y1 = card.bbox("smear")
card.event_generate("<Motion>", x=(x0 + x1) // 2, y=(y0 + y1) // 2); pump(2)
assert 0 < card.smear.clear < 1, card.smear.clear                                # on its way
app.anim.finish_all(); pump(1)
assert card.smear.clear == 1 and card.itemcget("word", "state") != "hidden" and not card.find_withtag("smear")
card.event_generate("<Motion>", x=3, y=3); app.anim.finish_all(); pump(1)        # (the card's corner: off the word)
assert card.smear.clear == 0 and card.find_withtag("smear") and card.itemcget("word", "state") == "hidden"
# placing it: the next word is not censored; the outgoing one leaves as its smear, never as readable text
app.place_word(2); pump(1)
assert not card.censored and card.itemcget("word", "state") != "hidden" and not card.find_withtag("smear")
assert card.find_withtag("oldsmear") and card.itemcget("oldword", "state") == "hidden"
app.anim.finish_all(); pump(2)
assert app.toast.cget("text") != "" and "shit" not in app.toast.cget("text")
# typing a word on the card (UI-51) is never smeared, and the word comes back as it was
s.unplace("shit"); app.refresh(); pump(2); assert card.censored
app.start_lookup(); assert not card.find_withtag("smear")
app.on_key(types.SimpleNamespace(keysym="Escape", char="", time=None, state=0)); pump(1)
assert card.censored and card.find_withtag("smear")
# the duel cards: smeared until hovered
app.mode_var.set("refine"); app.on_mode_change(); pump(4)
root.event_generate("<Motion>", warp=True, x=2, y=2); pump(2)       # (a pointer resting on a card would un-smear it)
app.duel.show("bastard", "table", censor=(True, False)); pump(2)
left, right = app.duel.left, app.duel.right
assert left.find_withtag("smear") and left.itemcget("label", "state") == "hidden" and not right.find_withtag("smear")
left.event_generate("<Enter>"); app.anim.finish_all(); pump(1)
assert left.smear.clear == 1 and left.itemcget("label", "state") != "hidden"
left.event_generate("<Leave>"); app.anim.finish_all(); pump(1)
assert left.smear.clear == 0 and left.find_withtag("smear")
app.duel.show("table", "moist"); pump(1); assert not left.find_withtag("smear") and left.itemcget("label", "state") != "hidden"
app.mode_var.set("place"); app.on_mode_change(); pump(4)
# Browse: the list masks it, its definition pane shows it whole; Show lists a kind
app.open_browser(); pump(6); bw = app.browsers[0]
assert bw.tree.item("bastard", "values")[1] == "b•••••d" and bw.tree.item("table", "values")[1] == "table"
bw.tree.selection_set("bastard"); pump(3)
assert bw.def_text.get("1.0", "2.0").strip() == "bastard"
bw.filter_var.set("Verbs"); bw.reload(); pump(4); assert list(bw.tree.get_children()) == ["run"]
bw.close(); pump(2)

# ---- the settings page --------------------------------------------------------------------------------------
font_px = font("body").measure("n")
d = app.edit_dealing(); pump(4)
assert list(d.buttons) == ["Cancel", "Apply"] and set(d.kind_ticks) == {"Nouns", "Verbs", "Adjectives", "Adverbs", "Other", "Obscene words"}
# what each kind holds is a hover note (over its tick box and its count), wrapped
tip = d.kind_tips["Other"][0]
assert "pronouns" in tip.text_fn(None) and "Nouns: names" in d.kind_tips["Nouns"][1].text_fn(None)
tip.show_at(types.SimpleNamespace(x_root=200, y_root=200, x=5, y=5)); pump(2)
assert "pronouns" in tip.text and tip._canvas.winfo_reqwidth() < font_px * 50
tip.hide()
assert "Point at a kind" in " ".join(str(w.cget("text")) for w in d.sections["kinds"].winfo_children() if w.winfo_class() == "TLabel")
assert d.censor_v.get()
d.censor_v.set(False); d.buttons["Apply"].invoke(); pump(4)                    # the censor tick alone: at once, no shuffle
assert not d.alive() and not s.deal_settings()["censor"] and not card.censored
d = app.edit_dealing(); pump(4)
for v in d.kind_vs.values():
    v.set(False)
d.obscene_v.set(False); d.buttons["Apply"].invoke(); pump(2)
assert d.alive() and "at least one" in str(d.status.cget("text"))
d.kind_vs["adj"].set(True); d.buttons["Apply"].invoke(); pump(2)
t_end = time.time() + 20
while d.alive() and time.time() < t_end:
    pump(2)
assert not d.alive() and not app.busy and s.deal_settings()["kinds"] == 4 and not s.deal_settings()["obscene"]
assert app.cur_word in ("luminous", "moist") or app.cur_word is None
assert app.toast.cget("text") == "Words dealt"
# everything chosen is placed: the empty card says how many are left out
for w in ("luminous", "moist"):
    if s.get_word(w)["tier"] is None:
        s.place(w, 1)
app.refresh(); pump(2)
assert app.cur_word is None and app.place_empty.title == "Every word you chose is placed" and "left out" in app.place_empty.text
s.set_deal(kinds=31, obscene=True); app.refresh(); pump(2)

# ---- the first start: three steps, then the anchors ----------------------------------------------------------
app.on_close()
s2 = T.Store(os.path.join(tempfile.mkdtemp(), "first.db")); s2.insert_words(WORDS)
root = tk.Tk(); root.geometry("1100x760+0+0")
app = T.App(root, s2, T.Definitions(s2), ask_dealing=True)
asked = []
app.edit_anchors = lambda: asked.append("anchors")
pump(30)
d = app._dealing
assert d.first and d.alive() and d.step == 0
assert "Step 1 of 3" in [str(w.cget("text")) for w in d.dlg.button_row.winfo_children() if w.winfo_class() == "TLabel"]
assert list(d.buttons) == ["Next"] and not asked                                  # the anchors wait for it
d.buttons["Next"].invoke(); pump(2); assert d.step == 1 and list(d.buttons) == ["Back", "Next"]
for v in d.kind_vs.values():
    v.set(False)
d.obscene_v.set(False); d.buttons["Next"].invoke(); pump(2)
assert d.step == 1 and "at least one" in str(d.status.cget("text"))
d.kind_vs["noun"].set(True); d.buttons["Back"].invoke(); pump(2); assert d.step == 0
d.order_btns["rank"].invoke(); d.buttons["Next"].invoke(); d.buttons["Next"].invoke(); pump(2)
assert d.step == 2 and list(d.buttons) == ["Back", "Done"]
d.censor_v.set(True); d.buttons["Done"].invoke(); pump(2)
t_end = time.time() + 20
while d.alive() and time.time() < t_end:
    pump(2)
assert not d.alive() and s2.get_meta("dealt_asked") == "1" and s2.queue_settings()["shape"] == "rank"
assert s2.deal_settings() == {"kinds": 1, "obscene": False, "censor": True} and asked == ["anchors"]
app.on_close()
# closing the first start keeps the defaults and is not asked again
s3 = T.Store(os.path.join(tempfile.mkdtemp(), "skip.db")); s3.insert_words(WORDS)
root = tk.Tk()
app = T.App(root, s3, T.Definitions(s3), ask_dealing=True)
app.edit_anchors = lambda: asked.append("anchors 2")
pump(30)
app._dealing.dlg.win.event_generate("<Escape>"); pump(2)
assert not app._dealing.alive() and s3.get_meta("dealt_asked") == "1" and asked[-1] == "anchors 2"
assert s3.deal_settings() == {"kinds": 31, "obscene": True, "censor": False}
app.on_close()
print("DEALING OK")
