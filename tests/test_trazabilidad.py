"""Pruebas del sello de los parquet y del estado de git."""

import subprocess
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point

from health_data import __version__
from health_data.trazabilidad import (
    describir_archivo,
    estado_git,
    guardar_parquet,
    huella,
    leer_sello,
    ruta_relativa,
)

GIT = {"commit": "c" * 40, "rama": "main", "cambios_sin_commit": []}


def test_sello_en_parquet(tmp_path: Path) -> None:
    ruta = tmp_path / "tabla.parquet"
    guardar_parquet(pd.DataFrame({"a": [1, 2, 3]}), ruta, git=GIT)
    sello = leer_sello(ruta)
    assert sello["version"] == __version__ and sello["commit"] == GIT["commit"]
    assert sello["cambios_sin_commit"] is False
    assert pd.read_parquet(ruta)["a"].tolist() == [1, 2, 3]


def test_sello_conserva_geoparquet(tmp_path: Path) -> None:
    """Con un GeoDataFrame, el sello se agrega sin perder los metadatos de GeoParquet."""
    ruta = tmp_path / "geo.parquet"
    tabla = gpd.GeoDataFrame({"n": [1]}, geometry=[Point(-110.9, 29.1)], crs="EPSG:4326")
    guardar_parquet(tabla, ruta, git=GIT)
    leida = gpd.read_parquet(ruta)
    assert leida.crs.to_epsg() == 4326 and leida.geometry.iloc[0].x == pytest.approx(-110.9)
    assert leer_sello(ruta)["commit"] == GIT["commit"]


def test_parquet_sin_sello(tmp_path: Path) -> None:
    ruta = tmp_path / "viejo.parquet"
    pd.DataFrame({"a": [1]}).to_parquet(ruta)
    assert leer_sello(ruta) is None


def test_describir_archivo(tmp_path: Path) -> None:
    ruta = tmp_path / "tabla.parquet"
    guardar_parquet(pd.DataFrame({"a": [1, 2], "b": ["x", "y"]}), ruta, git=GIT)
    descripcion = describir_archivo(ruta, tmp_path)
    assert descripcion["ruta"] == "tabla.parquet"
    assert descripcion["huella"] == huella(ruta)
    assert (descripcion["filas"], descripcion["columnas"]) == (2, 2)
    assert descripcion["sello"]["commit"] == GIT["commit"]


def test_describir_parquet_danado(tmp_path: Path) -> None:
    ruta = tmp_path / "roto.parquet"
    ruta.write_bytes(b"no es parquet")
    assert "error" in describir_archivo(ruta, tmp_path)


def test_ruta_relativa(tmp_path: Path) -> None:
    assert ruta_relativa(tmp_path / "data" / "x.csv", tmp_path) == "data/x.csv"
    assert ruta_relativa(Path("/otro/lugar.csv"), tmp_path) == "/otro/lugar.csv"


def test_estado_git_fuera_de_un_repositorio(tmp_path: Path) -> None:
    git = estado_git(tmp_path)
    assert git["commit"] is None and git["motivo"]


def test_estado_git_detecta_cambios(tmp_path: Path) -> None:
    def git(*args: str) -> None:
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True, capture_output=True)

    git("init", "-q", "-b", "main")
    git("config", "user.email", "prueba@example.org")
    git("config", "user.name", "Prueba")
    (tmp_path / "a.txt").write_text("1")
    git("add", "a.txt")
    git("commit", "-q", "-m", "inicial")

    limpio = estado_git(tmp_path)
    assert len(limpio["commit"]) == 40 and limpio["rama"] == "main"
    assert limpio["cambios_sin_commit"] == []

    (tmp_path / "a.txt").write_text("2")
    assert estado_git(tmp_path)["cambios_sin_commit"] == ["a.txt"]
