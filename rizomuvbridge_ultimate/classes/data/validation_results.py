"""Result objects from validation functions.

Maya port note: the Blender original typed ``target_object`` as a
``bpy.types.Object``. Maya has no equivalent single wrapper type -- nodes are
identified by their name or by an ``MObject``/``MDagPath``. Since these result
objects are consumed by UI and logging code that only needs a human-readable
identifier, we store the node name (a ``str``).
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class UVValidationResult:
    """Result of comparing a mesh's UV sets against the base mesh's sets.

    Attributes:
        target_object: Node name of the mesh whose UV sets didn't match.
        extra_uvmaps: UV set names present on the mesh but not the base.
        missing_uvmaps: UV set names present on the base but not the mesh.

    """

    target_object: str
    extra_uvmaps: List[str] = field(default_factory=list)
    missing_uvmaps: List[str] = field(default_factory=list)


@dataclass
class ObjectNameValidationResult:
    """Result of checking a node name for illegal characters.

    Attributes:
        target_object: Node name that contained illegal characters.
        invalid_name_substrings: The specific substrings that were rejected.

    """

    target_object: str
    invalid_name_substrings: List[str] = field(default_factory=list)