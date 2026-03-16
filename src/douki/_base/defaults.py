"""
title: Language-agnostic defaults for Douki.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LanguageDefaults:
    """
    title: Per-language defaults for docstring field values.
    summary: >-
      Each language plugin provides an instance of this class. Fields whose
      values match these defaults are omitted from the emitted YAML.
    attributes:
      visibility:
        type: str
      mutability:
        type: str
      scope_function:
        type: str
        description: Default scope for stand-alone functions.
      scope_method:
        type: str
        description: Default scope for class methods.
      file_extensions:
        type: tuple[str, Ellipsis]
        description: File extensions to collect (e.g. ('.py',)).
      config_files:
        type: tuple[str, Ellipsis]
        description: Config files to search for exclude patterns.
      field_defaults:
        type: dict[str, Any]
        description: >-
          Mapping of top-level YAML key to the default value that should be
          omitted when emitting.
    """

    visibility: str = 'public'
    mutability: str = 'mutable'
    scope_function: str = 'static'
    scope_method: str = 'instance'
    file_extensions: tuple[str, ...] = ()
    config_files: tuple[str, ...] = ()
    field_defaults: dict[str, Any] = field(default_factory=dict)

    def get_field_defaults(self) -> dict[str, Any]:
        """
        title: >-
          Return the mapping of top-level YAML key to the default value that
          should be omitted.
        returns:
          type: dict[str, Any]
        """
        defaults = {
            'visibility': self.visibility,
            'mutability': self.mutability,
            'scope': self.scope_function,
        }
        defaults.update(self.field_defaults)
        return defaults
