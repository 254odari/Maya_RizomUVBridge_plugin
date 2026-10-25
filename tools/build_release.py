"""Build distributable Maya module packages for RizomUV Bridge.

Run with Maya's interpreter so bundled bytecode matches Maya's Python:

    "C:\\Program Files\\Autodesk\\Maya2026\\bin\\mayapy.exe" tools\\build_release.py

Outputs (in dist/):
  RizomUVBridge-<version>/                       source staging tree
  RizomUVBridge-<version>-compiled/              bytecode staging tree
  RizomUVBridge-<version>-maya2026-source.zip
  RizomUVBridge-<version>-maya2026-py311-compiled.zip
  SHA256SUMS.txt
"""

from __future__ import annotations

import argparse
import hashlib
import py_compile
import re
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "rizomuvbridge_ultimate"
ENTRY = "RizomUVBridge_plugin.py"
MOD_NAME = "RizomUVBridge"
DIST = ROOT / "dist"

_PKG_VERSION_RE = re.compile(r'^__version__\s*=\s*"([^"]+)"', re.MULTILINE)
_ENTRY_VERSION_RE = re.compile(r'^PLUGIN_VERSION\s*=\s*"([^"]+)"', re.MULTILINE)


def fail(message: str) -> None:
    raise SystemExit(f"build_release: {message}")


def read_version() -> str:
    package_init = (ROOT / PACKAGE / "__init__.py").read_text(encoding="utf-8")
    entry = (ROOT / ENTRY).read_text(encoding="utf-8")

    package_match = _PKG_VERSION_RE.search(package_init)
    entry_match = _ENTRY_VERSION_RE.search(entry)
    if not package_match or not entry_match:
        fail("could not find the version in __init__.py or the plugin entry")

    if package_match.group(1) != entry_match.group(1):
        fail(
            "version mismatch: package is "
            f"{package_match.group(1)}, entry point is {entry_match.group(1)}"
        )
    return package_match.group(1)


def ignore_artifacts(_directory: str, names: list[str]) -> list[str]:
    ignored = []
    for name in names:
        if name in {"__pycache__", ".git"}:
            ignored.append(name)
        elif name.endswith((".pyc", ".pyo")):
            ignored.append(name)
    return ignored


def stage(source_dir: Path, version: str) -> Path:
    """Create the module tree and return its plug-ins directory.

    Layout (matches the convention Maya actually scans):

        RizomUVBridge-<version>/
          RizomUVBridge.mod
          RizomUVBridge/
            plug-ins/
              RizomUVBridge_plugin.py
              rizomuvbridge_ultimate/
          README.md
          THIRD_PARTY_NOTICES.md

    ``RizomUVBridge.mod`` must sit directly in a directory on
    ``MAYA_MODULE_PATH``; its payload folder is resolved relative to it.
    """
    if source_dir.exists():
        shutil.rmtree(source_dir)

    module_dir = source_dir / MOD_NAME
    plugins = module_dir / "plug-ins"
    plugins.mkdir(parents=True)

    shutil.copytree(
        ROOT / PACKAGE,
        plugins / PACKAGE,
        ignore=ignore_artifacts,
    )
    shutil.copy2(ROOT / ENTRY, plugins / ENTRY)
    shutil.copy2(ROOT / "README.md", source_dir / "README.md")
    shutil.copy2(ROOT / "THIRD_PARTY_NOTICES.md", source_dir / "THIRD_PARTY_NOTICES.md")

    with (source_dir / "RizomUVBridge.mod").open(
        "w", encoding="utf-8", newline="\n"
    ) as handle:
        handle.write(f"+ {MOD_NAME} {version} {MOD_NAME}\nMAYA_PLUG_IN_PATH +:= plug-ins\n")
    return plugins


def compile_bridge_modules(plugins: Path) -> int:
    """Compile the bridge's own modules in place, leaving source-less .pyc.

    The vendored RizomUVLink and ``rizom_script.py`` stay as source: the
    former loads native libraries relative to its package, the latter is
    executed by RizomUV's embedded Python, not Maya's.
    """
    package_root = plugins / PACKAGE
    compiled_count = 0

    for source in sorted(package_root.rglob("*.py")):
        relative = source.relative_to(package_root)
        if "__pycache__" in relative.parts:
            continue
        if relative.parts[0] == "lib":
            continue
        if source.name == "rizom_script.py":
            continue

        py_compile.compile(
            str(source),
            cfile=str(source.with_suffix(".pyc")),
            dfile=f"{PACKAGE}/{relative.as_posix()}",
            doraise=True,
        )
        source.unlink()
        compiled_count += 1

    return compiled_count


def zip_tree(folder: Path, archive: Path, arc_root: str) -> None:
    if archive.exists():
        archive.unlink()
    with zipfile.ZipFile(
        archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as zf:
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                zf.write(
                    path,
                    arcname=f"{arc_root}/{path.relative_to(folder).as_posix()}",
                )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-compiled",
        action="store_true",
        help="only build the source package",
    )
    args = parser.parse_args()

    if sys.version_info < (3, 11):
        fail(
            "run this with mayapy from Maya 2026 (Python 3.11); "
            f"this interpreter is {sys.version.split()[0]}"
        )

    version = read_version()
    py_tag = f"py{sys.version_info[0]}{sys.version_info[1]}"
    DIST.mkdir(exist_ok=True)

    source_dir = DIST / f"{MOD_NAME}-{version}"
    stage(source_dir, version)
    source_zip = DIST / f"{MOD_NAME}-{version}-maya2026-source.zip"
    zip_tree(source_dir, source_zip, f"{MOD_NAME}-{version}")
    print(f"source:   {source_zip.name}")

    if not args.skip_compiled:
        compiled_dir = DIST / f"{MOD_NAME}-{version}-compiled"
        if compiled_dir.exists():
            shutil.rmtree(compiled_dir)
        shutil.copytree(
            source_dir,
            compiled_dir,
            ignore=None,
        )

        count = compile_bridge_modules(compiled_dir / MOD_NAME / "plug-ins")
        if count == 0:
            fail("no modules were compiled")

        compiled_zip = (
            DIST / f"{MOD_NAME}-{version}-maya2026-{py_tag}-compiled.zip"
        )
        zip_tree(compiled_dir, compiled_zip, f"{MOD_NAME}-{version}")
        print(f"compiled: {compiled_zip.name} ({count} modules)")

    archives = sorted(DIST.glob("*.zip"))
    checksums = DIST / "SHA256SUMS.txt"
    with checksums.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(
            "".join(f"{sha256(path)}  {path.name}\n" for path in archives)
        )
    print(f"checksums: {checksums.name}")

    for archive in archives:
        size_mb = archive.stat().st_size / (1024 * 1024)
        print(f"  {archive.name}  {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
