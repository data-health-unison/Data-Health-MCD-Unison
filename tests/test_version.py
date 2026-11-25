"""La versión del proyecto es válida y el CHANGELOG la documenta."""

import re

from health_data import __version__
from health_data.config import PROJECT_ROOT

CHANGELOG = (PROJECT_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")


def test_version_semantica() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", __version__), __version__


def test_changelog_documenta_la_version_actual() -> None:
    """Al subir __version__ hay que pasar Sin publicar a su sección, con fecha y enlace."""
    assert re.search(rf"^## \[{re.escape(__version__)}\] - \d{{4}}-\d{{2}}-\d{{2}}$", CHANGELOG, re.M), (
        f"CHANGELOG.md no tiene la sección ## [{__version__}] - AAAA-MM-DD"
    )
    assert f"[{__version__}]: https://github.com/" in CHANGELOG
    assert "## [Sin publicar]" in CHANGELOG
