"""RizomUV Link native extension dispatch (Maya port).

The folder is named ``win`` for historical reasons — it is not Windows-
specific. Every platform RizomUV supports ships a package literally named
``win`` containing the native extension for each Python ABI it targets.

This module:

1. Registers this directory as a Windows DLL search path (Python 3.8+ needs
   the explicit ``os.add_dll_directory`` call — ``PATH`` is not consulted
   when resolving extension-module dependencies).
2. Adds this directory to ``sys.path`` so the Python importer can find the
   ``.pyd`` files. **This is separate from the DLL search path** — the
   Windows loader uses one mechanism, the Python importer uses another,
   and the ``.pyd`` needs both.
3. Selects the ABI-specific module matching the running interpreter.
4. Re-exports it as ``rizomuvlink`` so ``RizomUVLinkBase.py`` can do
   ``from win import rizomuvlink``.
"""

import os
import sys


# ---------------------------------------------------------------------------
# Step 1: Register this directory for DLL resolution
# ---------------------------------------------------------------------------
# Must run before any .pyd import. ``libzmq-v142-mt-4_3_4.dll`` and
# ``libsodium.dll`` sit next to the .pyd files; without this call, Python
# 3.8+ raises "DLL load failed while importing rizomuvlink_pythonXXX".

_HERE = os.path.dirname(os.path.abspath(__file__))

_dll_handle = None

if sys.platform == "win32":
    if hasattr(os, "add_dll_directory"):
        try:
            _dll_handle = os.add_dll_directory(_HERE)
        except (OSError, FileNotFoundError) as e:
            raise ImportError(
                f"Could not register '{_HERE}' as a DLL search "
                f"directory: {e}"
            )
    else:
        # Python 3.7 and older use PATH.
        os.environ["PATH"] = _HERE + os.pathsep + os.environ.get("PATH", "")


# ---------------------------------------------------------------------------
# Step 2: Make this directory importable as a Python module location
# ---------------------------------------------------------------------------
# ``os.add_dll_directory`` above only affects the *Windows loader*. The
# *Python importer* still needs the directory on ``sys.path`` to find the
# .pyd file itself. Without this line, ``__import__("rizomuvlink_python311")``
# raises ModuleNotFoundError even though the file is present.

if _HERE not in sys.path:
    sys.path.insert(0, _HERE)


# ---------------------------------------------------------------------------
# Step 3: ABI dispatch
# ---------------------------------------------------------------------------

_ABI_MODULES = {
    (3, 6): "rizomuvlink_python36",
    (3, 7): "rizomuvlink_python37",
    (3, 8): "rizomuvlink_python38",
    (3, 9): "rizomuvlink_python39",
    (3, 10): "rizomuvlink_python310",
    (3, 11): "rizomuvlink_python311",
    (3, 12): "rizomuvlink_python312",
    (3, 13): "rizomuvlink_python313",
}


def _resolve_abi_module() -> str:
    """Return the name of the native module matching this interpreter."""
    version = sys.version_info[:2]
    if version not in _ABI_MODULES:
        supported = ", ".join(f"{a}.{b}" for a, b in _ABI_MODULES)
        raise ImportError(
            f"RizomUV Link has no native extension for Python "
            f"{version[0]}.{version[1]}. Supported ABIs: {supported}. "
            "Ask the Rizom-Lab team to add a build for this Python version."
        )
    return _ABI_MODULES[version]


# ---------------------------------------------------------------------------
# Step 4: Import the ABI-specific module and bind it as ``rizomuvlink``
# ---------------------------------------------------------------------------

try:
    _module_name = _resolve_abi_module()
    rizomuvlink = __import__(_module_name)
except ImportError as e:
    # Diagnose which of the two failure modes this is: missing file, or
    # missing dependency. Report the existence of both the .pyd and each
    # support DLL so the user has everything they need to fix it.
    expected_pyd = f"{_ABI_MODULES.get(sys.version_info[:2], '<unknown>')}.pyd"
    pyd_path = os.path.join(_HERE, expected_pyd)
    support_dlls = ("libsodium.dll", "libzmq-v142-mt-4_3_4.dll")

    details = [
        "RizomUV Link's native extension could not be loaded.",
        f"  Python interpreter : {sys.version.split()[0]} "
        f"({sys.version_info[:2]})",
        f"  Expected .pyd      : {expected_pyd}",
        f"  .pyd exists        : {os.path.isfile(pyd_path)}",
        f"  Search directory   : {_HERE}",
        f"  Directory on path  : {_HERE in sys.path}",
        "  Support DLLs:",
    ]
    for dll in support_dlls:
        details.append(
            f"    {dll}: {os.path.isfile(os.path.join(_HERE, dll))}"
        )
    details.append(
        "If the .pyd is present but the import still fails, the native "
        "extension's dependencies could not be resolved. Install the "
        "Visual C++ 2015-2022 Redistributable (x64) and verify that "
        "libsodium.dll and libzmq-v142-mt-4_3_4.dll are in this directory."
    )

    raise ImportError("\n".join(details)) from e


__all__ = ["rizomuvlink"]