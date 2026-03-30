"""Tests for absolutize.py -- converting relative imports to absolute."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from conftest import instantiate_project_from_fixture, snapshot_state

import absolutize
from rope_bootstrap import run


def test_absolutize_all(tmp_path: Path) -> None:
    """Convert all relative imports in the fixture to absolute."""
    project = instantiate_project_from_fixture("fixture-deexport", tmp_path)

    run(
        absolutize.refactor,
        args=Namespace(
            project_root=project,
            paths=[],
            dry_run=False,
            diff=False,
        ),
    )

    # pendant/models.py: from .utils import format_name -> from pendant.utils import format_name
    models = (project / "pendant/models.py").read_text()
    assert "from pendant.utils import format_name" in models
    assert "from .utils" not in models

    # pendant/__init__.py: from .models -> from pendant.models, from .utils -> from pendant.utils
    init = (project / "pendant/__init__.py").read_text()
    assert "from pendant.models import" in init
    assert "from pendant.utils import" in init
    assert "from ." not in init

    # pendant/daemon/__init__.py: relative -> absolute
    daemon_init = (project / "pendant/daemon/__init__.py").read_text()
    assert "from pendant.daemon.protocol import" in daemon_init
    assert "from pendant.daemon.handler import" in daemon_init
    assert "from ." not in daemon_init

    # pendant/daemon/handler.py: from .protocol -> from pendant.daemon.protocol
    handler = (project / "pendant/daemon/handler.py").read_text()
    assert "from pendant.daemon.protocol import" in handler
    assert "from .protocol" not in handler

    # pendant/config/__init__.py: from .settings -> from pendant.config.settings
    config_init = (project / "pendant/config/__init__.py").read_text()
    assert "from pendant.config.settings import" in config_init
    assert "from ." not in config_init


def test_absolutize_specific_files(tmp_path: Path) -> None:
    """Only process specified files, leaving others untouched."""
    project = instantiate_project_from_fixture("fixture-deexport", tmp_path)

    run(
        absolutize.refactor,
        args=Namespace(
            project_root=project,
            paths=[project / "pendant/models.py"],
            dry_run=False,
            diff=False,
        ),
    )

    # pendant/models.py should be absolutized
    models = (project / "pendant/models.py").read_text()
    assert "from pendant.utils import format_name" in models
    assert "from .utils" not in models

    # pendant/daemon/handler.py should still have relative imports (not processed)
    handler = (project / "pendant/daemon/handler.py").read_text()
    assert "from .protocol import" in handler


def test_absolutize_dry_run(tmp_path: Path) -> None:
    """Dry run should not modify any files."""
    project = instantiate_project_from_fixture("fixture-deexport", tmp_path)
    before = snapshot_state(project)

    run(
        absolutize.refactor,
        args=Namespace(
            project_root=project,
            paths=[],
            dry_run=False,
            diff=True,
        ),
    )

    assert before == snapshot_state(project)
