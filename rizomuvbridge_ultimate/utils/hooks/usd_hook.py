"""USD hook which runs during USD import and export in Maya.

Uses mayaUsd export / import chasers to attach RizomUV-specific attributes
to USD prims on export and to recover them on import. Chasers must be named
in the ``chaser`` argument of ``mayaUSDExport`` / ``mayaUSDImport``.

The public surface (``UsdHookRizom``) mirrors the original Blender class so
the rest of the bridge code is unchanged.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Dict, List

try:
    from pxr import Sdf, Usd  # type: ignore
    _PX_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on the Maya install
    Sdf = Usd = None  # type: ignore
    _PX_AVAILABLE = False

logger = logging.getLogger(__name__)

# Name used for the chasers in mayaUSDExport / mayaUSDImport.
CHASER_NAME = "rizomuv"

UsdTypes = (
    "float[]",
    "int[]",
    "string[]",
    "bool[]",
    "double[]",
    "float",
    "int",
    "string",
    "bool",
    "double",
)

USD_TYPE_MAP = {
    "float[]": Sdf.ValueTypeNames.FloatArray,
    "int[]": Sdf.ValueTypeNames.IntArray,
    "string[]": Sdf.ValueTypeNames.StringArray,
    "bool[]": Sdf.ValueTypeNames.BoolArray,
    "double[]": Sdf.ValueTypeNames.DoubleArray,
    "float": Sdf.ValueTypeNames.Float,
    "int": Sdf.ValueTypeNames.Int,
    "string": Sdf.ValueTypeNames.String,
    "bool": Sdf.ValueTypeNames.Bool,
    "double": Sdf.ValueTypeNames.Double,
} if _PX_AVAILABLE else {}


class UsdHookRizom:
    """RizomUV USD hook state shared with the chasers.

    Class-level state (``properties``, ``is_enabled``) is stored on the class
    itself to match the original static-field usage.
    """

    properties: Dict[str, List[dict]] = {}
    is_enabled: bool = False

    @classmethod
    def enable(cls):
        """Enable the hook."""
        cls.is_enabled = True

    @classmethod
    def disable(cls):
        """Disable the hook."""
        cls.is_enabled = False

    @classmethod
    @contextmanager
    def enabled(cls):
        """Context manager to temporarily enable the hook."""
        cls.enable()
        try:
            yield
        finally:
            cls.disable()

    @staticmethod
    def _write_to_stage(stage: Any):
        """Write stored RizomUV properties onto matching prims in the stage."""
        if not stage or not UsdHookRizom.properties:
            return

        for prim in stage.Traverse():
            prop_array = UsdHookRizom.properties.get(prim.GetName())
            if not prop_array:
                continue

            for prop_dict in prop_array:
                prop_name = prop_dict.get("prop")
                prop_type = prop_dict.get("type")
                value = prop_dict.get("value")

                if not prop_name or not prop_type or value is None:
                    logger.warning(
                        f"Skipping {prop_name}: incomplete property dict."
                    )
                    continue

                usd_type = USD_TYPE_MAP.get(prop_type)
                if not usd_type:
                    logger.warning(
                        f"Skipping {prop_name}: unknown USD type '{prop_type}'."
                    )
                    continue

                prim.CreateAttribute(prop_name, usd_type).Set(value)

    @staticmethod
    def _extract_from_prim(prim: Any):
        """Extract RizomUV attributes from a single prim (no recursion)."""
        for prop in prim.GetPropertyNames():
            if not prop.startswith("RizomUV:"):
                continue
            attribute = prim.GetAttribute(prop)
            if not attribute:
                continue

            prop_type = str(attribute.GetTypeName())
            value = attribute.Get()

            if prop_type.endswith("[]") and value is not None:
                value = list(value)

            rizom_prop = {
                "prop": prop,
                "type": prop_type,
                "value": value,
            }
            props = UsdHookRizom.properties.setdefault(prim.GetName(), [])
            if not any(item.get("prop") == prop for item in props):
                props.append(rizom_prop)

    @staticmethod
    def _extract_from_stage(stage: Any):
        """Extract RizomUV attributes from every prim in the stage."""
        if not stage:
            return
        for prim in stage.Traverse():
            UsdHookRizom._extract_from_prim(prim)


# ---------------------------------------------------------------------------
# mayaUsd chaser registration
# ---------------------------------------------------------------------------

_maya_usd_registered: bool = False
_export_chaser_class = None
_import_chaser_class = None


def _try_register_maya_usd() -> bool:
    """Register export / import chasers with mayaUsd if available."""
    if not _PX_AVAILABLE:
        logger.debug("pxr not available; USD hook will be passive.")
        return False
    try:
        from mayaUsd.lib import (  # type: ignore
            ExportChaser,
            ImportChaser,
        )
    except ImportError:
        logger.debug("mayaUsd not available; USD hook will be passive.")
        return False

    class RizomUsdExportChaser(ExportChaser):
        """Adds RizomUV attributes to prims during USD export."""

        def __init__(self, factory_context, *args, **kwargs):
            super().__init__(factory_context, *args, **kwargs)
            self._stage = factory_context.GetStage()

        def ExportDefault(self):
            return self.ExportFrame(Usd.TimeCode.Default())

        def ExportFrame(self, frame):
            return True

        def PostExport(self):
            if UsdHookRizom.is_enabled:
                UsdHookRizom._write_to_stage(self._stage)
            return True

    class RizomUsdImportChaser(ImportChaser):
        """Recovers RizomUV attributes from prims during USD import."""

        def PostImport(
            self, return_predicate, stage, dag_paths, sdf_paths, job_args
        ):
            if UsdHookRizom.is_enabled:
                UsdHookRizom._extract_from_stage(stage)
            return True

    global _export_chaser_class, _import_chaser_class
    try:
        ExportChaser.Register(RizomUsdExportChaser, CHASER_NAME)
        ImportChaser.Register(RizomUsdImportChaser, CHASER_NAME)
    except Exception as e:
        logger.warning(f"Failed to register mayaUsd chasers: {e}")
        return False

    _export_chaser_class = RizomUsdExportChaser
    _import_chaser_class = RizomUsdImportChaser
    logger.info("RizomUV USD export/import chasers registered with mayaUsd.")
    return True


def register() -> bool:
    """Register the mayaUsd chasers (no-op if already registered)."""
    global _maya_usd_registered
    if _maya_usd_registered:
        return True
    _maya_usd_registered = _try_register_maya_usd()
    return _maya_usd_registered


def unregister():
    """Unregister the chasers and clear all hook state."""
    global _maya_usd_registered, _export_chaser_class, _import_chaser_class

    if _export_chaser_class is not None:
        try:
            from mayaUsd.lib import ExportChaser, ImportChaser  # type: ignore

            ExportChaser.Unregister(_export_chaser_class, CHASER_NAME)
            ImportChaser.Unregister(_import_chaser_class, CHASER_NAME)
        except Exception as e:
            logger.warning(f"Failed to unregister mayaUsd chasers: {e}")

    _export_chaser_class = None
    _import_chaser_class = None
    _maya_usd_registered = False
    UsdHookRizom.properties.clear()
    UsdHookRizom.disable()
