"""
title: Tests for the performance comparison PR comment generator.
"""

from __future__ import annotations

import json

from pathlib import Path

from scripts.format_benchmark_report import build_report, collect_results


def _write_result(
    directory: Path, sha: str, results: dict[str, float | None]
) -> None:
    """
    title: Write a minimal ASV results fixture.
    """
    destination = directory / 'github-ubuntu-python311'
    destination.mkdir(parents=True, exist_ok=True)
    payload = {
        'commit_hash': sha,
        'env_name': 'virtualenv-py3.11',
        'result_columns': ['result', 'params', 'version'],
        'results': {key: [value, [], '1'] for key, value in results.items()},
    }
    (destination / f'{sha[:8]}-virtualenv-py3.11.json').write_text(
        json.dumps(payload), encoding='utf-8'
    )


def test_build_report_includes_changes_and_speedups(
    tmp_path: Path,
) -> None:
    """
    title: PR report compares exact revisions in a Markdown table.
    """
    base = 'a' * 40
    head = 'b' * 40
    _write_result(
        tmp_path,
        base,
        {'benchmarks.time_fast': 0.010, 'benchmarks.time_slow': 0.010},
    )
    _write_result(
        tmp_path,
        head,
        {'benchmarks.time_fast': 0.005, 'benchmarks.time_slow': 0.015},
    )
    report = build_report(
        tmp_path, base, head, 'https://github.com/actions/runs/123', 1
    )
    assert '| Benchmark | main | PR | Time change | Speedup |' in report
    assert '| -50.0% | 2.00x | Faster |' in report
    assert '| +50.0% | 0.67x | Slower |' in report
    assert '1 faster, 1 slower' in report
    assert base in report
    assert head in report


def test_report_warns_on_failed_or_missing_measurements(
    tmp_path: Path,
) -> None:
    """
    title: Do not invent measurements for a failed benchmark.
    """
    base = 'c' * 40
    head = 'd' * 40
    _write_result(tmp_path, base, {'benchmarks.time_sync': 0.001})
    report = build_report(
        tmp_path, base, head, 'https://example.com/runs/3', 2
    )
    assert 'Benchmark execution failed' in report
    assert 'Not comparable' in report
    assert 'n/a' in report
    assert '0 faster, 0 slower, 0 similar, 1 not comparable' in report


def test_collect_results_filters_other_commits(
    tmp_path: Path,
) -> None:
    """
    title: Never compare timing records from a different revision.
    """
    base = 'e' * 40
    other = 'f' * 40
    _write_result(tmp_path, base, {'benchmarks.time_validate': 0.001})
    _write_result(tmp_path, other, {'benchmarks.time_validate': 0.002})
    results = collect_results(tmp_path, base)
    assert results == {
        ('benchmarks.time_validate', 'virtualenv-py3.11'): 0.001
    }
