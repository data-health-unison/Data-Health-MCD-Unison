"""Trazabilidad: con qué código se generó cada archivo y cómo reconocerlo después.

- ``huella``: SHA-256 de un archivo, para saber si dos archivos son idénticos.
- ``estado_git``: commit, rama y cambios sin commit del proyecto.
- ``guardar_parquet``: escribe un parquet con un *sello* en sus metadatos (versión del proyecto,
  commit y fecha), de modo que el archivo dice con qué código se generó aunque se copie a otra
  computadora. ``leer_sello`` lo recupera.
- ``describir_archivo``: huella, tamaño y, para los parquet, filas, columnas y sello.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

from health_data import __version__
from health_data.config import PROJECT_ROOT

# Clave del sello dentro de los metadatos del esquema Parquet
CLAVE_SELLO = b"health_data"


def huella(ruta: Path) -> str:
    """Huella SHA-256 del archivo, con el prefijo ``sha256:``."""
    with ruta.open("rb") as archivo:
        return "sha256:" + hashlib.file_digest(archivo, "sha256").hexdigest()


def ruta_relativa(ruta: Path, raiz: Path | None = None) -> str:
    """Ruta relativa a la raíz del proyecto, con diagonales (o absoluta si está fuera)."""
    base = (raiz or PROJECT_ROOT).resolve()
    try:
        return Path(ruta).resolve().relative_to(base).as_posix()
    except ValueError:
        return Path(ruta).as_posix()


def _git(raiz: Path, *argumentos: str) -> str:
    # safe.directory: dentro de Docker el proyecto montado pertenece a otro usuario y git lo rechazaría
    resultado = subprocess.run(
        ["git", "-c", f"safe.directory={raiz}", "-C", str(raiz), *argumentos],
        capture_output=True, text=True, check=True, timeout=30,
    )
    # Solo se quita el salto final: `git status --porcelain` empieza con un espacio significativo
    return resultado.stdout.rstrip("\n")


def estado_git(raiz: Path | None = None) -> dict[str, Any]:
    """Commit, rama y archivos con cambios sin commit; ``commit`` es None si no hay git."""
    raiz = raiz or PROJECT_ROOT
    try:
        commit = _git(raiz, "rev-parse", "HEAD")
        rama = _git(raiz, "rev-parse", "--abbrev-ref", "HEAD")
        estado = _git(raiz, "status", "--porcelain")
    except (OSError, subprocess.SubprocessError) as exc:
        motivo = "git no está instalado" if isinstance(exc, FileNotFoundError) else "no es un repositorio de git"
        return {"commit": None, "rama": None, "cambios_sin_commit": [], "motivo": motivo}
    cambios = [linea[3:] for linea in estado.splitlines() if linea.strip()]
    return {"commit": commit, "rama": rama, "cambios_sin_commit": cambios}


def sello(git: dict[str, Any] | None = None) -> dict[str, Any]:
    """Con qué se generó un archivo: versión del proyecto, commit y fecha."""
    git = git if git is not None else estado_git()
    return {
        "version": __version__,
        "commit": git.get("commit"),
        "cambios_sin_commit": bool(git.get("cambios_sin_commit")),
        "generado_en": datetime.now().astimezone().isoformat(timespec="seconds"),
    }


def guardar_parquet(tabla: pd.DataFrame, ruta: Path, *, git: dict[str, Any] | None = None) -> None:
    """Guarda la tabla (también GeoDataFrame) en Parquet, con el sello en sus metadatos."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tabla.to_parquet(ruta, index=False)
    # Se agrega el sello sin tocar los demás metadatos (los de pandas y los de GeoParquet)
    archivo = pq.read_table(ruta)
    metadatos = dict(archivo.schema.metadata or {})
    metadatos[CLAVE_SELLO] = json.dumps(sello(git), ensure_ascii=False).encode("utf-8")
    pq.write_table(archivo.replace_schema_metadata(metadatos), ruta)


def leer_sello(ruta: Path) -> dict[str, Any] | None:
    """Sello de un parquet, o None si se generó antes de existir el sello."""
    metadatos = pq.read_schema(ruta).metadata or {}
    if CLAVE_SELLO not in metadatos:
        return None
    return json.loads(metadatos[CLAVE_SELLO])


def describir_archivo(ruta: Path, raiz: Path | None = None) -> dict[str, Any]:
    """Huella, tamaño y, si es parquet, filas, columnas y sello del archivo."""
    descripcion: dict[str, Any] = {
        "ruta": ruta_relativa(ruta, raiz),
        "huella": huella(ruta),
        "bytes": ruta.stat().st_size,
    }
    if ruta.suffix == ".parquet":
        try:
            metadatos = pq.ParquetFile(ruta).metadata
            descripcion["filas"] = metadatos.num_rows
            descripcion["columnas"] = metadatos.num_columns
            descripcion["sello"] = leer_sello(ruta)
        except Exception as exc:  # Un parquet dañado no debe impedir describir los demás
            descripcion["error"] = f"No se pudo leer como Parquet: {exc}"
    return descripcion
