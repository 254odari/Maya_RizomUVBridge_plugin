"""Maya plugin entry point for the RizomUV Bridge - Ultimate Edition.

Maya's Python plugin loader runs this file with ``exec()`` in a bare
namespace that lacks ``__file__`` and ``__package__``. The path of the
executed file is still available from the running frame's code object, so
the package root is derived dynamically and the plugin works from any
install location.

Everything the plugin does — registering commands, forwarding lifecycle
callbacks — is implemented in the ``rizomuvbridge_ultimate`` package. This
file's only job is to bridge Maya's plugin system to that package.
"""

import logging
import os
import sys

# Maya API 2.0 — MSyntax, MFnMesh, MDagPath, MSelectionList, ...
import maya.api.OpenMaya as om      # noqa: F401

# Maya API 1.0 — MObject, MFnPlugin, MPxCommand, MPxNode, ...
# NOTE: ``MFnPlugin`` lives in OpenMayaMPx, not OpenMaya.
import maya.OpenMayaMPx as ompx

# Maya command layer.
import maya.cmds as cmds            # noqa: F401


# ---------------------------------------------------------------------------
# Package root
# ---------------------------------------------------------------------------
#
# Maya's plugin loader does not set ``__file__`` for files it execs, but the
# code object of the executing frame still records the plugin's path. Using
# that keeps the plugin relocatable (module installs, per-user folders).

_PLUGIN_FILE = globals().get("__file__") or sys._getframe().f_code.co_filename

_PACKAGE_ROOT = os.path.dirname(os.path.abspath(_PLUGIN_FILE))

if _PACKAGE_ROOT not in sys.path:
    sys.path.insert(0, _PACKAGE_ROOT)


# ---------------------------------------------------------------------------
# Package imports
# ---------------------------------------------------------------------------

import rizomuvbridge_ultimate  # noqa: E402, F401

from rizomuvbridge_ultimate import operators, ui                         # noqa: E402
from rizomuvbridge_ultimate.file_access import ensure_data_dir_integrity # noqa: E402
from rizomuvbridge_ultimate.properties.preferences import get_prefs      # noqa: E402
from rizomuvbridge_ultimate.utils import addon_utils, rizom_utils        # noqa: E402


# ---------------------------------------------------------------------------
# Plugin metadata
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

MODULES = (operators, ui)

PLUGIN_NAME = "RizomUVBridge"
PLUGIN_VERSION = "3.3.3"
PLUGIN_VENDOR = "Matt Ashpole"
PLUGIN_API = "Any"


# ---------------------------------------------------------------------------
# Plugin lifecycle
# ---------------------------------------------------------------------------

def initializePlugin(mobject):
    """Register the plugin with Maya.

    Args:
        mobject: The plugin's ``MObject``, supplied by Maya. It is an API 1.0
            ``MObject`` because that is what the plugin loader constructs by
            default.

    """
    # ``MFnPlugin`` is in maya.OpenMayaMPx, not maya.OpenMaya.
    plugin = ompx.MFnPlugin(mobject, PLUGIN_VENDOR, PLUGIN_VERSION, PLUGIN_API)

    # 1. Ensure the bridge's data directory exists.
    ensure_data_dir_integrity()

    # 2. Warm the preference singleton.
    prefs = get_prefs()
    logger.info(f"RizomUV Bridge preferences loaded: {prefs}")

    # 3. Seed logging state from the persisted preference.
    addon_utils.set_logging(bool(prefs.enable_logging))

    # 4. Probe LiveLink availability and record the result on the prefs.
    try:
        prefs.use_livelink = rizom_utils.check_for_livelink(prefs.rizom_path)
    except Exception as e:
        logger.warning(f"LiveLink probe failed: {e}")
        prefs.use_livelink = False

    # 5. Register the command classes and the UI.
    for module in MODULES:
        module.register(plugin)

    logger.info(
        f"RizomUV Bridge initialized "
        f"(LiveLink={'enabled' if prefs.use_livelink else 'disabled'})."
    )


def uninitializePlugin(mobject):
    """Unregister the plugin from Maya."""
    plugin = ompx.MFnPlugin(mobject)

    try:
        from rizomuvbridge_ultimate.utils.hooks import usd_hook

        usd_hook.unregister()
    except Exception as e:
        logger.warning(f"Could not unregister USD hook: {e}")

    for module in reversed(MODULES):
        try:
            module.unregister(plugin)
        except RuntimeError:
            pass

    logger.info("RizomUV Bridge uninitialized.")