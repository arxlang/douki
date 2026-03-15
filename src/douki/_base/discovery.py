"""
title: Shared file discovery helpers for language backends.
"""

from __future__ import annotations

import re
import sys

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Pattern, Tuple

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
        type: Path
      exclude_patterns:
        type: Tuple[str, Ellipsis]
      respect_gitignore:
        type: bool
    """

    root: Path
    exclude_patterns: Tuple[str, ...] = ()
    respect_gitignore: bool = True


@dataclass(frozen=True)
class _GitIgnoreRule:
    """
    title: Parsed `.gitignore` rule.
    attributes:
      scope_dir:
        type: Path
      pattern:
        type: str
      regex:
        type: Pattern[str]
      negated:
        type: bool
      basename_only:
        type: bool
      directory_only:
        type: bool
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
        type: Path
    returns:
      type: DiscoveryConfig
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
    paths: List[Path],
    *,
    file_extensions: Tuple[str, ...],
    discovery: DiscoveryConfig,
) -> List[Path]:
    """
    title: Expand paths into source files using shared discovery rules.
    parameters:
      paths:
        type: List[Path]
      file_extensions:
        type: Tuple[str, Ellipsis]
      discovery:
        type: DiscoveryConfig
    returns:
      type: List[Path]
    """
    matcher = _GitIgnoreMatcher(discovery.root)
    result: List[Path] = []

    for path in paths:
        if path.is_dir():
            for child in path.rglob('*'):
                if not child.is_file():
                    continue
                if not _matches_extension(child, file_extensions):
                    continue
                if not _is_excluded(
                    child,
                    discovery=discovery,
                    matcher=matcher,
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


def _load_pyproject_discovery_config(pyproject: Path) -> DiscoveryConfig:
    """
    title: Load `[tool.douki]` discovery settings from a pyproject file.
    parameters:
      pyproject:
        type: Path
    returns:
      type: DiscoveryConfig
    """
    excludes: Tuple[str, ...] = ()
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


def _matches_extension(path: Path, file_extensions: Tuple[str, ...]) -> bool:
    """
    title: Check whether a path uses one of the configured file extensions.
    parameters:
      path:
        type: Path
      file_extensions:
        type: Tuple[str, Ellipsis]
    returns:
      type: bool
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
        type: Path
      discovery:
        type: DiscoveryConfig
      matcher:
        type: _GitIgnoreMatcher
    returns:
      type: bool
    """
    return _matches_exclude_patterns(
        path,
        exclude_patterns=discovery.exclude_patterns,
        root=discovery.root,
    ) or (discovery.respect_gitignore and matcher.is_ignored(path))


def _matches_exclude_patterns(
    path: Path,
    *,
    exclude_patterns: Tuple[str, ...],
    root: Path,
) -> bool:
    """
    title: Check whether a path matches any configured exclude pattern.
    parameters:
      path:
        type: Path
      exclude_patterns:
        type: Tuple[str, Ellipsis]
      root:
        type: Path
    returns:
      type: bool
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
        type: str
      pattern:
        type: str
    returns:
      type: bool
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
        type: Path
      _rules_by_dir:
        type: Dict[Path, Tuple[_GitIgnoreRule, Ellipsis]]
    """

    def __init__(self, root: Path) -> None:
        self._root: Path = root.resolve()
        self._rules_by_dir: Dict[Path, Tuple[_GitIgnoreRule, ...]] = {}

    def is_ignored(self, path: Path) -> bool:
        """
        title: Check whether a path is ignored by any applicable `.gitignore`.
        parameters:
          path:
            type: Path
        returns:
          type: bool
        """
        resolved = path.resolve()
        try:
            resolved.relative_to(self._root)
        except ValueError:
            return False

        ignored = False
        for scope_dir in self._iter_scope_dirs(resolved):
            for rule in self._load_rules(scope_dir):
                if _rule_matches_path(rule, resolved):
                    ignored = not rule.negated
        return ignored

    def _iter_scope_dirs(self, path: Path) -> Iterable[Path]:
        """
        title: Yield directories whose `.gitignore` files apply to `path`.
        parameters:
          path:
            type: Path
        returns:
          type: Iterable[Path]
        """
        rel_parent = path.relative_to(self._root).parent
        curr = self._root
        yield curr
        for part in rel_parent.parts:
            if part == '.':
                continue
            curr = curr / part
            yield curr

    def _load_rules(self, scope_dir: Path) -> Tuple[_GitIgnoreRule, ...]:
        """
        title: Load and cache parsed rules for a scope directory.
        parameters:
          scope_dir:
            type: Path
        returns:
          type: Tuple[_GitIgnoreRule, Ellipsis]
        """
        if scope_dir in self._rules_by_dir:
            return self._rules_by_dir[scope_dir]

        gitignore = scope_dir / '.gitignore'
        if not gitignore.is_file():
            self._rules_by_dir[scope_dir] = ()
            return ()

        rules: List[_GitIgnoreRule] = []
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
        type: str
      scope_dir:
        type: Path
    returns:
      type: _GitIgnoreRule | None
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


def _rule_matches_path(rule: _GitIgnoreRule, path: Path) -> bool:
    """
    title: Check whether a parsed `.gitignore` rule matches a path.
    parameters:
      rule:
        type: _GitIgnoreRule
      path:
        type: Path
    returns:
      type: bool
    """
    try:
        rel_path = path.relative_to(rule.scope_dir).as_posix()
    except ValueError:
        return False

    if rule.basename_only:
        parts = rel_path.split('/')
        if rule.directory_only:
            parts = parts[:-1]
        return any(rule.regex.fullmatch(part) for part in parts)

    prefixes = _relative_prefixes(rel_path)
    if rule.directory_only:
        prefixes = prefixes[:-1]
    return any(rule.regex.fullmatch(prefix) for prefix in prefixes)


def _relative_prefixes(path_str: str) -> List[str]:
    """
    title: Return cumulative relative path prefixes for a path string.
    parameters:
      path_str:
        type: str
    returns:
      type: List[str]
    """
    parts = [part for part in path_str.split('/') if part]
    prefixes: List[str] = []
    for idx in range(len(parts)):
        prefixes.append('/'.join(parts[: idx + 1]))
    return prefixes


def _compile_gitignore_regex(pattern: str) -> Pattern[str]:
    """
    title: Compile a simplified gitignore-style glob into a regex.
    parameters:
      pattern:
        type: str
    returns:
      type: Pattern[str]
    """
    regex: List[str] = ['^']
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
