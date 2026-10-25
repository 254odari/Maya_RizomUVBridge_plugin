"""Maya-specific exceptions.

Maya has no direct equivalent of Blender's ``bpy_struct`` hierarchy, so
these exceptions operate on node names (strings) and Maya node types
(strings like ``"mesh"``, ``"transform"``). The Blender original relied on
``obj.name`` and ``obj.type``; here, callers pass the node name and the
expected type as plain strings.
"""

from typing import Optional


class UnexpectedNodeTypeError(Exception):
    """Raised when a Maya node is not of the expected type.

    Attributes:
        node: The name of the offending node.
        expected_type: The Maya node type that was expected
            (e.g. ``"mesh"``, ``"transform"``).

    """

    def __init__(self, node: str, expected_type: str):
        self.node = node
        self.expected_type = expected_type
        super().__init__(
            f"Expected node '{node}' to be a {expected_type}."
        )


# ---------------------------------------------------------------------------
# Backwards-compatible aliases
# ---------------------------------------------------------------------------
#
# The Blender original defined ``UnexpectedObjectTypeError`` and
# ``UnexpectedSpaceTypeError``. The Maya port consolidates both into
# ``UnexpectedNodeTypeError`` because Maya doesn't distinguish "objects"
# from "spaces" -- a viewport is just another node. Any lingering reference
# to the old names will still resolve, but new code should use
# ``UnexpectedNodeTypeError``.

UnexpectedObjectTypeError = UnexpectedNodeTypeError
UnexpectedSpaceTypeError = UnexpectedNodeTypeError