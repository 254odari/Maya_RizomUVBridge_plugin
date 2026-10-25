"""Utility functions for handling exceptions (Maya)."""

import logging
import traceback
from typing import Callable, Optional

import maya.cmds as cmds

logger = logging.getLogger(__name__)


def report_and_log_exception(exception: Exception, fn: Optional[Callable] = None):
    """Report an exception to the Maya script editor and log it.

    Args:
        exception: The exception to report.
        fn: A function to call after logging the exception.

    """
    cmds.warning(str(exception))
    logger.error(traceback.format_exc())

    if fn:
        fn()