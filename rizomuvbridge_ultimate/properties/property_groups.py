"""Addon property groups (Maya edition).

Blender's ``PropertyGroup`` let the addon attach enum properties to
``WindowManager`` and drive UI widgets directly. Maya has no such system —
this module exposes:

- ``RizomBridgeGuiTabs``: static tab identifier list.
- ``RizomBridgeUVMaps``: a thin wrapper around ``cmds.polyUVSet`` for the
  active mesh, so the UI can list / set the active UV set.
"""

from typing import List, Tuple

import maya.cmds as cmds


# ---------------------------------------------------------------------------
# GUI tabs
# ---------------------------------------------------------------------------

class RizomBridgeGuiTabs:
    """Static tab definitions used by the RizomUV Bridge panel.

    In Blender this was a ``PropertyGroup`` with an ``EnumProperty``. In
    Maya the UI reads ``TABS`` directly.
    """

    TABS: Tuple[Tuple[str, str], ...] = (
        ("OPERATIONS", "Operations"),
        ("ADDON_SETTINGS", "Addon Settings"),
    )

    # Session-scoped current tab (matches the Blender "names" enum).
    _current: str = "OPERATIONS"

    @classmethod
    def get_current(cls) -> str:
        return cls._current

    @classmethod
    def set_current(cls, tab_id: str):
        valid = {tid for tid, _ in cls.TABS}
        if tab_id not in valid:
            raise ValueError(f"Unknown tab id: {tab_id!r}")
        cls._current = tab_id


# ---------------------------------------------------------------------------
# UV map enumeration
# ---------------------------------------------------------------------------

def _get_active_mesh_transform() -> str:
    """Return the active mesh transform long name, or empty string.

    ``cmds.ls`` has no ``active`` flag; Maya treats the last item of the
    selection as the active object, so walk the selection in reverse.
    """
    selection = cmds.ls(selection=True, long=True) or []
    for node in reversed(selection):
        shapes = cmds.listRelatives(node, shapes=True, fullPath=True) or []
        if any(cmds.nodeType(s) == "mesh" for s in shapes):
            return node
    return ""


def get_uvmaps() -> List[Tuple[str, str, str]]:
    """Return (identifier, label, description) tuples for the active mesh's UV sets.

    Mirrors the Blender ``get_uvmaps`` item callback.
    """
    mesh = _get_active_mesh_transform()
    if not mesh:
        return [("NO_OBJ", "[No object selected]", "")]

    uv_sets = cmds.polyUVSet(mesh, query=True, allUVSets=True) or []
    if not uv_sets:
        return [("NO_UV", "[The active object has no UV maps]", "")]

    RizomBridgeUVMaps._uv_maps_list = [(uv, uv, "") for uv in uv_sets]

    # Seed the session-scoped active UV set from Maya so export/unwrap
    # actions work before the user touches the dropdown.
    if RizomBridgeUVMaps._active not in uv_sets:
        current = cmds.polyUVSet(mesh, query=True, currentUVSet=True)
        if isinstance(current, (list, tuple)):
            current = current[0] if current else ""
        RizomBridgeUVMaps._active = current if current in uv_sets else uv_sets[0]

    return list(RizomBridgeUVMaps._uv_maps_list)


def set_uvmap(uv_name: str):
    """Set the active UV set on the active mesh.

    Mirrors the Blender ``uvmaps_update`` callback.
    """
    mesh = _get_active_mesh_transform()
    if not mesh:
        return
    current = cmds.polyUVSet(mesh, query=True, allUVSets=True) or []
    if uv_name in current:
        cmds.polyUVSet(mesh, currentUVSet=True, uvSet=uv_name)


class RizomBridgeUVMaps:
    """Thin wrapper around the active mesh's UV set list.

    Kept as a class (rather than the Blender ``PropertyGroup``) so the UI
    can call the same method names as before.
    """

    # Blender kept a class-level list to work around an EnumProperty bug.
    # We keep it too — the UI can read it synchronously without re-querying.
    _uv_maps_list: List[Tuple[str, str, str]] = []

    @classmethod
    def items(cls) -> List[Tuple[str, str, str]]:
        return get_uvmaps()

    @classmethod
    def set(cls, uv_name: str):
        set_uvmap(uv_name)

    # Session-scoped active UV set, so UI code can persist selection across
    # rebuilds without re-querying Maya.
    _active: str = ""

    @classmethod
    def get_active(cls) -> str:
        if not cls._active:
            mesh = _get_active_mesh_transform()
            if mesh:
                current = cmds.polyUVSet(mesh, query=True, currentUVSet=True)
                if isinstance(current, (list, tuple)):
                    current = current[0] if current else ""
                cls._active = current
        return cls._active

    @classmethod
    def set_active(cls, uv_name: str):
        cls._active = uv_name
        cls.set(uv_name)