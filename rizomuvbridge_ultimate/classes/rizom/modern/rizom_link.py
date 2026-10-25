"""Wrapper class for the RizomUVLink API, includes some extended functionality.

Maya port note: the class is host-agnostic (no ``bpy`` imports). Two changes
from the Blender original:

1. The old ``platform.system() != "Windows"`` guard has been replaced with
   an actual import probe. If the native extension loads, the platform is
   supported; if it doesn't, ``RizomLinkUnsupportedError`` is raised. This
   is more accurate than a hard-coded OS check.

2. ``connection_timeout`` is stored on ``self`` so callers can inspect it
   (matches the behaviour of ``RizomLegacy``).
"""

import logging
from typing import Literal

from ....file_access import DataDirectory
from ....utils.rizom_utils import validate_and_transform_rizom_path
from ...data.import_models import RizomData
from ...exceptions.rizom_exceptions import RizomLinkUnsupportedError
from ..rizom_base import RizomBase
from .base.rizom_api import RizomApi
from .base.rizom_connection_manager import RizomConnectionManager
from .base.rizom_module_loader import RizomModuleLoader
from .commands.file_commands import FileCommands
from .commands.object_commands import ObjectCommands
from .commands.select_commands import SelectCommands
from .commands.uvmap_commands import UvmapCommands

logger = logging.getLogger(__name__)


def _texel_density(
    tex_den: float,
    unit: Literal["km", "m", "dm", "cm", "mm", "in", "ft", "yd", "mi"],
) -> float:
    """Convert texel density value to different units of measurement.

    Args:
       tex_den: The texel density value to convert.
       unit: The unit to convert to.

    Returns:
       float: The converted texel density value.

    """
    unit_dict = {
        "km": tex_den,
        "m": tex_den,
        "dm": tex_den * 10,
        "cm": tex_den * 100,
        "mm": tex_den * 1000,
        "in": tex_den * 39.370079,
        "ft": tex_den * 3.28084,
        "yd": tex_den * 1.093613,
        "mi": tex_den * 0.000621371,
    }
    return unit_dict[unit]


def _livelink_is_available() -> bool:
    """Return True if the native RizomUVLink extension can be imported.

    The vendored library lives at ``<package>/lib/RizomUVLink``. It is a
    proper Python package (has its own ``__init__.py``), and its internal
    initialization handles the DLL registration and ABI-specific extension
    load. From the bridge's perspective, importing it successfully is the
    definitive test for "LiveLink is available."

    To make that import work, we add ``<package>/lib`` to ``sys.path`` first
    — the package is a top-level name (``RizomUVLink``), not a submodule of
    ``rizomuvbridge_ultimate``.

    We compute the path from ``__file__`` rather than relying on the relative
    import machinery. A relative import here would have to climb four levels
    and descend into a sibling package, and getting the depth wrong produces
    a silent ImportError that this function would interpret as "not available."

    Returns:
        True if the vendored RizomUVLink package imports successfully.

    """
    import os
    import sys

    # rizom_link.py is at <package>/classes/rizom/modern/rizom_link.py.
    # Four dirname() calls walk up to <package>.
    here = os.path.abspath(__file__)
    package_dir = os.path.dirname(          # <package>
        os.path.dirname(                    # <package>/classes
            os.path.dirname(                # <package>/classes/rizom
                os.path.dirname(here)       # <package>/classes/rizom/modern
            )
        )
    )
    lib_parent = os.path.join(package_dir, "lib")

    if not os.path.isdir(lib_parent):
        return False

    if lib_parent not in sys.path:
        sys.path.insert(0, lib_parent)

    try:
        from RizomUVLink import CRizomUVLink  # noqa: F401
        return True
    except ImportError:
        return False


class RizomLink(RizomBase):
    """Class for managing the RizomUVLink process."""

    def __init__(
        self,
        rizom_path: str,
        data_dir: DataDirectory,
        connection_timeout: int,
    ):
        """Initialize the RizomLink class.

        Args:
            rizom_path: The path to the RizomUV executable.
            data_dir: The data directory.
            connection_timeout: Duration to wait for the RizomUVLink
                connection before timing out.

        Raises:
            RizomLinkUnsupportedError: If the native RizomUVLink extension
                is not available.
            InvalidRizomPathError: If the rizom installation path is invalid.

        """
        if not _livelink_is_available():
            raise RizomLinkUnsupportedError(
                "RizomUV LiveLink module could not be loaded. Verify that the "
                "RizomUV installation includes its Python API for this "
                "platform and Python version."
            )

        self._rizom_path = validate_and_transform_rizom_path(rizom_path)
        self._data_dir = data_dir
        self.connection_timeout = connection_timeout

        self._module_manager = RizomModuleLoader(rizom_path)
        self.connection_manager = RizomConnectionManager(
            self._module_manager,
            self._data_dir,
            self._rizom_path,
            connection_timeout,
        )

        self.api = RizomApi(self.connection_manager)
        self.select = SelectCommands(self.api)
        self.uvmaps = UvmapCommands(self.select, self.api)
        self.files = FileCommands(self.api, self.select, self._data_dir)
        self.objects = ObjectCommands(self.api, self.files)

    def get_scene_data(self) -> RizomData:
        """Get the data from the current RizomUV session.

        Returns:
            A dataclass containing the object names and UV map names from the
            current RizomUV session.

        """
        self.save_file()
        return RizomData(
            self.objects.get_object_names(),
            self.uvmaps.get_uvmap_names(),
            self.files.get_file(),
        )

    def save_file(self):
        """Save the currently loaded file in RizomUV."""
        self.files.save_file()

    def quit(self):
        """Close the RizomUV instance."""
        self.api.quit()