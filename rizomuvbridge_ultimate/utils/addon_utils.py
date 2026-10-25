"""Utility helpers for the RizomUV Bridge (Maya edition).

Preference access is centralised in :mod:`..properties.preferences`, which
exposes a lazily-instantiated singleton via ``get_prefs()``. This module
re-exports that accessor for convenience and provides a small set of
procedural helpers that do not belong on the preference class itself
(logging toggle, static enum tables, capability probes).

Import topology note
--------------------
``properties.preferences`` transitively imports every ``*Preferences``
mixin, including ``properties/export_preferences.py``. That module imports
``export_formats`` from *this* module. Importing ``get_prefs`` at module
scope would therefore create a cycle:

    addon_utils  →  properties.preferences  →  export_preferences  →  addon_utils

To break the cycle, ``get_prefs`` is wrapped in a thin function that
performs the real import lazily on first call. This preserves the public
API (``addon_utils.get_prefs()`` keeps working exactly as before) while
eliminating the module-level dependency.
"""

import logging
import platform
from typing import List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    # Only imported for static analysis. Never executed at runtime, so the
    # cycle is never triggered.
    from ..properties.preferences import RizomBridgePreferences

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Re-exports (lazy)
# ---------------------------------------------------------------------------

__all__ = [
    "get_prefs",
    "set_pref",
    "set_logging",
    "export_formats",
    "axis_items",
    "platform_is_windows",
    "platform_is_macos",
    "platform_is_linux",
]


def get_prefs():
    """Return the singleton preference object.

    Lazy-wrapped to avoid a circular import. See the module docstring for
    the full explanation. Callers see the same object as
    ``properties.preferences.get_prefs()`` — this is only a thin shim so
    the utility namespace can expose the accessor alongside its helpers.

    Returns:
        The ``RizomBridgePreferences`` singleton.

    """
    from ..properties.preferences import get_prefs as _get_prefs
    return _get_prefs()


def set_pref(name: str, value) -> None:
    """Persist a single preference through its descriptor.

    Args:
        name: The descriptor name on the preferences object, e.g.
            ``"export_format"``.
        value: The new value; the descriptor converts and clamps it.

    """
    setattr(get_prefs(), name, value)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def set_logging(enabled: bool) -> None:
    """Enable or disable stdout logging for the bridge's loggers.

    Delegates to :func:`..utils.update_callbacks.logging_toggle`, which
    installs or removes a ``StreamHandler`` on the root logger and sets
    the ``rizomuv_bridge`` logger level accordingly.

    Args:
        enabled: True to enable debug logging to stdout, False to silence.

    """
    # Also imported lazily — update_callbacks may reach back into this
    # module in some configurations, and keeping the import local makes the
    # dependency direction unambiguous.
    from .update_callbacks import logging_toggle
    logging_toggle(bool(enabled), logging.getLogger("rizomuv_bridge"))


# ---------------------------------------------------------------------------
# Static enum tables for UI
# ---------------------------------------------------------------------------

def export_formats() -> List[Tuple[str, str, str]]:
    """Return the available export formats as (id, label, description) tuples.

    Matches the shape Maya's ``optionMenu`` + ``menuItem`` pattern expects
    after flattening — callers iterate over the tuples and create one
    ``menuItem`` per entry.

    Returns:
        A list of ``(identifier, label, description)`` tuples, in display
        order. The identifiers match :data:`..types.ExportTypes`.

    """
    return [
        ("FBX", "FBX", "Autodesk FBX — supports multiple UV sets"),
        ("OBJ", "OBJ", "Wavefront OBJ — single UV set only"),
        ("USD", "USD", "Universal Scene Description — supports UV sets and prim attributes"),
    ]


def axis_items() -> List[Tuple[str, str, str]]:
    """Return the axis options as (id, label, description) tuples.

    Shared by the ``up_axis`` and ``forward_axis`` preferences.

    Returns:
        A list of ``(identifier, label, description)`` tuples, in display
        order. The identifiers match :data:`..types.Axis`.

    """
    return [
        ("X", "X Axis", ""),
        ("Y", "Y Axis", ""),
        ("Z", "Z Axis", ""),
        ("NEGATIVE_X", "-X Axis", ""),
        ("NEGATIVE_Y", "-Y Axis", ""),
        ("NEGATIVE_Z", "-Z Axis", ""),
    ]


# ---------------------------------------------------------------------------
# Platform helpers
# ---------------------------------------------------------------------------

def platform_is_windows() -> bool:
    """Return True if running on Windows."""
    return platform.system() == "Windows"


def platform_is_macos() -> bool:
    """Return True if running on macOS."""
    return platform.system() == "Darwin"


def platform_is_linux() -> bool:
    """Return True if running on Linux."""
    return platform.system() == "Linux"