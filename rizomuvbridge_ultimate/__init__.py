"""RizomUV Bridge - Ultimate Edition for Maya.

Plain package initializer.

This file intentionally does very little. It does NOT define
``initializePlugin`` / ``uninitializePlugin`` — those live in the top-level
entry point at ``RizomUVBridge_plugin.py`` (one directory up).

Maya's Python plugin loader executes plugin files with ``exec()`` in a bare
namespace that lacks ``__file__`` and ``__package__``. Any file Maya runs
directly therefore cannot use relative imports and cannot read ``__file__``.
Keeping this module trivial keeps it out of that trap: it is only ever
reached via a normal ``import rizomuvbridge_ultimate`` statement from the
entry point.
"""

__version__ = "3.3.3"
__author__ = "Matt Ashpole"
__all__ = ["__version__", "__author__"]