"""Utility functions for DRY Maya UI code.

Maya has no equivalent of Blender's ``UILayout`` DSL. These helpers return
Maya layout names that the caller can attach children to. They exist for
convenience, not as a declarative API — call sites still use Maya's own
layout commands directly.
"""

import maya.cmds as cmds


def scaled_row(parent: str, scale: float = 1.5, align: bool = False) -> str:
    """Create a two-column row layout inside ``parent``.

    Maya's ``rowLayout`` has no per-row scale factor, so ``scale`` is accepted
    for API compatibility with the original Blender helper and ignored.

    Args:
        parent: The parent layout name.
        scale: Ignored — kept for API parity with the Blender version.
        align: If True, uses the modern tuple-based column config.

    Returns:
        The name of the newly-created row layout.

    """
    return cmds.rowLayout(
        numberOfColumns=2,
        adjustableColumn=2,
        columnWidth2=(140, 140),
        columnAlign2=("right", "left"),
        columnAttach2=("both", "both"),
        parent=parent,
    )


def split_scaled_row(parent: str, factor: float, scale: float = 1.5) -> str:
    """Create a form layout inside ``parent``.

    Maya's ``formLayout`` has no direct "split factor" — the caller attaches
    children using ``formLayout -edit -attachForm / -attachPosition``.

    Args:
        parent: The parent layout name.
        factor: Proportion of the width for the left child (0.0–1.0).
        scale: Ignored — kept for API parity with the Blender version.

    Returns:
        The name of the newly-created form layout.

    """
    return cmds.formLayout(parent=parent, numberOfDivisions=100)