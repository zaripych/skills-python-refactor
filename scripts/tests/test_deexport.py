"""Tests for deexport.py -- removing re-exports from __init__.py."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from conftest import instantiate_project_from_fixture, snapshot_state

import deexport
from rope_bootstrap import run


def test_deexport_all(tmp_path: Path) -> None:
    """De-export all symbols from pendant/__init__.py."""
    project = instantiate_project_from_fixture("fixture-deexport", tmp_path)

    run(
        deexport.refactor,
        args=Namespace(
            project_root=project,
            package_path=project / "pendant",
            symbols=[],
            dry_run=False,
            diff=False,
        ),
    )

    # __init__.py should be empty (all symbols were re-exports)
    init_content = (project / "pendant/__init__.py").read_text().strip()
    assert init_content == "", f"Expected empty __init__.py, got:\n{init_content}"

    # cli/main.py should import from source modules
    main_content = (project / "cli/main.py").read_text()
    assert "from pendant.models import StatusCommand, DeviceInfo" in main_content or (
        "from pendant.models import" in main_content
        and "StatusCommand" in main_content
        and "DeviceInfo" in main_content
    )
    assert "from pendant.utils import format_name" in main_content
    assert "from pendant import" not in main_content

    # tests/test_models.py should import from pendant.models
    test_models = (project / "tests/test_models.py").read_text()
    assert "from pendant.models import" in test_models
    assert "StatusCommand" in test_models
    assert "DeviceInfo" in test_models
    assert "from pendant import" not in test_models


def test_deexport_specific_symbols(tmp_path: Path) -> None:
    """De-export only StatusCommand, leaving other re-exports intact."""
    project = instantiate_project_from_fixture("fixture-deexport", tmp_path)

    run(
        deexport.refactor,
        args=Namespace(
            project_root=project,
            package_path=project / "pendant",
            symbols=["StatusCommand"],
            dry_run=False,
            diff=False,
        ),
    )

    # __init__.py should still have DeviceInfo and utils re-exports
    init_content = (project / "pendant/__init__.py").read_text()
    assert "DeviceInfo" in init_content
    assert "format_name" in init_content
    assert "parse_address" in init_content
    assert "StatusCommand" not in init_content

    # tests/test_models.py should have StatusCommand from pendant.models,
    # but DeviceInfo still from pendant
    test_models = (project / "tests/test_models.py").read_text()
    assert "from pendant.models import StatusCommand" in test_models
    assert "from pendant import DeviceInfo" in test_models


def test_deexport_nested_package(tmp_path: Path) -> None:
    """De-export from pendant/daemon/__init__.py."""
    project = instantiate_project_from_fixture("fixture-deexport", tmp_path)

    run(
        deexport.refactor,
        args=Namespace(
            project_root=project,
            package_path=project / "pendant/daemon",
            symbols=[],
            dry_run=False,
            diff=False,
        ),
    )

    # daemon/__init__.py should keep imports used by build_registry()
    init_content = (project / "pendant/daemon/__init__.py").read_text()
    assert "def build_registry" in init_content
    assert "ProtocolHandler" in init_content
    assert "MessageType" in init_content
    assert "RequestHandler" in init_content

    # cli/commands.py should import from source modules directly
    commands = (project / "cli/commands.py").read_text()
    assert "from pendant.daemon.protocol import" in commands
    assert "ProtocolHandler" in commands
    assert "MessageType" in commands
    assert "from pendant.daemon.handler import RequestHandler" in commands

    # tests/test_daemon.py should import from source modules directly
    test_daemon = (project / "tests/test_daemon.py").read_text()
    assert "from pendant.daemon.protocol import" in test_daemon


def test_deexport_keeps_imports_used_locally(tmp_path: Path) -> None:
    """Re-exported names used in __init__.py function bodies stay as imports."""
    project = instantiate_project_from_fixture("fixture-deexport", tmp_path)

    run(
        deexport.refactor,
        args=Namespace(
            project_root=project,
            package_path=project / "pendant/daemon",
            symbols=[],
            dry_run=False,
            diff=False,
        ),
    )

    init_content = (project / "pendant/daemon/__init__.py").read_text()
    # build_registry() uses all three names -- imports must remain
    assert "from .protocol import ProtocolHandler, MessageType" in init_content or (
        "ProtocolHandler" in init_content and "MessageType" in init_content
    )
    assert "RequestHandler" in init_content
    assert "def build_registry" in init_content

    # But callers should still be rewritten to import directly
    commands = (project / "cli/commands.py").read_text()
    assert "from pendant.daemon.protocol import" in commands


def test_deexport_preserves_local_definitions(tmp_path: Path) -> None:
    """De-export from pendant/config/__init__.py preserving CONFIG_VERSION."""
    project = instantiate_project_from_fixture("fixture-deexport", tmp_path)

    run(
        deexport.refactor,
        args=Namespace(
            project_root=project,
            package_path=project / "pendant/config",
            symbols=[],
            dry_run=False,
            diff=False,
        ),
    )

    # __init__.py should still have CONFIG_VERSION but no re-exports
    init_content = (project / "pendant/config/__init__.py").read_text()
    assert 'CONFIG_VERSION = "1.0"' in init_content
    assert "from .settings import" not in init_content
    assert "Settings" not in init_content
    assert "DEFAULT_PORT" not in init_content

    # tests/test_config.py: Settings and DEFAULT_PORT from settings, CONFIG_VERSION from config
    test_config = (project / "tests/test_config.py").read_text()
    assert "from pendant.config.settings import" in test_config
    assert "Settings" in test_config
    assert "DEFAULT_PORT" in test_config
    assert "from pendant.config import CONFIG_VERSION" in test_config


def test_deexport_dry_run(tmp_path: Path) -> None:
    """Dry run should not modify any files."""
    project = instantiate_project_from_fixture("fixture-deexport", tmp_path)
    before = snapshot_state(project)

    run(
        deexport.refactor,
        args=Namespace(
            project_root=project,
            package_path=project / "pendant",
            symbols=[],
            dry_run=False,
            diff=True,
        ),
    )

    assert before == snapshot_state(project)


def test_deexport_aliased_imports(tmp_path: Path) -> None:
    """Aliased imports should preserve the alias after rewriting."""
    project = instantiate_project_from_fixture("fixture-deexport", tmp_path)

    run(
        deexport.refactor,
        args=Namespace(
            project_root=project,
            package_path=project / "pendant",
            symbols=["StatusCommand"],
            dry_run=False,
            diff=False,
        ),
    )

    content = (project / "cli/aliased.py").read_text()
    assert "from pendant.models import StatusCommand as SC" in content
    assert "from pendant import" not in content
