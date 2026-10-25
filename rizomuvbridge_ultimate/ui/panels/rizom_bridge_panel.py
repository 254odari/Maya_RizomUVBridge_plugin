"""Main panel for the addon (Maya edition).

Maya has no declarative panel system; each section is built imperatively
into a parent layout. The ``build_bridge_section`` entry point is called by
``ui/__init__.py`` when the window is (re)built.
"""

import platform

import maya.cmds as cmds

from ...utils import addon_utils
from ..constants import BRIDGE_FRAME


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

def build_bridge_section(parent: str):
    """Build the main RizomUV Bridge panel into ``parent``."""

    cmds.frameLayout(
        BRIDGE_FRAME,
        label="RizomUV Bridge - Ultimate Edition",
        collapsable=True,
        collapse=False,
        parent=parent,
        marginWidth=4,
        marginHeight=4,
    )
    cmds.columnLayout(
        "rizomBridgeInner",
        adjustableColumn=True,
        rowSpacing=6,
        parent=BRIDGE_FRAME,
    )

    _build_tab_bar()
    _rebuild_tab_content()

    cmds.setParent("..")
    cmds.setParent("..")


# ---------------------------------------------------------------------------
# Tab bar
# ---------------------------------------------------------------------------

def _build_tab_bar():
    """Two-button row that mimics the OPERATIONS / ADDON_SETTINGS enum.

    ``adjustableColumn`` is a 1-based column index. Passing 0 makes Maya
    raise "Invalid column number specified".
    """
    current = _get_current_tab()

    cmds.rowLayout(
        numberOfColumns=2,
        adjustableColumn=1,
        columnWidth2=(150, 150),
        columnAlign2=("left", "left"),
        columnAttach2=("both", "both"),
        parent="rizomBridgeInner",
    )

    cmds.button(
        "rizomTabOperations",
        label="UV Transfer",
        height=26,
        backgroundColor=(
            (0.4, 0.4, 0.4) if current == "OPERATIONS" else (0.25, 0.25, 0.25)
        ),
        command=lambda *_: _on_tab_change("OPERATIONS"),
    )
    cmds.button(
        "rizomTabSettings",
        label="Addon Settings",
        height=26,
        backgroundColor=(
            (0.4, 0.4, 0.4) if current == "ADDON_SETTINGS" else (0.25, 0.25, 0.25)
        ),
        command=lambda *_: _on_tab_change("ADDON_SETTINGS"),
    )

    cmds.setParent("rizomBridgeInner")


# ---------------------------------------------------------------------------
# Tab content
# ---------------------------------------------------------------------------

def _rebuild_tab_content():
    """Delete the current tab body and rebuild it for the active tab."""
    if cmds.frameLayout("rizomTabBody", exists=True):
        cmds.deleteUI("rizomTabBody")

    cmds.frameLayout(
        "rizomTabBody",
        label="",
        collapsable=False,
        borderVisible=False,
        parent="rizomBridgeInner",
        marginWidth=0,
        marginHeight=0,
    )
    cmds.columnLayout(
        "rizomTabBodyInner",
        adjustableColumn=True,
        rowSpacing=6,
        parent="rizomTabBody",
    )

    tab = _get_current_tab()
    if tab == "OPERATIONS":
        _draw_operations_ui("rizomTabBodyInner")
    else:
        _draw_addon_settings_ui("rizomTabBodyInner")

    cmds.setParent("..")
    cmds.setParent("..")


def _on_tab_change(tab: str):
    _set_current_tab(tab)
    _rebuild_tab_content()

    if cmds.button("rizomTabOperations", exists=True):
        cmds.button(
            "rizomTabOperations",
            edit=True,
            backgroundColor=(
                (0.4, 0.4, 0.4) if tab == "OPERATIONS" else (0.25, 0.25, 0.25)
            ),
        )
    if cmds.button("rizomTabSettings", exists=True):
        cmds.button(
            "rizomTabSettings",
            edit=True,
            backgroundColor=(
                (0.4, 0.4, 0.4) if tab == "ADDON_SETTINGS" else (0.25, 0.25, 0.25)
            ),
        )


# ---------------------------------------------------------------------------
# OPERATIONS tab
# ---------------------------------------------------------------------------

def _draw_operations_ui(parent: str):
    """Build the Operations tab contents into ``parent``."""

    prefs = addon_utils.get_prefs()

    cmds.frameLayout(
        "rizomMainOpsFrame",
        label="Main Operations",
        collapsable=False,
        parent=parent,
        marginWidth=4,
        marginHeight=4,
    )
    cmds.columnLayout(
        adjustableColumn=True, rowSpacing=6, parent="rizomMainOpsFrame"
    )

    # --- Export / Import ---
    cmds.rowLayout(
        numberOfColumns=2,
        adjustableColumn=1,
        columnWidth2=(150, 150),
        columnAlign2=("left", "left"),
        columnAttach2=("both", "both"),
        parent="rizomMainOpsFrame",
    )
    cmds.button(
        label="Export",
        height=30,
        command=lambda *_: _safe_command("rizomExport"),
        annotation="Export selected objects to a file and load in RizomUV",
    )
    cmds.button(
        label="Import",
        height=30,
        command=lambda *_: _safe_command("rizomImport"),
        annotation="Import meshes from RizomUV and transfer UV maps",
    )
    cmds.setParent("rizomMainOpsFrame")

    # --- Close Rizom (LiveLink only) ---
    if prefs.use_livelink:
        cmds.button(
            label="Close Rizom",
            height=26,
            command=lambda *_: _run_rizom_action("CLOSE"),
            annotation="Close the RizomUV instance",
            parent="rizomMainOpsFrame",
        )

    _uv_map_row(parent="rizomMainOpsFrame")
    _format_load_row(parent="rizomMainOpsFrame")

    if prefs.use_livelink:
        _action_row(parent="rizomMainOpsFrame")

    cmds.setParent("..")
    cmds.setParent("..")

    # --- Texture (LiveLink + export_texture only) ---
    if prefs.use_livelink and prefs.export_texture:
        _texture_ui(parent=parent)


def _uv_map_row(parent: str):
    """Row: [ UV Map ▼ ] [ Rename ] [ ↻ ]"""
    from ...properties.property_groups import RizomBridgeUVMaps

    cmds.rowLayout(
        numberOfColumns=3,
        adjustableColumn=1,
        columnWidth3=(160, 80, 24),
        columnAlign3=("left", "left", "left"),
        columnAttach3=("both", "both", "both"),
        parent=parent,
    )

    cmds.optionMenu("rizomUvmapMenu", changeCommand=_on_uvmap_change)
    for _, label, _ in _safe_uvmaps():
        cmds.menuItem(label=label)

    active = RizomBridgeUVMaps.get_active()
    if active:
        cmds.optionMenu("rizomUvmapMenu", edit=True, value=active)

    cmds.button(
        label="Rename",
        height=22,
        command=lambda *_: _safe_command("rizomRenameUVMaps"),
    )
    cmds.button(
        label="↻",
        width=24,
        height=22,
        command=lambda *_: _refresh_uvmap_menu(),
        annotation="Refresh UV map list",
    )
    cmds.setParent(parent)


def _format_load_row(parent: str):
    """Row: [ Format ▼ ] [ Load ]"""
    prefs = addon_utils.get_prefs()

    cmds.rowLayout(
        numberOfColumns=2,
        adjustableColumn=1,
        columnWidth2=(160, 100),
        columnAlign2=("left", "left"),
        columnAttach2=("both", "both"),
        parent=parent,
    )
    cmds.optionMenu(
        "rizomFormatMenu",
        changeCommand=lambda v: addon_utils.set_pref("export_format", v),
    )
    for fmt in ("FBX", "OBJ", "USD"):
        cmds.menuItem(label=fmt)
    cmds.optionMenu("rizomFormatMenu", edit=True, value=prefs.export_format)

    cmds.button(
        label="Load",
        height=22,
        command=lambda *_: _safe_command("rizomLoad"),
        annotation="Load the selected file format into RizomUV",
    )
    cmds.setParent(parent)


def _action_row(parent: str):
    """Row: [ Action ▼ ] — friendly labels, identifier values.

    Menu items display human-readable labels (from ``ACTIONS[key][1]``),
    while the preference stores the identifier (``ACTIONS[key][0]``). We
    translate in both directions:

    * on change: friendly label -> identifier (what gets persisted)
    * on initial value: identifier -> friendly label (what the menu shows)
    """
    prefs = addon_utils.get_prefs()
    from ... import addon_constants

    action_keys = (
        "EXPORT", "USE_SEAMS", "RESET_UVS",
        "SHARP_EDGES", "MOSAIC", "PELT", "BOX",
    )
    # Friendly label -> identifier (for the change callback).
    label_to_id = {addon_constants.ACTIONS[k][1]: k for k in action_keys}
    # Identifier -> friendly label (for setting the current menu value).
    id_to_label = {v: k for k, v in label_to_id.items()}

    cmds.rowLayout(
        numberOfColumns=2,
        adjustableColumn=2,
        columnWidth2=(60, 220),
        columnAlign2=("left", "left"),
        columnAttach2=("both", "both"),
        parent=parent,
    )
    cmds.text(label="Action")

    def _on_action_change(label):
        identifier = label_to_id.get(label)
        if identifier:
            addon_utils.set_pref("export_action", identifier)

    cmds.optionMenu("rizomActionMenu", changeCommand=_on_action_change)
    for k in action_keys:
        cmds.menuItem(label=addon_constants.ACTIONS[k][1])

    current_label = id_to_label.get(prefs.export_action)
    if current_label:
        cmds.optionMenu("rizomActionMenu", edit=True, value=current_label)

    cmds.setParent(parent)


def _texture_ui(parent: str):
    """Texture file picker + display toggles."""
    prefs = addon_utils.get_prefs()

    cmds.frameLayout(
        "rizomTextureFrame",
        label="Texture",
        collapsable=False,
        parent=parent,
        marginWidth=4,
        marginHeight=4,
    )
    cmds.columnLayout(
        adjustableColumn=True, rowSpacing=4, parent="rizomTextureFrame"
    )

    cmds.rowLayout(
        numberOfColumns=3,
        adjustableColumn=2,
        columnWidth3=(50, 160, 24),
        columnAlign3=("left", "left", "left"),
        columnAttach3=("both", "both", "both"),
        parent="rizomTextureFrame",
    )
    cmds.text(label="File")
    cmds.textField(
        "rizomTexturePath",
        text=prefs.rizom_texture,
        changeCommand=lambda v: addon_utils.set_pref("rizom_texture", v),
    )
    cmds.button(label="…", width=22, command=lambda *_: _browse_texture())
    cmds.setParent("rizomTextureFrame")

    cmds.text(
        label="Display Texture On:",
        align="left",
        parent="rizomTextureFrame",
    )
    for attr, label in (
        ("background_texture", "Background"),
        ("uv_texture", "UV Islands"),
        ("mesh_texture", "Meshes"),
    ):
        cmds.checkBox(
            f"rizom_{attr}",
            label=label,
            value=bool(getattr(prefs, attr)),
            changeCommand=_bool_cb(attr),
            parent="rizomTextureFrame",
            align="left",
        )

    cmds.setParent("..")
    cmds.setParent("..")


# ---------------------------------------------------------------------------
# ADDON_SETTINGS tab
# ---------------------------------------------------------------------------

def _draw_addon_settings_ui(parent: str):
    prefs = addon_utils.get_prefs()

    # --- Addon Settings box ---
    cmds.frameLayout(
        "rizomAddonSettingsFrame",
        label="Addon Settings",
        collapsable=False,
        parent=parent,
        marginWidth=4,
        marginHeight=4,
    )
    cmds.columnLayout(
        adjustableColumn=True, rowSpacing=6, parent="rizomAddonSettingsFrame"
    )

    cmds.rowLayout(
        numberOfColumns=3,
        adjustableColumn=2,
        columnWidth3=(80, 160, 24),
        columnAlign3=("left", "left", "left"),
        columnAttach3=("both", "both", "both"),
        parent="rizomAddonSettingsFrame",
    )
    cmds.text(label="Rizom Path")
    cmds.textField(
        "rizomPathField",
        text=prefs.rizom_path,
        changeCommand=lambda v: addon_utils.set_pref("rizom_path", v),
    )
    cmds.button(label="…", width=22, command=lambda *_: _browse_rizom())
    cmds.setParent("rizomAddonSettingsFrame")

    livelink_cb = cmds.checkBox(
        "rizomUseLivelink",
        label="Use RizomUVLink Connection",
        value=bool(prefs.use_livelink),
        changeCommand=_bool_cb("use_livelink"),
        parent="rizomAddonSettingsFrame",
        align="left",
    )
    if not _livelink_available():
        cmds.checkBox(livelink_cb, edit=True, enable=False)

    cmds.setParent("..")
    cmds.setParent("..")

    # --- Interface box ---
    cmds.frameLayout(
        "rizomUiPrefsFrame",
        label="Interface",
        collapsable=True,
        collapse=True,
        parent=parent,
        marginWidth=4,
        marginHeight=4,
    )
    cmds.columnLayout(
        adjustableColumn=True, rowSpacing=4, parent="rizomUiPrefsFrame"
    )

    cmds.rowLayout(
        numberOfColumns=2,
        adjustableColumn=2,
        columnWidth2=(90, 200),
        columnAlign2=("left", "left"),
        columnAttach2=("both", "both"),
        parent="rizomUiPrefsFrame",
    )
    cmds.text(label="Tab Name")
    cmds.textField(
        "rizomTabNameField",
        text=prefs.addon_tab_name,
        changeCommand=lambda v: addon_utils.set_pref("addon_tab_name", v),
    )
    cmds.setParent("rizomUiPrefsFrame")

    cmds.rowLayout(
        numberOfColumns=2,
        adjustableColumn=2,
        columnWidth2=(90, 200),
        columnAlign2=("left", "left"),
        columnAttach2=("both", "both"),
        parent="rizomUiPrefsFrame",
    )
    cmds.text(label="Location")
    cmds.optionMenu(
        "rizomDockLocation",
        changeCommand=lambda v: addon_utils.set_pref("dock_location", v),
    )
    cmds.menuItem(label="SIDE")
    cmds.menuItem(label="HEADER")
    cmds.optionMenu("rizomDockLocation", edit=True, value=prefs.dock_location)
    cmds.setParent("rizomUiPrefsFrame")

    cmds.setParent("..")
    cmds.setParent("..")

    # --- Diagnostics box ---
    cmds.frameLayout(
        "rizomDiagnosticsFrame",
        label="Diagnostics",
        collapsable=True,
        collapse=True,
        parent=parent,
        marginWidth=4,
        marginHeight=4,
    )
    cmds.columnLayout(
        adjustableColumn=True, rowSpacing=4, parent="rizomDiagnosticsFrame"
    )

    cmds.checkBox(
        "rizomEnableLogging",
        label="Enable Logging",
        value=bool(prefs.enable_logging),
        changeCommand=_logging_cb,
        parent="rizomDiagnosticsFrame",
        align="left",
    )

    cmds.setParent("..")
    cmds.setParent("..")

    # --- Axes + timeout box ---
    cmds.frameLayout(
        "rizomAxesFrame",
        label="Axes & Timeout",
        collapsable=True,
        collapse=True,
        parent=parent,
        marginWidth=4,
        marginHeight=4,
    )
    cmds.columnLayout(
        adjustableColumn=True, rowSpacing=4, parent="rizomAxesFrame"
    )

    for attr, label in (("up_axis", "Up Axis"), ("forward_axis", "Forward Axis")):
        _enum_row_inline(
            attr,
            label,
            ("X", "Y", "Z", "NEGATIVE_X", "NEGATIVE_Y", "NEGATIVE_Z"),
            parent="rizomAxesFrame",
        )

    cmds.rowLayout(
        numberOfColumns=2,
        adjustableColumn=2,
        columnWidth2=(150, 140),
        columnAlign2=("left", "left"),
        columnAttach2=("both", "both"),
        parent="rizomAxesFrame",
    )
    cmds.text(label="RizomUV Timeout (s)")
    cmds.intField(
        "rizomTimeoutField",
        value=int(prefs.connection_timeout),
        minValue=10,
        changeCommand=lambda v: addon_utils.set_pref("connection_timeout", int(v)),
    )
    cmds.setParent("rizomAxesFrame")

    cmds.setParent("..")
    cmds.setParent("..")


# ---------------------------------------------------------------------------
# Callbacks and helpers
# ---------------------------------------------------------------------------

def _safe_command(command_name: str):
    try:
        getattr(cmds, command_name)()
    except RuntimeError as e:
        cmds.warning(str(e))
    except AttributeError:
        cmds.warning(
            f"Command '{command_name}' is not registered. "
            "Is the RizomUV Bridge plugin loaded?"
        )


def _run_rizom_action(action: str):
    try:
        cmds.rizomAction(action=action)
    except RuntimeError as e:
        cmds.warning(str(e))


def _on_uvmap_change(uv_name: str):
    from ...properties.property_groups import RizomBridgeUVMaps
    if uv_name in ("NO_OBJ", "NO_UV"):
        return
    RizomBridgeUVMaps.set_active(uv_name)


def _refresh_uvmap_menu():
    if not cmds.optionMenu("rizomUvmapMenu", exists=True):
        return
    for item in cmds.optionMenu("rizomUvmapMenu", query=True, itemListLong=True) or []:
        cmds.deleteUI(item)
    for _, label, _ in _safe_uvmaps():
        cmds.menuItem(label=label, parent="rizomUvmapMenu")


def _safe_uvmaps():
    from ...properties.property_groups import get_uvmaps
    try:
        return get_uvmaps()
    except Exception:
        return [("NO_OBJ", "[No object selected]", "")]


def _browse_rizom():
    path = cmds.fileDialog2(
        fileMode=1,
        caption="Select the RizomUV executable",
        fileFilter=_rizom_path_filter(),
    )
    if path:
        addon_utils.set_pref("rizom_path", path[0])
        if cmds.textField("rizomPathField", exists=True):
            cmds.textField("rizomPathField", edit=True, text=path[0])


def _browse_texture():
    path = cmds.fileDialog2(
        fileMode=1,
        caption="Select a texture file",
        fileFilter="Image files (*.png *.jpg *.jpeg *.tga *.bmp *.tiff)",
    )
    if path:
        addon_utils.set_pref("rizom_texture", path[0])
        if cmds.textField("rizomTexturePath", exists=True):
            cmds.textField("rizomTexturePath", edit=True, text=path[0])


def _bool_cb(attr: str):
    def _cb(value):
        addon_utils.set_pref(attr, bool(value))
    return _cb


def _logging_cb(value):
    addon_utils.set_pref("enable_logging", bool(value))
    from ...utils.update_callbacks import logging_toggle
    import logging as _logging
    logging_toggle(bool(value), _logging.getLogger("rizomuv_bridge"))


def _enum_row_inline(attr: str, label: str, items, parent: str):
    cmds.rowLayout(
        numberOfColumns=2,
        adjustableColumn=2,
        columnWidth2=(150, 140),
        columnAlign2=("left", "left"),
        columnAttach2=("both", "both"),
        parent=parent,
    )
    cmds.text(label=label)
    menu = cmds.optionMenu(
        f"rizom_{attr}",
        changeCommand=lambda v: addon_utils.set_pref(attr, v),
    )
    for item in items:
        cmds.menuItem(label=item)
    current = getattr(addon_utils.get_prefs(), attr)
    if current in items:
        cmds.optionMenu(menu, edit=True, value=current)
    cmds.setParent(parent)


# ---------------------------------------------------------------------------
# Platform / capability helpers
# ---------------------------------------------------------------------------

def _livelink_available() -> bool:
    try:
        from ...classes.rizom.modern.rizom_link import _livelink_is_available
        return _livelink_is_available()
    except Exception:
        return False


def _rizom_path_filter() -> str:
    system = platform.system()
    if system == "Windows":
        return "RizomUV (rizomuv.exe)"
    if system == "Darwin":
        return "RizomUV (RizomUV.app);;Any (*)"
    return "RizomUV (RizomUV)"


# ---------------------------------------------------------------------------
# Tab state
# ---------------------------------------------------------------------------

_TAB_OPTION = "rizomUVBridge_current_tab"


def _get_current_tab() -> str:
    if cmds.optionVar(exists=_TAB_OPTION):
        value = cmds.optionVar(q=_TAB_OPTION)
        if value in ("OPERATIONS", "ADDON_SETTINGS"):
            return value
    return "OPERATIONS"


def _set_current_tab(tab: str):
    cmds.optionVar(sv=(_TAB_OPTION, tab))