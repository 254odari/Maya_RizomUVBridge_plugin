"""Command for exporting mesh items to RizomUV."""

import logging
from typing import List, Optional

import maya.OpenMaya as om1                # API 1.0: MSyntax, MArgParser
import maya.OpenMayaMPx as ompx            # API 1.0: MPxCommand
import maya.cmds as cmds

from ..classes.exceptions.rizom_exceptions import (
    RizomLinkModuleNotFoundError,
    RizomLinkUnsupportedError,
)
from ..classes.exceptions.validation_exceptions import (
    InvalidObjectNamesError,
    InvalidUVSetNamesError,
    InvalidUVSetsError,
)
from ..classes.rizom.legacy.rizom_legacy import RizomLegacy
from ..classes.rizom.modern.rizom_link import RizomLink
from ..file_access import get_data_directory
from ..properties.property_groups import RizomBridgeUVMaps
from ..utils import (
    addon_utils,
    io_utils,
    mesh_utils,
    object_utils,
    selection_utils,
    usd_utils,
    uv_utils,
    validation_utils,
)
from ..utils.hooks.usd_hook import UsdHookRizom

logger = logging.getLogger(__name__)


class ExportToRizomCommand(ompx.MPxCommand):
    """Export selected meshes and open the resulting file in RizomUV."""

    COMMAND_NAME = "rizomExport"

    def __init__(self):
        super().__init__()
        self._skip_confirm = False
        # Populated in doIt — instance state survives the command invocation.
        self.data_dir = None

    # ---------------------------------------------------------------------
    # Syntax / argument parsing
    # ---------------------------------------------------------------------

    @classmethod
    def _syntax(cls):
        syntax = om1.MSyntax()
        syntax.addFlag("-sc", "-skipConfirm", om1.MSyntax.kBoolean)
        return syntax

    def parseArguments(self, args):
        arg_data = om1.MArgParser(self.syntax(), args)
        if arg_data.isFlagSet("-sc"):
            self._skip_confirm = arg_data.flagArgumentBool("-sc", 0)

    # ---------------------------------------------------------------------
    # Validation
    # ---------------------------------------------------------------------

    def _validate(
        self,
        prefs,
        active_object: str,
        target_objects: List[str],
        all_objects: Optional[List[str]] = None,
    ) -> bool:
        try:
            validation_utils.assert_valid_for_export(
                active_object,
                target_objects,
                prefs.export_format,
                all_objects,
            )
        except InvalidUVSetNamesError as e:
            cmds.warning(
                "The active object has invalid UV map names "
                "(see script editor)."
            )
            validation_utils.log_invalid_uvmap_names(e.invalid_uvmaps)
            return False
        except InvalidUVSetsError as e:
            cmds.warning(
                "Selected objects do not all have the same UV map names "
                "(see script editor)."
            )
            validation_utils.log_non_matching_uvmaps(e.results)
            return False
        except InvalidObjectNamesError as e:
            validation_utils.log_invalid_object_names(e.results)
            if prefs.fix_object_names:
                object_utils.fix_object_names(e.results)
                logger.info("Object names were automatically fixed.")
                return True
            cmds.warning(
                "Some objects have invalid names (see script editor)."
            )
            return False
        return True

    # ---------------------------------------------------------------------
    # Pre-export actions
    # ---------------------------------------------------------------------

    def _run_pre_export_actions(self, prefs, target_objects: List[str]):
        active_uvmap = RizomBridgeUVMaps.get_active()

        if prefs.export_action == "USE_SEAMS" and active_uvmap:
            for node in target_objects:
                uv_utils.unwrap_uvs(
                    active_uvmap,
                    node,
                    prefs.target_all_uvmaps,
                )

        if prefs.triangulate:
            mesh_utils.triangulate(target_objects)

        if prefs.apply_modifiers:
            object_utils.apply_modifiers(target_objects)

    # ---------------------------------------------------------------------
    # Export
    # ---------------------------------------------------------------------

    def _export(self, prefs, objects: List[str]):
        cmds.select(objects, replace=True)

        fmt = prefs.export_format.upper()
        if fmt == "OBJ":
            io_utils.export_obj(
                str(self.data_dir.mesh_files.obj),
                prefs.forward_axis,
                prefs.up_axis,
            )
        elif fmt == "FBX":
            io_utils.export_fbx(
                str(self.data_dir.mesh_files.fbx),
                prefs.forward_axis,
                prefs.up_axis,
            )
        elif fmt == "USD":
            usd_utils.export_usd_props(objects)
            chaser = (
                usd_utils.CHASER_NAME if usd_utils.register_hook() else None
            )
            with UsdHookRizom.enabled():
                io_utils.export_usd(
                    str(self.data_dir.mesh_files.usd),
                    prefs.up_axis,
                    chaser=chaser,
                )

    # ---------------------------------------------------------------------
    # Send to RizomUV
    # ---------------------------------------------------------------------

    def _send_to_rizom(self, prefs, uvmaps: List[str]):
        if prefs.use_livelink:
            try:
                link = RizomLink(
                    prefs.rizom_path,
                    self.data_dir,
                    prefs.connection_timeout,
                )
                link.connection_manager.connect_or_start()

                active_uvmap = RizomBridgeUVMaps.get_active() or ""
                link.files.load_file(
                    active_uvmap,
                    prefs.export_format,
                    prefs.up_axis,
                    prefs.forward_axis,
                    prefs.weld_uvs,
                    prefs.normals,
                )

                if prefs.rizom_texture and prefs.export_texture:
                    link.api.load_user_texture(
                        prefs.rizom_texture,
                        prefs.background_texture,
                        prefs.uv_texture,
                        prefs.mesh_texture,
                    )

                self._run_post_export_action(prefs, uvmaps, link)
            except (RizomLinkUnsupportedError, RizomLinkModuleNotFoundError) as e:
                prefs.use_livelink = False
                logger.info(
                    "RizomUV version does not support RizomUVLink; "
                    "live link disabled."
                )
                logger.error(e)
                self._send_to_rizom(prefs, uvmaps)
        else:
            legacy = RizomLegacy(
                prefs.rizom_path,
                self.data_dir,
                prefs.connection_timeout,
            )
            legacy.connect_or_start()
            legacy.load_file(uvmaps[0] if uvmaps else "", prefs.export_format)

    def _run_post_export_action(
        self,
        prefs,
        uvmaps: List[str],
        rizom_link: Optional[RizomLink],
    ):
        if prefs.export_action == "RESET_UVS" and rizom_link is not None:
            rizom_link.uvmaps.reset_uvmaps(uvmaps)

    # ---------------------------------------------------------------------
    # doIt
    # ---------------------------------------------------------------------

    def doIt(self, args):
        self.parseArguments(args)

        prefs = addon_utils.get_prefs()
        self.data_dir = get_data_directory()

        if not prefs.rizom_path:
            raise RuntimeError(
                "Rizom path not set in the addon preferences."
            )

        selection_utils.deselect_non_exportable_objects()
        active = _get_active_mesh_or_empty()
        if not active:
            raise RuntimeError("No active mesh or group selected.")

        target_objects = selection_utils.get_objects_for_export(
            active, prefs.exclude_clones
        )
        target_empties = selection_utils.get_selected_empties()

        if not target_objects:
            raise RuntimeError("No mesh objects selected for export.")

        active_mesh = active if _is_mesh(active) else target_objects[0]

        if not self._skip_confirm:
            if object_utils.has_unapplied_scale(target_objects):
                if not _confirm(
                    "Unapplied Scale Detected",
                    "Some objects have unapplied scale, "
                    "this may cause issues in RizomUV. Continue?",
                ):
                    raise RuntimeError("Export cancelled by user.")

            if prefs.confirm_export:
                if not _confirm(
                    "Confirm Export",
                    f"This will overwrite the existing RizomUV "
                    f"{prefs.export_format} file.",
                ):
                    raise RuntimeError("Export cancelled by user.")

        if not self._validate(
            prefs,
            active_mesh,
            target_objects,
            target_objects + target_empties,
        ):
            raise RuntimeError("Validation failed.")

        self._run_pre_export_actions(prefs, target_objects)

        uvmaps = uv_utils.get_uv_set_names(active_mesh)

        self._export(prefs, target_objects + target_empties)
        self._send_to_rizom(prefs, uvmaps)

        cmds.inViewMessage(
            amg=f"Exported {len(target_objects)} objects to RizomUV.",
            pos="midCenter",
            fade=True,
        )

    # ---------------------------------------------------------------------
    # Plugin registration
    # ---------------------------------------------------------------------

    @classmethod
    def _creator(cls):
        return ExportToRizomCommand()

    @classmethod
    def register(cls, plugin_fn):
        plugin_fn.registerCommand(cls.COMMAND_NAME, cls._creator, cls._syntax)

    @classmethod
    def unregister(cls, plugin_fn):
        try:
            plugin_fn.deregisterCommand(cls.COMMAND_NAME)
        except RuntimeError:
            pass


ExportToRizom = ExportToRizomCommand


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_mesh(node: str) -> bool:
    shapes = cmds.listRelatives(node, shapes=True, fullPath=True) or []
    return any(cmds.nodeType(s) == "mesh" for s in shapes)


def _get_active_mesh_or_empty() -> str:
    """Return the last selected node, or empty string if nothing selected."""
    selection = cmds.ls(selection=True, long=True) or []
    return selection[-1] if selection else ""


def _confirm(title: str, message: str) -> bool:
    result = cmds.confirmDialog(
        title=title,
        message=message,
        button=["Continue", "Cancel"],
        defaultButton="Continue",
        cancelButton="Cancel",
        dismissString="Cancel",
    )
    return result == "Continue"