"""Pruebas del pipeline principal."""

import json

import pandas as pd
import pytest

from health_data import pipeline
from health_data.pipeline import ensure_directories


def test_ensure_directories() -> None:
    """Comprueba que los directorios puedan crearse."""
    ensure_directories()


def _tabla(routing_status: list[str]) -> pd.DataFrame:
    n = len(routing_status)
    return pd.DataFrame(
        {
            "locality_id": [f"2605500{i:02d}" for i in range(n)],
            "locality_name": ["Loc"] * n,
            "municipality_name": ["Hermosillo"] * n,
            "population": [100] * n,
            "latitude": [29.07] * n,
            "longitude": [-110.95] * n,
            "nearest_primary_clues": ["A"] * n,
            "primary_distance_km": [2.5] * n,
            "primary_time_min": [5.0] * n,
            "nearest_secondary_clues": ["B"] * n,
            "secondary_distance_km": [6.0] * n,
            "secondary_time_min": [12.0] * n,
            "routing_status": routing_status,
        }
    )


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    """Redirige las rutas del pipeline a un directorio temporal."""
    monkeypatch.setattr(pipeline, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(pipeline, "RAW_DATA_DIR", tmp_path / "raw")
    monkeypatch.setattr(pipeline, "PROCESSED_DATA_DIR", tmp_path / "processed")
    monkeypatch.setattr(pipeline, "ARCHIVO_TABLA_FINAL", tmp_path / "processed" / "tabla.parquet")
    monkeypatch.setattr(pipeline, "ARCHIVO_MANIFIESTO", tmp_path / "processed" / "manifiesto.json")
    monkeypatch.setattr(pipeline, "ensure_directories", lambda: None)
    monkeypatch.setattr(pipeline, "paso_cartografia", lambda **_: None)
    monkeypatch.setattr(pipeline, "paso_descargas", lambda **_: {})
    (tmp_path / "processed").mkdir()
    return tmp_path


def test_paso_validacion_sin_tabla(entorno) -> None:
    assert pipeline.paso_validacion() is None


def test_paso_validacion_tabla_valida(entorno) -> None:
    _tabla(["ok", "ok"]).to_parquet(pipeline.ARCHIVO_TABLA_FINAL)
    reporte = pipeline.paso_validacion()
    assert reporte is not None and reporte.paso


def test_paso_validacion_reporta_fallas_sin_excepcion(entorno) -> None:
    _tabla(["ok", "estimado", "estimado", "estimado"]).to_parquet(pipeline.ARCHIVO_TABLA_FINAL)
    reporte = pipeline.paso_validacion()
    assert reporte is not None and not reporte.paso
    assert [c.nombre for c in reporte.fallidas] == ["cobertura_ruteo_sakbe"]


def test_run_pipeline_valida_y_registra_en_manifiesto(entorno, monkeypatch) -> None:
    """Recorrido completo: sin insumos no hay ruteo, pero se valida la tabla existente."""
    llamadas = []
    monkeypatch.setattr(pipeline, "paso_ruteo", lambda: llamadas.append("ruteo"))
    _tabla(["ok", "estimado"]).to_parquet(pipeline.ARCHIVO_TABLA_FINAL)

    pipeline.run_pipeline()

    assert llamadas == []
    manifiesto = json.loads(pipeline.ARCHIVO_MANIFIESTO.read_text(encoding="utf-8"))
    assert manifiesto["validacion"]["paso"] is False
    assert manifiesto["validacion"]["fallidas"][0]["nombre"] == "cobertura_ruteo_sakbe"
    assert manifiesto["archivos_salida"]["tabla_final"] == "processed/tabla.parquet"


def test_run_pipeline_siempre_recalcula_ruteo(entorno, monkeypatch) -> None:
    """Con insumos procesados el ruteo se recalcula aunque la tabla ya exista."""
    llamadas = []
    monkeypatch.setattr(pipeline, "paso_ruteo", lambda: llamadas.append("ruteo"))
    for nombre in ("inegi-pop-001_localidades.parquet", "salud-001_establecimientos.parquet"):
        (entorno / "processed" / nombre).touch()
    _tabla(["ok"]).to_parquet(pipeline.ARCHIVO_TABLA_FINAL)

    pipeline.run_pipeline()

    assert llamadas == ["ruteo"]
    manifiesto = json.loads(pipeline.ARCHIVO_MANIFIESTO.read_text(encoding="utf-8"))
    assert manifiesto["validacion"]["paso"] is True


def test_paso_ruteo_usa_solo_cache(monkeypatch) -> None:
    """El pipeline llama al ruteo sin argumentos: nunca con --sakbe (no gasta cuota)."""
    from health_data.processing import ruteo

    recibidos = []
    monkeypatch.setattr(ruteo, "main", lambda argv=None: recibidos.append(argv) or 0)
    pipeline.paso_ruteo()
    assert recibidos == [None]
