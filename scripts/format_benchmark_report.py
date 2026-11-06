"""
title: Format ASV base-versus-PR measurements as a Markdown comment.
summary: Reads ASV result JSON; never executes code from benchmark artifacts.
"""

from __future__ import annotations

import argparse
import json
import math

from pathlib import Path
from typing import Any


def _measurement(value: Any) -> float | None:
    """
    title: Extract a finite, positive timing result in seconds.
    parameters:
      value:
        description: Raw ASV timing value, optionally enclosed in
          a one-item list.
    returns: Positive finite duration in seconds, or None for invalid
      measurements.
    """
    if isinstance(value, list):
        if len(value) != 1:
            return None
        value = value[0]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if math.isfinite(result) and result > 0 else None


def collect_results(
    directory: Path,
    sha: str,
) -> dict[tuple[str, str], float | None]:
    """
    title: Find results for one exact commit and environment.
    parameters:
      directory:
        description: Directory tree containing ASV result JSON files.
      sha:
        description: Exact commit hash whose timing results should
          be collected.
    returns: Timings keyed by benchmark and environment, with None
      for missing results.
    """
    collected: dict[tuple[str, str], float | None] = {}
    for path in sorted(directory.rglob('*.json')):
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict) or data.get('commit_hash') != sha:
            continue
        columns = data.get('result_columns')
        results = data.get('results')
        environment = data.get('env_name')
        if (
            not isinstance(columns, list)
            or 'result' not in columns
            or not isinstance(results, dict)
            or not isinstance(environment, str)
        ):
            continue
        index = columns.index('result')
        for name, row in results.items():
            if not isinstance(name, str):
                continue
            raw = (
                row[index]
                if isinstance(row, list) and len(row) > index
                else None
            )
            collected[(name, environment)] = _measurement(raw)
    return collected


def _format_seconds(seconds: float) -> str:
    """
    title: Format durations consistently with useful units.
    parameters:
      seconds:
        description: Measured execution duration in seconds.
    returns: Duration with a suitable unit and consistent precision.
    """
    if seconds < 0.001:
        return f'{seconds * 1_000_000:,.1f} μs'
    if seconds < 1:
        return f'{seconds * 1_000:,.2f} ms'
    return f'{seconds:,.3f} s'


def _escape_cell(value: str) -> str:
    """
    title: Prevent benchmark names breaking Markdown table structure.
    parameters:
      value:
        description: Benchmark label to include in a Markdown table cell.
    returns: Single-line label with Markdown table delimiters escaped.
    """
    return value.replace('|', '&#124;').replace('\n', ' ')


def build_report(
    directory: Path,
    base_sha: str,
    head_sha: str,
    run_url: str,
    asv_status: int,
) -> str:
    """
    title: Render measured PR performance against its upstream base.
    parameters:
      directory:
        description: Directory tree containing ASV result JSON files.
      base_sha:
        description: Upstream base commit used for the performance
          comparison.
      head_sha:
        description: Pull request commit used for the performance
          comparison.
      run_url:
        description: Workflow URL linked from the report for logs
          and artifacts.
      asv_status:
        description: Exit status of the ASV benchmark command.
    returns: Markdown comparison of available base and pull request
      timings.
    """
    base_results = collect_results(directory, base_sha)
    head_results = collect_results(directory, head_sha)
    keys = sorted(set(base_results) | set(head_results))
    count = {'faster': 0, 'slower': 0, 'similar': 0, 'missing': 0}
    lines = [
        '## Douki PR performance comparison',
        '',
        f'**Upstream main:** `{base_sha}`  ',
        f'**PR head:** `{head_sha}`',
        '',
        'The same GitHub Actions runner measures both revisions with '
        'Python 3.11 and ASV. Lower execution times are better.',
        '',
    ]

    if asv_status not in (0, 1):
        lines.extend(
            [
                '**Benchmark execution failed.** Some measurements may be '
                'missing; inspect the CI log before interpreting results.',
                '',
            ]
        )

    if keys:
        lines.extend(
            [
                '| Benchmark | main | PR | Time change | '
                'Speedup | Assessment |',
                '| --- | ---: | ---: | ---: | ---: | --- |',
            ]
        )
        for name, env in keys:
            before = base_results.get((name, env))
            after = head_results.get((name, env))
            label = _escape_cell(name)
            if before is None or after is None:
                count['missing'] += 1
                lines.append(
                    f'| `{label}` | '
                    f'{_format_seconds(before) if before else "n/a"} | '
                    f'{_format_seconds(after) if after else "n/a"} | '
                    'n/a | n/a | Not comparable |'
                )
                continue
            change = (after / before - 1.0) * 100.0
            speedup = before / after
            if change <= -10:
                state = 'Faster'
                count['faster'] += 1
            elif change >= 10:
                state = 'Slower'
                count['slower'] += 1
            else:
                state = 'Similar'
                count['similar'] += 1
            lines.append(
                f'| `{label}` | {_format_seconds(before)} | '
                f'{_format_seconds(after)} | {change:+.1f}% | '
                f'{speedup:.2f}x | {state} |'
            )
        lines.extend(
            [
                '',
                '**Summary:** '
                f'{count["faster"]} faster, {count["slower"]} slower, '
                f'{count["similar"]} similar, '
                f'{count["missing"]} not comparable.',
            ]
        )
    else:
        lines.append(
            '**No comparable ASV measurements were produced.** '
            'Check the CI log and build artifacts.'
        )

    lines.extend(
        [
            '',
            'Assessments reflect a ±10% raw timing threshold, not a '
            'statistical guarantee. Hosted runners are noisy; treat these '
            'results as advisory and repeat large regressions.',
            '',
            f'[Full benchmark workflow and artifacts]({run_url})',
            '',
        ]
    )
    return '\n'.join(lines)


def main() -> None:
    """
    title: Write the Markdown report for GitHub Actions.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--results', type=Path, required=True)
    parser.add_argument('--base-sha', required=True)
    parser.add_argument('--head-sha', required=True)
    parser.add_argument('--run-url', required=True)
    parser.add_argument('--status', required=True, type=int)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    report = build_report(
        args.results,
        args.base_sha,
        args.head_sha,
        args.run_url,
        args.status,
    )
    args.output.write_text(report, encoding='utf-8')
    print(report)

    # ASV can report success after failing to install either revision.
    # A comparison job must not pass without at least one valid pair.
    base = collect_results(args.results, args.base_sha)
    head = collect_results(args.results, args.head_sha)
    if not any(
        value is not None and head.get(key) is not None
        for key, value in base.items()
    ):
        parser.exit(2, 'No comparable ASV measurements were recorded.\n')


if __name__ == '__main__':
    main()
