"""Preferences for handling addon configuration (Maya)."""

import logging
import platform

from ..utils import rizom_utils
from ..utils.update_callbacks import logging_toggle
from ._pref_base import BoolPref, EnumPref, IntPref, StringPref

logger = logging.getLogger(__name__)


def _logging_update(self, value):
    logging_toggle(bool(value), logger)


class ConfigPreferences:
    """Preferences for handling addon configuration."""

    rizom_path = StringPref(
        "rizom_path",
        default=rizom_utils.get_rizom_path() or "",
        # subtype="FILE_PATH" is not a Maya concept; the UI uses fileDialog2.
    )

    use_livelink = BoolPref(
        "use_livelink",
        default=(platform.system() == "Windows"),
        # description="Use the RizomUVLink module (Windows only / Rizom 2023+)"
    )

    enable_logging = BoolPref(
        "enable_logging",
        default=True,
        update=_logging_update,
    )

    connection_timeout = IntPref(
        "connection_timeout",
        default=10,
        min=10,
        # description="Seconds Maya will wait for RizomUV before cancelling."
    )