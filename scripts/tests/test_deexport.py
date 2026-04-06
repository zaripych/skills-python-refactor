"""Tests for deexport.py -- removing re-exports from __init__.py."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from textwrap import dedent

from conftest import (
    instantiate_project_from_fixture,
    read_directory_structure_sorted,
    snapshot_state,
)

import deexport
from rope_bootstrap import run

FIXTURE_STRUCTURE = [
    ".gitignore",
    "cli/__init__.py",
    "cli/aliased.py",
    "cli/commands.py",
    "cli/main.py",
    "pendant/__init__.py",
    "pendant/config/__init__.py",
    "pendant/config/settings.py",
    "pendant/daemon/__init__.py",
    "pendant/daemon/handler.py",
    "pendant/daemon/protocol.py",
    "pendant/models.py",
    "pendant/utils.py",
    "pyproject.toml",
    "tests/__init__.py",
    "tests/test_config.py",
    "tests/test_daemon.py",
    "tests/test_models.py",
    "uv.lock",
]


def test_deexport_all(tmp_path: Path) -> None:
    """De-export all symbols from pendant/__init__.py."""
    project = instantiate_project_from_fixture("fixture-deexport", tmp_path)

    assert read_directory_structure_sorted(project) == FIXTURE_STRUCTURE

    assert (project / "pendant/__init__.py").read_text() == dedent("""\
        from .models import StatusCommand, DeviceInfo
        from .utils import format_name, parse_address
    """)
    assert (project / "cli/main.py").read_text() == dedent("""\
        from pendant import StatusCommand, DeviceInfo
        from pendant import format_name


        def run():
            cmd = StatusCommand("device1")
            info = DeviceInfo(name=format_name("raw name"), address="localhost:8080")
            return cmd, info
    """)
    assert (project / "tests/test_models.py").read_text() == dedent("""\
        from pendant import StatusCommand, DeviceInfo


        def test_status_command():
            cmd = StatusCommand("test")
            assert cmd.target == "test"


        def test_device_info():
            info = DeviceInfo(name="dev", address="localhost:80")
            assert info.name == "dev"
    """)
    assert (project / "cli/aliased.py").read_text() == dedent("""\
        from pendant import StatusCommand as SC


        def run():
            return SC("test")
    """)

    run(
        deexport.refactor,
        args=Namespace(
            project_root=project,
            package_path=project / "pendant",
            symbols=[],
            diff=False,
        ),
    )

    assert read_directory_structure_sorted(project) == FIXTURE_STRUCTURE

    assert (project / "pendant/__init__.py").read_text() == ""

    assert (project / "cli/main.py").read_text() == dedent("""\
        from pendant.models import StatusCommand, DeviceInfo
        from pendant.utils import format_name


        def run():
            cmd = StatusCommand("device1")
            info = DeviceInfo(name=format_name("raw name"), address="localhost:8080")
            return cmd, info
    """)

    assert (project / "tests/test_models.py").read_text() == dedent("""\
        from pendant.models import StatusCommand, DeviceInfo


        def test_status_command():
            cmd = StatusCommand("test")
            assert cmd.target == "test"


        def test_device_info():
            info = DeviceInfo(name="dev", address="localhost:80")
            assert info.name == "dev"
    """)

    assert (project / "cli/aliased.py").read_text() == dedent("""\
        from pendant.models import StatusCommand as SC


        def run():
            return SC("test")
    """)


def test_deexport_specific_symbols(tmp_path: Path) -> None:
    """De-export only StatusCommand, leaving other re-exports intact."""
    project = instantiate_project_from_fixture("fixture-deexport", tmp_path)

    assert read_directory_structure_sorted(project) == FIXTURE_STRUCTURE

    assert (project / "pendant/__init__.py").read_text() == dedent("""\
        from .models import StatusCommand, DeviceInfo
        from .utils import format_name, parse_address
    """)
    assert (project / "tests/test_models.py").read_text() == dedent("""\
        from pendant import StatusCommand, DeviceInfo


        def test_status_command():
            cmd = StatusCommand("test")
            assert cmd.target == "test"


        def test_device_info():
            info = DeviceInfo(name="dev", address="localhost:80")
            assert info.name == "dev"
    """)

    run(
        deexport.refactor,
        args=Namespace(
            project_root=project,
            package_path=project / "pendant",
            symbols=["StatusCommand"],
            diff=False,
        ),
    )

    assert read_directory_structure_sorted(project) == FIXTURE_STRUCTURE

    assert (project / "pendant/__init__.py").read_text() == dedent("""\
        from .models import DeviceInfo
        from .utils import format_name, parse_address
    """)

    assert (project / "cli/main.py").read_text() == dedent("""\
        from pendant import DeviceInfo
        from pendant import format_name
        from pendant.models import StatusCommand


        def run():
            cmd = StatusCommand("device1")
            info = DeviceInfo(name=format_name("raw name"), address="localhost:8080")
            return cmd, info
    """)

    assert (project / "tests/test_models.py").read_text() == dedent("""\
        from pendant import DeviceInfo
        from pendant.models import StatusCommand


        def test_status_command():
            cmd = StatusCommand("test")
            assert cmd.target == "test"


        def test_device_info():
            info = DeviceInfo(name="dev", address="localhost:80")
            assert info.name == "dev"
    """)

    assert (project / "cli/aliased.py").read_text() == dedent("""\
        from pendant.models import StatusCommand as SC


        def run():
            return SC("test")
    """)


def test_deexport_nested_package(tmp_path: Path) -> None:
    """De-export from pendant/daemon/__init__.py."""
    project = instantiate_project_from_fixture("fixture-deexport", tmp_path)

    assert read_directory_structure_sorted(project) == FIXTURE_STRUCTURE

    assert (project / "pendant/daemon/__init__.py").read_text() == dedent("""\
        from .protocol import ProtocolHandler, MessageType
        from .handler import RequestHandler


        def build_registry() -> dict[str, ProtocolHandler | RequestHandler]:
            \"\"\"Uses re-exported names locally.\"\"\"
            return {
                MessageType.REQUEST.value: ProtocolHandler(),
                "handle": RequestHandler(),
            }
    """)
    assert (project / "cli/commands.py").read_text() == dedent("""\
        from pendant.daemon import ProtocolHandler, RequestHandler, MessageType


        def execute():
            handler = ProtocolHandler()
            handler.handle(MessageType.REQUEST)
            req = RequestHandler()
            return req.process(MessageType.RESPONSE)
    """)
    assert (project / "tests/test_daemon.py").read_text() == dedent("""\
        from pendant.daemon import MessageType, ProtocolHandler


        def test_protocol():
            handler = ProtocolHandler()
            handler.handle(MessageType.REQUEST)
    """)

    run(
        deexport.refactor,
        args=Namespace(
            project_root=project,
            package_path=project / "pendant/daemon",
            symbols=[],
            diff=False,
        ),
    )

    assert read_directory_structure_sorted(project) == FIXTURE_STRUCTURE

    assert (project / "pendant/daemon/__init__.py").read_text() == dedent("""\
        from .protocol import ProtocolHandler, MessageType
        from .handler import RequestHandler


        def build_registry() -> dict[str, ProtocolHandler | RequestHandler]:
            \"\"\"Uses re-exported names locally.\"\"\"
            return {
                MessageType.REQUEST.value: ProtocolHandler(),
                "handle": RequestHandler(),
            }
    """)

    assert (project / "cli/commands.py").read_text() == dedent("""\
        from pendant.daemon.handler import RequestHandler
        from pendant.daemon.protocol import ProtocolHandler, MessageType


        def execute():
            handler = ProtocolHandler()
            handler.handle(MessageType.REQUEST)
            req = RequestHandler()
            return req.process(MessageType.RESPONSE)
    """)

    assert (project / "tests/test_daemon.py").read_text() == dedent("""\
        from pendant.daemon.protocol import MessageType, ProtocolHandler


        def test_protocol():
            handler = ProtocolHandler()
            handler.handle(MessageType.REQUEST)
    """)


def test_deexport_keeps_imports_used_locally(tmp_path: Path) -> None:
    """Re-exported names used in __init__.py function bodies stay as imports."""
    project = instantiate_project_from_fixture("fixture-deexport", tmp_path)

    assert read_directory_structure_sorted(project) == FIXTURE_STRUCTURE

    assert (project / "pendant/daemon/__init__.py").read_text() == dedent("""\
        from .protocol import ProtocolHandler, MessageType
        from .handler import RequestHandler


        def build_registry() -> dict[str, ProtocolHandler | RequestHandler]:
            \"\"\"Uses re-exported names locally.\"\"\"
            return {
                MessageType.REQUEST.value: ProtocolHandler(),
                "handle": RequestHandler(),
            }
    """)
    assert (project / "cli/commands.py").read_text() == dedent("""\
        from pendant.daemon import ProtocolHandler, RequestHandler, MessageType


        def execute():
            handler = ProtocolHandler()
            handler.handle(MessageType.REQUEST)
            req = RequestHandler()
            return req.process(MessageType.RESPONSE)
    """)

    run(
        deexport.refactor,
        args=Namespace(
            project_root=project,
            package_path=project / "pendant/daemon",
            symbols=[],
            diff=False,
        ),
    )

    assert read_directory_structure_sorted(project) == FIXTURE_STRUCTURE

    # daemon/__init__.py unchanged -- all imports used locally by build_registry()
    assert (project / "pendant/daemon/__init__.py").read_text() == dedent("""\
        from .protocol import ProtocolHandler, MessageType
        from .handler import RequestHandler


        def build_registry() -> dict[str, ProtocolHandler | RequestHandler]:
            \"\"\"Uses re-exported names locally.\"\"\"
            return {
                MessageType.REQUEST.value: ProtocolHandler(),
                "handle": RequestHandler(),
            }
    """)

    assert (project / "cli/commands.py").read_text() == dedent("""\
        from pendant.daemon.handler import RequestHandler
        from pendant.daemon.protocol import ProtocolHandler, MessageType


        def execute():
            handler = ProtocolHandler()
            handler.handle(MessageType.REQUEST)
            req = RequestHandler()
            return req.process(MessageType.RESPONSE)
    """)


def test_deexport_preserves_local_definitions(tmp_path: Path) -> None:
    """De-export from pendant/config/__init__.py preserving CONFIG_VERSION."""
    project = instantiate_project_from_fixture("fixture-deexport", tmp_path)

    assert read_directory_structure_sorted(project) == FIXTURE_STRUCTURE

    assert (project / "pendant/config/__init__.py").read_text() == dedent("""\
        from .settings import Settings, DEFAULT_PORT

        CONFIG_VERSION = "1.0"
    """)
    assert (project / "tests/test_config.py").read_text() == dedent("""\
        from pendant.config import Settings, DEFAULT_PORT, CONFIG_VERSION


        def test_settings():
            s = Settings()
            assert s.port == DEFAULT_PORT


        def test_config_version():
            assert CONFIG_VERSION == "1.0"
    """)

    run(
        deexport.refactor,
        args=Namespace(
            project_root=project,
            package_path=project / "pendant/config",
            symbols=[],
            diff=False,
        ),
    )

    assert read_directory_structure_sorted(project) == FIXTURE_STRUCTURE

    assert (project / "pendant/config/__init__.py").read_text() == dedent("""\
        CONFIG_VERSION = "1.0"
    """)

    assert (project / "tests/test_config.py").read_text() == dedent("""\
        from pendant.config import CONFIG_VERSION
        from pendant.config.settings import Settings, DEFAULT_PORT


        def test_settings():
            s = Settings()
            assert s.port == DEFAULT_PORT


        def test_config_version():
            assert CONFIG_VERSION == "1.0"
    """)


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
            diff=True,
        ),
    )

    assert before == snapshot_state(project)


def test_deexport_aliased_imports(tmp_path: Path) -> None:
    """Aliased imports should preserve the alias after rewriting."""
    project = instantiate_project_from_fixture("fixture-deexport", tmp_path)

    assert read_directory_structure_sorted(project) == FIXTURE_STRUCTURE

    assert (project / "cli/aliased.py").read_text() == dedent("""\
        from pendant import StatusCommand as SC


        def run():
            return SC("test")
    """)

    run(
        deexport.refactor,
        args=Namespace(
            project_root=project,
            package_path=project / "pendant",
            symbols=["StatusCommand"],
            diff=False,
        ),
    )

    assert read_directory_structure_sorted(project) == FIXTURE_STRUCTURE

    assert (project / "cli/aliased.py").read_text() == dedent("""\
        from pendant.models import StatusCommand as SC


        def run():
            return SC("test")
    """)
