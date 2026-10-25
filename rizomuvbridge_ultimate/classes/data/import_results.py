"""Data classes for storing import results.

Maya port note: the Blender original typed ``missing_uvmaps`` as
``dict[bpy.types.Object, list[str]]`` — a mapping from Blender object
references to the UV set names that couldn't be transferred. Maya nodes
are identified by name, so the port uses ``Dict[str, List[str]]`` keyed
on the target node's name. Callers in ``operators/rizom_import.py``
already construct this dict with string keys.
"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class UVTransferResult:
    """Result of transferring UV maps from RizomUV back into the scene.

    Attributes:
        missing_objects: Names of imported nodes that had no matching scene
            node. These are typically objects that were deleted from the
            scene while RizomUV still had them loaded.
        missing_uvmaps: Mapping from target node name to the list of UV set
            names that could not be created or transferred on that node.

    """

    missing_objects: List[str] = field(default_factory=list)
    missing_uvmaps: Dict[str, List[str]] = field(default_factory=dict)