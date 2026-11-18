"""
title: Keep benchmark definitions usable with older installed revisions.
"""

from __future__ import annotations

import importlib.util
import sys

from pathlib import Path
from types import ModuleType

import douki
import pytest
import yaml

from benchmarks import bench_douki


def test_benchmark_module_imports_without_new_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    title: Absent enrichment APIs skip only enrichment on the baseline.
    """
    baseline = ModuleType('douki')
    path = Path(bench_douki.__file__)
    spec = importlib.util.spec_from_file_location('baseline_benchmarks', path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    with monkeypatch.context() as patch:
        patch.setitem(sys.modules, 'douki', baseline)
        spec.loader.exec_module(module)

    shared = module.DocstringBenchmarks()
    shared.setup()
    shared.time_validate()
    shared.time_sync()
    source = module.SourceBenchmarks()
    source.setup()
    source.time_sync_source_25()
    source.time_sync_source_250()
    discovery = module.DiscoveryBenchmarks()
    discovery.setup()
    try:
        discovery.time_collect_files()
    finally:
        discovery.teardown()
    with pytest.raises(NotImplementedError, match='unavailable'):
        module.EnrichmentBenchmarks().setup()


def test_enrichment_benchmark_runs_on_current_api() -> None:
    """
    title: Prepare metadata outside timing and exercise the current API.
    """
    benchmark = bench_douki.EnrichmentBenchmarks()
    benchmark.setup()
    benchmark.time_enrich()
    result = douki.enrich(benchmark.raw, benchmark.signature)
    assert result['parameters']['value']['type'] == 'int'
    assert result['returns']['type'] == 'str'
    assert 'type' not in yaml.safe_load(benchmark.raw)['parameters']['value']
