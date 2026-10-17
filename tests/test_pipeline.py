"""Pruebas del pipeline principal."""

import csv
import hashlib
from pathlib import Path

from health_data import pipeline


def test_ensure_directories() -> None:
    """Comprueba que los directorios puedan crearse."""
    pipeline.ensure_directories()


def test_registrar_ingesta_guarda_checksum_y_ruta_relativa(
    tmp_path: Path, monkeypatch
) -> None:
    """Registra descarga con checksum verificable sin añadir datos al repositorio."""
    raiz = tmp_path
    crudo = raiz / "data" / "raw" / "fuente.bin"
    crudo.parent.mkdir(parents=True)
    crudo.write_bytes(b"contenido de prueba")
    catalogo = raiz / "catalog" / "ingestions.csv"
    monkeypatch.setattr(pipeline, "PROJECT_ROOT", raiz)
    monkeypatch.setattr(pipeline, "ARCHIVO_INGESTAS", catalogo)

    pipeline.registrar_ingesta("TEST-001", crudo, "downloaded", "prueba")

    with catalogo.open(encoding="utf-8", newline="") as archivo:
        filas = list(csv.DictReader(archivo))
    assert len(filas) == 1
    assert filas[0]["dataset_id"] == "TEST-001"
    assert filas[0]["raw_path"] == "data/raw/fuente.bin"
    assert filas[0]["checksum"] == hashlib.sha256(b"contenido de prueba").hexdigest()
    assert filas[0]["status"] == "downloaded"