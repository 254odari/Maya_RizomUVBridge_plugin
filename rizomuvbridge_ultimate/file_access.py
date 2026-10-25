"""Functions for accessing external data files (Maya edition)."""

import json
import logging
import os
import re
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, TypeVar
from uuid import uuid4

logger = logging.getLogger(__name__)


def _resolve_data_path() -> Path:
    """Resolve the bridge's data directory, preferring Maya's prefs folder."""
    try:
        import maya.cmds as cmds
        maya_prefs = cmds.internalVar(userPrefDir=True)
        if maya_prefs:
            return Path(maya_prefs) / "RizomUV Bridge"
    except Exception:
        pass
    return Path.home() / "Documents" / "RizomUV Bridge"


data_path: Path = _resolve_data_path()


DATA_FILE_NAMES = (
    "rizom_port.txt",
    "rizom_pid.txt",
    "rizom_session.json",
    "rizom_output.json",   # RizomUV → Maya
    "maya_output.json",    # Maya → RizomUV
)


# ---------------------------------------------------------------------------
# Scene-derived transfer file names
# ---------------------------------------------------------------------------

_DEFAULT_BASENAME = "rizom_transfer"

_SAFE_BASENAME_RE = re.compile(r"[^A-Za-z0-9_\-]+")


def _scene_basename() -> str:
    """Return a filesystem-safe base name derived from the current Maya scene.

    Examples:
        ``C:/projects/robot.ma``           → ``robot``
        ``C:/projects/high poly.ma``       → ``high_poly``
        ``C:/projects/version.v3.ma``      → ``version_v3``
        (unsaved scene)                    → ``rizom_transfer``

    """
    try:
        import maya.cmds as cmds
        scene_path = cmds.file(query=True, sceneName=True) or ""
    except Exception:
        scene_path = ""

    if not scene_path:
        return _DEFAULT_BASENAME

    stem = Path(scene_path).stem
    if not stem:
        return _DEFAULT_BASENAME

    cleaned = _SAFE_BASENAME_RE.sub("_", stem).strip("_")
    return cleaned or _DEFAULT_BASENAME


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class MeshFiles:
    fbx: Path
    obj: Path
    usd: Path


@dataclass
class DataDirectory:
    root: Path
    mesh_files: MeshFiles
    rizom_port: Path
    rizom_pid: Path
    rizom_session: Path
    rizom_output: Path     # RizomUV writes here, Maya reads
    maya_output: Path      # Maya writes here, RizomUV reads


def get_data_directory() -> DataDirectory:
    """Return the data directory structure.

    The mesh transfer files are named after the current Maya scene. The
    session state files (port cache, pid, session lock, RizomUV I/O JSON)
    keep fixed names — they describe shared bridge state, not the scene.

    Note: ``maya_output.json`` was previously ``blender_output.json``. The
    rename reflects the Maya port; the matching ``rizom_script.py`` that
    runs inside RizomUV has been updated to read the new name.

    """
    base = _scene_basename()
    mesh_dir = data_path / "mesh_files"

    mesh_files = MeshFiles(
        fbx=mesh_dir / f"{base}.fbx",
        obj=mesh_dir / f"{base}.obj",
        usd=mesh_dir / f"{base}.usd",
    )

    return DataDirectory(
        root=data_path,
        rizom_port=data_path / "rizom_port.txt",
        rizom_pid=data_path / "rizom_pid.txt",
        rizom_session=data_path / "rizom_session.json",
        rizom_output=data_path / "rizom_output.json",
        maya_output=data_path / "maya_output.json",
        mesh_files=mesh_files,
    )


def ensure_data_dir_integrity() -> None:
    """Create directories and files the addon needs."""
    os.makedirs(data_path, exist_ok=True)
    os.makedirs(data_path / "mesh_files", exist_ok=True)
    for file_name in DATA_FILE_NAMES:
        (data_path / file_name).touch()


# ---------------------------------------------------------------------------
# Port / PID helpers
# ---------------------------------------------------------------------------

def read_port_file() -> Optional[int]:
    try:
        with open(data_path / "rizom_port.txt", "r") as f:
            contents = f.read().strip()
            return int(contents) if contents else None
    except Exception as e:
        logger.warning(f"Error reading port file: {e}")
        return None


def write_port_file(port: int) -> None:
    try:
        with open(data_path / "rizom_port.txt", "w") as f:
            f.write(str(port))
    except Exception:
        logger.warning(traceback.format_exc())


def read_pid_file() -> Optional[int]:
    try:
        with open(data_path / "rizom_pid.txt", "r") as f:
            contents = f.read().strip()
            return int(contents) if contents else None
    except Exception:
        logger.warning(traceback.format_exc())
        return None


# ---------------------------------------------------------------------------
# Persistent stores
# ---------------------------------------------------------------------------

data_dir = get_data_directory()

T = TypeVar("T", bound="StoreBase")


class StoreBase:
    json_path: Path

    def __init__(self):
        if not self.json_path.exists():
            raise FileNotFoundError(
                f"Could not find the store file at {self.json_path}"
            )

    def set_properties_with_write(self, **kwargs) -> None:
        for k, v in kwargs.items():
            self.__dict__[k] = v
        try:
            with open(self.json_path, "r") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            data = {}
        data.update(kwargs)
        with open(self.json_path, "w") as f:
            json.dump(data, f)

    def update_from_file(self) -> None:
        try:
            with open(self.json_path, "r") as f:
                data = json.load(f)
                self.__dict__.update(**data)
        except json.JSONDecodeError:
            pass

    def serialize(self) -> None:
        with open(self.json_path, "w") as f:
            data = {
                k: v
                for k, v in self.__dict__.items()
                if not k.startswith("_") and k != "json_path"
            }
            json.dump(data, f, indent=2)

    @classmethod
    def deserialize(cls: Type[T]) -> T:
        try:
            with open(cls.json_path, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            data = {}
        try:
            return cls(**data)
        except TypeError:
            return cls()


class RizomOutput(StoreBase):
    """RizomUV → Maya: the currently-loaded file, UV sets, objects."""

    json_path: Path = data_dir.rizom_output

    def __init__(self):
        super().__init__()
        self.file_path: str = ""
        self.uvmaps: List[str] = []
        self.loaded_objects: List[str] = []
        self.update_from_file()


class MayaOutput(StoreBase):
    """Maya → RizomUV: the requested operation and its parameters.

    Renamed from ``BlenderOutput``. The matching ``rizom_script.py`` that
    runs inside RizomUV now reads ``maya_output.json``. The two must stay
    in sync — RizomUV is responsible for setting ``locked = False`` on the
    session file after processing the request.

    """

    json_path: Path = data_dir.maya_output

    def __init__(
        self,
        file_path: Optional[str] = None,
        uvmap: Optional[str] = None,
        operation: str = "EXPORT",
    ):
        super().__init__()
        self.file_path = file_path
        self.uvmap = uvmap
        self.operation = operation

    def start_export(self) -> None:
        self.operation = "EXPORT"
        self.serialize()

    def start_import(self) -> None:
        self.operation = "IMPORT"
        self.serialize()

    def __str__(self) -> str:
        return (
            f"File Path: {self.file_path}\n"
            f"UV Map: {self.uvmap}\n"
            f"Operation: {self.operation}"
        )


class Session(StoreBase):
    json_path: Path = data_dir.rizom_session

    def __init__(
        self,
        request_id: Optional[str] = None,
        pid: int = -1,
        locked: bool = True,
    ):
        super().__init__()
        self.pid: int = pid
        self.locked: bool = locked
        self.request_id: str = request_id or str(uuid4())

    def lock(self) -> None:
        if "Rizom" in sys.executable:
            raise RuntimeError(
                "Maya is responsible for locking the session file."
            )
        self.locked = True
        self.serialize()

    def __str__(self) -> str:
        return f"Locked: {self.locked}, Pid: {self.pid}"