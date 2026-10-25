"""Command for loading an existing file into RizomUV."""

import logging

import maya.OpenMaya as om1                # API 1.0: MSyntax
import maya.OpenMayaMPx as ompx            # API 1.0: MPxCommand
import maya.cmds as cmds

from ..classes.exceptions.rizom_exceptions import RizomLinkUnsupportedError
from ..classes.rizom.modern.rizom_link import RizomLink
from ..file_access import get_data_directory
from ..utils import addon_utils
from ..utils.exceptions_utils import report_and_log_exception

logger = logging.getLogger(__name__)


class LoadInRizomCommand(ompx.MPxCommand):
    """Load an existing file into RizomUV without exporting meshes."""

    COMMAND_NAME = "rizomLoad"

    def __init__(self):
        super().__init__()

    # ---------------------------------------------------------------------
    # Syntax
    # ---------------------------------------------------------------------

    @classmethod
    def _syntax(cls):
        return om1.MSyntax()

    # ---------------------------------------------------------------------
    # Load logic
    # ---------------------------------------------------------------------

    def _load_in_rizom(self, prefs, data_dir):
        if prefs.use_livelink:
            try:
                link = RizomLink(
                    prefs.rizom_path,
                    data_dir,
                    prefs.connection_timeout,
                )
                link.connection_manager.connect_or_start()
                link.files.load_file(
                    None,
                    prefs.export_format,
                    prefs.up_axis,
                    prefs.forward_axis,
                    prefs.weld_uvs,
                    prefs.normals,
                )
                if prefs.export_texture and prefs.rizom_texture:
                    link.api.load_user_texture(
                        prefs.rizom_texture,
                        prefs.background_texture,
                        prefs.uv_texture,
                        prefs.mesh_texture,
                    )
            except RizomLinkUnsupportedError as e:
                logger.info(
                    "RizomUV version does not support RizomUVLink; "
                    "live link disabled."
                )
                logger.error(e)
                prefs.use_livelink = False
                self._load_in_rizom(prefs, data_dir)
        else:
            from ..classes.rizom.legacy.rizom_legacy import RizomLegacy

            legacy = RizomLegacy(
                prefs.rizom_path,
                data_dir,
                prefs.connection_timeout,
            )
            legacy.connect_or_start()

            files = {
                "OBJ": data_dir.mesh_files.obj,
                "FBX": data_dir.mesh_files.fbx,
                "USD": data_dir.mesh_files.usd,
            }
            mesh_file = files.get(prefs.export_format)
            if mesh_file is None or not mesh_file.exists():
                raise RuntimeError(
                    f"No {prefs.export_format} file found to load. "
                    "Run an export first to populate the transfer file."
                )

            legacy.load_file(uvmap="", file_format=prefs.export_format)

    # ---------------------------------------------------------------------
    # doIt
    # ---------------------------------------------------------------------

    def doIt(self, args):
        prefs = addon_utils.get_prefs()
        data_dir = get_data_directory()

        if not prefs.rizom_path:
            raise RuntimeError(
                "Rizom path not set in the addon preferences."
            )

        try:
            self._load_in_rizom(prefs, data_dir)
        except Exception as e:
            report_and_log_exception(e)
            raise RuntimeError(str(e))

        cmds.inViewMessage(
            amg=f"Loading {prefs.export_format} file into RizomUV.",
            pos="midCenter",
            fade=True,
        )

    # ---------------------------------------------------------------------
    # Plugin registration
    # ---------------------------------------------------------------------

    @classmethod
    def _creator(cls):
        return LoadInRizomCommand()

    @classmethod
    def register(cls, plugin_fn):
        plugin_fn.registerCommand(cls.COMMAND_NAME, cls._creator, cls._syntax)

    @classmethod
    def unregister(cls, plugin_fn):
        try:
            plugin_fn.deregisterCommand(cls.COMMAND_NAME)
        except RuntimeError:
            pass


LoadInRizom = LoadInRizomCommand