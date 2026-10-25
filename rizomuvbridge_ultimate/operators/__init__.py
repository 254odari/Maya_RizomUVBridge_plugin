"""Operators module (Maya edition)."""

from .rename_uvmaps import RenameUVMaps
from .rizom_action import RizomAction
from .rizom_export import ExportToRizom
from .rizom_import import ImportFromRizom
from .rizom_load import LoadInRizom

OPERATORS = (
    ExportToRizom,
    ImportFromRizom,
    LoadInRizom,
    RizomAction,
    RenameUVMaps,
)


def register(plugin):
    """Register all operator commands with the given MFnPlugin."""
    for op in OPERATORS:
        op.register(plugin)


def unregister(plugin):
    """Deregister all operator commands."""
    for op in reversed(OPERATORS):
        try:
            op.unregister(plugin)
        except RuntimeError:
            # Command already gone (plugin reload). Ignore.
            pass