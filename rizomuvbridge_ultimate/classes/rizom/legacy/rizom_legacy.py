"""Connection manager class for connecting to RizomUV using legacy methods.

Only supports basic functionality and is never intended to be expanded with more features.
This isn't a nice solution but it works and is used by a shrinking number of users
and I don't want to spend more time on it.

RizomUVLink should be used on all compatible systems instead.

Maya port note: this module is host-agnostic (it does not import ``bpy`` or any
DCC library) so it is copied nearly verbatim from the Blender addon. The only
changes are import-path adjustments, the ``BlenderOutput`` → ``MayaOutput``
rename, and a small amount of defensive code around Windows' ``tasklist``
invocation.
"""

import os
import platform
import subprocess
import time
import traceback
from typing import Optional

from ....addon_constants import RIZOM_SCRIPT
from ....file_access import DataDirectory, MayaOutput, RizomOutput, Session
from ....types import ExportTypes
from ....utils.rizom_utils import validate_and_transform_rizom_path
from ...data.import_models import RizomData
from ..rizom_base import RizomBase

import logging
logger = logging.getLogger(__name__)


class RizomLegacy(RizomBase):
    """Connection manager class for connecting to RizomUV using legacy methods."""

    pid: Optional[int] = None
    process: Optional[subprocess.Popen] = None

    def __init__(self, rizom_path: str, data_dir: DataDirectory, import_timeout: int):
        self.rizom_path = validate_and_transform_rizom_path(rizom_path)
        self.data_root = data_dir.root
        self.mesh_files = data_dir.mesh_files
        self.rizom_output = data_dir.rizom_output
        self.maya_output = data_dir.maya_output
        self.rizom_session = data_dir.rizom_session
        self.pid_file = data_dir.rizom_pid
        self.remote_file = RIZOM_SCRIPT
        self.lock_timeout = import_timeout

        self.files = {
            "OBJ": data_dir.mesh_files.obj,
            "FBX": data_dir.mesh_files.fbx,
            "USD": data_dir.mesh_files.usd,
        }

    # -------------------------------------------------------------------
    # Process liveness
    # -------------------------------------------------------------------

    def _check_output(self, encoding: str) -> bool:
        """Check if the Rizom process is still running (Windows).

        Args:
            encoding: Encoding to use for tasklist output.

        Returns:
            True if the Rizom process is still running.

        """
        output = subprocess.check_output(
            ["tasklist", "/fi", f"PID eq {self.pid}"],
            text=True,
            encoding=encoding,
        )
        return str(self.pid) in output

    def is_connected(self) -> bool:
        """Check if RizomUV is open and connectable.

        Works for both Windows and macOS.

        Returns:
            True if RizomUV is open and connectable.

        """
        if self.pid is None:
            session = Session.deserialize()
            self.pid = session.pid

        if self.pid is None:
            return False

        if platform.system() == "Darwin":
            try:
                result = subprocess.run(
                    ["ps", "-p", str(self.pid)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                return str(self.pid) in result.stdout.decode()
            except subprocess.SubprocessError:
                return False

        if platform.system() == "Windows":
            # Had problems before with different languages where switching
            # encoding fixed it.
            try:
                return self._check_output("latin-1")
            except UnicodeDecodeError:
                return self._check_output("utf-8")
            except subprocess.CalledProcessError:
                return False

        # Linux: ps is universal and works the same as macOS.
        if platform.system() == "Linux":
            try:
                result = subprocess.run(
                    ["ps", "-p", str(self.pid)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                return str(self.pid) in result.stdout.decode()
            except subprocess.SubprocessError:
                return False

        return False

    # -------------------------------------------------------------------
    # Connection / launch
    # -------------------------------------------------------------------

    def connect_or_start(self) -> Session:
        """Attempt to connect to RizomUV, starting a new process if needed.

        Returns:
           Session instance.

        """
        if self.is_connected():
            return self._trigger_rizomuv_update()

        try:
            # ``rizom_script.py`` runs inside RizomUV and needs to find the
            # same handshake files Maya is watching. Pass the resolved data
            # directory through the child process environment.
            env = os.environ.copy()
            env["RIZOMUV_BRIDGE_DATA"] = str(self.data_root)
            self.process = subprocess.Popen(
                [self.rizom_path, "-cfi", str(self.remote_file)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                close_fds=True,
                env=env,
            )
        except Exception as e:
            logger.error(traceback.format_exc())
            raise RuntimeError(f"Failed to start RizomUV: {e}") from e

        self.pid = self.process.pid
        session = Session.deserialize()
        session.set_properties_with_write(pid=self.pid, locked=True)

        return session

    # -------------------------------------------------------------------
    # Session lock dance
    # -------------------------------------------------------------------

    def _trigger_rizomuv_update(self) -> Session:
        """Trigger RizomUV to read the command file.

        RizomUV's remote file works by watching the command file for changes.
        We fake a change by updating the timestamp, which triggers a refresh.

        Session locks the file so that Maya will not proceed until RizomUV
        unlocks it.

        Returns:
           Session object.

        """
        session = Session.deserialize()
        session.lock()
        new_time = time.time()
        os.utime(self.remote_file, (new_time, new_time))
        return session

    def _await_rizom_update(self, session: Session) -> RizomOutput:
        """Wait for RizomUV to release the session lock.

        Args:
            session: The current RizomUV session object.

        Returns:
            The RizomUV output object.

        """
        sleep_time = 0.25
        time_slept = 0.0

        logger.info(
            f"Waiting for RizomUV to release the session lock for "
            f"request {session.request_id}"
        )
        while session.locked:
            time.sleep(sleep_time)
            session.update_from_file()
            time_slept += sleep_time

            if time_slept >= self.lock_timeout:
                raise RuntimeError(
                    f"RizomUV is not releasing the session lock for "
                    f"request {session.request_id}."
                )

        logger.info(
            f"RizomUV released the session lock for request {session.request_id}"
        )
        return RizomOutput.deserialize()

    # -------------------------------------------------------------------
    # RizomBase implementation
    # -------------------------------------------------------------------

    def get_scene_data(self) -> RizomData:
        """Trigger RizomUV to execute code returning scene data.

        Returns:
            A dataclass containing the object names, UV map names, and file
            path from the current RizomUV session.

        """
        # ``MayaOutput`` writes the requested operation into
        # ``maya_output.json``; RizomUV's ``rizom_script.py`` reads it.
        maya_out = MayaOutput.deserialize()
        maya_out.start_import()
        session = self._trigger_rizomuv_update()
        rizom_out = self._await_rizom_update(session)
        return RizomData(
            rizom_out.loaded_objects,
            rizom_out.uvmaps,
            rizom_out.file_path,
        )

    def load_file(self, uvmap: str, file_format: ExportTypes):
        """Load a file into RizomUV.

        Args:
            uvmap: The name of the active uvmap.
            file_format: The format of the file to load.

        Raises:
            FileNotFoundError: If the mesh file does not exist.

        """
        file_path = self.files[file_format]
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        maya_out = MayaOutput(str(file_path), uvmap, "EXPORT")
        maya_out.serialize()
        self._trigger_rizomuv_update()
        # Note: the original Blender addon intentionally does not await here —
        # the caller (rizom_export) awaits via the next get_scene_data call.
        # Keep that behaviour.