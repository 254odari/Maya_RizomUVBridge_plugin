"""Preferences for handling RizomUV app settings (Maya)."""

from ._pref_base import BoolPref, FloatPref, IntPref, StringPref


class RizomPreferences:
    """Preferences for handling RizomUV app settings."""

    link_gaps = BoolPref("link_gaps", default=False)

    open_cylinders = BoolPref("open_cylinders", default=False)

    cut_handles = BoolPref("cut_handles", default=False)

    sharp_angle = IntPref("sharp_angle", default=70, min=0, max=180)

    mosaic_force = FloatPref("mosaic_force", default=0.5, min=0.0, max=1.0)

    pelt_trunk = BoolPref("pelt_trunk", default=False)

    pelt_branch = BoolPref("pelt_branch", default=False)

    pelt_leaf = BoolPref("pelt_leaf", default=False)

    texture_path = StringPref("texture_path", default="")

    stretch_limiter = FloatPref("stretch_limiter", default=0.25, min=0.0, max=0.99)

    rizom_texture = StringPref("rizom_texture", default="")

    background_texture = BoolPref("background_texture", default=False)

    uv_texture = BoolPref("uv_texture", default=False)

    mesh_texture = BoolPref("mesh_texture", default=False)