# Diccionario de datos: CONAPO-MARG-001 (experimental)

Índice de marginación por localidad 2020 de CONAPO para Sonora. Fuente en estado `proposed`, rama
`exp/indice-marginacion`: no entra al pipeline ni a la tabla final.

- Fuente: CONAPO, Índice de marginación por localidad 2020, estimado con el Censo de Población y Vivienda 2020.
- Página: https://www.gob.mx/conapo/documentos/indices-de-marginacion-2020-284372
- Metodología: https://www.gob.mx/cms/uploads/attachment/file/835461/Indices_Coleccion_280623_localidad.pdf
- Descarga: https://conapo.segob.gob.mx/work/models/CONAPO/Datos_Abiertos/Localidad/IML_2020.zip
- Fecha de descarga: 14/11/2026
- Archivo crudo: `data/raw/conapo_iml2020_localidades.zip`, con `IML_2020.xls` (hojas `IML_2020_MICH-ZAC` e `IML_2020_LOC2viv`)
- Script: `src/health_data/processing/conapo_marg_001.py`
- Archivos procesados: `data/processed/conapo-marg-001_localidades.parquet` y `data/processed/conapo-marg-001_agregados_2viv.parquet`
- Generación en Bash: `PYTHONPATH=src python -m health_data.processing.conapo_marg_001`
- Generación en PowerShell: `$env:PYTHONPATH="src"; python -m health_data.processing.conapo_marg_001`
- Requiere `xlrd` (el crudo es un .xls de Excel 97-2003).

La unión con la tabla final se hace por cvegeo (`health_data.marginacion.unir_marginacion`), nunca por nombre.
El archivo escribe Alamos y Onavas sin acento.

## Cómo leer el índice

- **Método DP2: un índice MAYOR indica MENOR marginación.** `indice_marginacion` va de 2.15 a 26.18 en Sonora.
- `indice_marginacion_norm` (IMN_2020) es el mismo índice reescalado a 0–1 a escala nacional, en el mismo sentido.
  En el análisis se usa `marginacion_norm = 1 - indice_marginacion_norm`, para que mayor sea más marginación.
- `grado_marginacion` es la forma oficial de reportarlo. Los grados no se traslapan:

| Grado | Índice mínimo | Índice máximo |
|---|---|---|
| MUY BAJO | 23.03 | 26.18 |
| BAJO | 21.15 | 23.03 |
| MEDIO | 18.63 | 21.14 |
| ALTO | 15.54 | 18.61 |
| MUY ALTO | 2.15 | 15.36 |

## Selección de registros

- CONAPO solo calcula el índice de las localidades con **3 viviendas habitadas o más**.
- `conapo-marg-001_localidades.parquet`: 1,850 localidades de Sonora (ENT 26) en los 72 municipios, con 2,921,049
  habitantes (el 99.2 % de la población de la tabla final). Cubre 1,850 de sus 7,297 localidades.
- `conapo-marg-001_agregados_2viv.parquet`: 68 municipios con el agregado de sus localidades de 1 y 2 viviendas
  (clave de localidad 9999 en el crudo), con 21,491 habitantes. Los municipios 008, 024, 028 y 063 no tienen
  localidades de ese tamaño.

## Columnas de `conapo-marg-001_localidades.parquet`

| Columna | Tipo | Descripción | Valores posibles | Columna original |
|---|---|---|---|---|
| cvegeo | texto | Clave geográfica de 9 dígitos: entidad, municipio y localidad. | 1,850 claves únicas. Empieza con 26. | CVE_LOC |
| cve_ent | texto | Clave de la entidad. | 26 | ENT |
| cve_mun | texto | Clave del municipio. | 001 a 072 | MUN |
| cve_loc | texto | Clave de la localidad. | 4 dígitos | LOC |
| municipio | texto | Nombre del municipio, sin espacios sobrantes. | 72 nombres | NOM_MUN |
| localidad | texto | Nombre de la localidad, sin espacios sobrantes. Solo para mostrar. | Texto libre | NOM_LOC |
| poblacion | entero | Población total. | 3 a 855,563 | POB_TOT |
| pct_analfabeta_15_y_mas | decimal | % de población de 15 años o más analfabeta. | 0 a 100 | ANALF |
| pct_sin_educacion_basica_15_y_mas | decimal | % de población de 15 años o más sin educación básica. | 0 a 100 | SBASC |
| pct_ocupantes_sin_drenaje_ni_excusado | decimal | % de ocupantes en viviendas particulares habitadas sin drenaje ni excusado. | 0 a 100 | OVSDE |
| pct_ocupantes_sin_electricidad | decimal | % de ocupantes en viviendas sin energía eléctrica. | 0 a 100 | OVSEE |
| pct_ocupantes_sin_agua_entubada | decimal | % de ocupantes en viviendas sin agua entubada. | 0 a 100 | OVSAE |
| pct_ocupantes_piso_de_tierra | decimal | % de ocupantes en viviendas con piso de tierra. | 0 a 100 | OVPT |
| pct_ocupantes_con_hacinamiento | decimal | % de ocupantes en viviendas con hacinamiento. | 0 a 100 | OVHAC |
| pct_ocupantes_sin_refrigerador | decimal | % de ocupantes en viviendas sin refrigerador. | 0 a 100 | OVSREF |
| indice_marginacion | decimal | Índice de marginación (DP2). Mayor = menos marginación. | 2.15 a 26.18 | IM_2020 |
| indice_marginacion_norm | decimal | Índice normalizado 0–1, mismo sentido. | 0.08 a 1.00 | IMN_2020 |
| grado_marginacion | categoría ordenada | Grado de marginación, de menor a mayor. | MUY BAJO (749), BAJO (606), MEDIO (282), ALTO (126), MUY ALTO (87) | GM_2020 |

`conapo-marg-001_agregados_2viv.parquet` tiene las mismas columnas salvo `cvegeo`, `cve_loc` y `localidad`, una fila
por municipio. Grados: MUY BAJO (11), BAJO (35), MEDIO (15), ALTO (6), MUY ALTO (1).

## Columnas que agrega `unir_marginacion` a la tabla final

| Columna | Descripción |
|---|---|
| grado_marginacion | Grado de la localidad o, si no tiene índice propio, el del agregado de 1 y 2 viviendas de su municipio. |
| indice_marginacion_norm | IMN_2020 con el mismo criterio. |
| marginacion_norm | 1 - indice_marginacion_norm: mayor = más marginación. |
| marginacion_origen | `localidad` (1,850) o `agregado_municipal` (5,447). El agregado describe al conjunto de ranchos del municipio, no a cada uno. |
