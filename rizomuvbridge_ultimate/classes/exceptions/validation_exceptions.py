"""Exceptions raised by validation errors.

Maya port note: the Blender original typed its arguments as ``bpy.types.Object``
and built messages via ``obj.name``. Maya has no equivalent single type --
meshes are identified by their DAG path (a ``str``) -- so the exceptions here
take node names directly. Callers that have the MObject handy should pass
``MFnDagNode(obj).fullPathName()`` or the equivalent.
"""

from typing import Dict, List

from ..data.validation_results import (
    ObjectNameValidationResult,
    UVValidationResult,
)


class NonMatchingTopologyError(Exception):
    """Exception raised when two meshes do not have the same topology."""

    def __init__(self, a: str, b: str):
        self.a = a
        self.b = b
        super().__init__(
            f"Objects do not have matching topology: {a} and {b}"
        )


class InvalidUVSetNamesError(Exception):
    """Exception raised when the active object has invalid UV set names."""

    def __init__(self, invalid_uvmaps: Dict[str, List[str]]):
        self.invalid_uvmaps = invalid_uvmaps
        super().__init__(
            "The active object has invalid UV map names, see console for details"
        )


class InvalidUVSetsError(Exception):
    """Exception raised when objects have invalid UV sets."""

    def __init__(self, results: List[UVValidationResult]):
        self.results = results
        super().__init__(
            "Some objects do not have valid UV maps, see console for details"
        )


class InvalidObjectNamesError(Exception):
    """Exception raised when objects have invalid names."""

    def __init__(self, results: List[ObjectNameValidationResult]):
        self.results = results
        super().__init__(
            "Some objects do not have valid names, see console for details"
        )