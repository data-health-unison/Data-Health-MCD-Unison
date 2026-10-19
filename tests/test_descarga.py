"""Pruebas sin red de la descarga y el registro de fuentes."""

import zipfile
from pathlib import Path

import pytest
import requests

from health_data.config import PROJECT_ROOT, FuenteInfo
from health_data.ingestion import descarga
from health_data.ingestion.descarga import (
    ArchivoInvalido,
    ErrorDeDescarga,
    descargar_dataset,
    huella,
    validar,
)

FUENTE = FuenteInfo(
    dataset_id="PRUEBA-001",
    nombre="Fuente de prueba",
    url="https://example.org/prueba.xlsx",
    nombre_archivo="prueba.xlsx",
    institucion="Ninguna",
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


def contenido(escribir, tmp_path: Path) -> bytes:
    """Bytes que produce una función ``escribir_*``."""
    ruta = tmp_path / "_contenido"
    escribir(ruta)
    return ruta.read_bytes()


class RespuestaFalsa:
    def __init__(self, datos: bytes) -> None:
        self.status_code = 200
        self._datos = datos

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def raise_for_status(self) -> None:
        pass

    def iter_content(self, chunk_size: int):
        yield self._datos


class SesionFalsa:
    """Sustituye a requests.Session: entrega ``datos`` o lanza ``error`` en cada GET."""

    def __init__(self, datos: bytes = b"", error: Exception | None = None) -> None:
        self.headers: dict[str, str] = {}
        self.datos, self.error, self.llamadas = datos, error, 0

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def get(self, url, **kwargs):
        self.llamadas += 1
        if self.error:
            raise self.error
        return RespuestaFalsa(self.datos)


@pytest.fixture
def raw(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Proyecto temporal con data/raw y un registro vacío con el encabezado real."""
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True)
    registro = tmp_path / "catalog" / "ingestions.csv"
    registro.parent.mkdir()
    encabezado = (PROJECT_ROOT / "catalog" / "ingestions.csv").read_text(encoding="utf-8").splitlines()[0]
    registro.write_text(encabezado + "\n", encoding="utf-8")
    monkeypatch.setattr(descarga, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(descarga, "RAW_DATA_DIR", raw)
    monkeypatch.setattr(descarga, "REGISTRO", registro)
    monkeypatch.setattr(descarga, "DESCRIPCION", tmp_path / "references" / "fuentes_descargadas.md")
    monkeypatch.setattr(descarga, "ensure_directories", lambda: None)
    monkeypatch.setattr(descarga.time, "sleep", lambda _: None)
    return raw


def servir(monkeypatch: pytest.MonkeyPatch, **kwargs) -> SesionFalsa:
    sesion = SesionFalsa(**kwargs)
    monkeypatch.setattr(descarga.requests, "Session", lambda: sesion)
    return sesion


def descargar(**kwargs):
    return descargar_dataset(FUENTE.dataset_id, FUENTE.url, FUENTE.nombre_archivo, tamano_minimo=1, **kwargs)


@pytest.mark.parametrize(
    "escribir",
    [escribir_vacio, escribir_pagina, escribir_zip_sin_libro, escribir_libro_cortado],
)
def test_rechaza_archivos_invalidos(tmp_path: Path, escribir) -> None:
    """Se rechazan los archivos que no son un libro de Excel completo."""
    ruta = tmp_path / "archivo.xlsx"
    escribir(ruta)
    with pytest.raises(ArchivoInvalido):
        validar(ruta, "xlsx", tamano_minimo=1)


def test_acepta_libro(tmp_path: Path) -> None:
    ruta = tmp_path / "libro.xlsx"
    escribir_libro(ruta)
    validar(ruta, "xlsx", tamano_minimo=1)


def test_acepta_zip(tmp_path: Path) -> None:
    ruta = tmp_path / "datos.zip"
    escribir_zip_sin_libro(ruta)
    validar(ruta, tamano_minimo=1)  # formato por la extensión


def test_fuentes_bien_definidas() -> None:
    """Cada fuente descargable es única, usa https, tiene validador y está descrita."""
    fuentes = descarga.fuentes_descargables()
    archivos = [f.nombre_archivo for f in fuentes.values()]
    assert len(set(archivos)) == len(archivos)
    for f in fuentes.values():
        assert f.url.startswith("https://")
        assert f.formato in descarga.VALIDADORES
        assert Path(f.nombre_archivo).suffix.lstrip(".") == f.formato
        assert f.institucion and f.descripcion


def test_descarga_y_registra(raw: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """La descarga queda en data/raw y en el registro con su huella y su enlace."""
    servir(monkeypatch, datos=contenido(escribir_libro, tmp_path))
    res = descargar()
    assert res.registrada and not res.reutilizado
    (fila,) = descarga.leer_registro()
    assert fila["dataset_id"] == "PRUEBA-001"
    assert fila["raw_path"] == "data/raw/prueba.xlsx"
    assert fila["checksum"] == huella(raw / "prueba.xlsx") == res.checksum
    assert fila["status"] == "ok"
    assert fila["download_url"] == FUENTE.url
    assert fila["notes"] == ""


def test_no_descarga_si_ya_existe(raw: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Un archivo ya registrado no se vuelve a descargar."""
    servir(monkeypatch, datos=contenido(escribir_libro, tmp_path))
    descargar()
    sesion = servir(monkeypatch, error=AssertionError("No debía descargar."))
    res = descargar()
    assert res.reutilizado and not res.registrada
    assert sesion.llamadas == 0
    assert len(descarga.leer_registro()) == 1


def test_detecta_crudo_modificado(raw: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Se detecta un crudo que cambió después de su descarga."""
    servir(monkeypatch, datos=contenido(escribir_libro, tmp_path))
    descargar()
    with (raw / "prueba.xlsx").open("ab") as archivo:
        archivo.write(b"x")
    with pytest.raises(ArchivoInvalido, match="huella"):
        descargar()


def test_descarta_descarga_invalida(raw: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Una página de error no queda en data/raw ni en el registro."""
    servir(monkeypatch, datos=contenido(escribir_pagina, tmp_path))
    with pytest.raises(ArchivoInvalido):
        descargar()
    assert not (raw / "prueba.xlsx").exists()
    assert descarga.leer_registro() == []


def test_reintenta_sin_conexion(raw: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Sin conexión se reintenta y no quedan archivos a medias."""
    sesion = servir(monkeypatch, error=requests.ConnectionError("Sin conexión."))
    with pytest.raises(ErrorDeDescarga):
        descargar()
    assert sesion.llamadas == descarga.REINTENTOS
    assert not (raw / "prueba.xlsx").exists()


def test_no_repite_descarga_igual(raw: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Una descarga idéntica (como en un clon nuevo) no agrega fila ni toca la descripción."""
    datos = contenido(escribir_libro, tmp_path)
    servir(monkeypatch, datos=datos)
    descargar()
    (raw / "prueba.xlsx").unlink()  # La fila está en el registro y el archivo no

    servir(monkeypatch, datos=datos)
    monkeypatch.setattr(descarga, "escribir_descripcion", lambda *_: pytest.fail("No debía cambiar la descripción."))
    res = descargar()
    assert not res.registrada
    assert (raw / "prueba.xlsx").read_bytes() == datos
    assert len(descarga.leer_registro()) == 1


def test_descripcion_de_fuentes(raw: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """La descripción lista la última descarga de cada fuente con su huella y su nota."""
    monkeypatch.setattr(descarga, "cargar_configuracion", lambda: type("C", (), {"fuentes": {"PRUEBA-001": FUENTE}})())
    servir(monkeypatch, datos=contenido(escribir_libro, tmp_path))
    res = descargar()
    texto = descarga.DESCRIPCION.read_text(encoding="utf-8")
    assert "## PRUEBA-001: Fuente de prueba" in texto
    assert "- Fuente: Ninguna" in texto
    assert res.checksum.removeprefix("sha256:") in texto


def test_cli_descarga_una_fuente(raw: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys) -> None:
    """``python -m health_data.ingestion.descarga PRUEBA-001`` descarga y registra."""
    monkeypatch.setattr(descarga, "fuentes_descargables", lambda: {"PRUEBA-001": FUENTE})
    servir(monkeypatch, datos=contenido(escribir_libro, tmp_path))
    # El libro de prueba pesa menos que el mínimo real (50 KB)
    monkeypatch.setattr(
        descarga, "descargar_dataset",
        lambda *a, **k: descargar_dataset(*a, **{**k, "tamano_minimo": 1}),
    )
    assert descarga.main(["PRUEBA-001"]) == 0
    assert "Registrado en catalog/ingestions.csv" in capsys.readouterr().out
    assert len(descarga.leer_registro()) == 1


def test_registro_real_coincide_con_data_raw() -> None:
    """Las huellas de catalog/ingestions.csv son las de los crudos de data/raw (si existen)."""
    filas = descarga.leer_registro()
    presentes = [f for f in filas if (PROJECT_ROOT / f["raw_path"]).exists()]
    if not presentes:
        pytest.skip("No hay crudos descargados en data/raw.")
    ultimas = {f["raw_path"]: f for f in presentes}
    for ruta, fila in ultimas.items():
        assert huella(PROJECT_ROOT / ruta) == fila["checksum"], ruta
