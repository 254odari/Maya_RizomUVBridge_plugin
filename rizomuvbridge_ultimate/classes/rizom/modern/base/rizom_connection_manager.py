"""Manager class for the RizomUV connection."""

import logging
import os
import time
from typing import TYPE_CHECKING, Optional, cast

from .....file_access import DataDirectory
from ....exceptions.rizom_exceptions import (
    RizomNotFoundError,
    RizomUVLinkTimeoutError,
)
from ..common.version import Version
from .rizom_module_loader import RizomModuleLoader

if TYPE_CHECKING:
    from .....lib.RizomUVLink import RizomUVLink

logger = logging.getLogger(__name__)


class RizomConnectionManager:
    """Wraps the RizomUVLink connection."""

    def __init__(
        self,
        module_loader: RizomModuleLoader,
        data_dir: DataDirectory,
        rizom_path: str,
        connection_timeout: int,
    ):
        self.module_loader = module_loader
        self.port_cache_path = data_dir.rizom_port

        self._link: "RizomUVLink.CRizomUVLink" = None  # type: ignore[assignment]
        self.port: Optional[int] = None
        self.version: Optional[Version] = None
        self.rizom_path = rizom_path

        self._connection_timeout = connection_timeout

    # ------------------------------------------------------------------
    # Connection probing
    # ------------------------------------------------------------------

    def is_connected(self) -> bool:
        """Return True if there is an active connection."""
        if not self._link or not self.port:
            return False

        try:
            if self._link.TCPPortIsOpen(self.port):
                self.version = Version(self._link.RizomUVVersion())
                return True
        except Exception:
            pass
        return False

    def connect(self) -> bool:
        """Connect to an existing RizomUV instance via the cached port.

        Returns False — without raising — when the port cache is missing,
        malformed, or points at a dead socket. That's a normal state and
        the caller is expected to fall through to ``start_new_instance``.
        """
        self._link = self.module_loader.module.CRizomUVLink()

        port = self._read_cached_port()
        if not port:
            return False

        self.port = port
        try:
            self._link.Connect(self.port)
        except Exception as e:
            logger.debug(f"Connect to port {port} failed: {e}")
            return False

        return self.is_connected()

    def start_new_instance(self) -> None:
        """Start a new RizomUV instance."""
        if not self._link:
            self._link = self.module_loader.module.CRizomUVLink()
            logger.info(
                f"RizomUVLink module loaded from: "
                f"{self.module_loader.module.__file__}"
            )

        try:
            self.port = self._start_rizom_process()
            self.version = Version(self._link.RizomUVVersion())
            self._cache_port(self.port)
            logger.info(f"RizomUV process started on port {self.port!s}")
        except (FileNotFoundError, OSError) as e:
            logger.error(f"Failed to launch RizomUV: {e}")
            raise RizomNotFoundError(self.rizom_path) from e

    def connect_or_start(self) -> None:
        """Connect to an existing instance or start a new one."""
        if self.connect():
            logger.info("Connected to existing RizomUV instance.")
            return

        logger.info("No running instance found; starting RizomUV.")
        self.start_new_instance()

    def quit(self) -> None:
        """Close the RizomUV instance."""
        if self._link:
            try:
                self._link.Quit()
            except Exception as e:
                logger.warning(f"Quit failed: {e}")

    # ------------------------------------------------------------------
    # Port cache
    # ------------------------------------------------------------------

    def _read_cached_port(self) -> Optional[int]:
        """Read the cached port, or return None if not available.

        Never raises. A missing file is the normal state before the first
        RizomUV launch of a session.
        """
        if not os.path.isfile(self.port_cache_path):
            return None

        try:
            with open(self.port_cache_path, "r", encoding="utf-8") as f:
                contents = f.read().strip()
        except OSError as e:
            logger.debug(f"Could not read port cache: {e}")
            return None

        if not contents:
            return None

        try:
            return int(contents)
        except ValueError:
            return None

    def _cache_port(self, port: int) -> None:
        """Write the port to the cache file."""
        try:
            os.makedirs(os.path.dirname(self.port_cache_path), exist_ok=True)
            with open(self.port_cache_path, "w", encoding="utf-8") as f:
                f.write(str(port))
        except OSError as e:
            logger.warning(f"Could not write port cache: {e}")

    # ------------------------------------------------------------------
    # Launch + retry
    # ------------------------------------------------------------------

    def _start_rizom_process(self) -> int:
        """Launch RizomUV and wait for the API to become ready."""
        start_time = time.time()
        connection_attempts = 1

        try:
            logger.info(f"Connection attempt {connection_attempts}...")
            port = self._link.RunRizomUV(self.rizom_path)
            self.version = Version(self._link.RizomUVVersion())
            return port
        except Exception as e:
            try:
                from .....lib.RizomUVLink.RizomUVLinkBase import CZEx  # type: ignore
            except ImportError:
                CZEx = None  # type: ignore[assignment, misc]

            if CZEx is not None and isinstance(e, CZEx):
                while time.time() - start_time < self._connection_timeout:
                    try:
                        connection_attempts += 1
                        logger.info(
                            f"Connection attempt {connection_attempts}..."
                        )
                        port = cast(int, self._link.port)
                        self._link.Connect(port)
                        self.version = Version(self._link.RizomUVVersion())
                        return port
                    except Exception:
                        continue
                raise RizomUVLinkTimeoutError(connection_attempts) from e
            raise