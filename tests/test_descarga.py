"""Pruebas sin red de la descarga de fuentes."""

import sys
import zipfile
from pathlib import Path

import pytest
import requests

from health_data.ingestion import descarga
from health_data.ingestion.descarga import ArchivoInvalido, descargar, huella, validar
from health_data.ingestion.fuentes import Fuente
from health_data.pipeline import PROJECT_ROOT


FUENTE = Fuente(
    dataset_id="PRUEBA-001",
    nombre="Fuente de prueba",
    institucion="Ninguna",
    url="https://example.org/prueba.xlsx",
    archivo="prueba.xlsx",
    formato="xlsx",
    descripcion="Archivo de prueba.",
)


def escribir_libro(ruta: Path) -> None:
    """Escribe un ZIP con la estructura mínima de un libro de Excel."""
    with zipfile.ZipFile(ruta, "w") as libro:
        libro.writestr("[Content_Types].xml", "<Types/>")
        libro.writestr("xl/workbook.xml", "<workbook/>" * 100)


def escribir_vacio(ruta: Path) -> None:
    """Escribe un archivo vacío."""
    ruta.write_bytes(b"")


def escribir_pagina(ruta: Path) -> None:
    """Escribe una página de error como la que devuelve un servidor."""
    ruta.write_text("<!DOCTYPE html><html>Error</html>", encoding="utf-8")


def escribir_zip_sin_libro(ruta: Path) -> None:
    """Escribe un ZIP que no es un libro de Excel."""
    with zipfile.ZipFile(ruta, "w") as comprimido:
        comprimido.writestr("datos.csv", "a,b\n1,2\n")


def escribir_libro_cortado(ruta: Path) -> None:
    """Escribe la mitad de un libro, como una descarga interrumpida."""
    escribir_libro(ruta)
    datos = ruta.read_bytes()
    ruta.write_bytes(datos[: len(datos) // 2])


def bajar_libro(url: str, destino: Path) -> None:
    """Simula una descarga correcta."""
    escribir_libro(destino)


def bajar_pagina(url: str, destino: Path) -> None:
    """Simula un servidor que responde con una página de error."""
    escribir_pagina(destino)


def no_bajar(url: str, destino: Path) -> None:
    """Falla si se intenta descargar."""
    raise AssertionError("No debía descargar.")


def no_describir() -> None:
    """Falla si se intenta reescribir la descripción."""
    raise AssertionError("No debía cambiar la descripción.")


@pytest.fixture
def raw(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Proyecto temporal con data/raw y un registro vacío con el encabezado real."""
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True)
    registro = tmp_path / "catalog" / "ingestions.csv"
    registro.parent.mkdir()
    real = PROJECT_ROOT / "catalog" / "ingestions.csv"
    encabezado = real.read_text(encoding="utf-8").splitlines()[0]
    registro.write_text(encabezado + "\n", encoding="utf-8")
    monkeypatch.setattr(descarga, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(descarga, "RAW_DATA_DIR", raw)
    monkeypatch.setattr(descarga, "REGISTRO", registro)
    return raw


@pytest.mark.parametrize(
    "escribir",
    [escribir_vacio, escribir_pagina, escribir_zip_sin_libro, escribir_libro_cortado],
)
def test_rechaza_archivos_invalidos(tmp_path: Path, escribir) -> None:
    """Comprueba que se rechacen los archivos que no son un libro de Excel completo."""
    ruta = tmp_path / "archivo.xlsx"
    escribir(ruta)
    with pytest.raises(ArchivoInvalido):
        validar(ruta, "xlsx")


def test_acepta_libro(tmp_path: Path) -> None:
    """Comprueba que un libro de Excel completo pase la validación."""
    ruta = tmp_path / "libro.xlsx"
    escribir_libro(ruta)
    validar(ruta, "xlsx")


def test_descarga_y_registra(raw: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Comprueba que la descarga quede en data/raw y en el registro con su enlace."""
    monkeypatch.setattr(descarga, "bajar", bajar_libro)
    assert descargar(FUENTE)
    (fila,) = descarga.leer_registro()
    assert fila["dataset_id"] == "PRUEBA-001"
    assert fila["raw_path"] == "data/raw/prueba.xlsx"
    assert fila["checksum"] == huella(raw / "prueba.xlsx")
    assert fila["status"] == "ok"
    assert fila["download_url"] == FUENTE.url
    assert fila["notes"] == ""


def test_no_descarga_si_ya_existe(raw: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Comprueba que un archivo ya registrado no se vuelva a descargar."""
    monkeypatch.setattr(descarga, "bajar", bajar_libro)
    descargar(FUENTE)
    monkeypatch.setattr(descarga, "bajar", no_bajar)
    assert not descargar(FUENTE)
    assert len(descarga.leer_registro()) == 1


def test_detecta_crudo_modificado(raw: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Comprueba que se detecte un crudo que cambió después de su descarga."""
    monkeypatch.setattr(descarga, "bajar", bajar_libro)
    descargar(FUENTE)
    with (raw / "prueba.xlsx").open("ab") as archivo:
        archivo.write(b"x")
    with pytest.raises(ArchivoInvalido, match="huella"):
        descargar(FUENTE)


def test_descarta_descarga_invalida(raw: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Comprueba que una página de error no quede en data/raw ni en el registro."""
    monkeypatch.setattr(descarga, "bajar", bajar_pagina)
    with pytest.raises(ArchivoInvalido):
        descargar(FUENTE)
    assert list(raw.iterdir()) == []
    assert descarga.leer_registro() == []


def test_reintenta_sin_conexion(raw: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Comprueba que se reintente sin conexión y no queden archivos a medias."""
    llamadas = []

    def sin_conexion(*args, **kwargs):
        llamadas.append(args)
        raise requests.ConnectionError("Sin conexión.")

    monkeypatch.setattr(descarga.requests, "get", sin_conexion)
    monkeypatch.setattr(descarga, "ESPERA_REINTENTO", 0)
    with pytest.raises(requests.ConnectionError):
        descargar(FUENTE)
    assert len(llamadas) == descarga.INTENTOS
    assert list(raw.iterdir()) == []


def test_no_repite_descarga_igual(raw: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Comprueba que una descarga idéntica no agregue fila ni toque la descripción."""
    monkeypatch.setattr(descarga, "bajar", bajar_libro)
    descargar(FUENTE)
    ruta = raw / FUENTE.archivo
    datos = ruta.read_bytes()
    # Como en un clon nuevo: la fila está en el registro y el archivo no.
    ruta.unlink()

    monkeypatch.setattr(
        descarga, "bajar", lambda url, destino: destino.write_bytes(datos)
    )
    monkeypatch.setattr(descarga, "escribir_descripcion", no_describir)
    monkeypatch.setattr(descarga, "FUENTES", [FUENTE])
    monkeypatch.setattr(sys, "argv", ["descarga", FUENTE.dataset_id])
    descarga.main()

    assert ruta.read_bytes() == datos
    assert len(descarga.leer_registro()) == 1
