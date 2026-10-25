"""Preferences for the Autoseams actions (Maya)."""

from ._pref_base import BoolPref


class AutoseamsPreferences:
    """Preferences for the Autoseams actions."""

    reset_before = BoolPref(
        "autoseams_reset_before",
        default=True,
        # Description: "Reset the UV map before running autoseams"
    )