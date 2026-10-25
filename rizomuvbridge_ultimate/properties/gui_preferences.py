"""Preferences for handling addon gui configuration (Maya)."""

import logging

from ._pref_base import EnumPref, StringPref

logger = logging.getLogger(__name__)


# Maya has no "sidebar tab" registry like Blender. The dock location controls
# whether we build the window docked (via `cmds.dockControl`) or as a floating
# window. `addon_tab_name` becomes the window title suffix — kept for
# compatibility with the Blender-style prefs panel, but has no functional role.
def _tab_location_update(self, value):
    logger.info(
        "Dock location changed to '%s'. Reopen the bridge window to apply.", value
    )


def _addon_tab_update(self, value):
    if not value:
        # Can't rebind via descriptor from within the update itself here;
        # the UI layer re-validates. Just log.
        logger.warning("Empty tab name; ignoring.")


class GuiPreferences:
    """Preferences for handling addon gui configuration."""

    dock_location = EnumPref(
        "dock_location",
        items=(("SIDE", "Side Panel", ""), ("HEADER", "Header", "")),
        default="SIDE",
        update=_tab_location_update,
    )

    addon_tab_name = StringPref(
        "addon_tab_name",
        default="RizomUV",
        update=_addon_tab_update,
    )