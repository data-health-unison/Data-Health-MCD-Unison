"""Pruebas del pipeline principal."""

import json

import pandas as pd
import pytest

from health_data import pipeline
from health_data.pipeline import ensure_directories


def test_ensure_directories() -> None:
    """Comprueba que los directorios puedan crearse."""
    ensure_directories()


GIT = {"commit": "a" * 40, "rama": "main", "cambios_sin_commit": []}


def _ruteo_falso(llamadas: list[str]):
    return lambda: llamadas.append("ruteo") or pipeline.Paso("ruteo", pipeline.ESTADO_EJECUTADO)


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
    monkeypatch.setattr(pipeline, "INTERIM_DATA_DIR", tmp_path / "interim")
    monkeypatch.setattr(pipeline, "PROCESSED_DATA_DIR", tmp_path / "processed")
    # Sin procesamientos reales: no deben tocar data/ del proyecto
    monkeypatch.setattr(pipeline, "PROCESAMIENTOS", ())
    monkeypatch.setattr(pipeline, "estado_git", lambda *_: GIT)
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
    monkeypatch.setattr(pipeline, "paso_ruteo", _ruteo_falso(llamadas))
    _tabla(["ok", "estimado"]).to_parquet(pipeline.ARCHIVO_TABLA_FINAL)

    pipeline.run_pipeline()

    assert llamadas == []
    manifiesto = json.loads(pipeline.ARCHIVO_MANIFIESTO.read_text(encoding="utf-8"))
    assert manifiesto["validacion"]["paso"] is False
    assert manifiesto["validacion"]["fallidas"][0]["nombre"] == "cobertura_ruteo_sakbe"
    assert len(manifiesto["validacion"]["comprobaciones"]) > 1
    estados = {p["nombre"]: p["estado"] for p in manifiesto["pasos"]}
    assert estados["ruteo"] == "omitido" and estados["validacion"] == "ejecutado"
    (salida,) = manifiesto["salidas"]
    assert salida["ruta"] == "processed/tabla.parquet" and salida["filas"] == 2
    assert salida["huella"].startswith("sha256:")
    # Escrita sin guardar_parquet: no tiene sello y se avisa
    assert salida["sello"] is None
    assert any("antes de existir el sello" in a for a in manifiesto["advertencias"])


def test_run_pipeline_siempre_recalcula_ruteo(entorno, monkeypatch) -> None:
    """Con insumos procesados el ruteo se recalcula aunque la tabla ya exista."""
    llamadas = []
    monkeypatch.setattr(pipeline, "paso_ruteo", _ruteo_falso(llamadas))
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


def test_manifiesto_registra_corrida_y_guarda_historial(entorno, monkeypatch) -> None:
    """El manifiesto dice versión y commit, y cada corrida queda también en el historial."""
    from health_data import __version__
    from health_data.trazabilidad import guardar_parquet

    monkeypatch.setattr(pipeline, "estado_git", lambda *_: {**GIT, "cambios_sin_commit": ["app.py"]})
    guardar_parquet(_tabla(["ok"]), pipeline.ARCHIVO_TABLA_FINAL, git=GIT)

    manifiesto = pipeline.run_pipeline()

    corrida = manifiesto["corrida"]
    assert corrida["version"] == __version__ and corrida["commit"] == GIT["commit"]
    assert corrida["cambios_sin_commit"] == ["app.py"]
    assert any("cambios sin commit" in a for a in manifiesto["advertencias"])
    (salida,) = manifiesto["salidas"]
    assert salida["sello"]["commit"] == GIT["commit"] and salida["al_dia"] is True
    historial = entorno / "processed" / "manifiestos" / f"{manifiesto['id_corrida']}.json"
    assert json.loads(historial.read_text(encoding="utf-8")) == json.loads(
        pipeline.ARCHIVO_MANIFIESTO.read_text(encoding="utf-8")
    )
    # Las rutas son relativas al proyecto
    assert "/Users/" not in pipeline.ARCHIVO_MANIFIESTO.read_text(encoding="utf-8")


def test_salida_de_otro_commit_se_avisa(entorno) -> None:
    from health_data.trazabilidad import guardar_parquet

    guardar_parquet(_tabla(["ok"]), pipeline.ARCHIVO_TABLA_FINAL, git={**GIT, "commit": "b" * 40})
    manifiesto = pipeline.run_pipeline()
    assert manifiesto["salidas"][0]["al_dia"] is False
    assert any("con el commit bbbbbbb" in a for a in manifiesto["advertencias"])


def test_paso_que_falla_queda_registrado(entorno, monkeypatch) -> None:
    """Un paso que falla no detiene la corrida, pero queda en el manifiesto con su error."""

    def ruteo_roto():
        return pipeline._ejecutar("ruteo", lambda: 1 / 0)

    monkeypatch.setattr(pipeline, "paso_ruteo", ruteo_roto)
    for nombre in pipeline.INSUMOS_RUTEO:
        (entorno / "processed" / nombre).touch()
    manifiesto = pipeline.run_pipeline()
    ruteo = next(p for p in manifiesto["pasos"] if p["nombre"] == "ruteo")
    assert ruteo["estado"] == "fallido" and "ZeroDivisionError" in ruteo["detalle"]
    assert any("Falló el paso «ruteo»" in a for a in manifiesto["advertencias"])


def test_procesamiento_reutiliza_omite_o_ejecuta(tmp_path, monkeypatch) -> None:
    """Sin crudo se omite; con todas las salidas se reutiliza; si falta una, se procesa."""
    import sys
    import types

    llamadas = []
    modulo = types.ModuleType("procesador_falso")
    modulo.ARCHIVO_CRUDO = tmp_path / "crudo.zip"
    modulo.SALIDAS = (tmp_path / "a.parquet", tmp_path / "b.parquet")
    modulo.main = lambda: llamadas.append("main")
    monkeypatch.setitem(sys.modules, "procesador_falso", modulo)

    assert pipeline.paso_procesamiento("X-001", "procesador_falso").estado == "omitido"
    modulo.ARCHIVO_CRUDO.touch()
    modulo.SALIDAS[0].touch()
    assert pipeline.paso_procesamiento("X-001", "procesador_falso").estado == "ejecutado"
    modulo.SALIDAS[1].touch()
    assert pipeline.paso_procesamiento("X-001", "procesador_falso").estado == "reutilizado"
    assert pipeline.paso_procesamiento("X-001", "procesador_falso", forzar=True).estado == "ejecutado"
    assert llamadas == ["main", "main"]


def test_procesamientos_declaran_crudo_y_salidas() -> None:
    """Cada módulo de procesamiento del pipeline define lo que el pipeline revisa."""
    import importlib

    for _, nombre_modulo in pipeline.PROCESAMIENTOS:
        modulo = importlib.import_module(nombre_modulo)
        assert modulo.ARCHIVO_CRUDO and modulo.SALIDAS and callable(modulo.main), nombre_modulo


def test_reprocesar_no_descarga(entorno, monkeypatch) -> None:
    """--reprocesar regenera lo procesado sin volver a descargar (forzar=False en las descargas)."""
    recibidos = {}
    monkeypatch.setattr(pipeline, "paso_descargas", lambda **k: recibidos.setdefault("descargas", k) and {})
    monkeypatch.setattr(
        pipeline, "paso_procesamiento",
        lambda i, m, **k: recibidos.setdefault("procesar", k) and pipeline.Paso(i, pipeline.ESTADO_EJECUTADO),
    )
    monkeypatch.setattr(pipeline, "PROCESAMIENTOS", (("X-001", "x"),))
    manifiesto = pipeline.run_pipeline(reprocesar=True)
    assert recibidos == {"descargas": {"forzar": False}, "procesar": {"forzar": True}}
    assert manifiesto["corrida"]["argumentos"] == {"forzar": False, "reprocesar": True}
