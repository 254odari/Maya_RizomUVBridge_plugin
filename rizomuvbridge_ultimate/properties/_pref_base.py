"""Shared base for Maya preference blocks.

Each preference subclass declares typed descriptors on the class body. These
descriptors read/write ``cmds.optionVar`` using a namespaced key so multiple
preference groups can coexist without collisions.
"""

from typing import Any, Callable, Optional

import maya.cmds as cmds


_OPTION_PREFIX = "rizomUVBridge_"


class _PrefDescriptor:
    """Descriptor that stores its value in a Maya optionVar."""

    def __init__(
        self,
        name: str,
        kind: str,
        default: Any = None,
        update: Optional[Callable] = None,
        min: Optional[float] = None,
        max: Optional[float] = None,
        items: Optional[list] = None,
    ):
        self.name = name
        self.kind = kind  # "bool" | "int" | "float" | "string" | "enum"
        self.default = default
        self.update = update
        self.min = min
        self.max = max
        self.items = items

    # -- key -----------------------------------------------------------------

    @property
    def _key(self) -> str:
        return _OPTION_PREFIX + self.name

    # -- get/set -------------------------------------------------------------

    def __get__(self, instance, owner):
        if instance is None:
            return self  # class access returns the descriptor itself
        if not cmds.optionVar(exists=self._key):
            return self.default
        if self.kind == "bool":
            return bool(cmds.optionVar(q=self._key))
        if self.kind == "enum":
            # Older builds stored enums as integer indices. Map those back
            # to identifiers so callers always see a string.
            value = cmds.optionVar(q=self._key)
            if isinstance(value, int):
                if self.items and 0 <= value < len(self.items):
                    return self.items[value][0]
                return self.default
            return str(value)
        if self.kind == "int":
            return cmds.optionVar(q=self._key)
        if self.kind == "float":
            return cmds.optionVar(q=self._key)
        return cmds.optionVar(q=self._key)

    def __set__(self, instance, value):
        if self.kind == "bool":
            cmds.optionVar(iv=(self._key, int(bool(value))))
        elif self.kind == "enum":
            if isinstance(value, int):
                if not (self.items and 0 <= value < len(self.items)):
                    raise ValueError(
                        f"Invalid index {value} for preference {self.name!r}"
                    )
                value = self.items[value][0]
            value = str(value)
            cmds.optionVar(sv=(self._key, value))
        elif self.kind == "int":
            if self.min is not None:
                value = max(self.min, value)
            if self.max is not None:
                value = min(self.max, value)
            cmds.optionVar(iv=(self._key, int(value)))
        elif self.kind == "float":
            if self.min is not None:
                value = max(self.min, value)
            if self.max is not None:
                value = min(self.max, value)
            cmds.optionVar(fv=(self._key, float(value)))
        else:
            cmds.optionVar(sv=(self._key, str(value)))

        if self.update is not None:
            try:
                self.update(instance, value)
            except TypeError:
                # Update callback may only accept the new value.
                self.update(value)


# -- convenience constructors ----------------------------------------------

def BoolPref(name: str, default: bool = False, update=None, **kwargs):
    return _PrefDescriptor(name, "bool", default=default, update=update, **kwargs)


def IntPref(name: str, default: int = 0, min=None, max=None, update=None, **kwargs):
    return _PrefDescriptor(name, "int", default=default, update=update, min=min, max=max, **kwargs)


def FloatPref(name: str, default: float = 0.0, min=None, max=None, update=None, **kwargs):
    return _PrefDescriptor(name, "float", default=default, update=update, min=min, max=max, **kwargs)


def StringPref(name: str, default: str = "", update=None, **kwargs):
    return _PrefDescriptor(name, "string", default=default, update=update, **kwargs)


def EnumPref(name: str, items: list, default=None, update=None, **kwargs):
    """`items` must be a list of (identifier, label, description) tuples."""
    if default is None and items:
        default = items[0][0]
    return _PrefDescriptor(name, "enum", default=default, update=update, items=items, **kwargs)