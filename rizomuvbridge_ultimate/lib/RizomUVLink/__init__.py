"""RizomUV Link — vendored copy of Rizom-Lab's official Python API.

Layout of this directory:

* ``RizomUVLink.py``       — public entry point, re-exports ``CRizomUVLink``.
* ``RizomUVLinkBase.py``   — Rizom-Lab generated. **Do not edit.**
* ``win/``                 — the native extension package. Contains one
                             ``rizomuvlink_python<ABI>.pyd`` per supported
                             CPython version, plus its two DLL dependencies
                             (``libsodium.dll`` and ``libzmq-v142-mt-4_3_4.dll``).

The upstream distribution expects these files to sit directly on
``PYTHONPATH``. Vendoring them inside the Maya plugin means we must do three
things ourselves at import time:

1. Add this directory to ``sys.path`` so ``RizomUVLinkBase`` resolves as a
   top-level module — the vendor file uses absolute imports internally.
2. Register ``win/`` as a Windows DLL search directory. Python 3.8+ does
   not consult ``PATH`` when resolving extension-module dependencies, and
   both support DLLs sit in ``win/``.
3. Import ``CRizomUVLink`` from the vendored ``RizomUVLink.py`` and re-export
   it so callers can do ``from ...lib.RizomUVLink import CRizomUVLink``.

The bulk of the diagnostic work — matching the interpreter ABI, verifying
the ``.pyd`` exists, resolving the two support DLLs — lives in
``win/__init__.py``. This file only handles the surrounding package context
and surfaces whatever error comes back unchanged.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_WIN_DIR = os.path.join(_HERE, "win")


# ---------------------------------------------------------------------------
# Step 1: make this directory importable as a top-level location
# ---------------------------------------------------------------------------
# ``RizomUVLink.py`` (vendor file) does ``from RizomUVLinkBase import ...``.
# Adding this directory to ``sys.path`` lets that absolute import succeed
# regardless of how the package itself was reached.

if _HERE not in sys.path:
    sys.path.insert(0, _HERE)


# ---------------------------------------------------------------------------
# Step 2: register the native DLL directory
# ---------------------------------------------------------------------------
# The ``.pyd`` files inside ``win/`` link against ``libsodium.dll`` and
# ``libzmq-v142-mt-4_3_4.dll``. On Python 3.8+ those must be registered
# explicitly via ``os.add_dll_directory``. We do this here in addition to
# doing it in ``win/__init__.py`` so that the DLLs are resolvable even if
# some other code path imports the ``.pyd`` before ``win/`` is reached.
#
# The returned handle is kept alive at module scope: if it's garbage
# collected, Python removes the directory from the search path.

_dll_handles = []

if sys.platform == "win32" and os.path.isdir(_WIN_DIR):
    if hasattr(os, "add_dll_directory"):
        try:
            _dll_handles.append(os.add_dll_directory(_WIN_DIR))
        except (OSError, FileNotFoundError) as e:
            raise ImportError(
                f"Could not register '{_WIN_DIR}' as a DLL search "
                f"directory: {e}"
            )
    else:
        # Python 3.7 and older fall back to PATH.
        os.environ["PATH"] = _WIN_DIR + os.pathsep + os.environ.get("PATH", "")


# ---------------------------------------------------------------------------
# Step 3: verify the win package is present before importing it
# ---------------------------------------------------------------------------
# If ``win/`` is missing entirely, the failure from ``from .RizomUVLink
# import CRizomUVLink`` would be a confusing chain of nested ImportErrors.
# Failing early here gives a single clear message.

if not os.path.isdir(_WIN_DIR):
    raise ImportError(
        "RizomUV Link: the native ``win/`` folder is missing.\n"
        f"  Expected at : {_WIN_DIR}\n"
        f"  Package root: {_HERE}\n"
        "Re-copy the ``win/`` folder from your RizomUV installation, or "
        "from a known-good build of the bridge, alongside RizomUVLink.py "
        "and RizomUVLinkBase.py."
    )


# ---------------------------------------------------------------------------
# Step 4: import the public class
# ---------------------------------------------------------------------------
# Any ImportError raised here comes from ``win/__init__.py`` and already
# carries a detailed diagnostic — the interpreter version, the ABI tag
# being looked for, whether the ``.pyd`` exists, and whether the support
# DLLs are present. We deliberately do NOT wrap it, so the inner message
# reaches the user unchanged.

from .RizomUVLink import CRizomUVLink  # noqa: E402


__all__ = ["CRizomUVLink"]