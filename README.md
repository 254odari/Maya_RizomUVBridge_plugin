# RizomUV Bridge — Ultimate Edition for Maya

Version 3.3.3 · Autodesk Maya 2026 (Python 3.11) · Windows

A two-way bridge between Maya and RizomUV Standalone. Send selected meshes to
RizomUV, unwrap or edit UVs there, and bring the UV maps back onto the original
Maya objects — with optional LiveLink for direct control of a running RizomUV
instance.

## Features

- **Export / Import** meshes and UV sets between Maya and RizomUV.
- **FBX, OBJ and USD** transfer formats (USD requires the MayaUSD plug-in that
  ships with Maya 2026).
- **LiveLink** via the bundled RizomUVLink API: load files, run unwrap actions
  and read UV maps without leaving Maya.
- **UV map tools**: choose the active UV set, rename UV sets to RizomUV-safe
  names, refresh the list.
- **Unwrap actions**: reset UVs, use seams, sharp edges, mosaic, pelt and box.
- **Name validation and repair** for RizomUV's stricter naming rules.
- **USD metadata round-trip** through custom `RizomUV:*` prim attributes.
- Optional texture display in RizomUV, configurable axes, timeouts and logging.

## Requirements

| Component | Requirement |
| --- | --- |
| Maya | 2026 (Python 3.11) |
| OS | Windows 10/11 — the bundled RizomUVLink native libraries are Windows-only |
| RizomUV | Standalone 2022.2 or newer for LiveLink |
| USD | MayaUSD, bundled with Maya 2026 |

## Installation (Maya module — recommended)

1. Unzip the release.
2. Copy **both** of these into:

   ```
   C:\Users\<you>\Documents\maya\2026\modules\
   ```

   (create the folder if it does not exist)

   - `RizomUVBridge.mod`
   - the `RizomUVBridge` folder

   The result should look like:

   ```
   Documents\maya\2026\modules\
     RizomUVBridge.mod
     RizomUVBridge\
       plug-ins\
         RizomUVBridge_plugin.py
         rizomuvbridge_ultimate\
   ```

   Maya only scans `.mod` files directly inside module-path folders, so do
   not leave the module file one folder deeper.

   Alternatively, keep the release folder intact and add it to
   `MAYA_MODULE_PATH`.
3. Restart Maya.
4. Open **Windows → Settings/Preferences → Plug-in Manager**, find
   `RizomUVBridge_plugin`, and tick **Loaded** and **Auto load**.

## Installation (manual)

Copy `RizomUVBridge\plug-ins\RizomUVBridge_plugin.py` **and** the
`RizomUVBridge\plug-ins\rizomuvbridge_ultimate` folder into
`Documents\maya\2026\scripts\`, then run:

```python
import maya.cmds as cmds
cmds.loadPlugin("RizomUVBridge_plugin")
```

## Opening the panel

```python
import maya.cmds as cmds
cmds.rizomShowWindow()
```

Assign that line to a shelf button if you want one-click access. The panel
remembers its tab and dock position in Maya's option variables.

## Configuration

Open the **Addon Settings** tab of the panel:

1. Set **Rizom Path** to your `rizomuv.exe`.
2. Leave **Use RizomUVLink Connection** enabled for LiveLink, or disable it to
   use the file-based transport.
3. Adjust format, axes, timeout and logging as needed.

## Typical workflow

1. Select one or more mesh objects in Maya.
2. In **UV Transfer**, choose a format (FBX / OBJ / USD) and press **Export**.
3. Maya writes the selection to RizomUV, opening or loading it automatically.
4. Edit or unwrap the UVs in RizomUV.
5. Press **Import** in Maya. UV maps are transferred back onto the original
   objects, including renamed or newly created UV sets.

Transfer files are written to:

```
C:\Users\<you>\Documents\maya\2026\prefs\RizomUV Bridge\mesh_files\
```

The mesh file is named after the current scene. Session and port files live in
the parent folder, `RizomUV Bridge`.

## Troubleshooting

- **Plug-in not listed in Plug-in Manager** — confirm the module folder is
  directly under `Documents\maya\2026\modules` and contains `RizomUVBridge.mod`;
  restart Maya.
- **LiveLink unavailable** — check the Rizom Path and that RizomUV is 2022.2 or
  newer. Windows only.
- **USD transfer fails** — load `mayaUsdPlugin` (Maya 2026 ships it). USD import
  is supported for one or more root prims.
- **Nothing appears in RizomUV** — check that the selected objects contain
  meshes and that the Rizom path is correct.
- **Need diagnostics** — enable **Addon Settings → Diagnostics → Enable Logging**
  and check the Script Editor.

## Uninstall

Unload the plug-in in the Plug-in Manager, then delete the module folder (or the
manually copied files). Optionally delete `Documents\maya\2026\prefs\RizomUV Bridge`.

## Building a release

From the repository root, using Maya's interpreter so that compiled bytecode
matches Maya's Python version:

```bat
"C:\Program Files\Autodesk\Maya2026\bin\mayapy.exe" tools\build_release.py
```

The script writes to `dist/`:

- `RizomUVBridge-3.3.3-maya2026-source.zip` — source module package.
- `RizomUVBridge-3.3.3-maya2026-py311-compiled.zip` — same package with the
  bridge's own modules compiled to `.pyc` for Maya 2026. The entry point,
  `rizom_script.py` (executed by RizomUV's embedded Python) and the vendored
  RizomUVLink stay as source.

Compiled bytecode is not encryption and only runs on the matching Python minor
version. Use the source package if users need to audit or patch the code.

## Third-party software

RizomUVLink is © Rizom-Lab and licensed under the MIT License. See
`THIRD_PARTY_NOTICES.md` and
`RizomUVBridge\plug-ins\rizomuvbridge_ultimate\lib\RizomUVLink\LICENSE.md`.
