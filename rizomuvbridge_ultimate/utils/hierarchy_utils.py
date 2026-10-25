"""Functions for working with Maya object hierarchies."""

from typing import Callable, Dict, List, Optional

import maya.cmds as cmds


def flatten_object_hierarchy(objects: List[str]) -> Callable[[], None]:
    """Flatten objects so no parent/child relationships exist.

    World transforms are preserved. Returns a callable that restores the
    original hierarchy.

    Args:
        objects: Transform node names to flatten.

    Returns:
        A function that restores the original hierarchy.

    """
    relationships: Dict[str, Optional[str]] = {}
    world_matrices: Dict[str, List[float]] = {}

    for obj in objects:
        parent_list = cmds.listRelatives(obj, parent=True, fullPath=True)
        relationships[obj] = parent_list[0] if parent_list else None
        world_matrices[obj] = cmds.xform(obj, q=True, ws=True, matrix=True)

    for obj in objects:
        if relationships[obj] is not None:
            cmds.parent(obj, world=True)

    def restore_hierarchy():
        # Restore in reverse order so parents are re-established before
        # children are parented back to them.
        for obj in reversed(objects):
            parent = relationships[obj]
            if parent and cmds.objExists(parent):
                cmds.parent(obj, parent)
            cmds.xform(obj, ws=True, matrix=world_matrices[obj])

    return restore_hierarchy