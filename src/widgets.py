"""The program's own widgets live in a module each by kind; this one only re-measures them all after a font change.

    smears.py    censored words drawn smeared (smear_items, Unsmear, smeared_label, TreeSmears)
    popups.py    Toast, Tooltip
    buttons.py   RoundButton, TierRow, TierChip, LinkButton, DevBubble
    menus.py     DropMenu, ChoiceButton, HeaderMenus, TabBar, close_popups, watch_focus
    drawer.py    the definitions pane (DefinitionDrawer, fill_definitions, word_at)
    cards.py     WordCard, DuelCards, AnchorLadder, EmptyCard, ShapeCard, FileList
    dialogs.py   StyledDialog, dialog_open

After a shared Font object is resized, call refresh_widgets(window) so they re-measure.
"""
import tkinter as tk

from dialogs import StyledDialog
from drawer import definition_tags


def refresh_widgets(widget):
    """Re-measure every canvas widget of ours (RoundButton, WordCard, AnchorLadder, TabBar, the chart...) under
    `widget` after shared fonts were resized; a definitions pane's italics follow, and an open dialog (StyledDialog)
    then re-wraps and resizes itself."""
    for child in widget.winfo_children():
        if isinstance(child, tk.Canvas) and callable(getattr(child, "refresh", None)):
            child.refresh()                  # our canvas widgets (here and in ui_chart.py) all have refresh()
        else:
            if isinstance(child, tk.Text) and getattr(child, "_tag_body", None) is not None:
                definition_tags(child, child._tag_body)       # (a definitions pane's italics: a copy of the size)
            refresh_widgets(child)
            dialog = getattr(child, "dialog", None)
            if isinstance(dialog, StyledDialog):
                dialog.rescale()
