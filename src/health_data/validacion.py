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

import numpy as np
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
    "primary_candidate_clues",
    "primary_distance_km",
    "primary_time_min",
    "primary_routing_status",
    "secondary_candidate_clues",
    "secondary_distance_km",
    "secondary_time_min",
    "secondary_routing_status",
    "routing_method",
    "facility_selection_method",
    "routing_status",
]

ESTADOS_POR_NIVEL = {
    "estimated",
    "sakbe_ok",
    "no_route",
    "api_error",
    "quota_exceeded",
    "invalid_coordinates",
}
ESTADOS_GLOBALES = {
    "estimated",
    "sakbe_ok",
    "partial",
    "no_route",
    "api_error",
    "quota_exceeded",
}


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

    @property
    def todas_pasan(self) -> bool:
        """Alias descriptivo para consumidores del reporte."""
        return self.paso

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

    # 4. Distancias y tiempos deben ser no negativos y finitos cuando existan.
    for col in (
        "primary_distance_km",
        "primary_time_min",
        "secondary_distance_km",
        "secondary_time_min",
    ):
        if col in tabla.columns:
            valores = pd.to_numeric(tabla[col], errors="coerce")
            invalidos = int(
                (valores.notna() & ((valores < 0) | ~values_finite(valores))).sum()
            )
            reporte.agregar(
                Comprobacion(
                    nombre=f"{col}_valida",
                    paso=invalidos == 0,
                    detalle=f"{col} no contiene valores negativos ni infinitos."
                    if invalidos == 0
                    else f"{invalidos} valores inválidos en {col}.",
                )
            )

    columnas_estado = (
        "primary_routing_status",
        "secondary_routing_status",
    )
    columnas_de_ruteo = [
        *columnas_estado,
        "routing_method",
        "facility_selection_method",
        "routing_status",
        "primary_distance_km",
        "primary_time_min",
        "secondary_distance_km",
        "secondary_time_min",
    ]
    if all(col in tabla.columns for col in columnas_de_ruteo):
        for col in columnas_estado:
            invalido = ~tabla[col].isin(ESTADOS_POR_NIVEL)
            reporte.agregar(
                Comprobacion(
                    nombre=f"{col}_valido",
                    paso=not invalido.any(),
                    detalle=f"Estados válidos en {col}."
                    if not invalido.any()
                    else f"Estados desconocidos en {col}: "
                    f"{sorted(tabla.loc[invalido, col].astype(str).unique())}.",
                )
            )

        metodo = tabla["routing_method"].astype("string")
        metodos_validos = metodo.isin({"estimated", "sakbe"})
        reporte.agregar(
            Comprobacion(
                nombre="metodo_ruteo_valido",
                paso=bool(metodos_validos.all() and metodo.nunique() == 1),
                detalle="Todas las filas usan el mismo método de ruteo."
                if metodos_validos.all() and metodo.nunique() == 1
                else "Debe existir un único método válido ('estimated' o 'sakbe') "
                "por dataset.",
            )
        )
        seleccion = tabla["facility_selection_method"]
        seleccion_valida = seleccion.eq("nearest_geodesic")
        reporte.agregar(
            Comprobacion(
                nombre="seleccion_de_establecimiento_identificada",
                paso=bool(seleccion_valida.all()),
                detalle="Se declara que el candidato se elige por distancia geodésica."
                if seleccion_valida.all()
                else "La selección del establecimiento no está declarada o no es válida.",
            )
        )

        filas_estimadas = metodo.eq("estimated")
        estados_estimados = tabla.loc[filas_estimadas, list(columnas_estado)]
        estados_sakbe = tabla.loc[~filas_estimadas, list(columnas_estado)]
        estimadas_marcadas = (
            estados_estimados.eq("estimated")
            | estados_estimados.eq("invalid_coordinates")
        ).all(axis=None)
        reales_marcadas = (
            estados_sakbe.isin(ESTADOS_POR_NIVEL - {"estimated"}).all(axis=None)
        )
        reporte.agregar(
            Comprobacion(
                nombre="metodo_y_estado_coherentes",
                paso=bool(estimadas_marcadas and reales_marcadas),
                detalle="Las estimaciones y consultas SAKBÉ tienen estados separados."
                if estimadas_marcadas and reales_marcadas
                else "Hay filas cuyo estado de ruta no corresponde con routing_method.",
            )
        )

        ambos_ok = tabla[list(columnas_estado)].eq("sakbe_ok").all(axis=1)
        valores_completos = tabla[
            [
                "primary_distance_km",
                "primary_time_min",
                "secondary_distance_km",
                "secondary_time_min",
            ]
        ].notna().all(axis=1)
        completa = ambos_ok & valores_completos
        estimadas_validas = estados_estimados.apply(
            lambda fila: fila.isin({"estimated", "invalid_coordinates"}).all(),
            axis=1,
        )
        metricas_por_nivel = []
        for campo_estado, campo_dist, campo_tiempo in (
            (
                "primary_routing_status",
                "primary_distance_km",
                "primary_time_min",
            ),
            (
                "secondary_routing_status",
                "secondary_distance_km",
                "secondary_time_min",
            ),
        ):
            requiere_metricas = tabla[campo_estado].isin({"estimated", "sakbe_ok"})
            presentes = tabla[[campo_dist, campo_tiempo]].notna().all(axis=1)
            metricas_por_nivel.append(requiere_metricas.eq(presentes))
        metricas_coherentes = pd.concat(metricas_por_nivel, axis=1).all(axis=1)
        reporte.agregar(
            Comprobacion(
                nombre="metricas_y_estado_coherentes",
                paso=bool(metricas_coherentes.all()),
                detalle="Cada nivel conserva solo métricas respaldadas por su estado."
                if metricas_coherentes.all()
                else "Hay métricas faltantes o asignadas a un estado sin ruta.",
            )
        )

        estado_global_esperado = []
        for _, fila in tabla.iterrows():
            p = fila["primary_routing_status"]
            s = fila["secondary_routing_status"]
            if fila["routing_method"] == "estimated":
                esperado = "estimated" if p == s == "estimated" else "no_route"
            elif p == s == "sakbe_ok":
                esperado = "sakbe_ok"
            elif p == "sakbe_ok" or s == "sakbe_ok":
                esperado = "partial"
            elif "quota_exceeded" in (p, s):
                esperado = "quota_exceeded"
            elif "api_error" in (p, s):
                esperado = "api_error"
            else:
                esperado = "no_route"
            estado_global_esperado.append(esperado)
        ruta_global_correcta = tabla["routing_status"].eq(estado_global_esperado)
        reporte.agregar(
            Comprobacion(
                nombre="routing_status_coherente",
                paso=bool(ruta_global_correcta.all()),
                detalle="El estado global coincide con los resultados por nivel."
                if ruta_global_correcta.all()
                else "Hay estados globales que no coinciden con los resultados por nivel.",
            )
        )
        total = len(tabla)
        cobertura = int(completa.sum()) / total if total else 0.0
        es_estimado = bool(filas_estimadas.all())
        cobertura_valida = es_estimado or cobertura >= 0.70
        detalle_cobertura = (
            "Dataset de estimaciones; no se reporta como cobertura SAKBÉ."
            if es_estimado
            else f"Rutas SAKBÉ completas en {int(completa.sum()):,} de "
            f"{total:,} localidades ({cobertura:.1%})."
        )
        reporte.agregar(
            Comprobacion(
                nombre="cobertura_real_sakbe",
                paso=cobertura_valida,
                detalle=detalle_cobertura
                if cobertura_valida
                else f"{detalle_cobertura} Se requiere al menos 70%.",
                valor=cobertura,
                esperado="0% para estimaciones; >=70% para SAKBÉ",
            )
        )
        if not estados_estimados.empty:
            reporte.agregar(
                Comprobacion(
                    nombre="estimaciones_con_valores",
                    paso=bool(estimadas_validas.all()),
                    detalle="Las filas estimadas contienen distancias y tiempos."
                    if estimadas_validas.all()
                    else "Una fila estimada tiene un estado de ruteo inesperado.",
                )
            )

    return reporte


def values_finite(values: pd.Series) -> pd.Series:
    """Devuelve máscara para valores numéricos finitos."""
    arr = values.to_numpy(dtype=float, na_value=np.nan)
    return pd.Series(np.isfinite(arr), index=values.index)


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


def ejecutar_todas() -> ReporteValidacion:
    """Ejecuta las validaciones del Parquet final configurado."""
    return validar_archivo_procesado()


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
