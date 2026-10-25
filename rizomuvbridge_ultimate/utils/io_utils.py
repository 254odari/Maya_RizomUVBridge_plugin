"""Functions for exporting/importing meshes between Maya and RizomUV."""

import logging
from typing import List, Optional

import maya.cmds as cmds

from ..classes.exceptions.io_exceptions import FileImportError
from ..file_access import DataDirectory
from ..types import Axis, ExportTypes

logger = logging.getLogger(__name__)


# Maya FBX/OBJ plugins accept these axis tokens.
AXIS_CONVERSION: dict = {
    "X": "x",
    "Y": "y",
    "Z": "z",
    "NEGATIVE_X": "-x",
    "NEGATIVE_Y": "-y",
    "NEGATIVE_Z": "-z",
}


# File translators are shipped as separate plug-ins. They are normally loaded
# in a full Maya session, but mayapy / batch sessions start with none of them,
# so load them on demand before handing a file to ``cmds.file``.
_TRANSLATOR_PLUGINS = {
    "OBJ": ("objExport",),
    "FBX": ("fbxmaya",),
    "USD": ("mayaUsdPlugin",),
}


def _ensure_translator(format: ExportTypes) -> None:
    for plugin_name in _TRANSLATOR_PLUGINS.get(format.upper(), ()):
        try:
            cmds.loadPlugin(plugin_name, quiet=True)
        except RuntimeError as e:
            logger.warning(
                f"Could not load {plugin_name!r} for {format} IO: {e}"
            )


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export_obj(path: str, forward_axis: Axis, up_axis: Axis):
    """Export the current selection to OBJ."""
    _ensure_translator("OBJ")
    cmds.file(
        path,
        force=True,
        options=(
            "groups=1;ptgroups=1;materials=0;smoothing=1;normals=1;"
            f"upAxis={AXIS_CONVERSION[up_axis]};"
            f"forwardAxis={AXIS_CONVERSION[forward_axis]}"
        ),
        typ="OBJexport",
        exportSelected=True,
        preserveReferences=False,
    )


def export_fbx(path: str, forward_axis: Axis, up_axis: Axis):
    """Export the current selection to FBX."""
    _ensure_translator("FBX")
    cmds.file(
        path,
        force=True,
        options=(
            "groups=1;ptgroups=1;materials=0;smoothing=1;normals=1;"
            f"upAxis={AXIS_CONVERSION[up_axis]};"
            f"forwardAxis={AXIS_CONVERSION[forward_axis]}"
        ),
        typ="FBX export",
        exportSelected=True,
        preserveReferences=False,
    )


def export_usd(path: str, up_axis: Axis, chaser: Optional[str] = None):
    """Export the current selection to USD.

    Args:
        path: Destination file path.
        up_axis: Stage up axis.
        chaser: Optional mayaUsd chaser name to run during the export.

    """
    _ensure_translator("USD")
    kwargs = {
        "file": path,
        "selection": True,
        "mergeTransformAndShape": True,
        "exportUVs": True,
        "exportColorSets": False,
        "exportMaterials": False,
        "upAxis": AXIS_CONVERSION[up_axis],
    }
    if chaser:
        kwargs["chaser"] = [chaser]
    cmds.mayaUSDExport(**kwargs)


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

_IMPORT_TYPE = {
    "OBJ": "OBJ",
    "FBX": "FBX",
}

# ``mo=1`` preserves object names on OBJ import. With the default (``mo=0``)
# every object is renamed to ``polySurfaceN``, which makes it impossible to
# match the imported meshes back to the scene objects they came from.
_IMPORT_OPTIONS = {
    "OBJ": "mo=1",
    "FBX": "",
}


def _usd_root_prim_paths(file_path: str) -> List[str]:
    """Return the root prim paths of a USD file.

    ``mayaUSDImport`` imports only the default root when no ``primPath`` is
    given, so multi-object transfer files need one import per root prim.

    """
    try:
        from pxr import Usd  # type: ignore

        stage = Usd.Stage.Open(file_path)
        if stage:
            return [
                prim.GetPath().pathString
                for prim in stage.GetPseudoRoot().GetChildren()
            ]
    except Exception as e:
        logger.warning(f"Could not read USD root prims from {file_path}: {e}")
    return []


def import_file(
    format: ExportTypes,
    data_dir: DataDirectory,
    chaser: Optional[str] = None,
) -> List[str]:
    """Import a file into Maya and return the imported mesh transforms.

    Args:
        format: One of ``"FBX"`` | ``"OBJ"`` | ``"USD"``.
        data_dir: The bridge's data directory model.
        chaser: Optional mayaUsd chaser name to run during a USD import.

    Returns:
        Long DAG paths of the mesh transforms created by the import.

    Raises:
        FileImportError: If the import still fails after several retries.

    """
    format = format.upper()
    mesh_dir = data_dir.mesh_files
    path_map = {
        "OBJ": str(mesh_dir.obj),
        "FBX": str(mesh_dir.fbx),
        "USD": str(mesh_dir.usd),
    }
    file_path = path_map[format]

    _ensure_translator(format)

    pre_meshes = set(cmds.ls(type="mesh", long=True) or [])

    def attempt_import():
        if format == "USD":
            kwargs = {"file": file_path}
            if chaser:
                kwargs["chaser"] = [chaser]

            roots = _usd_root_prim_paths(file_path)
            if roots:
                for root in roots:
                    cmds.mayaUSDImport(primPath=root, **kwargs)
            else:
                cmds.mayaUSDImport(**kwargs)
            return

        kwargs = {
            "i": True,
            "ignoreVersion": True,
            "typ": _IMPORT_TYPE[format],
            "returnNewNodes": False,
        }
        if _IMPORT_OPTIONS[format]:
            kwargs["options"] = _IMPORT_OPTIONS[format]
        cmds.file(file_path, **kwargs)

    # Maya raises RuntimeError for a variety of transient conditions during
    # import — file locks from RizomUV, antivirus scans on Windows, etc.
    # Retry a few times using Maya's idle loop rather than blocking.
    max_attempts = 5
    last_exception = None

    for attempt in range(max_attempts):
        try:
            attempt_import()
            last_exception = None
            break
        except RuntimeError as e:
            last_exception = e
            logger.warning(
                f"Import attempt {attempt + 1}/{max_attempts} failed: {e}"
            )
            # Non-blocking yield so Maya stays responsive.
            cmds.refresh()

    if last_exception is not None:
        raise FileImportError() from last_exception

    post_meshes = set(cmds.ls(type="mesh", long=True) or [])
    imported: List[str] = []
    for shape in sorted(post_meshes - pre_meshes):
        parents = cmds.listRelatives(shape, parent=True, fullPath=True) or []
        if parents and parents[0] not in imported:
            imported.append(parents[0])

    return imported