"""Data classes for storing scene data."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BlenderSceneState:
    """Dataclass for storing the state of the Blender scene so it can be changed and restored."""

    active_object: Any | None
    selected_objects: list[Any]
