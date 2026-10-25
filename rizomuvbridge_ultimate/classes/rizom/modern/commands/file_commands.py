"""Handles file operations in RizomUV."""

import logging
import os
from typing import Optional, cast

from .....file_access import DataDirectory
from .....types import ExportTypes
from ....exceptions.io_exceptions import InvalidFileFormatError
from ..base.rizom_api import RizomApi
from .select_commands import SelectCommands

logger = logging.getLogger(__name__)


class FileCommands:
    def __init__(self, api: RizomApi, select: SelectCommands, data_dir: DataDirectory):
        self.api = api
        self.select = select

        self.files = {
            "OBJ": data_dir.mesh_files.obj,
            "FBX": data_dir.mesh_files.fbx,
            "USD": data_dir.mesh_files.usd,
        }

    def _set_up_axis(self, up_axis: str, forward_axis: str):
        """Set the Rizom viewport up axis based on the user preference."""
        if up_axis in ("NEGATIVE_Z", "Z"):
            self.api.set({"Path": "Prefs.Viewport.Viewport3D.UpVector", "Value": "z"})
        elif up_axis in ("NEGATIVE_Y", "Y"):
            self.api.set({"Path": "Prefs.Viewport.Viewport3D.UpVector", "Value": "y"})
        elif up_axis in ("NEGATIVE_X", "X"):
            self.api.set({"Path": "Prefs.Viewport.Viewport3D.UpVector", "Value": "x"})

    def get_file(self) -> str:
        """Return the path of the file currently loaded in RizomUV.

        Returns an empty string when nothing is loaded — RizomUV reports
        ``Prefs.LastLoadedFile`` as ``""`` in that state, which is a normal
        condition (fresh launch, or a scene that was cleared).

        """
        value = self.api.get("Prefs.LastLoadedFile")
        return value if isinstance(value, str) else ""

    def save_file(self):
        """Save the currently loaded file.

        When RizomUV has no file loaded, there is nothing to save. Skipping
        with a warning is the correct behavior — raising here would turn a
        normal "empty scene" state into a hard error and mask the more
        actionable message about needing to export first.

        """
        loaded_file = self.get_file()
        if not loaded_file:
            logger.warning(
                "RizomUV has no file loaded; skipping save. "
                "Run Export first to load a mesh into RizomUV."
            )
            return

        # Ensure the file suffix is not set so import works properly.
        self.api.set({"Path": "Prefs.FileSuffix", "Value": ""})
        self.api.save(self.get_file_type(), loaded_file)

    def get_file_type(self) -> ExportTypes:
        """Return the type of the file currently loaded in RizomUV.

        Raises:
            InvalidFileFormatError: If no file is loaded, or the loaded
                file's extension is not one of ``FBX`` / ``OBJ`` / ``USD``.

        """
        loaded_file = self.get_file()

        if not loaded_file:
            raise InvalidFileFormatError(
                "RizomUV has no file loaded. Run Export first to load a "
                "mesh, or open a file manually in RizomUV."
            )

        extension = os.path.splitext(loaded_file)[1][1:][:3].upper()
        if extension not in ("FBX", "OBJ", "USD"):
            raise InvalidFileFormatError(
                f"Unsupported extension '{extension}' on file: {loaded_file}"
            )
        return cast(ExportTypes, extension)

    def set_texture_file(self, texture_path: str):
        """Set the texture file in RizomUV."""
        self.api.set({
            "Path": "Lib.Scene.Textures.List[0].File.Path",
            "Value": texture_path,
            "UndoAble": False,
        })

    def load_file(
        self,
        uvmap: Optional[str],
        file_format: ExportTypes,
        up_axis: str,
        forward_axis: str,
        weld_uvs: bool,
        normals: bool,
    ):
        """Load a file into RizomUV via the LiveLink API.

        RizomUV's ``Load`` task expects its parameters as a **nested dict**
        (``{"File": {"Path": ...}}``). The flat dotted form
        (``{"File.Path": ...}``) is the legacy file-watching protocol's
        shape and is silently ignored by the LiveLink API.

        Args:
            uvmap: The name of the UV map to select after loading. May be
                ``None`` or an empty string, in which case the current UV
                set is left untouched.
            file_format: The format of the file to load
                (``"FBX"`` | ``"OBJ"`` | ``"USD"``).
            up_axis: The up axis preference to apply to the RizomUV viewport.
            forward_axis: The forward axis preference (currently unused by
                RizomUV's importer, but accepted for parity).
            weld_uvs: Whether to auto-weld overlapping UV edges on import.
            normals: Whether to import file user normals.

        """
        params = {
            "File": {
                "Path": str(self.files[file_format]),
                "XYZUVW": True,
                "UVWProps": True,
                "ImportGroups": True,
                "Normals": bool(normals),
                "AutoWeld": bool(weld_uvs),
                "Meta": True,
            },
            "__Focus": True,
        }

        # FBX-specific options.
        if file_format == "FBX":
            params["File"]["FBX"] = {"UseUVSetNames": True}

        self.api.load(params)
        self._set_up_axis(up_axis, forward_axis)
        logger.info(f"{file_format} file loaded into RizomUV")

        if file_format == "OBJ":
            self.api.set({
                "Path": "Lib.Scene.Settings.Unit",
                "Value": "m",
                "UndoAble": False,
            })
            if uvmap:
                self.api.uv_set({"Mode": "Rename", "Name": uvmap})

        if uvmap:
            self.select.select_uvmap(uvmap)
            logger.info(f"Active UV map set to {uvmap} in RizomUV")