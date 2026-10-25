"""Export settings panel (Maya edition).

Mirrors Blender's ``ExportSettingsPanel`` — including the ``action_settings``
sub-box that only appears when LiveLink is on and the export action isn't
plain ``EXPORT``.
"""

import maya.cmds as cmds

from ... import addon_constants
from ...utils import addon_utils
from ..constants import EXPORT_FRAME


def build_export_settings_section(parent: str):
    """Build the export settings frame into ``parent``."""

    prefs = addon_utils.get_prefs()

    cmds.frameLayout(
        EXPORT_FRAME,
        label="Export Settings",
        collapsable=True,
        collapse=True,
        parent=parent,
        marginWidth=4,
        marginHeight=4,
    )
    cmds.columnLayout(
        "rizomExportInner",
        adjustableColumn=True,
        rowSpacing=4,
        parent=EXPORT_FRAME,
    )

    # Action-specific box (mirrors Blender's ``action_settings``).
    if prefs.use_livelink and prefs.export_action != "EXPORT":
        _build_action_settings(prefs)

    _build_common_settings(prefs)

    cmds.setParent("..")
    cmds.setParent("..")


# ---------------------------------------------------------------------------
# Action-specific settings (Blender: ``action_settings``)
# ---------------------------------------------------------------------------

def _build_action_settings(prefs):
    """Mirrors Blender's ``action_settings`` box."""

    is_autoseams = prefs.export_action in addon_constants.AUTOSEAMS_ACTIONS.keys()

    cmds.frameLayout(
        "rizomActionSettingsFrame",
        label="Action Settings",
        collapsable=False,
        parent="rizomExportInner",
        marginWidth=4,
        marginHeight=4,
    )
    cmds.columnLayout(
        adjustableColumn=True,
        rowSpacing=4,
        parent="rizomActionSettingsFrame",
    )

    # Row: [ All UV Maps ] [ Reset UVs First ]  (Reset only shown for autoseams)
    cmds.rowLayout(
        numberOfColumns=2,
        adjustableColumn=1,
        columnWidth2=(150, 150),
        columnAlign2=("left", "left"),
        columnAttach2=("both", "both"),
        parent="rizomActionSettingsFrame",
    )
    # OBJ only supports one UV map, so hide the toggle for OBJ.
    if prefs.export_format != "OBJ":
        cmds.checkBox(
            "rizomTargetAllUvmaps",
            label="All UV Maps",
            value=bool(prefs.target_all_uvmaps),
            changeCommand=_bool_cb("target_all_uvmaps"),
        )
    if is_autoseams:
        cmds.checkBox(
            "rizomResetBefore",
            label="Reset UVs First",
            value=bool(prefs.reset_before),
            changeCommand=_bool_cb("reset_before"),
        )
    cmds.setParent("rizomActionSettingsFrame")

    if not is_autoseams:
        cmds.setParent("..")
        cmds.setParent("..")
        return

    # --- Autoseams-only rows ---

    cmds.rowLayout(
        numberOfColumns=3,
        adjustableColumn=1,
        columnWidth3=(120, 110, 110),
        columnAlign3=("left", "left", "left"),
        columnAttach3=("both", "both", "both"),
        parent="rizomActionSettingsFrame",
    )
    cmds.checkBox(
        "rizomCutHandles",
        label="Cut Handles",
        value=bool(prefs.cut_handles),
        changeCommand=_bool_cb("cut_handles"),
    )
    cmds.checkBox(
        "rizomLinkGaps",
        label="Link Gaps",
        value=bool(prefs.link_gaps),
        changeCommand=_bool_cb("link_gaps"),
    )
    cmds.checkBox(
        "rizomOpenCylinders",
        label="Open Cylinders",
        value=bool(prefs.open_cylinders),
        changeCommand=_bool_cb("open_cylinders"),
    )
    cmds.setParent("rizomActionSettingsFrame")

    _float_slider_row(
        attr="stretch_limiter",
        label="Stretch Limiter",
        parent="rizomActionSettingsFrame",
        min_value=0.0,
        max_value=0.99,
        step=0.01,
    )

    if prefs.export_action == "SHARP_EDGES":
        _int_slider_row(
            attr="sharp_angle",
            label="Sharp Angle",
            parent="rizomActionSettingsFrame",
            min_value=0,
            max_value=180,
        )
    elif prefs.export_action == "MOSAIC":
        _float_slider_row(
            attr="mosaic_force",
            label="Force",
            parent="rizomActionSettingsFrame",
            min_value=0.0,
            max_value=1.0,
            step=0.05,
        )
    elif prefs.export_action == "PELT":
        cmds.rowLayout(
            numberOfColumns=3,
            adjustableColumn=1,
            columnWidth3=(100, 100, 100),
            columnAlign3=("left", "left", "left"),
            columnAttach3=("both", "both", "both"),
            parent="rizomActionSettingsFrame",
        )
        for attr, label in (
            ("pelt_trunk", "Trunk"),
            ("pelt_branch", "Branch"),
            ("pelt_leaf", "Leaf"),
        ):
            cmds.checkBox(
                f"rizom_{attr}",
                label=label,
                value=bool(getattr(prefs, attr)),
                changeCommand=_bool_cb(attr),
            )
        cmds.setParent("rizomActionSettingsFrame")

    cmds.setParent("..")
    cmds.setParent("..")


# ---------------------------------------------------------------------------
# Common export settings (Blender: ``draw``)
# ---------------------------------------------------------------------------

def _build_common_settings(prefs):
    """Mirrors the body of Blender's ``draw`` beyond ``action_settings``."""

    cmds.columnLayout(
        adjustableColumn=True, rowSpacing=4, parent="rizomExportInner"
    )

    _checkbox_pair(
        ("exclude_clones", "Exclude Clones"),
        ("confirm_export", "Confirm Export"),
        prefs,
        parent="rizomExportInner",
    )

    _checkbox_pair(
        ("triangulate", "Triangulate"),
        ("fix_object_names", "Fix Names"),
        prefs,
        parent="rizomExportInner",
    )

    if prefs.use_livelink:
        _checkbox_pair(
            ("normals", "Normals"),
            ("weld_uvs", "Weld UVs"),
            prefs,
            parent="rizomExportInner",
        )

    if prefs.export_format != "USD":
        cmds.rowLayout(
            numberOfColumns=2,
            adjustableColumn=1,
            columnWidth2=(150, 150),
            columnAlign2=("left", "left"),
            columnAttach2=("both", "both"),
            parent="rizomExportInner",
        )
        cmds.checkBox(
            "rizomApplyModifiers",
            label="Apply Modifiers",
            value=bool(prefs.apply_modifiers),
            changeCommand=_bool_cb("apply_modifiers"),
        )
        if prefs.use_livelink:
            cmds.checkBox(
                "rizomExportTexture",
                label="Export Texture",
                value=bool(prefs.export_texture),
                changeCommand=_on_export_texture_toggle,
            )
        cmds.setParent("rizomExportInner")

    cmds.setParent("..")


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

def _bool_cb(attr: str):
    def _cb(value):
        addon_utils.set_pref(attr, bool(value))
    return _cb


def _on_export_texture_toggle(value):
    """Persist, then rebuild the window so the texture box appears."""
    addon_utils.set_pref("export_texture", bool(value))
    # Lazy import — ui/__init__.py may not be fully initialized when this
    # runs during the very first window build.
    from .. import refresh
    refresh()


# ---------------------------------------------------------------------------
# Small widget helpers
# ---------------------------------------------------------------------------

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


def _float_slider_row(attr, label, parent, min_value, max_value, step=0.01):
    """Float slider + numeric readout; the two stay in sync."""
    cmds.rowLayout(
        numberOfColumns=3,
        adjustableColumn=2,
        columnWidth3=(100, 140, 60),
        columnAlign3=("left", "left", "left"),
        columnAttach3=("both", "both", "both"),
        parent=parent,
    )
    cmds.text(label=label)

    slider_name = f"rizom_{attr}_slider"
    field_name = f"rizom_{attr}_field"
    initial = float(getattr(addon_utils.get_prefs(), attr))

    def _on_change(value):
        v = float(value)
        addon_utils.set_pref(attr, v)
        # Keep the paired numeric field in sync.
        if cmds.floatField(field_name, exists=True):
            cmds.floatField(field_name, edit=True, value=v)

    def _on_field_change(value):
        v = float(value)
        addon_utils.set_pref(attr, v)
        if cmds.floatSlider(slider_name, exists=True):
            cmds.floatSlider(slider_name, edit=True, value=v)

    cmds.floatSlider(
        slider_name,
        minValue=min_value,
        maxValue=max_value,
        step=step,
        value=initial,
        changeCommand=_on_change,
        dragCommand=_on_change,
    )
    cmds.floatField(
        field_name,
        value=initial,
        minValue=min_value,
        maxValue=max_value,
        step=step,
        changeCommand=_on_field_change,
    )
    cmds.setParent(parent)


def _int_slider_row(attr, label, parent, min_value, max_value):
    """Int slider + numeric readout; the two stay in sync."""
    cmds.rowLayout(
        numberOfColumns=3,
        adjustableColumn=2,
        columnWidth3=(100, 140, 60),
        columnAlign3=("left", "left", "left"),
        columnAttach3=("both", "both", "both"),
        parent=parent,
    )
    cmds.text(label=label)

    slider_name = f"rizom_{attr}_slider"
    field_name = f"rizom_{attr}_field"
    initial = int(getattr(addon_utils.get_prefs(), attr))

    def _on_change(value):
        v = int(value)
        addon_utils.set_pref(attr, v)
        if cmds.intField(field_name, exists=True):
            cmds.intField(field_name, edit=True, value=v)

    def _on_field_change(value):
        v = int(value)
        addon_utils.set_pref(attr, v)
        if cmds.intSlider(slider_name, exists=True):
            cmds.intSlider(slider_name, edit=True, value=v)

    cmds.intSlider(
        slider_name,
        minValue=min_value,
        maxValue=max_value,
        value=initial,
        changeCommand=_on_change,
        dragCommand=_on_change,
    )
    cmds.intField(
        field_name,
        value=initial,
        minValue=min_value,
        maxValue=max_value,
        changeCommand=_on_field_change,
    )
    cmds.setParent(parent)