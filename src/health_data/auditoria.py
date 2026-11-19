"""Auditoría sin red de los archivos locales y las uniones del proyecto."""

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from health_data.calidad_ruteo import ESTADOS, METODOS, padron_provisional, tiempos_por_nivel
from health_data.config import cargar_configuracion

BASE = "accesibilidad_localidades"
ITER = "inegi-pop-001_localidades"
SALUD = "salud-001_establecimientos"
URG = "urgencias_mensuales"
FUENTES = {
    BASE: (None, ("locality_id",)),
    ITER: ("INEGI-POP-001", ("cvegeo",)),
    SALUD: ("SALUD-001", ("clues",)),
    URG: ("SONORA-URG-001", ("clues", "periodo")),
    "inegi-resloc-001_localidades": ("INEGI-RESLOC-001", ("cvegeo",)),
    "conapo-marg-001_localidades": ("CONAPO-MARG-001", ("cvegeo",)),
    "coneval-acc-001_localidades": ("CONEVAL-ACC-001", ("cvegeo",)),
    "escenario_vial_localidades": ("INEGI-RNC-001", ("tramo_cerrado", "locality_id")),
}


def clave_valida(valores: pd.Series, patron: str) -> pd.Series:
    return valores.astype("string").str.fullmatch(patron, na=False)


def auditar_tabla(tabla: pd.DataFrame, claves: tuple[str, ...]) -> dict:
    reglas = {}
    for clave in claves:
        valores = tabla.reindex(columns=[clave])[clave]
        if clave in ("cvegeo", "locality_id", "clues"):
            patron = r"26\d{7}" if clave != "clues" else r"[A-Z]{2}[A-Z0-9]{9}"
            reglas[f"{clave}_invalida"] = int((~clave_valida(valores, patron)).sum())
        else:
            reglas[f"{clave}_invalida"] = int(valores.isna().sum())
    for col, limite in {
        "latitude": (25.5, 33), "latitud": (25.5, 33),
        "longitude": (-116, -108), "longitud": (-116, -108),
        "population": (0, float("inf")), "poblacion_total": (0, float("inf")),
        "primary_time_min": (0, float("inf")), "secondary_time_min": (0, float("inf")),
    }.items():
        if col in tabla:
            valores = pd.to_numeric(tabla[col], errors="coerce")
            reglas[f"{col}_fuera_de_rango"] = int(
                (tabla[col].notna() & (~valores.between(*limite) | valores.eq(float("inf")))).sum()
            )
    for col, permitido in {"routing_status": ESTADOS, "primary_method": METODOS,
                            "secondary_method": METODOS}.items():
        if col in tabla:
            reglas[f"{col}_invalido"] = int((~tabla[col].isin(permitido)).sum())
    if "routing_status" in tabla and {"primary_method", "secondary_method"} <= set(tabla):
        medidos = tabla[["primary_method", "secondary_method"]].eq("sakbe").sum(axis=1)
        coherente = (tabla["routing_status"].eq("ok") & medidos.eq(2)
                     | tabla["routing_status"].eq("parcial") & medidos.eq(1)
                     | tabla["routing_status"].isin(["sin_ruta", "estimado"]) & medidos.eq(0))
        reglas["estado_incoherente_con_metodos"] = int((~coherente).sum())
    geo = next((c for c in ("cvegeo", "locality_id") if c in tabla), None)
    municipios = (tabla.loc[clave_valida(tabla[geo], r"26\d{7}"), geo]
                  .astype("string").str[:5].nunique() if geo else None)
    return {
        "filas": len(tabla),
        "municipios_por_clave": municipios,
        "nulos_por_columna": tabla.isna().sum().to_dict(),
        "filas_con_clave_duplicada": (
            int(tabla.duplicated(list(claves), keep=False).sum())
            if claves and set(claves) <= set(tabla) else None
        ),
        "reglas": reglas,
        "pct_clave_valida": {
            clave: round(100 * (1 - reglas[f"{clave}_invalida"] / len(tabla)), 2)
            for clave in claves if len(tabla)
        },
    }


def revisar_union(izq: pd.DataFrame, der: pd.DataFrame, a: str, b: str) -> dict:
    """Diagnóstico sin descartar registros ni materializar un producto cartesiano."""
    if a not in izq or b not in der:
        faltantes = [lado for lado, tabla, clave in (("izquierda", izq, a), ("derecha", der, b))
                     if clave not in tabla]
        return {"filas_izquierda": len(izq), "filas_derecha": len(der),
                "lado_sin_columna_clave": faltantes}
    a_n = izq[a].dropna().astype(str).value_counts()
    b_n = der[b].dropna().astype(str).value_counts()
    comunes = a_n.index.intersection(b_n.index)
    sin_der = a_n.index.difference(b_n.index)
    sin_izq = b_n.index.difference(a_n.index)
    detectados = {}
    pares = izq.loc[izq[a].notna() & ~izq[a].duplicated(keep=False)].merge(
        der.loc[der[b].notna() & ~der[b].duplicated(keep=False)],
        left_on=a, right_on=b, suffixes=("_izq", "_der"),
    )
    for campo in ("cve_mun", "municipio", "latitud", "longitud"):
        x, y = f"{campo}_izq", f"{campo}_der"
        if x in pares and y in pares:
            presentes = pares[x].notna() & pares[y].notna()
            if campo in ("latitud", "longitud"):
                difiere = (pd.to_numeric(pares[x], errors="coerce")
                           - pd.to_numeric(pares[y], errors="coerce")).abs().gt(0.0001)
            else:
                difiere = (pares[x].astype("string").str.strip().str.casefold()
                           .ne(pares[y].astype("string").str.strip().str.casefold()))
            detectados[campo] = sorted(pares.loc[presentes & difiere, a].astype(str).tolist())
    return {
        "filas_izquierda": len(izq), "filas_derecha": len(der),
        "filas_left_join": len(izq) - int(a_n.loc[comunes].sum())
        + int((a_n.loc[comunes] * b_n.loc[comunes]).sum()),
        "claves_unicas_coincidentes": len(comunes),
        "claves_sin_correspondencia_izquierda": sorted(sin_der),
        "claves_sin_correspondencia_derecha": sorted(sin_izq),
        "claves_nulas_izquierda": int(izq[a].isna().sum()),
        "claves_nulas_derecha": int(der[b].isna().sum()),
        "claves_repetidas_izquierda": sorted(a_n[a_n.gt(1)].index),
        "claves_repetidas_derecha": sorted(b_n[b_n.gt(1)].index),
        "conflictos_en_claves_unicas": detectados,
    }


def estructura_cruda(ruta: Path) -> dict:
    if ruta.suffix.lower() == ".zip":
        with zipfile.ZipFile(ruta) as archivo:
            capas = {}
            for nombre in archivo.namelist():
                if nombre.lower().endswith(".dbf"):
                    with archivo.open(nombre) as capa:
                        capas[nombre] = int.from_bytes(capa.read(8)[4:8], "little")
                elif nombre.lower().endswith(".csv"):
                    with archivo.open(nombre) as capa:
                        capas[nombre] = max(0, sum(1 for _ in capa) - 1)
            return {"conteo_por_componente": capas, "unidad": "registros DBF o líneas CSV sin cabecera"}
    if ruta.suffix.lower() == ".xlsx":
        libro = load_workbook(ruta, read_only=True)
        try:
            return {"conteo_por_componente": {hoja.title: hoja.max_row for hoja in libro.worksheets},
                    "unidad": "filas declaradas por hoja, incluidas cabeceras"}
        finally:
            libro.close()
    return {}


def construir_reporte(raiz: Path) -> tuple[dict, dict[str, pd.DataFrame]]:
    catalogo = pd.read_csv(raiz / "catalog/datasets.csv", dtype=str).fillna("").set_index("dataset_id")
    ingestas = pd.read_csv(raiz / "catalog/ingestions.csv", dtype=str).fillna("")
    ingestas = ingestas.loc[ingestas["status"].eq("ok")].sort_values("retrieved_at")
    ultimas = ingestas.drop_duplicates("raw_path", keep="last").set_index("raw_path")
    reporte = {"archivos": {}, "uniones": {}}
    tablas = {}
    for carpeta in ("data/raw", "data/processed"):
        presentes = {p.relative_to(raiz).as_posix() for p in (raiz / carpeta).glob("*")
                     if p.is_file() and not p.name.startswith(".")}
        esperados = (set(ultimas.index) if carpeta == "data/raw" else
                     {f"{carpeta}/{nombre}.parquet" for nombre in FUENTES})
        for relativo in sorted(presentes | esperados):
            ruta = raiz / relativo
            meta = ultimas.loc[relativo] if relativo in ultimas.index else {}
            fuente, claves = FUENTES.get(ruta.stem, (meta.get("dataset_id"), ()))
            if ruta.name == "escenario_vial_trayectos.geojson":
                fuente = "INEGI-RNC-001"
            ficha = catalogo.loc[fuente] if fuente in catalogo.index else {}
            registro = {"presente": ruta.is_file(), "fuente": fuente,
                        "periodo_fuente": [ficha.get("start_year"), ficha.get("end_year")],
                        "version_fuente": ficha.get("version"),
                        "ingesta_registrada": meta.get("retrieved_at")}
            reporte["archivos"][relativo] = registro
            if not ruta.is_file():
                continue
            registro["bytes"] = ruta.stat().st_size
            try:
                if carpeta == "data/raw":
                    with ruta.open("rb") as entrada:
                        checksum = "sha256:" + hashlib.file_digest(entrada, "sha256").hexdigest()
                    esperado = meta.get("checksum")
                    registro.update(checksum=checksum, checksum_coincide=checksum == esperado if esperado else None)
                    registro.update(estructura_cruda(ruta))
                elif ruta.suffix == ".parquet":
                    tabla = pd.read_parquet(ruta)
                    tablas[ruta.stem] = tabla
                    registro.update(auditar_tabla(tabla, claves))
                    if "periodo" in tabla and tabla["periodo"].notna().any():
                        registro["periodo_procesado"] = [str(tabla["periodo"].min()),
                                                         str(tabla["periodo"].max())]
                elif ruta.suffix == ".geojson":
                    registro["filas"] = len(json.loads(ruta.read_text(encoding="utf-8"))["features"])
            except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
                registro["error_lectura"] = str(exc)

    for nombre in ("inegi-resloc-001_localidades", "conapo-marg-001_localidades",
                   "coneval-acc-001_localidades", SALUD):
        if ITER in tablas and nombre in tablas:
            reporte["uniones"][f"ITER → {nombre}"] = revisar_union(tablas[ITER], tablas[nombre], "cvegeo", "cvegeo")
    if BASE in tablas and ITER in tablas:
        accesibilidad = tablas[BASE].rename(columns={"latitude": "latitud", "longitude": "longitud",
                                                      "municipality_name": "municipio"})
        reporte["uniones"]["Accesibilidad → ITER"] = revisar_union(accesibilidad, tablas[ITER], "locality_id", "cvegeo")
        excluidas = cargar_configuracion(raiz / "config/fuentes_health.yaml").localidades_excluidas
        reporte["exclusiones_configuradas"] = excluidas
        reporte["exclusiones_en_tabla"] = (
            sorted(set(excluidas) & set(accesibilidad["locality_id"]))
            if "locality_id" in accesibilidad else None
        )
    if SALUD in tablas:
        if URG in tablas:
            reporte["uniones"]["Urgencias → CLUES"] = revisar_union(tablas[URG], tablas[SALUD], "clues", "clues")
        if BASE in tablas:
            for nivel in ("primary", "secondary"):
                clave = f"nearest_{nivel}_clues"
                reporte["uniones"][f"Accesibilidad {nivel} → CLUES"] = revisar_union(
                    tablas[BASE], tablas[SALUD], clave, "clues"
                )
    return reporte, tablas


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raiz", type=Path, default=Path.cwd())
    parser.add_argument("--salida", type=Path)
    args = parser.parse_args()
    salida = args.salida or args.raiz / "data/processed/calidad"
    reporte, tablas = construir_reporte(args.raiz)
    salida.mkdir(parents=True, exist_ok=True)
    (salida / "calidad_y_cobertura.json").write_text(
        json.dumps(reporte, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if BASE in tablas:
        padron = padron_provisional(tiempos_por_nivel(tablas[BASE]))
        padron.to_csv(salida / "padron_provisional_ruteo.csv", index=False, encoding="utf-8-sig")
    print(f"Reporte disponible en {salida}")


if __name__ == "__main__":
    main()
