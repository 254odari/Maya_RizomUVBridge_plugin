"""UI module (Maya edition).

Maya has no declarative panel system; each section is built imperatively
into a parent layout. The ``register(plugin)`` entry point is called by the
plugin's ``initializePlugin``. It:

* registers two commands — ``rizomShowWindow`` and ``rizomHideWindow``
* builds the window in a hidden state so the shelf button has something
  to toggle.

If the window build fails (e.g. a widget name collision from a prior session,
or an error inside one of the panel builders), the exception is logged but
*not* propagated. The two commands are still registered, so the user can
recover by calling ``cmds.rizomShowWindow()`` again — this time with a clean
window — rather than having to restart Maya.
"""

import logging

import maya.cmds as cmds
import maya.OpenMaya as om1              # API 1.0: MSyntax
import maya.OpenMayaMPx as ompx          # API 1.0: MPxCommand

from ..properties.preferences import get_prefs
from . import constants
from .panels.export_settings_panel import build_export_settings_section
from .panels.import_settings_panel import build_import_settings_section
from .panels.rizom_bridge_panel import build_bridge_section

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register(plugin):
    """Register the UI's commands and build the window (hidden).

    Commands are registered first so a failure in the window build does not
    leave the plugin without a way to recover.
    """
    plugin.registerCommand(
        "rizomShowWindow", _show_creator, _no_args_syntax
    )
    plugin.registerCommand(
        "rizomHideWindow", _hide_creator, _no_args_syntax
    )

    try:
        _ensure_window_built()
    except Exception as e:
        # The commands are registered — the user can still call
        # ``cmds.rizomShowWindow()`` to retry with a clean slate.
        logger.error(
            f"RizomUV Bridge window build failed: {e}", exc_info=True
        )
        return

    logger.info("RizomUV Bridge UI registered.")


def unregister(plugin):
    """Deregister the UI."""
    try:
        _destroy_window()
    except Exception as e:
        logger.warning(f"Window teardown raised: {e}", exc_info=True)

    for cmd in ("rizomShowWindow", "rizomHideWindow"):
        try:
            plugin.deregisterCommand(cmd)
        except RuntimeError:
            # Already gone (plugin reload). Safe to ignore.
            pass

    logger.info("RizomUV Bridge UI unregistered.")


# ---------------------------------------------------------------------------
# MPxCommand wrappers
# ---------------------------------------------------------------------------

def _no_args_syntax():
    """API 1.0 MSyntax — must match the ompx.MPxCommand base class."""
    return om1.MSyntax()


class _ShowWindowCommand(ompx.MPxCommand):
    COMMAND_NAME = "rizomShowWindow"

    def doIt(self, args):
        show_window()


class _HideWindowCommand(ompx.MPxCommand):
    COMMAND_NAME = "rizomHideWindow"

    def doIt(self, args):
        hide_window()


def _show_creator():
    return _ShowWindowCommand()


def _hide_creator():
    return _HideWindowCommand()


# ---------------------------------------------------------------------------
# Window lifecycle
# ---------------------------------------------------------------------------

def _ensure_window_built():
    """Build the window widgets (invisible) if they don't exist yet.

    Safe to call multiple times — checks for the window's existence first.
    """
    if cmds.window(constants.WINDOW_NAME, exists=True):
        return
    _build_window()


def show_window():
    """Dock or float the bridge window per the ``dock_location`` pref."""
    prefs = get_prefs()

    try:
        _ensure_window_built()
    except Exception as e:
        cmds.warning(f"Could not build RizomUV Bridge window: {e}")
        logger.error("Window build failed during show.", exc_info=True)
        return

    # Remove any existing dock control before creating a new one.
    if cmds.dockControl(constants.DOCK_CONTROL_NAME, exists=True):
        cmds.deleteUI(constants.DOCK_CONTROL_NAME)

    area = "top" if prefs.dock_location == "HEADER" else "right"
    cmds.dockControl(
        constants.DOCK_CONTROL_NAME,
        area=area,
        content=constants.WINDOW_NAME,
        label=f"RizomUV Bridge — {prefs.addon_tab_name}",
        allowedArea="all",
        sizeable=True,
        width=340,
    )


def hide_window():
    """Close the dock or window."""
    if cmds.dockControl(constants.DOCK_CONTROL_NAME, exists=True):
        cmds.deleteUI(constants.DOCK_CONTROL_NAME)
    elif cmds.window(constants.WINDOW_NAME, exists=True):
        cmds.deleteUI(constants.WINDOW_NAME)


def refresh():
    """Rebuild the window contents (e.g. after a tab or pref change).

    Preserves the visible/hidden state: if the window was docked before,
    it stays docked after.
    """
    was_visible = (
        cmds.dockControl(constants.DOCK_CONTROL_NAME, exists=True)
        or cmds.window(constants.WINDOW_NAME, exists=True)
    )

    _destroy_window()

    try:
        _ensure_window_built()
    except Exception as e:
        cmds.warning(f"Could not rebuild RizomUV Bridge window: {e}")
        logger.error("Window rebuild failed during refresh.", exc_info=True)
        return

    if was_visible:
        show_window()


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _build_window():
    """Build the top-level window and all panel sections."""
    prefs = get_prefs()

    cmds.window(
        constants.WINDOW_NAME,
        title=f"RizomUV Bridge — {prefs.addon_tab_name}",
        widthHeight=(340, 560),
        sizeable=True,
        menuBar=False,
        minimizeButton=True,
        maximizeButton=False,
    )
    cmds.scrollLayout(
        "rizomBridgeScroll",
        childResizable=True,
        horizontalScrollBarThickness=0,
    )
    cmds.columnLayout(
        "rizomBridgeColumn",
        adjustableColumn=True,
        rowSpacing=6,
        columnAttach=("both", 6),
    )

    build_bridge_section("rizomBridgeColumn")
    build_export_settings_section("rizomBridgeColumn")
    build_import_settings_section("rizomBridgeColumn")


def _destroy_window():
    """Delete the dock control (if any) and the window itself."""
    if cmds.dockControl(constants.DOCK_CONTROL_NAME, exists=True):
        cmds.deleteUI(constants.DOCK_CONTROL_NAME)
    if cmds.window(constants.WINDOW_NAME, exists=True):
        cmds.deleteUI(constants.WINDOW_NAME)