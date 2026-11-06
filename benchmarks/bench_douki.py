"""
title: ASV benchmarks for Douki synchronization and file discovery.
"""

from __future__ import annotations

import tempfile

from pathlib import Path

import douki

from douki._base.discovery import DiscoveryConfig, collect_source_files
from douki._base.sync import ParamInfo, sync_docstring, validate_docstring
from douki._python.sync import sync_source


class DocstringBenchmarks:
    """
    title: Microbenchmarks for validation and synchronization.
    """

    def setup(self) -> None:
        """
        title: Prepare a representative YAML docstring and signature.
        """
        self.raw = (
            'title: Convert a value\n'
            'summary: Convert the given value to a text representation.\n'
            'parameters:\n'
            '  value:\n'
            '    description: The integer to convert.\n'
            'returns:\n'
            '  description: The formatted result.\n'
        )
        self.params = [ParamInfo('value', 'int', 'regular')]

    def time_validate(self) -> None:
        """
        title: Time schema validation for one existing docstring.
        """
        validate_docstring(self.raw, 'convert')

    def time_sync(self) -> None:
        """
        title: Time synchronization of one existing docstring.
        """
        sync_docstring(self.raw, self.params, 'str')


class EnrichmentBenchmarks:
    """
    title: Benchmark annotation enrichment where the API is available.
    """

    def setup(self) -> None:
        """
        title: Skip older revisions without affecting shared benchmarks.
        """
        if not hasattr(douki, 'enrich'):
            raise NotImplementedError('Annotation enrichment is unavailable')
        fixture = DocstringBenchmarks()
        fixture.setup()
        self.raw = fixture.raw
        self.signature = douki.Signature(
            (douki.Parameter('value', 'int'),), 'str'
        )

    def time_enrich(self) -> None:
        """
        title: Time structured annotation enrichment without source writes.
        """
        douki.enrich(self.raw, self.signature)


class SourceBenchmarks:
    """
    title: End-to-end Python source synchronization benchmarks.
    """

    def setup(self) -> None:
        """
        title: Construct realistic small and large Python modules.
        """
        self.small = self._module(25)
        self.large = self._module(250)

    def _module(self, count: int) -> str:
        """
        title: Produce source with documented function signatures.
        parameters:
          count:
            description: Number of documented functions to include in the
              synthetic module.
        returns:
          description: Synthetic Python source for the source-formatting
            benchmark.
        """
        functions = ['"""title: Benchmark module"""\n']
        for idx in range(count):
            functions.append(
                f'def func_{idx}(value: int) -> int:\n'
                '    """\n'
                f'    title: Function {idx}\n'
                '    parameters:\n'
                '      value:\n'
                '        description: Details.\n'
                '    returns:\n'
                '      description: Details.\n'
                '    """\n'
                '    return value\n'
            )
        return '\n'.join(functions)

    def time_sync_source_25(self) -> None:
        """
        title: Time full-source synchronization with 25 functions.
        """
        sync_source(self.small)

    def time_sync_source_250(self) -> None:
        """
        title: Time full-source synchronization with 250 functions.
        """
        sync_source(self.large)


class DiscoveryBenchmarks:
    """
    title: File discovery with a large ignored subtree.
    """

    def setup(self) -> None:
        """
        title: Create included files and an ignored Python source tree.
        """
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / '.gitignore').write_text('ignored/\n')
        ignored = self.root / 'ignored'
        ignored.mkdir()
        for idx in range(400):
            (ignored / f'ignored_{idx}.py').write_text('pass\n')
        for idx in range(40):
            (self.root / f'visible_{idx}.py').write_text('pass\n')
        self.config = DiscoveryConfig(root=self.root)

    def time_collect_files(self) -> None:
        """
        title: Time directory scanning with a large ignored subtree.
        """
        collect_source_files(
            [self.root],
            file_extensions=('.py',),
            discovery=self.config,
        )

    def teardown(self) -> None:
        """
        title: Clean up the temporary fixture directory.
        """
        self.temporary.cleanup()
