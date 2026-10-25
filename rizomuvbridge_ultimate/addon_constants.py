"""Global constants for the RizomUV Bridge (Maya edition).

This module has no imports beyond the standard library, so it is safe to
import from any layer of the package (including preference descriptors and
low-level file-access helpers) without triggering circular dependencies.
"""

from pathlib import Path
from typing import cast

# ---------------------------------------------------------------------------
# Package identity
# ---------------------------------------------------------------------------

# ``__package__`` is ``"rizomuvbridge_ultimate"`` when imported as the plugin
# package, or ``""`` when the module is executed as a top-level script. The
# cast keeps type checkers happy about the resulting ``str``.
PACKAGE = cast(str, __package__)


# ---------------------------------------------------------------------------
# Filesystem layout
# ---------------------------------------------------------------------------

_PKG_DIR = Path(__file__).parent

# The remote-control script RizomUV watches when using the legacy transport.
# RizomUV loads this file with ``-cfi <path>`` and re-executes it whenever
# the file's mtime changes. Do not move or rename it without updating
# ``rizom_utils.trigger_rizom_update``.
RIZOM_SCRIPT = _PKG_DIR / "rizom_script.py"

# The vendored RizomUVLink Python API. In the Blender addon this was
# expected to sit next to the RizomUV executable; the Maya port keeps it
# inside the package so multiple installations cannot collide.
RIZOMUV_LINK_PACKAGE = str(_PKG_DIR / "lib" / "RizomUVLink")


# ---------------------------------------------------------------------------
# Name sanitisation rules
# ---------------------------------------------------------------------------
#
# RizomUV is stricter than either Blender or Maya about what characters are
# allowed in UV set and object names. These tables drive the "fix names"
# feature: every key is replaced by its value when a name is sanitised.
#
# The ordering matters for multi-character sequences. Python 3.7+ dicts
# preserve insertion order, so ``"___dot___"`` is processed before ``"."``
# when iterating, which is what we want.

# UV set names in RizomUV must not contain dots or forward slashes. The
# ``___dot___`` sentinel is a convention some exporters use to represent a
# literal dot in a name; we restore it to an underscore.
BANNED_UVMAP_SUBSTRINGS = {
    "___dot___": "_",
    ".": "_",
}

# Object names in exported files. The set is identical across OBJ, FBX and
# USD because the bridge normalises before deciding the target format, so
# one name that works for all three is the safest policy.
BANNED_USD_SUBSTRINGS = {".", "/"}
BANNED_OBJ_SUBSTRINGS = {".", "/"}
BANNED_FBX_SUBSTRINGS = {".", "/"}


# ---------------------------------------------------------------------------
# Action tables (id, label, description) — consumed by UI + operators
# ---------------------------------------------------------------------------

AUTOSEAMS_ACTIONS = {
    "SHARP_EDGES": (
        "SHARP_EDGES",
        "Autoseams - Sharp Edges",
        "Unwrap using the Sharp Edges Autoseams algorithm",
    ),
    "MOSAIC": (
        "MOSAIC",
        "Autoseams - Mosaic",
        "Unwrap using the Mosaic Autoseams algorithm",
    ),
    "PELT": (
        "PELT",
        "Autoseams - Pelt",
        "Unwrap using the Pelt Autoseams algorithm",
    ),
    "BOX": (
        "BOX",
        "Autoseams - Box",
        "Unwrap using the Box Autoseams algorithm",
    ),
}

ACTIONS = {
    "EXPORT": (
        "EXPORT",
        "Export UVs",
        "Export existing UV data with no changes",
    ),
    "USE_SEAMS": (
        "USE_SEAMS",
        "Unwrap Seams",
        "Use seams to unwrap the UVs inside Maya before sending to RizomUV",
    ),
    "RESET_UVS": (
        "RESET_UVS",
        "Reset UVs",
        "Reset UVs (weld all seams)",
    ),
    "CLOSE": (
        "CLOSE",
        "Close Rizom",
        "Close RizomUV",
    ),
    "APPLY_RIZOM_SETTINGS": (
        "APPLY_RIZOM_SETTINGS",
        "Apply Rizom Settings",
        "Overwrite RizomUV preferences with those set in the bridge UI",
    ),
    # Flatten the autoseams entries into the main table so callers can
    # iterate a single dict when building menus.
    **AUTOSEAMS_ACTIONS,
}


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------

def action_items():
    """Return ``ACTIONS`` values as an ordered tuple.

    Convenience for UI code that iterates without needing the keys.
    """
    return tuple(ACTIONS.values())


def autoseams_action_keys():
    """Return the set of action identifiers that belong to autoseams.

    Used by the export-settings panel to decide whether to display the
    autoseams-specific parameter box.
    """
    return set(AUTOSEAMS_ACTIONS.keys())