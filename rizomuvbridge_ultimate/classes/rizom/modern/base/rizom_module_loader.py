"""Handles loading and importing the RizomUVLink module."""

import importlib
import logging
import sys
from pathlib import Path
from types import ModuleType
from typing import Optional

from ....exceptions.rizom_exceptions import RizomLinkModuleNotFoundError

logger = logging.getLogger(__name__)


class RizomModuleLoader:
    """Handles loading and importing the RizomUVLink module.

    The loader probes two locations in order:

    1. The RizomUV installation directory (``<install>/RizomUVLink``), so that
       a user running a recent RizomUV always uses the API shipped with it.
    2. The bundled copy inside this addon (``lib/RizomUVLink``), so that the
       bridge works even when the installed API is missing or incompatible.
    """

    def __init__(self, rizom_path: str):
        """Initialize the RizomModuleLoader.

        Args:
            rizom_path: The path to the RizomUV installation.

        Raises:
            RizomLinkModuleNotFoundError: If the RizomUVLink module could not
                be found in either location.

        """
        self.rizom_path = rizom_path
        self.module_path: Optional[Path] = None
        self.module = self._find_and_import_module()

    # ------------------------------------------------------------------

    def _find_and_import_module(self) -> ModuleType:
        """Attempt to import from the installation, then the bundled copy.

        Raises:
            RizomLinkModuleNotFoundError: If neither location contains a
                usable ``RizomUVLink`` package.

        """
        installed_path = Path(self.rizom_path).parent / "RizomUVLink"
        logger.info(
            f"Attempting to load RizomUVLink from installed path: {installed_path}"
        )
        module = self._attempt_import(installed_path)
        if module:
            logger.info("Loaded RizomUVLink from installed path.")
            return module

        # ``parents[4]`` assumes:
        #   <addon>/classes/rizom/modern/base/rizom_module_loader.py
        #   ^^^^^^^^ <- this is the addon root, four parents up.
        bundled_path = Path(__file__).parents[4] / "lib" / "RizomUVLink"
        logger.info(f"Attempting to load RizomUVLink from bundled path: {bundled_path}")
        module = self._attempt_import(bundled_path)
        if module:
            logger.info("Loaded RizomUVLink from bundled path.")
            return module

        raise RizomLinkModuleNotFoundError()

    # ------------------------------------------------------------------

    def _attempt_import(self, path: Path) -> Optional[ModuleType]:
        """Try to import ``RizomUVLink`` from the given directory.

        Args:
            path: The directory that should contain the ``RizomUVLink`` package.

        Returns:
            The imported module, or None if the import failed.

        """
        if not (path.exists() and path.is_dir()):
            return None

        # ``path`` is the package directory itself, so its *parent* is the
        # entry that must be on sys.path for ``import RizomUVLink`` to work.
        parent_path = str(path.parent)

        # Temporarily prepend the candidate path so importlib resolves *this*
        # copy first, even if a different RizomUVLink is already on sys.path.
        sys.path.insert(0, parent_path)
        try:
            # Drop any previously imported copy (and its submodules) so the
            # new path takes effect.
            for mod_name in list(sys.modules):
                if mod_name == "RizomUVLink" or mod_name.startswith("RizomUVLink."):
                    sys.modules.pop(mod_name, None)

            module = importlib.import_module("RizomUVLink")
            self.module_path = path
            return module
        except Exception:
            logger.error(
                f"Failed to import RizomUVLink from {path}", exc_info=True
            )
            return None
        finally:
            # Always clean up the sys.path entry, whether the import
            # succeeded or failed. If it succeeded we rely on the module
            # object being cached in sys.modules; the package's internal
            # imports already resolved.
            try:
                sys.path.remove(parent_path)
            except ValueError:
                pass