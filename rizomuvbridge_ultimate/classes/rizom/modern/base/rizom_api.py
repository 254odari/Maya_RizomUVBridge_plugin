"""Wraps the basic RizomUV API commands."""

import logging
from typing import Any, Dict, Literal, Optional

from .rizom_connection_manager import RizomConnectionManager

logger = logging.getLogger(__name__)


class RizomApi:
    """Thin façade over the vendored ``CRizomUVLink`` object.

    Every method delegates to ``self.rizomuv._link.<Command>(...)``. This class
    exists so callers don't have to reach through the connection manager, and so
    the bridge has a single place to add pre/post-conditions (version checks,
    argument sanitising) without touching the vendored library.
    """

    def __init__(self, connection: RizomConnectionManager):
        self.rizomuv = connection

    # -- lifecycle ---------------------------------------------------------

    def load(self, params: Dict[str, Any]) -> Any:
        """Wrap the Load command."""
        return self.rizomuv._link.Load(params)

    def quit(self) -> None:
        """Wrap the Quit command."""
        self.rizomuv._link.Quit()

    # -- queries -----------------------------------------------------------

    def item_names(self, path: str) -> Any:
        """Wrap the ItemNames command."""
        return self.rizomuv._link.ItemNames(path)

    def get(self, path: str) -> Any:
        """Wrap the Get command."""
        return self.rizomuv._link.Get(path)

    # -- setters -----------------------------------------------------------

    def set(self, params: Dict[str, Any]) -> Any:
        """Wrap the Set command."""
        return self.rizomuv._link.Set(params)

    def uv_set(self, params: Dict[str, Any]) -> Any:
        """Wrap the Uvset command."""
        return self.rizomuv._link.Uvset(params)

    def reset_to_3d(self) -> None:
        """Wrap the ResetTo3D command."""
        self.rizomuv._link.ResetTo3d({"WorkingSet": "Visible", "Rescale": True})

    # -- textures ----------------------------------------------------------

    def load_user_texture(
        self,
        texture_path: str,
        background_on: bool,
        uv_view: bool,
        mesh_view: bool,
    ) -> None:
        """Wrap the LoadUserTexture command.

        Args:
            texture_path: The path to the texture file.
            background_on: Render the texture in the UV window background.
            uv_view: Render the texture on UV islands.
            mesh_view: Render the texture on meshes.

        """
        if not texture_path.endswith((".png", ".jpg", ".jpeg", ".tga", ".bmp", ".tiff")):
            logger.warning(f"Unsupported texture format: {texture_path}")
            return

        self.rizomuv._link.LoadUserTexture(texture_path)

        # The ``version`` attribute is populated by
        # ``RizomConnectionManager.is_connected`` / ``start_new_instance``.
        version = self.rizomuv.version
        if version is None:
            logger.warning("RizomUV version unknown; skipping viewport texture setup.")
            return

        if version.major == 2023:
            if mesh_view:
                self.set({"Path": "Vars.Viewport.Texture", "Value": "User"})
                self.set({"Path": "Vars.Viewport.TextureID", "Value": 2})
            if uv_view:
                self.set({"Path": "Vars.Viewport.TextureID", "Value": 2})
                self.set({"Path": "Vars.Viewport.ViewportUV.Textured", "Value": True})
            if background_on:
                self.set({"Path": "Vars.Viewport.Texture", "Value": "User"})
                self.set({"Path": "Vars.Viewport.BackGroundTextureOn", "Value": True})

        elif version.major >= 2024:
            if mesh_view:
                self.set({"Path": "Vars.Viewport.Texture", "Value": "User"})
                self.set({"Path": "Vars.Viewport.Viewport3D.Textured", "Value": True})
            if uv_view:
                self.set({"Path": "Vars.Viewport.Texture", "Value": "User"})
                self.set({"Path": "Vars.Viewport.ViewportUV.Textured", "Value": True})
            if background_on:
                self.set({"Path": "Vars.Viewport.Texture", "Value": "User"})
                self.set({"Path": "Vars.Viewport.BackGroundTextureOn", "Value": True})

    # -- save --------------------------------------------------------------

    def save(self, format: Literal["OBJ", "FBX", "USD"], path: str) -> None:
        """Wrap the Save command.

        Args:
            format: The format to save the file in.
            path: The path to save the file to.

        """
        self.rizomuv._link.Save({
            "File": {
                format: {"UseUVSetNames": True},
                "Path": path,
                "UVWProps": True,
            }
        })

    # -- island groups -----------------------------------------------------

    def island_groups(self, params: Dict[str, Any]) -> Any:
        """Wrap the IslandGroups command."""
        return self.rizomuv._link.IslandGroups(params)