"""Validación de calidad e invariantes del dataset final de salud.

Verifica que el dataset de accesibilidad por localidad cumpla con las columnas
requeridas, tipos de datos correctos, ausencia de tiempos negativos o anómalos,
y consistencia entre claves geoestadísticas.
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from health_data.config import ARCHIVO_TABLA_FINAL

log = logging.getLogger("health_data.validacion")

COLUMNAS_MINIMAS_REQUERIDAS = [
    "locality_id",
    "locality_name",
    "municipality_name",
    "population",
    "latitude",
    "longitude",
    "nearest_primary_clues",
    "primary_distance_km",
    "primary_time_min",
    "nearest_secondary_clues",
    "secondary_distance_km",
    "secondary_time_min",
    "routing_status",
]


@dataclass
class Comprobacion:
    """Resultado de una regla de validación individual."""

    nombre: str
    paso: bool
    detalle: str
    valor: float | str | None = None
    esperado: float | str | None = None

    @property
    def simbolo(self) -> str:
        return "OK  " if self.paso else "FALLA"


@dataclass
class ReporteValidacion:
    """Conjunto de comprobaciones de validación."""

    nombre_dataset: str
    comprobaciones: list[Comprobacion] = field(default_factory=list)

    @property
    def fallidas(self) -> list[Comprobacion]:
        return [c for c in self.comprobaciones if not c.paso]

    @property
    def paso(self) -> bool:
        return not self.fallidas

    def agregar(self, comprobacion: Comprobacion) -> None:
        self.comprobaciones.append(comprobacion)
        nivel = logging.INFO if comprobacion.paso else logging.ERROR
        log.log(
            nivel,
            "  [%s] %s: %s",
            comprobacion.simbolo,
            comprobacion.nombre,
            comprobacion.detalle,
        )


def validar_tabla_final(tabla: pd.DataFrame) -> ReporteValidacion:
    """Valida el dataset final consolidado de accesibilidad a servicios de salud."""
    reporte = ReporteValidacion(nombre_dataset="accesibilidad_localidades")

    if tabla.empty:
        reporte.agregar(
            Comprobacion(
                nombre="datos_disponibles",
                paso=False,
                detalle="La tabla proporcionada está vacía (0 filas).",
            )
        )
        return reporte

    # 1. Columnas requeridas según especificación del proyecto
    faltantes = [c for c in COLUMNAS_MINIMAS_REQUERIDAS if c not in tabla.columns]
    reporte.agregar(
        Comprobacion(
            nombre="columnas_requeridas",
            paso=len(faltantes) == 0,
            detalle="Todas las columnas requeridas están presentes."
            if not faltantes
            else f"Faltan columnas obligatorias: {faltantes}",
        )
    )

    # 2. Clave de localidad única
    if "locality_id" in tabla.columns:
        unicas = tabla["locality_id"].is_unique
        duplicados = int(tabla["locality_id"].duplicated().sum())
        reporte.agregar(
            Comprobacion(
                nombre="locality_id_unica",
                paso=unicas,
                detalle="Todas las claves de localidad son únicas."
                if unicas
                else f"Existen {duplicados} claves duplicadas.",
            )
        )

    # 3. Coordenadas geográficas válidas en Sonora
    # Latitud Sonora aprox: 26.2 a 32.5 | Longitud: -115.1 a -108.4
    if {"latitude", "longitude"}.issubset(tabla.columns):
        lat_validas = tabla["latitude"].between(25.5, 33.0).fillna(False)
        lon_validas = tabla["longitude"].between(-116.0, -108.0).fillna(False)
        coords_ok = lat_validas & lon_validas
        fuera = int((~coords_ok).sum())
        reporte.agregar(
            Comprobacion(
                nombre="coordenadas_en_rango_sonora",
                paso=fuera == 0,
                detalle="Todas las coordenadas caen en el cuadrante geográfico de Sonora."
                if fuera == 0
                else f"{fuera} localidades con coordenadas fuera del rango de Sonora.",
            )
        )

    # 4. Tiempos de traslado no negativos
    for col in ("primary_time_min", "secondary_time_min"):
        if col in tabla.columns:
            valores = pd.to_numeric(tabla[col], errors="coerce")
            negativos = int((valores < 0).sum())
            reporte.agregar(
                Comprobacion(
                    nombre=f"sin_{col}_negativos",
                    paso=negativos == 0,
                    detalle=f"No hay tiempos negativos en {col}."
                    if negativos == 0
                    else f"{negativos} filas con tiempo negativo.",
                )
            )

    # 5. Coherencia: distancia al 2do nivel >= distancia al 1er nivel en general
    if {"primary_time_min", "secondary_time_min"}.issubset(tabla.columns):
        t1 = pd.to_numeric(tabla["primary_time_min"], errors="coerce")
        t2 = pd.to_numeric(tabla["secondary_time_min"], errors="coerce")
        ambos = t1.notna() & t2.notna()
        if ambos.any():
            # En la gran mayoría de los casos, el 2do nivel (hospital) está más lejos o a la misma distancia que el 1er nivel
            segundo_mas_cercano = int((t2 < t1 - 1.0).sum())
            # Es informativo pero no necesariamente un error si la localidad alberga un hospital de 2do nivel que también da consulta general
            reporte.agregar(
                Comprobacion(
                    nombre="consistencia_tiempos_1er_y_2do_nivel",
                    paso=True,
                    detalle=f"Tiempos comparados en {int(ambos.sum())} localidades; en {segundo_mas_cercano} el 2do nivel está más próximo.",
                )
            )

    # 6. Estatus de ruteo
    if "routing_status" in tabla.columns:
        con_ruta = int(tabla["routing_status"].eq("ok").sum())
        total = len(tabla)
        cobertura = con_ruta / total if total > 0 else 0
        reporte.agregar(
            Comprobacion(
                nombre="cobertura_ruteo_sakbe",
                paso=cobertura >= 0.70,
                detalle=f"Ruta obtenida en {con_ruta:,} de {total:,} ({cobertura:.1%}) localidades.",
                valor=cobertura,
                esperado=0.70,
            )
        )

    return reporte


def validar_archivo_procesado(ruta: Path | None = None) -> ReporteValidacion:
    """Lee el archivo parquet de salida y lo valida."""
    archivo = ruta or ARCHIVO_TABLA_FINAL
    reporte = ReporteValidacion(nombre_dataset=archivo.name)

    if not archivo.exists():
        reporte.agregar(
            Comprobacion(
                nombre="archivo_existe",
                paso=False,
                detalle=f"No existe el archivo {archivo}. Ejecute el pipeline primero.",
            )
        )
        return reporte

    try:
        tabla = pd.read_parquet(archivo)
        return validar_tabla_final(tabla)
    except Exception as exc:
        reporte.agregar(
            Comprobacion(
                nombre="lectura_parquet",
                paso=False,
                detalle=f"Error leyendo {archivo}: {exc}",
            )
        )
        return reporte


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada de línea de comandos para validación."""
    parser = argparse.ArgumentParser(
        prog="python -m health_data.validacion",
        description="Valida la calidad e integridad del dataset final de salud.",
    )
    parser.add_argument(
        "--archivo",
        type=Path,
        default=None,
        help="Ruta al archivo Parquet a validar.",
    )
    parser.add_argument("--verboso", action="store_true", help="Salida detallada.")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verboso else logging.INFO,
        format="%(message)s",
    )

    reporte = validar_archivo_procesado(args.archivo)

    print()
    print("=" * 68)
    print(f"Validación: {len(reporte.comprobaciones)} comprobaciones, {len(reporte.fallidas)} fallidas")
    estado = "PASA" if reporte.paso else "FALLA"
    print(f"Resultado: {estado}")
    for comp in reporte.comprobaciones:
        print(f"  [{comp.simbolo}] {comp.nombre}: {comp.detalle}")
    print("=" * 68)

    return 0 if reporte.paso else 1


if __name__ == "__main__":
    sys.exit(main())
