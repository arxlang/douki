"""
title: Shared file discovery helpers for language backends.
"""

from __future__ import annotations

import os
import re
import sys

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Pattern

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


@dataclass(frozen=True)
class DiscoveryConfig:
    """
    title: Shared file discovery settings.
    attributes:
      root:
        description: Project root for relative paths and configuration.
      exclude_patterns:
        description: Glob patterns of files and directories to skip.
      respect_gitignore:
        description: Whether gitignore rules participate in file discovery.
    """

    root: Path
    exclude_patterns: tuple[str, ...] = ()
    respect_gitignore: bool = True


@dataclass(frozen=True)
class _GitIgnoreRule:
    """
    title: Parsed `.gitignore` rule.
    attributes:
      scope_dir:
        description: Directory whose gitignore file defined the rule.
      pattern:
        description: Pattern after removing negation and directory markers.
      regex:
        description: Compiled expression for matching the pattern.
      negated:
        description: Whether a match re-includes a previously ignored path.
      basename_only:
        description: Whether the pattern matches individual path components.
      directory_only:
        description: Whether the pattern applies only to directories.
    """

    scope_dir: Path
    pattern: str
    regex: Pattern[str]
    negated: bool
    basename_only: bool
    directory_only: bool


def load_douki_discovery_config(cwd: Path) -> DiscoveryConfig:
    """
    title: Load shared discovery settings from `pyproject.toml`.
    parameters:
      cwd:
        description: Starting directory for the upward project configuration
          search.
    returns:
      description: Nearest project discovery settings, or defaults rooted
        at cwd.
    """
    curr = cwd.resolve()
    while True:
        pyproject = curr / 'pyproject.toml'
        if pyproject.is_file():
            return _load_pyproject_discovery_config(pyproject)
        parent = curr.parent
        if parent == curr:
            break
        curr = parent
    return DiscoveryConfig(root=cwd.resolve())


def collect_source_files(
    paths: list[Path],
    *,
    file_extensions: tuple[str, ...],
    discovery: DiscoveryConfig,
) -> list[Path]:
    """
    title: Expand paths into source files using shared discovery rules.
    parameters:
      paths:
        description: Files or directories to expand into source files.
      file_extensions:
        description: Filename suffixes accepted by the language backend.
      discovery:
        description: Project root and exclusion settings used during file
          discovery.
    returns:
      description: Sorted, unique source paths after applying exclusion rules.
    """
    matcher = _GitIgnoreMatcher(discovery.root)
    result: list[Path] = []

    for path in paths:
        if path.is_dir():
            # Top-down traversal lets us skip excluded subtrees entirely.
            for root, directories, filenames in os.walk(path):
                parent = Path(root)
                directories[:] = [
                    name
                    for name in directories
                    if not _can_prune_directory(
                        parent / name,
                        discovery=discovery,
                        matcher=matcher,
                    )
                ]
                for name in filenames:
                    child = parent / name
                    if (
                        child.is_file()
                        and _matches_extension(child, file_extensions)
                        and not _is_excluded(
                            child, discovery=discovery, matcher=matcher
                        )
                    ):
                        result.append(child)
            continue

        if _matches_extension(path, file_extensions) and not _is_excluded(
            path,
            discovery=discovery,
            matcher=matcher,
        ):
            result.append(path)

    return sorted(set(result))


def _can_prune_directory(
    directory: Path,
    *,
    discovery: DiscoveryConfig,
    matcher: '_GitIgnoreMatcher',
) -> bool:
    """
    title: Prune subtrees excluded by whole-directory patterns or gitignore.
    parameters:
      directory:
        description: Directory being considered for exclusion from traversal.
      discovery:
        description: Project root and exclusion settings used during file
          discovery.
      matcher:
        description: Cached gitignore matcher for the project root.
    returns:
      description: Whether traversal can skip the entire directory subtree.
    """
    for pattern in discovery.exclude_patterns:
        normalized = pattern.replace('\\', '/').lstrip('/')
        if normalized.endswith('/**'):
            normalized = normalized[:-3]
        elif normalized.endswith('/*'):
            normalized = normalized[:-2]
        else:
            normalized = normalized.rstrip('/')
        if normalized and _matches_exclude_patterns(
            directory,
            exclude_patterns=(normalized,),
            root=discovery.root,
        ):
            return True

    if not discovery.respect_gitignore:
        return False
    # An ancestor !rule may re-include a descendant. Be conservative.
    return matcher.is_ignored(
        directory, is_directory=True
    ) and not matcher.has_negated_rules(directory)


def _load_pyproject_discovery_config(pyproject: Path) -> DiscoveryConfig:
    """
    title: Load `[tool.douki]` discovery settings from a pyproject file.
    parameters:
      pyproject:
        description: Project configuration file containing optional Douki
          settings.
    returns:
      description: Parsed settings, with defaults for absent or unreadable
        values.
    """
    excludes: tuple[str, ...] = ()
    respect_gitignore = True

    try:
        with pyproject.open('rb') as handle:
            data = tomllib.load(handle)
        tool_douki = data.get('tool', {}).get('douki', {})
        raw_excludes = tool_douki.get('exclude', [])
        if isinstance(raw_excludes, list):
            excludes = tuple(str(pattern) for pattern in raw_excludes)
        raw_respect_gitignore = tool_douki.get(
            'respect-gitignore',
            True,
        )
        if isinstance(raw_respect_gitignore, bool):
            respect_gitignore = raw_respect_gitignore
    except Exception:
        pass

    return DiscoveryConfig(
        root=pyproject.parent.resolve(),
        exclude_patterns=excludes,
        respect_gitignore=respect_gitignore,
    )


def _matches_extension(path: Path, file_extensions: tuple[str, ...]) -> bool:
    """
    title: Check whether a path uses one of the configured file extensions.
    parameters:
      path:
        description: Candidate path to check against discovery rules.
      file_extensions:
        description: Filename suffixes accepted by the language backend.
    returns:
      description: Whether the filename has an accepted suffix.
    """
    return any(path.name.endswith(ext) for ext in file_extensions)


def _is_excluded(
    path: Path,
    *,
    discovery: DiscoveryConfig,
    matcher: '_GitIgnoreMatcher',
) -> bool:
    """
    title: Check whether a path is excluded by config or `.gitignore`.
    parameters:
      path:
        description: Candidate path to check against discovery rules.
      discovery:
        description: Project root and exclusion settings used during file
          discovery.
      matcher:
        description: Cached gitignore matcher for the project root.
    returns:
      description: Whether configuration or gitignore rules exclude the path.
    """
    return _matches_exclude_patterns(
        path,
        exclude_patterns=discovery.exclude_patterns,
        root=discovery.root,
    ) or (discovery.respect_gitignore and matcher.is_ignored(path))


def _matches_exclude_patterns(
    path: Path,
    *,
    exclude_patterns: tuple[str, ...],
    root: Path,
) -> bool:
    """
    title: Check whether a path matches any configured exclude pattern.
    parameters:
      path:
        description: Candidate path to check against discovery rules.
      exclude_patterns:
        description: Configured glob patterns for paths to exclude.
      root:
        description: Project root used to resolve relative paths and discovery
          rules.
    returns:
      description: Whether any configured exclusion pattern matches the path.
    """
    if not exclude_patterns:
        return False

    try:
        path_str = path.resolve().relative_to(root).as_posix()
    except ValueError:
        path_str = path.resolve().as_posix()

    for pattern in exclude_patterns:
        if _match_exclude_pattern(path_str, pattern):
            return True
    return False


def _match_exclude_pattern(path_str: str, pattern: str) -> bool:
    """
    title: Match a configured exclude pattern against a relative path.
    parameters:
      path_str:
        description: Path expressed with forward slashes relative to its
          discovery root.
      pattern:
        description: Gitignore-style glob pattern to match.
    returns:
      description: Whether the pattern matches the path or an applicable
        ancestor.
    """
    normalized = pattern.replace('\\', '/').lstrip('/')
    directory_only = normalized.endswith('/')
    normalized = normalized.rstrip('/')
    if not normalized:
        return False

    regex = _compile_gitignore_regex(normalized)
    prefixes = _relative_prefixes(path_str)
    if directory_only:
        prefixes = prefixes[:-1]

    if '/' in normalized:
        return any(regex.fullmatch(prefix) for prefix in prefixes)

    parts = path_str.split('/')
    if directory_only:
        parts = parts[:-1]
    basename_regex = _compile_gitignore_regex(normalized)
    return any(basename_regex.fullmatch(part) for part in parts)


class _GitIgnoreMatcher:
    """
    title: Lazy `.gitignore` matcher rooted at a discovery directory.
    attributes:
      _root:
        description: Resolved project root that bounds gitignore lookup.
      _rules_by_dir:
        description: Cached parsed rules keyed by their containing directory.
    """

    _root: Path
    _rules_by_dir: dict[Path, tuple[_GitIgnoreRule, ...]]

    def __init__(self, root: Path) -> None:
        """
        title: Initialize the matcher with a root directory.
        parameters:
          root:
            description: Project root used to resolve relative paths and
              discovery rules.
        """
        self._root = root.resolve()
        self._rules_by_dir = {}

    def is_ignored(self, path: Path, *, is_directory: bool = False) -> bool:
        """
        title: Check whether a path is ignored by any applicable `.gitignore`.
        parameters:
          path:
            description: Candidate path to check against discovery rules.
          is_directory:
            description: Whether the candidate itself is a directory.
        returns:
          description: Whether the last matching gitignore rule excludes
            the path.
        """
        resolved = path.resolve()
        try:
            resolved.relative_to(self._root)
        except ValueError:
            return False

        ignored = False
        for scope_dir in self._iter_scope_dirs(resolved):
            for rule in self._load_rules(scope_dir):
                if _rule_matches_path(
                    rule, resolved, is_directory=is_directory
                ):
                    ignored = not rule.negated
        return ignored

    def has_negated_rules(self, directory: Path) -> bool:
        """
        title: Detect inherited negations before pruning a directory.
        parameters:
          directory:
            description: Directory being considered for exclusion
              from traversal.
        returns:
          description: Whether an applicable rule may re-include
            a descendant.
        """
        resolved = directory.resolve()
        try:
            resolved.relative_to(self._root)
        except ValueError:
            return False
        return any(
            rule.negated
            for scope in self._iter_scope_dirs(resolved)
            for rule in self._load_rules(scope)
        )

    def _iter_scope_dirs(self, path: Path) -> Iterable[Path]:
        """
        title: Yield directories whose `.gitignore` files apply to `path`.
        parameters:
          path:
            description: Resolved candidate path beneath the matcher root.
        returns:
          description: Iterator over applicable directories, from root to
            the candidate parent.
        """
        rel_parent = path.relative_to(self._root).parent
        curr = self._root
        yield curr
        for part in rel_parent.parts:
            if part == '.':
                continue
            curr = curr / part
            yield curr

    def _load_rules(self, scope_dir: Path) -> tuple[_GitIgnoreRule, ...]:
        """
        title: Load and cache parsed rules for a scope directory.
        parameters:
          scope_dir:
            description: Directory containing the gitignore file for these
              rules.
        returns:
          description: Rules in file order, or an empty tuple if the file
            cannot be read.
        """
        if scope_dir in self._rules_by_dir:
            return self._rules_by_dir[scope_dir]

        gitignore = scope_dir / '.gitignore'
        if not gitignore.is_file():
            self._rules_by_dir[scope_dir] = ()
            return ()

        rules: list[_GitIgnoreRule] = []
        try:
            lines = gitignore.read_text(encoding='utf-8').splitlines()
        except OSError:
            self._rules_by_dir[scope_dir] = ()
            return ()

        for raw_line in lines:
            rule = _parse_gitignore_rule(raw_line, scope_dir)
            if rule is not None:
                rules.append(rule)

        cached_rules = tuple(rules)
        self._rules_by_dir[scope_dir] = cached_rules
        return cached_rules


def _parse_gitignore_rule(
    raw_line: str,
    scope_dir: Path,
) -> _GitIgnoreRule | None:
    """
    title: Parse a single `.gitignore` line into a match rule.
    parameters:
      raw_line:
        description: Unprocessed line from a gitignore file.
      scope_dir:
        description: Directory containing the gitignore file for these rules.
    returns:
      description: Parsed rule, or None for blank, comment, or empty patterns.
    """
    line = raw_line.rstrip()
    if not line:
        return None

    if line.startswith('\\#') or line.startswith('\\!'):
        line = line[1:]
    elif line.startswith('#'):
        return None

    negated = line.startswith('!')
    if negated:
        line = line[1:]
    if not line:
        return None

    directory_only = line.endswith('/')
    if directory_only:
        line = line.rstrip('/')
    if not line:
        return None

    if line.startswith('/'):
        line = line.lstrip('/')
    basename_only = '/' not in line

    return _GitIgnoreRule(
        scope_dir=scope_dir.resolve(),
        pattern=line,
        regex=_compile_gitignore_regex(line),
        negated=negated,
        basename_only=basename_only,
        directory_only=directory_only,
    )


def _rule_matches_path(
    rule: _GitIgnoreRule, path: Path, *, is_directory: bool = False
) -> bool:
    """
    title: Check whether a parsed `.gitignore` rule matches a path.
    parameters:
      rule:
        description: Parsed gitignore rule to apply.
      path:
        description: Candidate path to check against discovery rules.
      is_directory:
        description: Whether the candidate itself is a directory.
    returns:
      description: Whether the rule matches the path within its scope.
    """
    try:
        rel_path = path.relative_to(rule.scope_dir).as_posix()
    except ValueError:
        return False

    if rule.basename_only:
        parts = rel_path.split('/')
        if rule.directory_only and not is_directory:
            parts = parts[:-1]
        return any(rule.regex.fullmatch(part) for part in parts)

    prefixes = _relative_prefixes(rel_path)
    if rule.directory_only and not is_directory:
        prefixes = prefixes[:-1]
    return any(rule.regex.fullmatch(prefix) for prefix in prefixes)


def _relative_prefixes(path_str: str) -> list[str]:
    """
    title: Return cumulative relative path prefixes for a path string.
    parameters:
      path_str:
        description: Path expressed with forward slashes relative to its
          discovery root.
    returns:
      description: Path prefixes from the first component through the full
        path.
    """
    parts = [part for part in path_str.split('/') if part]
    prefixes: list[str] = []
    for idx in range(len(parts)):
        prefixes.append('/'.join(parts[: idx + 1]))
    return prefixes


def _compile_gitignore_regex(pattern: str) -> Pattern[str]:
    """
    title: Compile a simplified gitignore-style glob into a regex.
    parameters:
      pattern:
        description: Gitignore-style glob pattern to match.
    returns:
      description: Compiled expression implementing the supported glob syntax.
    """
    regex: list[str] = ['^']
    idx = 0
    while idx < len(pattern):
        char = pattern[idx]
        if char == '*':
            if pattern[idx : idx + 2] == '**':
                idx += 2
                if idx < len(pattern) and pattern[idx] == '/':
                    regex.append('(?:.*/)?')
                    idx += 1
                else:
                    regex.append('.*')
                continue
            regex.append('[^/]*')
        elif char == '?':
            regex.append('[^/]')
        else:
            regex.append(re.escape(char))
        idx += 1
    regex.append('$')
    return re.compile(''.join(regex))
