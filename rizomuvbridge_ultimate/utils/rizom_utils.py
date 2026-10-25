"""Functions for finding/managing the user's RizomUV application."""

import logging
import os
import platform
from pathlib import Path
from typing import Optional

from ..classes.exceptions.rizom_exceptions import RizomNotFoundError

logger = logging.getLogger(__name__)


def check_for_livelink(rizom_path: str) -> bool:
    """Return True if the RizomUV install next to ``rizom_path`` has LiveLink."""
    if not rizom_path:
        return False
    module = Path(rizom_path).parent / "RizomUVLink"
    return module.exists() and module.is_dir()


def validate_and_transform_rizom_path(rizom_path: str) -> str:
    """Validate the rizom path and adjust it for the current OS.

    On Windows, the path must end in ``.exe``. On macOS, if the user picked
    the ``.app`` bundle, we resolve to the executable inside ``Contents/MacOS/``.

    Args:
        rizom_path: The path to the RizomUV executable.

    Returns:
        The validated (and possibly transformed) path.

    Raises:
        RizomNotFoundError: If the path is invalid on Windows.

    """
    if platform.system() == "Windows":
        if not rizom_path.endswith(".exe"):
            raise RizomNotFoundError(rizom_path)
        return rizom_path

    if platform.system() == "Darwin" and rizom_path.endswith(".app"):
        filename = os.path.basename(rizom_path)
        basename, _ = os.path.splitext(filename)
        final_path = os.path.join(rizom_path, "Contents", "MacOS", basename)
        logger.info(
            f"MacOS detected, adjusting path from {rizom_path} to {final_path}"
        )
        return final_path

    return rizom_path


def get_latest_rizomuv_path_windows() -> Optional[str]:
    """Locate the most recent RizomUV installation directory via the registry.

    Returns:
        The installation directory, or None if no version was found.

    """
    import winreg

    for major in range(9, 1, -1):
        for minor in range(10, -1, -1):
            if major == 2 and minor < 2:
                continue
            reg_path = (
                f"SOFTWARE\\Rizom Lab\\RizomUV VS RS 202{major}.{minor}"
            )
            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path)
                exe_path = winreg.QueryValue(key, "rizomuv.exe")
                return os.path.dirname(exe_path)
            except FileNotFoundError:
                pass
    return None


def get_rizom_path() -> str:
    """Attempt to locate a RizomUV installation on this system.

    Returns:
        The path to ``rizomuv.exe``, or an empty string if not found.

    """
    if platform.system() == "Windows":
        path = get_latest_rizomuv_path_windows()
        if not path:
            return ""
        rizom_exe = os.path.join(path, "rizomuv.exe")
        if os.path.isfile(rizom_exe):
            return rizom_exe
    return ""