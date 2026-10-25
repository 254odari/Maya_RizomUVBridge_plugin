"""Utility functions for working with UV sets in Maya."""

from typing import List

import maya.cmds as cmds

from ..classes.exceptions.maya_exceptions import UnexpectedNodeTypeError


def is_mesh(node: str) -> bool:
    """Return True if node is a mesh transform or shape."""
    if not cmds.objExists(node):
        return False
    if cmds.nodeType(node) == "mesh":
        return True
    shapes = cmds.listRelatives(node, shapes=True, fullPath=True) or []
    return any(cmds.nodeType(s) == "mesh" for s in shapes)


def get_uv_set_names(node: str) -> List[str]:
    """Return UV set names for a mesh node (transform or shape)."""
    if not is_mesh(node):
        raise UnexpectedNodeTypeError(node, "mesh")
    return cmds.polyUVSet(node, query=True, allUVSets=True) or []


def unwrap_uvs(uvmap_name: str, node: str, all_uvmaps: bool):
    """Unwrap UVs on the given mesh.

    Args:
        uvmap_name: The UV set to unwrap.
        node: The mesh transform.
        all_uvmaps: If True, unwrap all UV sets on the mesh.

    """
    if not is_mesh(node):
        raise UnexpectedNodeTypeError(node, "mesh")

    def unwrap(uv_set: str):
        cmds.polyUVSet(node, currentUVSet=True, uvSet=uv_set)
        cmds.unfold(node, iterations=1, useScale=False, constructionHistory=False)
        # Optionally weld, matching Blender's weld-then-unwrap:
        cmds.polyMapSewMove(node, constructionHistory=False)

    unwrap(uvmap_name)

    if all_uvmaps:
        for uv_set in get_uv_set_names(node):
            if uv_set != uvmap_name:
                unwrap(uv_set)

    cmds.polyUVSet(node, currentUVSet=True, uvSet=uvmap_name)


def pop_uvmaps(node: str, count: int):
    """Remove the last N UV sets from the mesh."""
    if not is_mesh(node):
        raise UnexpectedNodeTypeError(node, "mesh")

    for _ in range(count):
        uv_sets = get_uv_set_names(node)
        if not uv_sets:
            return
        cmds.polyUVSet(node, delete=True, uvSet=uv_sets[-1])


def add_uvmaps(node: str, count: int):
    """Add N empty UV sets to the mesh."""
    if not is_mesh(node):
        raise UnexpectedNodeTypeError(node, "mesh")

    for i in range(count):
        name = f"map{i + 1}"
        existing = set(get_uv_set_names(node))
        suffix = 1
        while name in existing:
            name = f"map{i + 1}_{suffix}"
            suffix += 1
        cmds.polyUVSet(node, create=True, uvSet=name)