"""Pruebas del respaldo y la restauración del caché de SAKBÉ."""

import gzip
from pathlib import Path

import pytest

from health_data.ingestion import respaldo_sakbe
from health_data.ingestion.respaldo_sakbe import ErrorDeRespaldo, leer_respaldos, respaldar, restaurar
from health_data.ingestion.sakbe import CacheSakbe, resumen_cache


def escribir_cache(ruta: Path, n: int) -> Path:
    """Caché de prueba con ``n`` respuestas."""
    cache = CacheSakbe(ruta)
    for i in range(n):
        parametros = {"x": i}
        cache.guardar(CacheSakbe.clave("ruta", parametros), "ruta", parametros, True, {"tiempo": i}, f"2026-10-1{i % 9}T10:00:00")
    cache.registrar_consulta("abc123")
    cache.cerrar()
    return ruta


@pytest.fixture
def rutas(tmp_path: Path) -> dict[str, Path]:
    return {
        "cache": escribir_cache(tmp_path / "interim" / "sakbe_cache.sqlite", 5),
        "respaldos": tmp_path / "respaldos",
        "registro": tmp_path / "catalog" / "respaldos.csv",
        "destino": tmp_path / "otra_pc" / "sakbe_cache.sqlite",
    }


def _respaldar(r: dict[str, Path]) -> Path | None:
    return respaldar(r["cache"], r["respaldos"], r["registro"])


def test_respaldo_y_restauracion(rutas) -> None:
    """Lo que se restaura en otra computadora tiene las mismas respuestas."""
    comprimido = _respaldar(rutas)
    (fila,) = leer_respaldos(rutas["registro"])
    assert list(fila) == respaldo_sakbe.COLUMNAS_RESPALDOS
    assert fila["archivo"] == comprimido.name and fila["respuestas"] == "5"
    assert not list(rutas["respaldos"].glob(".*"))  # No quedan copias temporales

    restaurar(comprimido, rutas["destino"], rutas["registro"])
    assert resumen_cache(rutas["destino"]) == resumen_cache(rutas["cache"])


def test_no_repite_respaldo_igual(rutas) -> None:
    _respaldar(rutas)
    assert _respaldar(rutas) is None
    assert len(leer_respaldos(rutas["registro"])) == 1


def test_huella_de_contenido_ignora_el_consumo_de_tokens(rutas) -> None:
    antes = resumen_cache(rutas["cache"])["huella_contenido"]
    cache = CacheSakbe(rutas["cache"])
    cache.registrar_consulta("otro")
    cache.cerrar()
    assert resumen_cache(rutas["cache"])["huella_contenido"] == antes


def test_rechaza_archivo_no_registrado(rutas, tmp_path: Path) -> None:
    comprimido = _respaldar(rutas)
    alterado = tmp_path / "alterado.sqlite.gz"
    alterado.write_bytes(comprimido.read_bytes()[:-10])
    with pytest.raises(ErrorDeRespaldo, match="no coincide"):
        restaurar(alterado, rutas["destino"], rutas["registro"])
    assert not rutas["destino"].exists()


def test_no_reemplaza_un_cache_distinto_sin_forzar(rutas) -> None:
    comprimido = _respaldar(rutas)
    escribir_cache(rutas["destino"], 2)
    with pytest.raises(ErrorDeRespaldo, match="--forzar"):
        restaurar(comprimido, rutas["destino"], rutas["registro"])
    assert resumen_cache(rutas["destino"])["respuestas"] == 2

    restaurar(comprimido, rutas["destino"], rutas["registro"], forzar=True)
    assert resumen_cache(rutas["destino"])["respuestas"] == 5
    (anterior,) = rutas["destino"].parent.glob("sakbe_cache.anterior-*.sqlite")
    assert resumen_cache(anterior)["respuestas"] == 2


def test_restaurar_dos_veces_no_cambia_nada(rutas) -> None:
    comprimido = _respaldar(rutas)
    restaurar(comprimido, rutas["destino"], rutas["registro"])
    restaurar(comprimido, rutas["destino"], rutas["registro"])
    assert not list(rutas["destino"].parent.glob("*.anterior-*"))


def test_respaldo_es_gzip_de_sqlite(rutas) -> None:
    comprimido = _respaldar(rutas)
    with gzip.open(comprimido, "rb") as archivo:
        assert archivo.read(16) == b"SQLite format 3\x00"


def test_registro_real_tiene_el_encabezado() -> None:
    encabezado = respaldo_sakbe.REGISTRO_RESPALDOS.read_text(encoding="utf-8").splitlines()[0]
    assert encabezado.split(",") == respaldo_sakbe.COLUMNAS_RESPALDOS
