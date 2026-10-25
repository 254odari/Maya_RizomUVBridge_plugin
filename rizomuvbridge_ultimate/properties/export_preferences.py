"""Preferences for handling export setting configuration (Maya)."""

from .. import addon_constants
from ..utils.addon_utils import export_formats
from ._pref_base import BoolPref, EnumPref


_AXIS_ITEMS = (
    ("X", "X Axis", ""),
    ("Y", "Y Axis", ""),
    ("Z", "Z Axis", ""),
    ("NEGATIVE_X", "-X Axis", ""),
    ("NEGATIVE_Y", "-Y Axis", ""),
    ("NEGATIVE_Z", "-Z Axis", ""),
)


class ExportPreferences:
    """Preferences for handling export setting configuration."""

    export_texture = BoolPref(
        "export_texture",
        default=False,
        # description="Export a user-defined texture file into RizomUV"
    )

    normals = BoolPref("normals", default=True)

    exclude_clones = BoolPref("exclude_clones", default=True)

    confirm_export = BoolPref("confirm_export", default=False)

    export_format = EnumPref(
        "export_format",
        items=export_formats(),
        default="FBX",
    )

    fix_object_names = BoolPref("fix_object_names", default=True)

    apply_modifiers = BoolPref("apply_modifiers", default=False)

    triangulate = BoolPref("triangulate", default=False)

    target_all_uvmaps = BoolPref("target_all_uvmaps", default=False)

    weld_uvs = BoolPref("weld_uvs", default=True)

    export_action = EnumPref(
        "export_action",
        items=(
            addon_constants.ACTIONS["EXPORT"],
            addon_constants.ACTIONS["USE_SEAMS"],
            addon_constants.ACTIONS["RESET_UVS"],
        ),
        default="EXPORT",
    )

    up_axis = EnumPref(
        "up_axis",
        items=_AXIS_ITEMS,
        default="Z",
    )

    forward_axis = EnumPref(
        "forward_axis",
        items=_AXIS_ITEMS,
        default="NEGATIVE_Y",
    )