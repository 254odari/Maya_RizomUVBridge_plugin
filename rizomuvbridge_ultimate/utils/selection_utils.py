"""Utility functions for working with Maya selections."""

from typing import List, Set, Tuple

import maya.cmds as cmds


def deselect_non_exportable_objects():
    """Deselect every node that is not a mesh transform or a group transform."""
    for node in cmds.ls(selection=True, long=True) or []:
        shapes = cmds.listRelatives(node, shapes=True, fullPath=True) or []
        is_mesh = any(cmds.nodeType(s) == "mesh" for s in shapes)
        is_group = not shapes
        if not (is_mesh or is_group):
            cmds.select(node, deselect=True)


def get_selected_meshes() -> List[str]:
    """Return the long names of selected mesh transforms.

    Maya has no ``-active`` flag on ``cmds.ls``. The convention is that the
    *last* item of the selection is the active object, so if nothing is
    selected but an active object exists, we fall back to it.

    Returns:
        A list of mesh transform long names.

    """
    selection = cmds.ls(selection=True, long=True) or []

    meshes: List[str] = []
    for node in selection:
        shapes = cmds.listRelatives(node, shapes=True, fullPath=True) or []
        if any(cmds.nodeType(s) == "mesh" for s in shapes):
            meshes.append(node)

    # Fall back to the last-selected (Maya's "active").
    if not meshes and selection:
        last = selection[-1]
        shapes = cmds.listRelatives(last, shapes=True, fullPath=True) or []
        if any(cmds.nodeType(s) == "mesh" for s in shapes):
            cmds.select(last, add=True)
            meshes.append(last)

    return meshes


def split_objects_by_shared_data(
    objects: List[str],
) -> Tuple[List[str], Set[str]]:
    """Separate unique meshes from instances (shared shape nodes)."""
    seen_shapes: Set[str] = set()
    unique: List[str] = []
    instanced: Set[str] = set()

    for node in objects:
        shapes = cmds.listRelatives(node, shapes=True, fullPath=True) or []
        if not shapes:
            continue
        shape = shapes[0]
        if shape not in seen_shapes:
            seen_shapes.add(shape)
            unique.append(node)
        else:
            instanced.add(node)

    return unique, instanced


def get_selected_empties() -> List[str]:
    """Return selected group / transform nodes that have no shapes."""
    result: List[str] = []
    for node in cmds.ls(selection=True, long=True) or []:
        if cmds.nodeType(node) != "transform":
            continue
        shapes = cmds.listRelatives(node, shapes=True, fullPath=True) or []
        if not shapes:
            result.append(node)
    return result


def get_objects_for_export(active_object: str, exclude_clones: bool) -> List[str]:
    """Return the list of meshes to export, optionally excluding instances."""
    selected = get_selected_meshes()
    if not exclude_clones:
        return selected

    unique, cloned = split_objects_by_shared_data(selected)

    if active_object in cloned:
        active_shapes = cmds.listRelatives(
            active_object, shapes=True, fullPath=True
        ) or []
        if active_shapes:
            active_shape = active_shapes[0]
            for i, node in enumerate(unique):
                shapes = cmds.listRelatives(
                    node, shapes=True, fullPath=True
                ) or []
                if shapes and shapes[0] == active_shape:
                    cloned.discard(active_object)
                    cloned.add(unique[i])
                    unique[i] = active_object
                    break

    return unique