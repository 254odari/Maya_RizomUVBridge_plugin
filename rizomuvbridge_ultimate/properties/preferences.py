"""Custom addon preferences (Maya edition).

Blender's `AddonPreferences` class does not exist in Maya. Instead:

- Each `*Preferences` mixin declares typed descriptors that read/write
  `cmds.optionVar`.
- `RizomBridgePreferences` composes every mixin.
- ``get_prefs()`` returns a module-level singleton so the rest of the bridge
  can call `get_prefs().export_format` etc. without any plumbing.
"""

import logging
from typing import Optional

from .. import addon_constants
from .autoseams_preferences import AutoseamsPreferences
from .config_preferences import ConfigPreferences
from .export_preferences import ExportPreferences
from .gui_preferences import GuiPreferences
from .import_preferences import ImportPreferences
from .rizom_preferences import RizomPreferences

logger = logging.getLogger(__name__)


class RizomBridgePreferences(
    ConfigPreferences,
    GuiPreferences,
    ExportPreferences,
    ImportPreferences,
    RizomPreferences,
    AutoseamsPreferences,
):
    """Composed preference block.

    On Blender this subclassed ``bpy.types.AddonPreferences`` and was
    registered with ``bpy.utils.register_class``. In Maya the class is
    registered by construction — ``get_prefs()`` caches a single instance.
    """

    # Kept for parity with the Blender ``bl_idname``.
    bl_idname = addon_constants.PACKAGE

    # ---- API parity helpers ------------------------------------------------

    def items(self, group: Optional[str] = None):
        """Return the current values of one preference group (or all).

        Args:
            group: Optional group name, one of
                   "config" | "gui" | "export" | "import" | "rizom" | "autoseams".
                   If None, returns all groups combined.

        """
        groups = {
            "config": ConfigPreferences,
            "gui": GuiPreferences,
            "export": ExportPreferences,
            "import": ImportPreferences,
            "rizom": RizomPreferences,
            "autoseams": AutoseamsPreferences,
        }

        if group is not None and group not in groups:
            raise ValueError(f"Unknown preference group: {group}")

        selected = groups.values() if group is None else [groups[group]]

        result = {}
        for cls in selected:
            for attr_name, attr in vars(cls).items():
                if attr_name.startswith("_"):
                    continue
                if hasattr(attr, "name") and hasattr(attr, "_key"):
                    result[attr_name] = getattr(self, attr_name)
        return result

    def reset(self):
        """Reset every preference to its default."""
        import maya.cmds as cmds

        for cls in (
            ConfigPreferences,
            GuiPreferences,
            ExportPreferences,
            ImportPreferences,
            RizomPreferences,
            AutoseamsPreferences,
        ):
            for attr_name, attr in vars(cls).items():
                if attr_name.startswith("_"):
                    continue
                if hasattr(attr, "name") and hasattr(attr, "_key"):
                    if cmds.optionVar(exists=attr._key):
                        cmds.optionVar(remove=attr._key)

    def __repr__(self):
        return f"RizomBridgePreferences({self.items()!r})"


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_prefs_instance: Optional[RizomBridgePreferences] = None


def get_prefs() -> RizomBridgePreferences:
    """Return the module-level singleton preferences instance.

    Matches the Blender ``addon_utils.get_prefs()`` call site so nothing
    in the rest of the bridge needs to change.
    """
    global _prefs_instance
    if _prefs_instance is None:
        _prefs_instance = RizomBridgePreferences()
    return _prefs_instance