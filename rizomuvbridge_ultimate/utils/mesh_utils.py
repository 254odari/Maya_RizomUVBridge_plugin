"""Functions for editing Maya mesh data and properties."""

from typing import List

import maya.cmds as cmds


def triangulate(target_objects: List[str]):
    """Triangulate the given mesh objects.

    Args:
        target_objects: Mesh transform or shape node names.

    """
    if not target_objects:
        return
    existing = [o for o in target_objects if cmds.objExists(o)]
    if not existing:
        return
    cmds.polyTriangulate(existing, constructionHistory=False)