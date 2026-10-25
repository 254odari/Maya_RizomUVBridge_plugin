"""Utility functions for working with Maya nodes."""

import logging
import re
from dataclasses import dataclass
from typing import Callable, Dict, List

import maya.cmds as cmds

from ..classes.data.validation_results import ObjectNameValidationResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Name fixing
# ---------------------------------------------------------------------------

def fix_object_names(object_results: List[ObjectNameValidationResult]):
    """Fix object names from validation results.

    Args:
        object_results: Results containing the invalid substrings per node.

    """
    for result in object_results:
        pattern = "|".join(re.escape(s) for s in result.invalid_name_substrings)
        target = result.target_object
        leaf = target.rsplit("|", 1)[-1].rsplit(":", 1)[-1]
        cleaned = re.sub(pattern, "_", leaf)

        if cleaned != leaf:
            try:
                # Rename the leaf only; renaming the full path would move
                # the node (or fail) and mangle grouped hierarchies.
                cmds.rename(target, cleaned)
            except RuntimeError as e:
                logger.warning(f"Could not rename {target}: {e}")


# ---------------------------------------------------------------------------
# Scale
# ---------------------------------------------------------------------------

def has_unapplied_scale(objects: List[str]) -> bool:
    """Return True if any transform has a non-unit local scale.

    Blender exposed ``obj.scale`` directly. Maya exposes three separate
    transform channels: ``scaleX``, ``scaleY``, ``scaleZ``. We query each
    and compare against 1.0 with a small tolerance so floating-point noise
    doesn't trigger false positives.

    Args:
        objects: Transform node names.

    Returns:
        True if any node's scale differs from (1, 1, 1).

    """
    tolerance = 1e-6

    for node in objects:
        if not cmds.objExists(node):
            continue
        try:
            sx = cmds.getAttr(f"{node}.scaleX")
            sy = cmds.getAttr(f"{node}.scaleY")
            sz = cmds.getAttr(f"{node}.scaleZ")
        except RuntimeError:
            # Node has no scale — likely a shape or non-transform type.
            continue

        if (
            abs(sx - 1.0) > tolerance
            or abs(sy - 1.0) > tolerance
            or abs(sz - 1.0) > tolerance
        ):
            return True

    return False


def apply_modifiers(objs: List[str]):
    """Bake the transform's construction history into the shape.

    Maya's equivalent of Blender's "apply modifiers": delete the construction
    history chain so the currently-evaluated mesh becomes the shape's raw data.

    Args:
        objs: Mesh transform node names.

    """
    for node in objs:
        if not cmds.objExists(node):
            continue
        if cmds.nodeType(node) != "transform":
            continue
        try:
            cmds.delete(node, constructionHistory=True)
        except RuntimeError as e:
            logger.warning(
                f"Could not delete construction history on {node}: {e}"
            )


# ---------------------------------------------------------------------------
# Visibility
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _NodeVisibilityState:
    visibility: bool


def unhide_all_objects() -> Callable[[], None]:
    """Reveal all hidden objects in the scene.

    Returns:
        A function that restores the previous visibility state.

    """
    states: Dict[str, _NodeVisibilityState] = {}

    for node in cmds.ls(type="transform", long=True) or []:
        try:
            vis = bool(cmds.getAttr(f"{node}.visibility"))
        except RuntimeError:
            vis = True
        states[node] = _NodeVisibilityState(visibility=vis)

    # Show every transform we tracked.
    for node in states:
        try:
            cmds.setAttr(f"{node}.visibility", True)
        except RuntimeError:
            pass

    # Also reveal anything hidden at the outliner level.
    #
    # ``cmds.showHidden()`` with no arguments reveals every hidden DAG node.
    # The earlier code used ``cmds.ls(hidden=True)`` — that's a Blender
    # pattern, not a Maya one. ``cmds.ls`` has no ``hidden`` flag, so the
    # call raised RuntimeError: "Invalid flag 'hidden'".
    try:
        cmds.showHidden()
    except RuntimeError as e:
        logger.warning(f"showHidden failed: {e}")

    def restore_visibility():
        for node, state in states.items():
            if not cmds.objExists(node):
                continue
            try:
                cmds.setAttr(f"{node}.visibility", state.visibility)
            except RuntimeError:
                pass

    return restore_visibility


# ---------------------------------------------------------------------------
# Deletion
# ---------------------------------------------------------------------------

def delete_objects(objects: List[str]):
    """Delete nodes from the scene."""
    if not objects:
        return
    existing = [o for o in objects if cmds.objExists(o)]
    if not existing:
        return
    try:
        cmds.delete(existing)
    except RuntimeError as e:
        logger.warning(f"Failed to delete objects: {e}")


# ---------------------------------------------------------------------------
# Edge marking
# ---------------------------------------------------------------------------

def mark_edges(objects: List[str], mark_seams: bool, mark_sharp: bool):
    """Mark UV island boundary edges as seams and/or hard edges.

    Maya has no native "seam" flag. We store one as a boolean custom
    attribute (``rizomSeams``) on the mesh. For "sharp" we soften or harden
    edges with ``polySoftEdge``.

    Args:
        objects: Mesh node names.
        mark_seams: Whether to tag island borders as seams.
        mark_sharp: Whether to mark island borders as hard edges.

    """
    if not objects:
        return

    for node in objects:
        if not cmds.objExists(node):
            continue

        if mark_sharp:
            try:
                cmds.polySoftEdge(node, angle=0, constructionHistory=False)
            except RuntimeError as e:
                logger.warning(f"polySoftEdge failed on {node}: {e}")

        if mark_seams:
            if not cmds.attributeQuery("rizomSeams", node=node, exists=True):
                try:
                    cmds.addAttr(
                        node, longName="rizomSeams", attributeType="bool"
                    )
                except RuntimeError:
                    continue
            try:
                cmds.setAttr(f"{node}.rizomSeams", True)
            except RuntimeError:
                pass