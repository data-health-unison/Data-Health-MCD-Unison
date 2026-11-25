# Cambios

Cambios de cada versión del proyecto. El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y la numeración, el [versionado semántico](https://semver.org/lang/es/) adaptado a un proyecto de datos: qué
significa cada número y cómo se publica una versión está en [CONTRIBUTING.md](CONTRIBUTING.md#versiones).

Cada pull request agrega su línea en **Sin publicar**, en el apartado que le toca: *Agregado*, *Cambiado*,
*Corregido* o *Eliminado*. Si el cambio mueve las cifras, la línea dice cuánto.

## [Sin publicar]

### Agregado

- Versión del proyecto en un solo lugar (`src/health_data/__init__.py`), este CHANGELOG, las reglas de versión
  en `CONTRIBUTING.md` y la versión en el pie de la barra lateral del tablero.

### Cambiado

- `pyproject.toml` toma las dependencias de `requirements.txt`; antes declaraba solo `pandas` y `requests`.
- Catálogo de fuentes como fuente única: `catalog/datasets.csv` dice qué es cada fuente, su estado y su
  responsable, y `config/fuentes_health.yaml` solo cómo descargarla. Columnas de `datasets.csv` e
  `ingestions.csv`, y estados de las fuentes, en español.

## [0.1.0] - 2026-11-24

Línea base: el estado del proyecto cuando empezó a versionarse. Las cifras de esta versión son la referencia
para comparar las siguientes.

### Agregado

- **Fuentes:** ITER 2020 (INEGI-POP-001), establecimientos de salud CLUES (SALUD-001), Marco Geoestadístico 2025
  (INEGI-GEO-001), API de Ruteo SAKBÉ v3.1 (INEGI-ROUTE-001) y grado de accesibilidad a carretera pavimentada
  2020 de CONEVAL (CONEVAL-ACC-001), con su diccionario en `references/`.
- **Ingesta:** descarga con validación de los archivos y registro de cada descarga en `catalog/ingestions.csv`,
  con su huella SHA-256 (`make download FUENTE=...`).
- **Procesamiento:** limpieza de cada fuente, con revisión manual de coordenadas de CLUES (58 verificadas y 12
  fuera de operación) y exclusión de 3 localidades de la Isla del Tiburón sin acceso por carretera.
- **Ruteo:** cliente de SAKBÉ con rotación de tokens, caché y límite de 10,000 consultas por token. Respaldo con
  CONEVAL y estimación por línea recta recalibrada para las localidades sin ruta, y candidatos de respaldo
  cuando SAKBÉ no ubica a un establecimiento.
- **Análisis:** indicadores de acceso comprometido (más de 60 min a un centro de salud o más de 120 min a un
  hospital) y de grupos vulnerables, por municipio y por localidad
  (`notebooks/2.0-dd-analisis-accesibilidad.ipynb`).
- **Tablero** en Streamlit con seis vistas, y figuras PNG para presentaciones en `reports/figures/`.
- **Validación** de la tabla final (7 comprobaciones) y manifiesto de cada corrida del pipeline.
- **Convenciones** de ramas, commits y pull requests en `CONTRIBUTING.md`.

### Cifras de la línea base

Ruteo completo del 16 al 18 de octubre de 2026; tabla final con 7,297 localidades.

- 21,560 personas (0.73 % del estado) en 882 localidades, de 53 municipios, tienen acceso comprometido.
- 20,520 personas viven a más de 2 horas de un hospital y 9,822 a más de 3.
- Con un umbral de 90 min al hospital serían 39,835 personas; con 60 min, 99,333.

[Sin publicar]: https://github.com/data-health-unison/Data-Health-MCD-Unison/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/data-health-unison/Data-Health-MCD-Unison/releases/tag/v0.1.0
