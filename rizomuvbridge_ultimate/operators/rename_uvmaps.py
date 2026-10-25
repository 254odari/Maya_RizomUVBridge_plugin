"""Command for batch renaming UV maps.

Main use is quickly fixing UV map names that are invalid in RizomUV.
"""

from typing import Dict, List

import maya.OpenMaya as om1              # API 1.0: MSyntax, MArgParser
import maya.OpenMayaMPx as ompx          # API 1.0: MPxCommand
import maya.cmds as cmds

from ..classes.exceptions.validation_exceptions import (
    InvalidUVSetNamesError,
    InvalidUVSetsError,
)
from ..utils import selection_utils, uv_utils, validation_utils


class RenameUVMapsCommand(ompx.MPxCommand):
    """Maya command equivalent of the Blender RenameUVMaps operator."""

    COMMAND_NAME = "rizomRenameUVMaps"

    def __init__(self):
        super().__init__()
        self.fix_names: bool = True
        self.remove_extra_uvmaps: bool = True
        self.uvmap_names: List[str] = []
        self._undo_data: Dict[str, List[str]] = {}

    # --- syntax ----------------------------------------------------------

    @classmethod
    def _syntax(cls):
        syntax = om1.MSyntax()
        syntax.addFlag("-fn", "-fixNames", om1.MSyntax.kBoolean)
        syntax.addFlag("-re", "-removeExtra", om1.MSyntax.kBoolean)
        syntax.addFlag("-n", "-names", om1.MSyntax.kString)
        return syntax

    def parseArguments(self, args):
        arg_data = om1.MArgParser(self.syntax(), args)
        if arg_data.isFlagSet("-fn"):
            self.fix_names = arg_data.flagArgumentBool("-fn", 0)
        if arg_data.isFlagSet("-re"):
            self.remove_extra_uvmaps = arg_data.flagArgumentBool("-re", 0)
        if arg_data.isFlagSet("-n"):
            names_str = arg_data.flagArgumentString("-n", 0)
            self.uvmap_names = [n.strip() for n in names_str.split(",") if n.strip()]

    # --- execution -------------------------------------------------------

    def isUndoable(self):
        return True

    def doIt(self, args):
        self.parseArguments(args)

        selected = selection_utils.get_selected_meshes()
        if not selected:
            raise RuntimeError("No mesh objects selected.")

        active = _get_active_mesh_transform()
        if not active:
            raise RuntimeError("No active mesh.")

        # Snapshot for undo.
        self._undo_data = {}
        for node in set(selected) | {active}:
            names = cmds.polyUVSet(node, query=True, allUVSets=True) or []
            self._undo_data[node] = list(names)

        # Rename the active object's UV sets to the user-supplied names.
        active_uv_sets = cmds.polyUVSet(active, query=True, allUVSets=True) or []
        if self.uvmap_names:
            for current, new in zip(active_uv_sets, self.uvmap_names):
                if current != new:
                    cmds.polyUVSet(active, rename=True, uvSet=current, newUVSet=new)

        # Validate / fix.
        try:
            validation_utils.assert_valid_uvmap_names(active)
        except InvalidUVSetNamesError as e:
            if self.fix_names:
                validation_utils.fix_invalid_uvmap_names(active, e.invalid_uvmaps)
            else:
                validation_utils.log_invalid_uvmap_names(e.invalid_uvmaps)
                raise RuntimeError(str(e))

        base_uvs = set(uv_utils.get_uv_set_names(active))

        for node in selected:
            if node == active:
                continue
            try:
                validation_utils.assert_matching_uvmap_sets_single(base_uvs, node)
            except InvalidUVSetsError:
                validation_utils.fix_nonmatching_uvmap_sets(
                    list(base_uvs), node, self.remove_extra_uvmaps
                )

    # --- undo ------------------------------------------------------------

    def undoIt(self):
        for node, names in self._undo_data.items():
            if not cmds.objExists(node):
                continue
            current = cmds.polyUVSet(node, query=True, allUVSets=True) or []
            for cur, orig in zip(current, names):
                if cur != orig:
                    cmds.polyUVSet(node, rename=True, uvSet=cur, newUVSet=orig)

    def redoIt(self):
        pass

    # --- plugin registration ---------------------------------------------

    @classmethod
    def _creator(cls):
        return RenameUVMapsCommand()

    @classmethod
    def register(cls, plugin_fn):
        plugin_fn.registerCommand(cls.COMMAND_NAME, cls._creator, cls._syntax)

    @classmethod
    def unregister(cls, plugin_fn):
        try:
            plugin_fn.deregisterCommand(cls.COMMAND_NAME)
        except RuntimeError:
            pass


RenameUVMaps = RenameUVMapsCommand


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_active_mesh_transform() -> str:
    """Return the active mesh transform, or empty string if none.

    Maya has no dedicated "active object" query. The convention is that the
    last item of the current selection is the active object.
    """
    selection = cmds.ls(selection=True, long=True) or []
    for node in reversed(selection):
        shapes = cmds.listRelatives(node, shapes=True, fullPath=True) or []
        if any(cmds.nodeType(s) == "mesh" for s in shapes):
            return node
    return ""


def show_rename_dialog():
    """Prompt the user for UV names and options, then run the command."""
    result = cmds.promptDialog(
        title="Rename UV Maps",
        message="Comma-separated UV set names (leave blank to keep):",
        button=["Rename", "Cancel"],
        defaultButton="Rename",
        cancelButton="Cancel",
        dismissString="Cancel",
    )
    if result != "Rename":
        return

    names = cmds.promptDialog(query=True, text=True) or ""

    fix = cmds.confirmDialog(
        title="Options",
        message="Automatically fix invalid names?",
        button=["Yes", "No"],
        defaultButton="Yes",
    )
    remove = cmds.confirmDialog(
        title="Options",
        message="Remove extra UV sets on other meshes?",
        defaultButton="Yes",
        button=["Yes", "No"],
    )

    cmds.rizomRenameUVMaps(
        fixNames=(fix == "Yes"),
        removeExtra=(remove == "Yes"),
        names=names,
    )