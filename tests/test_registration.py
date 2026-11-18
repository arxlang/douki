"""
title: Package ownership boundaries for annotation-enriched help.
"""

from __future__ import annotations

import builtins
import pydoc
import subprocess
import sys

from pathlib import Path
from types import ModuleType

import douki
import pytest

from douki import helping
from typeguard import TypeCheckError


def module(name: str, source: str) -> ModuleType:
    """
    title: Create declarations with a real defining module identity.
    parameters:
      name: Full import name assigned to the fixture module.
      source: Python declarations to execute in the module namespace.
    returns: Module containing the test declarations.
    """
    result = ModuleType(name)
    exec(source, result.__dict__)
    return result


@pytest.mark.parametrize(
    ('name', 'scoped'),
    [
        ('widgets', True),
        ('widgets.io', True),
        ('widgets.io.parsers', True),
        ('widgets_extra', False),
        ('widgets2', False),
        ('namespace.widgets', False),
    ],
)
def test_registration_uses_dotted_package_boundaries(
    name: str, scoped: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    title: Registration covers future descendants but not similar names.
    parameters:
      name: Defining module name to test against the registered root.
      scoped: Whether the declaration belongs to the root package.
      monkeypatch: Fixture replacing the original helper and pager.
    """
    fallback: list[object] = []
    output: list[str] = []
    monkeypatch.setattr(builtins, 'help', fallback.append)
    monkeypatch.setattr(pydoc, 'pager', output.append)
    douki.register('widgets')
    library = module(
        name,
        'def echo(value: int) -> int:\n'
        '    """title: Echo\nreturns: The supplied value."""\n'
        '    return value\n',
    )
    help(library.echo)
    assert bool(output) is scoped
    assert fallback == ([] if scoped else [library.echo])
    if scoped:
        assert 'type: int' in output[0]
        assert 'description: The supplied value.' in output[0]


@pytest.mark.parametrize('raw', ['title: Foreign', 'title: ['])
def test_foreign_declarations_never_enter_douki_inspection(
    raw: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    title: Unregistered libraries bypass YAML and signature inspection.
    parameters:
      raw: Valid or malformed Douki-looking foreign prose.
      monkeypatch: Fixture replacing help and guarding the Douki parser.
    """
    foreign = module(
        'dependency',
        'def untyped(value): return value\n'
        'class Foreign:\n'
        '    def untyped(self, value): return value\n'
        '    @property\n'
        '    def value(self): raise AssertionError("do not call")\n',
    )
    objects = [
        foreign,
        foreign.untyped,
        foreign.Foreign,
        foreign.Foreign().untyped,
        foreign.Foreign.value,
    ]
    for obj in objects:
        if hasattr(obj, '__func__'):
            obj.__func__.__doc__ = raw
        else:
            obj.__doc__ = raw
    fallback: list[object] = []
    monkeypatch.setattr(builtins, 'help', fallback.append)
    douki.register('widgets')

    def unexpected_inspection(obj: object) -> bool:
        """
        title: Fail if foreign objects reach Douki-specific inspection.
        parameters:
          obj: Unexpected documentation or overload inspection input.
        returns: Never returns because inspecting the foreign object is wrong.
        """
        raise AssertionError(f'Unexpected inspection: {obj!r}')

    monkeypatch.setattr(helping, 'is_douki', unexpected_inspection)
    monkeypatch.setattr(helping, 'variants', unexpected_inspection)
    for obj in objects:
        help(obj)
    assert fallback == objects


def test_foreign_reexports_and_inherited_members_use_standard_rendering(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    title: Registered containers do not enrich foreign members or properties.
    parameters:
      monkeypatch: Fixture capturing standard and enriched rendering.
    """
    foreign = module(
        'dependency',
        'def foreign(value):\n'
        '    """title: ["""\n'
        '    return value\n'
        'class Base:\n'
        '    """title: ["""\n'
        '    def inherited(self, value):\n'
        '        """title: ["""\n'
        '        return value\n'
        '    @property\n'
        '    def untyped(self):\n'
        '        """title: ["""\n'
        '        raise AssertionError("do not call")\n',
    )
    library = module('widgets', '"""title: Widgets"""\n')
    library.Base = foreign.Base
    library.foreign = foreign.foreign
    exec(
        'class Local(Base):\n'
        '    """title: Local"""\n'
        '    count: int\n'
        '    alias = Base.untyped\n'
        '    @property\n'
        '    def own(self) -> str:\n'
        '        """title: Owned property"""\n'
        '        raise AssertionError("do not call")\n'
        'class Undocumented(Base): pass\n'
        '__all__ = ["Local", "foreign"]\n',
        library.__dict__,
    )
    output: list[str] = []
    standard: list[object] = []
    fallback: list[object] = []
    original_document = pydoc.plaintext.document

    def document(obj: object, name: str = '', *args: object) -> str:
        """
        title: Record members passed through Python's standard renderer.
        parameters:
          obj: Object rendered without Douki enrichment.
          name: Display name used by the enclosing container.
          args: Additional pydoc rendering arguments.
        returns: Standard Python documentation for the object.
        """
        standard.append(obj)
        return original_document(obj, name, *args)

    monkeypatch.setattr(builtins, 'help', fallback.append)
    monkeypatch.setattr(pydoc, 'pager', output.append)
    monkeypatch.setattr(pydoc.plaintext, 'document', document)
    douki.register('widgets')
    help(library)
    assert 'type: int' in output[0]
    assert 'Owned property' in output[0]
    assert foreign.foreign in standard
    assert foreign.Base.inherited in standard
    assert foreign.Base.untyped in standard
    inherited = library.Local().inherited
    help(library.foreign)
    help(inherited)
    help(library.Undocumented)
    assert fallback == [
        foreign.foreign,
        inherited,
        library.Undocumented,
    ]


def test_plum_extensions_from_other_packages_are_not_enriched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    title: Foreign dispatch implementations retain standard documentation.
    parameters:
      monkeypatch: Fixture capturing the rendered dispatch variants.
    """
    library = module(
        'widgets',
        'from plum import Dispatcher\n'
        'dispatch = Dispatcher()\n'
        '@dispatch\n'
        'def choose(value: int) -> int:\n'
        '    """title: Owned variant"""\n'
        '    return value\n',
    )
    foreign = module(
        'dependency',
        'def choose(value: str):\n    """title: ["""\n    return value\n',
    )
    library.choose.dispatch(foreign.choose)
    output: list[str] = []
    monkeypatch.setattr(pydoc, 'pager', output.append)
    douki.register('widgets')
    help(library.choose)
    assert 'type: int' in output[0]
    assert 'type: str' not in output[0]
    assert 'title: [' in output[0]


def test_foreign_attribute_overrides_hide_registered_base_annotations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    title: Foreign declarations cannot expose stale types from an owned base.
    parameters:
      monkeypatch: Fixture capturing help for the registered subclass.
    """
    base = module(
        'widgets.base',
        'class Base:\n    """title: Base"""\n    count: int\n',
    )
    foreign = module('dependency', '')
    foreign.Base = base.Base
    exec('class Middle(Base):\n    count: str\n', foreign.__dict__)
    library = module('widgets.leaf', '')
    library.Middle = foreign.Middle
    exec(
        'class Leaf(Middle):\n    """title: Leaf"""\n    own: bool\n',
        library.__dict__,
    )
    output: list[str] = []
    monkeypatch.setattr(pydoc, 'pager', output.append)
    douki.register('widgets')
    help(library.Leaf)
    assert 'type: bool' in output[0]
    assert 'count:' not in output[0]
    assert 'type: int' not in output[0]


@pytest.mark.parametrize(
    'name', ['', '.widgets', 'widgets.', 'a..b', '*', 'a/b']
)
def test_invalid_registration_does_not_change_help(name: str) -> None:
    """
    title: Reject malformed package names before installing a help hook.
    parameters:
      name: Invalid registration name to reject.
    """
    original = builtins.help
    with pytest.raises(douki.DocumentationError, match='registration'):
        douki.register(name)
    assert builtins.help is original
    assert not helping.registered_packages


def test_registration_requires_a_string_name() -> None:
    """
    title: Runtime contracts reject non-string registration inputs.
    """
    original = builtins.help
    with pytest.raises(TypeCheckError):
        douki.register(['widgets'])  # type: ignore[arg-type]
    assert builtins.help is original
    assert not helping.registered_packages


def test_library_import_registers_future_submodules(tmp_path: Path) -> None:
    """
    title: Consumers get scoped help by importing a self-registering library.
    parameters:
      tmp_path: Directory holding an importable library for a new interpreter.
    """
    package = tmp_path / 'scoped_library'
    package.mkdir()
    (package / '__init__.py').write_text(
        'import douki\ndouki.register(__name__)\n', encoding='utf-8'
    )
    (package / 'api.py').write_text(
        'def echo(value: str) -> str:\n'
        '    """title: Echo\nreturns: Supplied text."""\n'
        '    return value\n',
        encoding='utf-8',
    )
    code = (
        'import builtins, json, pydoc, sys\n'
        'original = builtins.help\n'
        'import douki\n'
        'from douki import register\n'
        'assert builtins.help is original\n'
        'assert not hasattr(douki, "enable")\n'
        'assert not hasattr(douki, "disable")\n'
        'calls = []\n'
        'builtins.help = calls.append\n'
        'import scoped_library\n'
        'assert "scoped_library.api" not in sys.modules\n'
        'from scoped_library import api\n'
        'raw = api.echo.__doc__\n'
        'output = []\n'
        'pydoc.pager = output.append\n'
        'help(api.echo)\n'
        'assert "type: str" in output[0]\n'
        'assert "description: Supplied text." in output[0]\n'
        'assert api.echo.__doc__ == raw\n'
        'help(json.dumps)\n'
        'assert calls == [json.dumps]\n'
    )
    subprocess.run(
        [sys.executable, '-c', code],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
