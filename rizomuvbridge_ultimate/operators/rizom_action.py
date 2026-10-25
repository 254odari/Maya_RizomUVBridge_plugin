"""Command to run remote actions in RizomUV via the RizomUVLink module."""

import maya.OpenMaya as om1                # API 1.0: MSyntax, MArgParser
import maya.OpenMayaMPx as ompx            # API 1.0: MPxCommand
import maya.cmds as cmds

from .. import addon_constants
from ..classes.exceptions.rizom_exceptions import RizomLinkUnsupportedError
from ..classes.rizom.modern.rizom_link import RizomLink
from ..file_access import get_data_directory
from ..utils import addon_utils


class RizomActionCommand(ompx.MPxCommand):
    """Maya command equivalent of the Blender RizomAction operator."""

    COMMAND_NAME = "rizomAction"

    ACTION_ITEMS = (
        addon_constants.ACTIONS["RESET_UVS"],
        addon_constants.ACTIONS["SHARP_EDGES"],
        addon_constants.ACTIONS["MOSAIC"],
        addon_constants.ACTIONS["PELT"],
        addon_constants.ACTIONS["BOX"],
        ("CLOSE", "Close Rizom", "Close RizomUV"),
    )

    def __init__(self):
        super().__init__()
        self.action: str = "RESET_UVS"

    # --- syntax ----------------------------------------------------------

    @classmethod
    def _syntax(cls):
        syntax = om1.MSyntax()
        syntax.addFlag("-a", "-action", om1.MSyntax.kString)
        return syntax

    def parseArguments(self, args):
        arg_data = om1.MArgParser(self.syntax(), args)
        if arg_data.isFlagSet("-a"):
            self.action = arg_data.flagArgumentString("-a", 0)

    # --- helpers ---------------------------------------------------------

    def _reset_uvmaps(self, rizom: RizomLink, prefs):
        if prefs.target_all_uvmaps:
            uvmaps = rizom.uvmaps.get_uvmap_names()
            rizom.uvmaps.reset_uvmaps(uvmaps)
        else:
            current_uvmap = rizom.uvmaps.get_selected_uvmap()
            rizom.uvmaps.reset_uvmap(current_uvmap)

    # --- doIt ------------------------------------------------------------

    def doIt(self, args):
        self.parseArguments(args)

        prefs = addon_utils.get_prefs()
        data_dir = get_data_directory()

        if not prefs.use_livelink:
            raise RuntimeError("LiveLink is not enabled.")

        try:
            rizom = RizomLink(
                prefs.rizom_path,
                data_dir,
                prefs.connection_timeout,
            )
        except RizomLinkUnsupportedError as e:
            raise RuntimeError(
                "Your RizomUV version does not support RizomUVLink; "
                "live link is disabled."
            ) from e

        if not rizom.connection_manager.connect():
            raise RuntimeError(
                "RizomLink is not connected; please connect to RizomUV."
            )

        if self.action == "RESET_UVS":
            self._reset_uvmaps(rizom, prefs)
        elif self.action == "CLOSE":
            rizom.quit()
        # SHARP_EDGES / MOSAIC / PELT / BOX are executed inside RizomUV via
        # rizom_script.py — no Maya-side work needed here.

    # --- plugin registration ---------------------------------------------

    @classmethod
    def _creator(cls):
        return RizomActionCommand()

    @classmethod
    def register(cls, plugin_fn):
        plugin_fn.registerCommand(cls.COMMAND_NAME, cls._creator, cls._syntax)

    @classmethod
    def unregister(cls, plugin_fn):
        try:
            plugin_fn.deregisterCommand(cls.COMMAND_NAME)
        except RuntimeError:
            pass


RizomAction = RizomActionCommand