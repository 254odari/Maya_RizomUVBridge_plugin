"""Import settings panel (Maya edition)."""

import maya.cmds as cmds

from ...utils import addon_utils
from ..constants import IMPORT_FRAME


def build_import_settings_section(parent: str):
    """Build the import settings frame into ``parent``."""

    prefs = addon_utils.get_prefs()

    cmds.frameLayout(
        IMPORT_FRAME,
        label="Import Settings",
        collapsable=True,
        collapse=True,
        parent=parent,
        marginWidth=4,
        marginHeight=4,
    )
    cmds.columnLayout(
        "rizomImportInner",
        adjustableColumn=True,
        rowSpacing=4,
        parent=IMPORT_FRAME,
    )

    _checkbox_pair(
        ("delete_unmatched_uvmaps", "Remove UV Maps"),
        ("create_missing_uvmaps", "Add UV Maps"),
        prefs,
        parent="rizomImportInner",
    )

    _checkbox_pair(
        ("reveal_hidden", "Reveal Hidden"),
        ("replace_objects", "Replace Objects"),
        prefs,
        parent="rizomImportInner",
    )

    _checkbox_pair(
        ("mark_seams", "Mark Seams"),
        ("mark_sharp", "Mark Sharp"),
        prefs,
        parent="rizomImportInner",
    )

    cmds.setParent("..")
    cmds.setParent("..")


def _checkbox_pair(left, right, prefs, parent):
    """Two side-by-side checkboxes in a fixed-width row."""
    cmds.rowLayout(
        numberOfColumns=2,
        adjustableColumn=1,
        columnWidth2=(150, 150),
        columnAlign2=("left", "left"),
        columnAttach2=("both", "both"),
        parent=parent,
    )
    for attr, label in (left, right):
        cmds.checkBox(
            f"rizom_{attr}",
            label=label,
            value=bool(getattr(prefs, attr)),
            changeCommand=_bool_cb(attr),
        )
    cmds.setParent(parent)


def _bool_cb(attr: str):
    def _cb(value):
        addon_utils.set_pref(attr, bool(value))
    return _cb