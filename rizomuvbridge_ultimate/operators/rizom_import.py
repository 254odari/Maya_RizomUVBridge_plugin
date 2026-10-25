"""Command for importing a file from RizomUV and transferring UV data."""

import logging
from typing import Callable, Dict, List, Optional
from uuid import uuid4

import maya.api.OpenMaya as om              # API 2.0: MFnMesh, MDagPath
import maya.OpenMaya as om1                 # API 1.0: MSyntax, MArgParser
import maya.OpenMayaMPx as ompx             # API 1.0: MPxCommand
import maya.cmds as cmds

from ..classes.data.import_models import RizomData
from ..classes.data.import_results import UVTransferResult
from ..classes.exceptions.rizom_exceptions import (
    RizomLegacyConnectionError,
    RizomLinkConnectionError,
    RizomLinkModuleNotFoundError,
    RizomLinkUnsupportedError,
)
from ..classes.rizom.legacy.rizom_legacy import RizomLegacy
from ..classes.rizom.modern.rizom_link import RizomLink
from ..classes.rizom.rizom_base import RizomBase
from ..file_access import get_data_directory
from ..utils import addon_utils, io_utils, object_utils, usd_utils
from ..utils.hooks.usd_hook import UsdHookRizom
from ..utils.exceptions_utils import report_and_log_exception
from ..utils.validation_utils import assert_has_equal_polycount

logger = logging.getLogger(__name__)


class ImportFromRizomCommand(ompx.MPxCommand):
    """Import meshes from RizomUV and transfer UV maps."""

    COMMAND_NAME = "rizomImport"

    def __init__(self):
        super().__init__()
        self._replace_override: Optional[bool] = None

    # ---------------------------------------------------------------------
    # Syntax / argument parsing
    # ---------------------------------------------------------------------

    @classmethod
    def _syntax(cls):
        syntax = om1.MSyntax()
        syntax.addFlag("-rp", "-replace", om1.MSyntax.kBoolean)
        return syntax

    def parseArguments(self, args):
        arg_data = om1.MArgParser(self.syntax(), args)
        if arg_data.isFlagSet("-rp"):
            self._replace_override = arg_data.flagArgumentBool("-rp", 0)

    # ---------------------------------------------------------------------
    # Connection
    # ---------------------------------------------------------------------

    def _connect_to_rizom(self, prefs, data_dir) -> RizomBase:
        if prefs.use_livelink:
            logger.info("Connecting to RizomUV using livelink")
            try:
                rizom = RizomLink(
                    prefs.rizom_path,
                    data_dir,
                    prefs.connection_timeout,
                )
                if rizom.connection_manager.connect():
                    return rizom
                raise RizomLinkConnectionError(
                    "There is no RizomUVLink instance active."
                )
            except (RizomLinkUnsupportedError, RizomLinkModuleNotFoundError):
                logger.info(
                    "RizomLink module unavailable, falling back to legacy methods"
                )
                prefs.use_livelink = False
                return self._connect_to_rizom(prefs, data_dir)
        else:
            logger.info("Connecting to RizomUV using legacy methods")
            legacy = RizomLegacy(
                prefs.rizom_path,
                data_dir,
                prefs.connection_timeout,
            )
            if not legacy.is_connected():
                raise RizomLegacyConnectionError()
            return legacy

    # ---------------------------------------------------------------------
    # Post-import actions
    # ---------------------------------------------------------------------

    def _post_import_actions(
        self,
        prefs,
        objects: List[str],
        usd_prop_keys: Optional[Dict[str, str]] = None,
    ):
        if prefs.export_format == "USD":
            usd_utils.import_usd_props(objects, usd_prop_keys)

        if prefs.mark_seams or prefs.mark_sharp:
            object_utils.mark_edges(
                objects, prefs.mark_seams, prefs.mark_sharp
            )

    def _handle_obj_import(
        self, imported_objects: List[str], incoming_data: RizomData
    ):
        for node in imported_objects:
            uv_sets = cmds.polyUVSet(node, query=True, allUVSets=True) or []
            if uv_sets and incoming_data.uv_maps:
                cmds.polyUVSet(
                    node,
                    rename=True,
                    uvSet=uv_sets[0],
                    newUVSet=incoming_data.uv_maps[0],
                )

    def _delete_object_materials(self, objects: List[str]):
        for node in objects:
            shapes = cmds.listRelatives(node, shapes=True, fullPath=True) or []
            for shape in shapes:
                sg = cmds.listConnections(shape, type="shadingEngine") or []
                for s in sg:
                    cmds.sets(shape, remove=s)

    # ---------------------------------------------------------------------
    # doIt
    # ---------------------------------------------------------------------

    def doIt(self, args):
        self.parseArguments(args)

        prefs = addon_utils.get_prefs()
        data_dir = get_data_directory()

        if self._replace_override is not None:
            prefs.replace_objects = bool(self._replace_override)

        try:
            rizom = self._connect_to_rizom(prefs, data_dir)
        except Exception as e:
            report_and_log_exception(e)
            raise RuntimeError(str(e))

        restore_selection = _save_selection()

        try:
            incoming_data = rizom.get_scene_data()
        except Exception as e:
            restore_selection()
            report_and_log_exception(e)
            raise RuntimeError(str(e))

        restore_visibility = object_utils.unhide_all_objects()
        restore_names, name_map, parent_empties = _rename_objects(incoming_data)

        def cleanup():
            restore_names()
            if prefs.reveal_hidden:
                restore_visibility()
            if not prefs.replace_objects:
                restore_selection()

        try:
            chaser = None
            if prefs.export_format == "USD" and usd_utils.register_hook():
                # The import chaser must be registered and enabled before the
                # import runs; it populates the hook properties in PostImport.
                UsdHookRizom.properties.clear()
                chaser = usd_utils.CHASER_NAME
                UsdHookRizom.enable()

            try:
                imported_objects = io_utils.import_file(
                    prefs.export_format, data_dir, chaser=chaser
                )
            finally:
                if chaser:
                    UsdHookRizom.disable()

            if incoming_data.file_path.lower().endswith(".obj"):
                self._handle_obj_import(imported_objects, incoming_data)

            if prefs.replace_objects:
                scene_objects = list(name_map.values())
                object_utils.delete_objects(scene_objects + parent_empties)
                self._post_import_actions(prefs, imported_objects)
                cmds.inViewMessage(
                    amg=f"Replaced {len(scene_objects)} objects after importing "
                        f"from RizomUV.",
                    pos="midCenter",
                    fade=True,
                )
                return

            _update_uvmaps(
                imported_objects,
                name_map,
                prefs.create_missing_uvmaps,
                prefs.delete_unmatched_uvmaps,
            )

            usd_prop_keys = {
                temp: original for original, temp in name_map.items()
            }
            self._post_import_actions(
                prefs, list(name_map.values()), usd_prop_keys
            )
            self._delete_object_materials(imported_objects)
            object_utils.delete_objects(imported_objects)
            cleanup()

            cmds.inViewMessage(
                amg=f"Updated {len(imported_objects)} objects from RizomUV.",
                pos="midCenter",
                fade=True,
            )

        except Exception as e:
            cleanup()
            report_and_log_exception(e)
            raise RuntimeError(str(e))

    # ---------------------------------------------------------------------
    # Plugin registration
    # ---------------------------------------------------------------------

    @classmethod
    def _creator(cls):
        return ImportFromRizomCommand()

    @classmethod
    def register(cls, plugin_fn):
        plugin_fn.registerCommand(cls.COMMAND_NAME, cls._creator, cls._syntax)

    @classmethod
    def unregister(cls, plugin_fn):
        try:
            plugin_fn.deregisterCommand(cls.COMMAND_NAME)
        except RuntimeError:
            pass


ImportFromRizom = ImportFromRizomCommand


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _maya_safe_uuid_name() -> str:
    """Generate a Maya-safe temporary node name.

    Maya requires node names to start with a letter and to contain only
    letters, digits, and underscores. A raw ``str(uuid4())`` fails both
    rules — it contains hyphens and may start with a digit — and Maya
    silently rewrites the name to something valid, breaking any lookup
    that used the original string.

    ``uuid4().hex`` produces a 32-character hex string with no hyphens,
    and the ``rizom_tmp_`` prefix guarantees a valid first character.
    """
    return f"rizom_tmp_{uuid4().hex}"


def _save_selection() -> Callable[[], None]:
    """Capture selection state and return a restore callback.

    Maya has no dedicated "active object" query; treat the last item of the
    selection as the active object.
    """
    selection = cmds.ls(selection=True, long=True) or []
    active = selection[-1] if selection else None

    def restore():
        cmds.select(clear=True)
        if selection:
            still_present = [n for n in selection if cmds.objExists(n)]
            if still_present:
                cmds.select(still_present, add=True)
        if active and cmds.objExists(active):
            cmds.select(active, add=True)

    return restore



def _resolve_to_transform(name: str) -> Optional[str]:
    """Resolve an incoming name to a renameable transform DAG path.

    Maya raises "Invalid path" on ``cmds.rename`` when the short name is
    ambiguous — two or more DAG nodes share the same leaf name. This is
    common in rigged scenes where a group and one of its descendants have
    identical names, e.g. ``|high_poly`` and ``|high_poly|high_poly``.

    The correct target in that case is the **topmost** matching transform.
    Renaming it clears the collision for the incoming FBX.

    Args:
        name: An incoming object name (may be short, may be ambiguous).

    Returns:
        A unique long DAG path to the shallowest matching transform, or
        None if no renameable transform was found.

    """
    if not name or not cmds.objExists(name):
        return None

    candidates = cmds.ls(name, long=True, dag=True) or []
    if not candidates:
        return None

    # Prefer transforms; among them the shallowest path.
    transform_paths: List[str] = []
    for path in candidates:
        try:
            if cmds.nodeType(path) == "transform":
                transform_paths.append(path)
        except RuntimeError:
            continue

    if transform_paths:
        transform_paths.sort(key=lambda p: p.count("|"))
        return transform_paths[0]

    # Fall back to the parent of any mesh shape.
    for path in candidates:
        try:
            if cmds.nodeType(path) == "mesh":
                parents = cmds.listRelatives(
                    path, parent=True, fullPath=True
                ) or []
                if parents:
                    return parents[0]
        except RuntimeError:
            continue

    return candidates[0]


def _rename_objects(incoming_data: RizomData):
    """Rename scene nodes to avoid name collisions during import.

    Resolves every incoming name to a unique transform DAG path before
    renaming. Using the short name is not reliable — Maya raises
    "Invalid path" when the name is ambiguous or resolves to a shape.

    Returns:
        A tuple ``(restore_names, name_map, parent_empties)``.

    """
    object_map: Dict[str, str] = {}     # current_name -> original_name
    name_map: Dict[str, str] = {}       # original_name -> current_name

    for name in incoming_data.objects:
        target = _resolve_to_transform(name)
        if target is None:
            logger.warning(f"Could not resolve {name!r} to a transform.")
            continue

        temp_name = _maya_safe_uuid_name()
        try:
            actual_name = cmds.rename(target, temp_name)
        except RuntimeError as e:
            logger.warning(
                f"Could not rename {target!r} (from {name!r}): {e}"
            )
            continue

        object_map[actual_name] = name
        name_map[name] = actual_name

    # Rename parent group nodes to avoid collisions during FBX import.
    parent_empties: List[str] = []
    seen_parents = set()

    for original_name, current_name in list(name_map.items()):
        parents = cmds.listRelatives(
            current_name, parent=True, fullPath=True
        ) or []
        parent = parents[0] if parents else None
        if parent and parent not in seen_parents:
            shapes = cmds.listRelatives(
                parent, shapes=True, fullPath=True
            ) or []
            if not shapes:
                seen_parents.add(parent)
                temp_name = _maya_safe_uuid_name()
                try:
                    actual_name = cmds.rename(parent, temp_name)
                except RuntimeError as e:
                    logger.warning(
                        f"Could not rename parent {parent!r}: {e}"
                    )
                    continue
                object_map[actual_name] = parent
                parent_empties.append(actual_name)

    def restore_names():
        for current_name, original in object_map.items():
            if cmds.objExists(current_name):
                try:
                    cmds.rename(current_name, original)
                except RuntimeError:
                    logger.warning(
                        f"Could not restore name for {current_name} -> "
                        f"{original}; name may be in use."
                    )

    return restore_names, name_map, parent_empties


def _update_uvmaps(
    rizom_objects: List[str],
    name_map: Dict[str, str],
    add_uvmaps: bool,
    remove_uvmaps: bool,
) -> UVTransferResult:
    missing_objects: List[str] = []
    missing_uvmaps: Dict[str, List[str]] = {}
    extra_uvmaps: Dict[str, List[str]] = {}

    # Build a short-name → temp-name lookup so we can match imported FBX
    # nodes back to the scene objects that were renamed.
    short_to_temp: Dict[str, str] = {}
    for original, temp_name in name_map.items():
        short = original.split("|")[-1].split(":")[-1]
        short_to_temp[short] = temp_name

    for node in rizom_objects:
        short = node.split(":")[-1].split("|")[-1]
        # Some FBX importers suffix "Shape" onto shape node names; strip it
        # when looking up the transform.
        short_base = (
            short.split("Shape")[0] if short.endswith("Shape") else short
        )

        matched_temp = short_to_temp.get(short) or short_to_temp.get(short_base)
        if not matched_temp or not cmds.objExists(matched_temp):
            missing_objects.append(node)
            continue

        assert_has_equal_polycount(node, matched_temp)

        source_uv_sets = cmds.polyUVSet(node, query=True, allUVSets=True) or []
        target_uv_sets = cmds.polyUVSet(
            matched_temp, query=True, allUVSets=True
        ) or []

        for source_name in source_uv_sets:
            if source_name not in target_uv_sets:
                missing_uvmaps.setdefault(matched_temp, []).append(source_name)
                if add_uvmaps:
                    cmds.polyUVSet(
                        matched_temp, create=True, uvSet=source_name
                    )
                else:
                    continue

            _copy_uv_set(node, source_name, matched_temp, source_name)

        if remove_uvmaps:
            target_uv_sets = cmds.polyUVSet(
                matched_temp, query=True, allUVSets=True
            ) or []
            for target_name in target_uv_sets:
                if target_name not in source_uv_sets:
                    extra_uvmaps.setdefault(matched_temp, []).append(
                        target_name
                    )
                    cmds.polyUVSet(
                        matched_temp, delete=True, uvSet=target_name
                    )

    return UVTransferResult(missing_objects, missing_uvmaps)


def _copy_uv_set(
    source_node: str,
    source_uv: str,
    target_node: str,
    target_uv: str,
):
    """Copy a UV set from one mesh to another using the Maya API.

    Uses ``MFnMesh.getUVs`` / ``MFnMesh.setUVs`` — that operates on the
    UV coordinate array directly and is orders of magnitude faster than
    per-vertex ``polyEditUV`` calls.
    """
    source_shape = _resolve_mesh_shape(source_node, source_uv)
    target_shape = _resolve_mesh_shape(target_node, target_uv)

    if source_shape is None or target_shape is None:
        logger.warning(
            f"Could not resolve mesh shapes for UV transfer: "
            f"{source_node} / {target_node}"
        )
        return

    source_fn = om.MFnMesh(source_shape)
    target_fn = om.MFnMesh(target_shape)

    try:
        u_array, v_array = source_fn.getUVs(source_uv)
    except RuntimeError as e:
        logger.warning(
            f"Could not read UV set '{source_uv}' on {source_node}: {e}"
        )
        return

    target_sets = set(target_fn.getUVSetNames())
    if target_uv not in target_sets:
        target_fn.createUVSet(target_uv)

    try:
        target_fn.setUVs(u_array, v_array, target_uv)
    except RuntimeError as e:
        logger.warning(
            f"Could not write UV set '{target_uv}' on {target_node}: {e} "
            f"(source has {len(u_array)} UVs)"
        )


def _resolve_mesh_shape(
    node_name: str, uv_set: str
) -> Optional[om.MDagPath]:
    """Resolve a node name to the mesh shape DAG path.

    Returns None if the node doesn't resolve to a mesh.
    """
    sel = om.MSelectionList()
    try:
        sel.add(node_name)
    except RuntimeError:
        return None

    dag = sel.getDagPath(0)
    if dag.hasFn(om.MFn.kTransform):
        try:
            dag.extendToShape()
        except RuntimeError:
            return None
    if not dag.hasFn(om.MFn.kMesh):
        return None
    return dag