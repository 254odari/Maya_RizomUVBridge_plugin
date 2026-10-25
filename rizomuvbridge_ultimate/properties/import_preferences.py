"""Preferences for handling import setting configuration (Maya)."""

from ._pref_base import BoolPref


class ImportPreferences:
    """Preferences for handling import setting configuration."""

    replace_objects = BoolPref(
        "replace_objects",
        default=False,
        # description="Replace scene objects with imported ones."
    )

    create_missing_uvmaps = BoolPref("create_missing_uvmaps", default=False)

    delete_unmatched_uvmaps = BoolPref("delete_unmatched_uvmaps", default=False)

    reveal_hidden = BoolPref("reveal_hidden", default=False)

    mark_seams = BoolPref("mark_seams", default=False)

    mark_sharp = BoolPref("mark_sharp", default=False)