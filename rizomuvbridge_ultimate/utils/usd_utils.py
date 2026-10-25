"""Helper functions for working with USD files (Maya)."""

import json
import logging
from typing import Dict, List, Optional

import maya.cmds as cmds

from .hooks.usd_hook import CHASER_NAME, UsdHookRizom

logger = logging.getLogger(__name__)


def register_hook() -> bool:
    """Load mayaUsd and register the USD chasers on first USD use.

    Returns:
        True if the chasers are registered and can be passed to
        ``mayaUSDExport`` / ``mayaUSDImport``.

    """
    try:
        cmds.loadPlugin("mayaUsdPlugin", quiet=True)
    except RuntimeError as e:
        logger.warning(f"Could not load mayaUsdPlugin: {e}")
        return False

    from .hooks import usd_hook

    return usd_hook.register()


def _leaf_name(node: str) -> str:
    """Return the short name of a DAG node or namespace-qualified name."""
    return node.rsplit("|", 1)[-1].rsplit(":", 1)[-1]


def get_name_from_prim(prim: str):
    """Get the object name and data name from a USD prim path."""
    split = prim.split("/")
    if len(split) > 1:
        return split[-2], split[-1]
    return split[-1], split[-1]


def name_to_xform(name: str) -> str:
    """Convert a name into a valid USD xform identifier."""
    if not name or not name[0].isalpha():
        return "".join("_" if not c.isalnum() else c for c in ("_" + name))
    return "".join("_" if not c.isalnum() else c for c in name)


def import_usd_props(
    objects: List[str],
    prop_keys: Optional[Dict[str, str]] = None,
):
    """Apply stored USD properties onto Maya nodes as custom attributes.

    Args:
        objects: Maya nodes that should receive the attributes.
        prop_keys: Optional mapping from Maya node name to the prim name
            used as the key in the hook properties.

    """
    props = UsdHookRizom.properties
    if not props:
        return

    for node in objects:
        key = (prop_keys or {}).get(node) or _leaf_name(node)
        node_props = props.get(key)
        if node_props is None:
            continue

        if not cmds.attributeQuery("rizomuv_attributes", node=node, exists=True):
            cmds.addAttr(
                node,
                longName="rizomuv_attributes",
                dataType="string",
            )
        cmds.setAttr(
            f"{node}.rizomuv_attributes",
            json.dumps(node_props),
            type="string",
        )

    props.clear()


def export_usd_props(objects: List[str]):
    """Read custom rizomuv_attributes off Maya nodes into the USD hook."""
    UsdHookRizom.properties.clear()

    for node in objects:
        if not cmds.attributeQuery("rizomuv_attributes", node=node, exists=True):
            continue
        props = cmds.getAttr(f"{node}.rizomuv_attributes")
        if props:
            UsdHookRizom.properties[_leaf_name(node)] = json.loads(props)
