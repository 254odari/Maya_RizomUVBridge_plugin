"""Utility functions for validating Maya meshes against custom rules.

The original Blender addon operated on ``bpy.types.Object`` instances; the
Maya port operates on node names (strings). Every function in this module
accepts either a mesh *transform* name (e.g. ``"pCube1"``) or a mesh *shape*
name (e.g. ``"pCubeShape1"``) and resolves to the mesh under the hood.
"""

import re
from typing import Dict, List, Optional, Set

import maya.cmds as cmds
from maya.api import OpenMaya as om

from ..addon_constants import (
    BANNED_FBX_SUBSTRINGS,
    BANNED_OBJ_SUBSTRINGS,
    BANNED_UVMAP_SUBSTRINGS,
)
from ..classes.data.validation_results import (
    ObjectNameValidationResult,
    UVValidationResult,
)
from ..classes.exceptions.maya_exceptions import UnexpectedNodeTypeError
from ..classes.exceptions.validation_exceptions import (
    InvalidObjectNamesError,
    InvalidUVSetNamesError,
    InvalidUVSetsError,
    NonMatchingTopologyError,
)
from ..types import ExportTypes
from ..utils import uv_utils
from . import log_utils


# ---------------------------------------------------------------------------
# Compiled regexes
# ---------------------------------------------------------------------------
#
# Dict iteration order is insertion order, so multi-character sentinels like
# ``___dot___`` are matched before the single-character ``.`` alternative.
# The alternation is escaped, so ``.`` in the pattern matches a literal dot.

uvmap_banned_substring_regex = re.compile(
    "|".join(re.escape(s) for s in BANNED_UVMAP_SUBSTRINGS)
)
obj_banned_substring_regex = re.compile(
    "|".join(re.escape(s) for s in BANNED_OBJ_SUBSTRINGS)
)
fbx_banned_substring_regex = re.compile(
    "|".join(re.escape(s) for s in BANNED_FBX_SUBSTRINGS)
)

# USD prim names must be identifiers: alphanumerics and underscores, and
# they may not start with a digit.
usd_identifier_regex = re.compile(r"[^a-zA-Z0-9_]|^[0-9]")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_mfn_mesh(node_name: str) -> om.MFnMesh:
    """Return an ``MFnMesh`` for the given mesh transform or shape name.

    Args:
        node_name: DAG path (full or partial) of a mesh transform or shape.

    Returns:
        An ``MFnMesh`` attached to the shape.

    Raises:
        UnexpectedNodeTypeError: If ``node_name`` does not resolve to a mesh.

    """
    sel = om.MSelectionList()
    try:
        sel.add(node_name)
    except RuntimeError as e:
        # Node doesn't exist or the path is ambiguous.
        raise UnexpectedNodeTypeError(node_name, "mesh") from e

    dag = sel.getDagPath(0)

    # If we were handed a transform, walk down to its shape.
    if dag.hasFn(om.MFn.kTransform):
        try:
            dag.extendToShape()
        except RuntimeError as e:
            raise UnexpectedNodeTypeError(node_name, "mesh") from e

    if not dag.hasFn(om.MFn.kMesh):
        raise UnexpectedNodeTypeError(node_name, "mesh")

    return om.MFnMesh(dag)


def _mesh_polygon_count(node_name: str) -> int:
    """Return the polygon count of a mesh, resolving transform → shape."""
    return _get_mfn_mesh(node_name).numPolygons


# ---------------------------------------------------------------------------
# Topology
# ---------------------------------------------------------------------------

def assert_has_equal_polycount(a: str, b: str) -> None:
    """Assert that two meshes have the same number of polygons.

    Args:
        a: The first mesh node name.
        b: The second mesh node name.

    Raises:
        NonMatchingTopologyError: If polygon counts differ.

    """
    a_count = _mesh_polygon_count(a)
    b_count = _mesh_polygon_count(b)
    if a_count != b_count:
        raise NonMatchingTopologyError(a, b)


# ---------------------------------------------------------------------------
# UV set name validation
# ---------------------------------------------------------------------------

def assert_valid_uvmap_names(node_name: str) -> None:
    """Assert that a mesh's UV set names contain no banned substrings.

    Args:
        node_name: The mesh node name.

    Raises:
        InvalidUVSetNamesError: If any UV set name is invalid.
        UnexpectedNodeTypeError: If the node is not a mesh.

    """
    invalid_names: Dict[str, List[str]] = {}

    for uv_set in uv_utils.get_uv_set_names(node_name):
        if match := uvmap_banned_substring_regex.findall(uv_set):
            invalid_names[uv_set] = match

    if invalid_names:
        raise InvalidUVSetNamesError(invalid_names)


def fix_invalid_uvmap_names(node_name: str, invalid_names: Dict[str, List[str]]) -> None:
    """Rename UV sets to remove invalid substrings.

    Renames are applied through ``polyUVSet``. If a rename would collide with
    an existing set name, the colliding set is first moved to a temporary
    name — this matches the strategy used by ``fix_nonmatching_uvmap_sets``.

    Args:
        node_name: The mesh node name.
        invalid_names: Mapping of UV set name → list of invalid substrings
            that were found in that name.

    """
    existing = set(uv_utils.get_uv_set_names(node_name))

    for uv_set, invalid_substrings in invalid_names.items():
        new_name = uv_set
        for sub_string in invalid_substrings:
            new_name = new_name.replace(sub_string, "_")

        if new_name == uv_set:
            continue

        # Resolve a name collision by relocating the offending set.
        if new_name in existing:
            temp_name = f"__rizom_tmp_{new_name}__"
            cmds.polyUVSet(node_name, rename=True, uvSet=new_name, newUVSet=temp_name)
            existing.discard(new_name)
            existing.add(temp_name)

        cmds.polyUVSet(node_name, rename=True, uvSet=uv_set, newUVSet=new_name)
        existing.discard(uv_set)
        existing.add(new_name)


# ---------------------------------------------------------------------------
# UV set matching
# ---------------------------------------------------------------------------

def assert_matching_uvmap_sets(base_uvmaps: Set[str], objects: List[str]) -> None:
    """Assert that a list of meshes share the same UV set names as a base mesh.

    Only the *set* of names is compared — order is not enforced here. Use
    ``fix_nonmatching_uvmap_sets`` to additionally normalise order.

    Args:
        base_uvmaps: UV set names of the base mesh.
        objects: Mesh node names to check.

    Raises:
        InvalidUVSetsError: If any mesh's UV sets differ from ``base_uvmaps``.
        UnexpectedNodeTypeError: If any node is not a mesh.

    """
    results: List[UVValidationResult] = []

    for node in objects:
        if not uv_utils.is_mesh(node):
            raise UnexpectedNodeTypeError(node, "mesh")

        obj_uvmaps = set(uv_utils.get_uv_set_names(node))
        extra_uvmaps = sorted(obj_uvmaps - base_uvmaps)
        missing_uvmaps = sorted(base_uvmaps - obj_uvmaps)

        if extra_uvmaps or missing_uvmaps:
            results.append(UVValidationResult(node, extra_uvmaps, missing_uvmaps))

    if results:
        raise InvalidUVSetsError(results)


def assert_matching_uvmap_sets_single(base_uvmaps: Set[str], node: str) -> None:
    """Single-mesh convenience wrapper around ``assert_matching_uvmap_sets``."""
    assert_matching_uvmap_sets(base_uvmaps, [node])


def fix_nonmatching_uvmap_sets(
    base_uvmaps: List[str],
    node: str,
    remove_extra_uvmaps: bool,
) -> None:
    """Force a mesh's UV sets to match the base mesh exactly.

    The base mesh's UV sets are treated as the canonical ordering. Any
    missing sets are created, extra sets are optionally removed, and
    matching sets are renamed and reordered to match.

    Args:
        base_uvmaps: UV set names of the base mesh (order matters).
        node: The mesh node to fix.
        remove_extra_uvmaps: Whether to delete extra UV sets.

    Raises:
        UnexpectedNodeTypeError: If the node is not a mesh.

    """
    if not uv_utils.is_mesh(node):
        raise UnexpectedNodeTypeError(node, "mesh")

    # 1. Ensure at least as many sets exist as the base expects.
    current = uv_utils.get_uv_set_names(node)
    if len(current) < len(base_uvmaps):
        uv_utils.add_uvmaps(node, len(base_uvmaps) - len(current))
        current = uv_utils.get_uv_set_names(node)

    # 2. Rename to match, using temporary names to avoid collisions.
    #
    #    Strategy: for each positional index i, we want the set at position i
    #    to be named base_uvmaps[i]. We do this in two passes:
    #      - Pass A: rename every set that will change to a unique temp name.
    #      - Pass B: rename temp names to their final target names.
    #
    #    This avoids the situation where renaming set[0] to "foo" clobbers
    #    set[1], which was also called "foo".
    current = uv_utils.get_uv_set_names(node)
    pending_renames: List[tuple] = []  # (temp_name, final_name)

    for i, expected_name in enumerate(base_uvmaps):
        existing = current[i]
        if existing == expected_name:
            continue
        temp_name = f"__rizom_tmp_{i}__"
        cmds.polyUVSet(node, rename=True, uvSet=existing, newUVSet=temp_name)
        pending_renames.append((temp_name, expected_name))

    for temp_name, final_name in pending_renames:
        # If something still holds the target name (shouldn't, but be safe),
        # shove it out of the way.
        current = uv_utils.get_uv_set_names(node)
        if final_name in current:
            collision_temp = f"__rizom_collide_{final_name}__"
            cmds.polyUVSet(
                node, rename=True, uvSet=final_name, newUVSet=collision_temp
            )
        cmds.polyUVSet(node, rename=True, uvSet=temp_name, newUVSet=final_name)

    # 3. Optionally trim extra sets.
    current = uv_utils.get_uv_set_names(node)
    if remove_extra_uvmaps and len(current) > len(base_uvmaps):
        uv_utils.pop_uvmaps(node, len(current) - len(base_uvmaps))


# ---------------------------------------------------------------------------
# Object name validation
# ---------------------------------------------------------------------------

def assert_valid_object_names(
    objects: List[str],
    export_format: ExportTypes,
) -> None:
    """Assert that object names are valid for the target export format.

    Args:
        objects: Maya node names.
        export_format: One of ``"FBX"``, ``"OBJ"``, ``"USD"``.

    Raises:
        InvalidObjectNamesError: If any name contains invalid characters.

    """
    format_regex_map = {
        "OBJ": obj_banned_substring_regex,
        "FBX": fbx_banned_substring_regex,
        "USD": usd_identifier_regex,
    }
    regex = format_regex_map[export_format]

    results: List[ObjectNameValidationResult] = []
    for name in objects:
        # ``name`` is usually a full DAG path (``|group|mesh``). Only the
        # leaf is written to the file, so ``|`` and any namespace prefix
        # must not be treated as part of the object name.
        leaf = name.rsplit("|", 1)[-1].rsplit(":", 1)[-1]
        if match := regex.findall(leaf):
            results.append(ObjectNameValidationResult(name, match))

    if results:
        raise InvalidObjectNamesError(results)


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------

def assert_valid_for_export(
    active_object: str,
    objects: List[str],
    export_format: ExportTypes,
    all_objects: Optional[List[str]] = None,
) -> None:
    """Run every validation required before exporting to RizomUV.

    Args:
        active_object: The active mesh node. Its UV set names define the
            canonical set that all other meshes must match.
        objects: Mesh node names to validate against ``active_object``.
        export_format: Target export format (``"FBX"`` | ``"OBJ"`` | ``"USD"``).
        all_objects: Every node that will be written to the export file —
            meshes plus group transforms. If ``None``, ``objects`` is used.

    Raises:
        InvalidUVSetNamesError: If the active mesh has invalid UV set names.
        InvalidUVSetsError: If other meshes' UV sets don't match the active mesh.
        InvalidObjectNamesError: If any name contains illegal characters.
        UnexpectedNodeTypeError: If a node is not a mesh where a mesh was
            expected.

    """
    if not uv_utils.is_mesh(active_object):
        raise UnexpectedNodeTypeError(active_object, "mesh")

    assert_valid_uvmap_names(active_object)

    base_uvs = set(uv_utils.get_uv_set_names(active_object))
    assert_matching_uvmap_sets(base_uvs, objects)
    assert_valid_object_names(
        all_objects if all_objects is not None else objects,
        export_format,
    )


# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------

def log_invalid_uvmap_names(invalid_uvmap_names: Dict[str, List[str]]) -> None:
    """Print a table of invalid UV set names to the script editor."""
    table_rows = [
        [uvmap, ", ".join(substrings)]
        for uvmap, substrings in invalid_uvmap_names.items()
    ]
    table = log_utils.Table(
        "RizomUV Bridge - Invalid UV Map Names",
        ["UV Map", "Invalid Substrings"],
    )
    table.add_rows(table_rows)
    table.print()


def log_non_matching_uvmaps(uvmap_results: List[UVValidationResult]) -> None:
    """Print a table of non-matching UV set results to the script editor."""
    table_rows = [
        [
            r.target_object,
            ", ".join(r.extra_uvmaps) or "-",
            ", ".join(r.missing_uvmaps) or "-",
        ]
        for r in uvmap_results
    ]
    table = log_utils.Table(
        "RizomUV Bridge - Non-Matching UV Maps",
        ["Target Object", "Extra UV Maps", "Missing UV Maps"],
    )
    table.add_rows(table_rows)
    table.print()


def log_invalid_object_names(object_results: List[ObjectNameValidationResult]) -> None:
    """Print a table of invalid object names to the script editor."""
    table_rows = [
        [r.target_object, ", ".join(r.invalid_name_substrings)]
        for r in object_results
    ]
    table = log_utils.Table(
        "RizomUV Bridge - Invalid Object Names",
        ["Target Object", "Invalid Substrings"],
    )
    table.add_rows(table_rows)
    table.print()