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
    summary: Each language plugin provides an instance of this class. Fields
      whose values match these defaults are omitted from the emitted YAML.
    attributes:
      scope_function:
        description: Default scope for stand-alone functions.
      scope_method:
        description: Default scope for class methods.
      file_extensions:
        description: File extensions to collect (e.g. ('.py',)).
      config_files:
        description: Config files to search for exclude patterns.
      field_defaults:
        description: Mapping of top-level YAML key to the default value that
          should be omitted when emitting.
      visibility:
        description: Default visibility to omit from emitted documentation.
      mutability:
        description: Default mutability to omit from emitted documentation.
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
        title: Return the mapping of top-level YAML key to the default value
          that should be omitted.
        returns:
          description: Built-in defaults combined with language-specific
            overrides.
        """
        defaults = {
            'visibility': self.visibility,
            'mutability': self.mutability,
            'scope': self.scope_function,
        }
        defaults.update(self.field_defaults)
        return defaults
