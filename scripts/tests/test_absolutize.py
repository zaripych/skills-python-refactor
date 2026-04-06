"""Tests for absolutize.py -- converting relative imports to absolute."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from textwrap import dedent

from conftest import (
    instantiate_project_from_fixture,
    read_directory_structure_sorted,
    snapshot_state,
)

import absolutize
from rope_bootstrap import run

FIXTURE_DIRECTORY_STRUCTURE = [
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


def test_absolutize_all(tmp_path: Path) -> None:
    """Convert all relative imports in the fixture to absolute."""
    project = instantiate_project_from_fixture("fixture-deexport", tmp_path)

    # -- before assertions --
    assert read_directory_structure_sorted(project) == FIXTURE_DIRECTORY_STRUCTURE

    assert (project / "pendant/__init__.py").read_text() == dedent("""\
        from .models import StatusCommand, DeviceInfo
        from .utils import format_name, parse_address
    """)

    assert (project / "pendant/models.py").read_text() == dedent("""\
        from .utils import format_name


        class StatusCommand:
            def __init__(self, target: str):
                self.target = target

            def label(self) -> str:
                return format_name(self.target)


        class DeviceInfo:
            def __init__(self, name: str, address: str):
                self.name = name
                self.address = address
    """)

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

    assert (project / "pendant/daemon/handler.py").read_text() == dedent("""\
        from .protocol import MessageType


        class RequestHandler:
            def process(self, msg_type: MessageType) -> str:
                return f"handled {msg_type.value}"

            def lazy_load(self):
                from ..config import get_settings

                return get_settings()
    """)

    assert (project / "pendant/config/__init__.py").read_text() == dedent("""\
        from .settings import Settings, DEFAULT_PORT

        CONFIG_VERSION = "1.0"
    """)

    # -- run refactor --
    run(
        absolutize.refactor,
        args=Namespace(
            project_root=project,
            paths=[],
            diff=False,
        ),
    )

    # -- after assertions --
    assert read_directory_structure_sorted(project) == FIXTURE_DIRECTORY_STRUCTURE

    assert (project / "pendant/__init__.py").read_text() == dedent("""\
        from pendant.models import StatusCommand, DeviceInfo
        from pendant.utils import format_name, parse_address
    """)

    assert (project / "pendant/models.py").read_text() == dedent("""\
        from pendant.utils import format_name


        class StatusCommand:
            def __init__(self, target: str):
                self.target = target

            def label(self) -> str:
                return format_name(self.target)


        class DeviceInfo:
            def __init__(self, name: str, address: str):
                self.name = name
                self.address = address
    """)

    assert (project / "pendant/daemon/__init__.py").read_text() == dedent("""\
        from pendant.daemon.protocol import ProtocolHandler, MessageType
        from pendant.daemon.handler import RequestHandler


        def build_registry() -> dict[str, ProtocolHandler | RequestHandler]:
            \"\"\"Uses re-exported names locally.\"\"\"
            return {
                MessageType.REQUEST.value: ProtocolHandler(),
                "handle": RequestHandler(),
            }
    """)

    assert (project / "pendant/daemon/handler.py").read_text() == dedent("""\
        from pendant.daemon.protocol import MessageType


        class RequestHandler:
            def process(self, msg_type: MessageType) -> str:
                return f"handled {msg_type.value}"

            def lazy_load(self):
                from pendant.config import get_settings

                return get_settings()
    """)

    assert (project / "pendant/config/__init__.py").read_text() == dedent("""\
        from pendant.config.settings import Settings, DEFAULT_PORT

        CONFIG_VERSION = "1.0"
    """)


def test_absolutize_specific_files(tmp_path: Path) -> None:
    """Only process specified files, leaving others untouched."""
    project = instantiate_project_from_fixture("fixture-deexport", tmp_path)

    # -- before assertions --
    assert read_directory_structure_sorted(project) == FIXTURE_DIRECTORY_STRUCTURE

    assert (project / "pendant/models.py").read_text() == dedent("""\
        from .utils import format_name


        class StatusCommand:
            def __init__(self, target: str):
                self.target = target

            def label(self) -> str:
                return format_name(self.target)


        class DeviceInfo:
            def __init__(self, name: str, address: str):
                self.name = name
                self.address = address
    """)

    assert (project / "pendant/daemon/handler.py").read_text() == dedent("""\
        from .protocol import MessageType


        class RequestHandler:
            def process(self, msg_type: MessageType) -> str:
                return f"handled {msg_type.value}"

            def lazy_load(self):
                from ..config import get_settings

                return get_settings()
    """)

    # -- run refactor --
    run(
        absolutize.refactor,
        args=Namespace(
            project_root=project,
            paths=[project / "pendant/models.py"],
            diff=False,
        ),
    )

    # -- after assertions --
    assert read_directory_structure_sorted(project) == FIXTURE_DIRECTORY_STRUCTURE

    # pendant/models.py should be absolutized
    assert (project / "pendant/models.py").read_text() == dedent("""\
        from pendant.utils import format_name


        class StatusCommand:
            def __init__(self, target: str):
                self.target = target

            def label(self) -> str:
                return format_name(self.target)


        class DeviceInfo:
            def __init__(self, name: str, address: str):
                self.name = name
                self.address = address
    """)

    # pendant/daemon/handler.py should still have relative imports (not processed)
    assert (project / "pendant/daemon/handler.py").read_text() == dedent("""\
        from .protocol import MessageType


        class RequestHandler:
            def process(self, msg_type: MessageType) -> str:
                return f"handled {msg_type.value}"

            def lazy_load(self):
                from ..config import get_settings

                return get_settings()
    """)


def test_absolutize_dry_run(tmp_path: Path) -> None:
    """Dry run should not modify any files."""
    project = instantiate_project_from_fixture("fixture-deexport", tmp_path)
    before = snapshot_state(project)

    run(
        absolutize.refactor,
        args=Namespace(
            project_root=project,
            paths=[],
            diff=True,
        ),
    )

    assert before == snapshot_state(project)
