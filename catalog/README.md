# Catálogo de fuentes

Dos archivos, cada uno con un papel distinto. Cada dato vive en un solo lugar:

| Archivo | Qué guarda | Quién lo edita |
|---|---|---|
| `datasets.csv` | Qué fuentes se evaluaron, su estado, su responsable y la decisión del equipo | El equipo, a mano |
| `ingestions.csv` | Cada descarga guardada en `data/raw`, con su huella SHA-256 | El script de descarga; no se edita a mano |
| `respaldos.csv` | Cada respaldo del caché de SAKBÉ, con su huella | `make respaldo-sakbe`; no se edita a mano |

Cómo se descarga cada fuente (enlace, nombre del archivo, token de la API) no está aquí, sino en
`config/fuentes_health.yaml`. Toda fuente de ese archivo debe estar antes en `datasets.csv`, y solo se descargan
las que aquí están `aprobada`. Las pruebas (`make test`) fallan si los dos archivos no cuadran.

El flujo para proponer una fuente nueva está en [docs/workflow.md](../docs/workflow.md).

## datasets.csv

Una fila por fuente, también las que se descartaron o se dejaron para después. Se guarda en UTF-8 con BOM
para que Excel respete los acentos.

| Columna | Qué lleva | Ejemplo |
|---|---|---|
| `id_fuente` | Clave única: institución, tema y número | `SALUD-001` |
| `nombre` | Nombre de la fuente | `Establecimientos de salud (CLUES)` |
| `descripcion` | Qué contiene | |
| `institucion` | Quién la publica | `INEGI` |
| `url_fuente` | Página de la fuente (no el enlace de descarga, que va en el YAML) | |
| `tipo_acceso` | `download` o `api` | `download` |
| `formato` | Formato de los datos | `CSV`, `XLSX`, `SHP`, `JSON` |
| `nivel_geografico` | Unidad de cada registro | `localidad`, `municipio`, `establecimiento` |
| `anio_inicio`, `anio_fin` | Años que cubren los datos; vacío si no aplica | `2020` |
| `responsable` | Integrante del equipo que lleva la fuente; si son varios, separados por `;` | `David; Victor` |
| `estado` | Ver la tabla de estados | `aprobada` |
| `notas` | Hallazgos y observaciones | |
| `prioridad` | `alta`, `media` o `baja` | `alta` |
| `version` | Edición publicada por la fuente: año, año-mes del corte o versión de la API | `2020`, `2026-08`, `v3.1` |
| `licencia` | Condiciones de uso | |
| `decision` | Por qué se aprobó, difirió o rechazó, y cómo se usa | |

### Estados

| Estado | Significado |
|---|---|
| `propuesta` | Alguien la encontró; falta que otro integrante la revise |
| `aprobada` | Se usa en el proyecto y se puede descargar |
| `diferida` | Sirve, pero no ahora; `decision` dice por qué |
| `rechazada` | No sirve para el proyecto; `decision` dice por qué |

## ingestions.csv

Lo llena el script de descarga, con una fila por archivo nuevo en `data/raw`:

```bash
make download FUENTE=SALUD-001
```

| Columna | Qué lleva |
|---|---|
| `id_ingesta` | `id_fuente` y fecha de la descarga, por ejemplo `SALUD-001_20261011T094740` |
| `id_fuente` | El mismo de `datasets.csv` |
| `fecha_descarga` | Fecha y hora de la descarga, con zona horaria |
| `ruta_crudo` | Ruta del archivo dentro del proyecto |
| `huella` | Huella SHA-256 del archivo, con el prefijo `sha256:` |
| `estado` | `ok` si el archivo pasó la validación |
| `notas` | Observaciones de la descarga; vacío si no hay |
| `url_descarga` | Enlace directo usado en la descarga (distinto de `url_fuente`, que lleva a la página de la fuente) |

## respaldos.csv

Lo llena `make respaldo-sakbe`, con una fila por respaldo distinto del anterior. El archivo comprimido no va en
git: se sube a la carpeta compartida del equipo. `make restaurar-sakbe` usa este registro para comprobar que
el archivo descargado esté intacto.

| Columna | Qué lleva |
|---|---|
| `id_respaldo` | `SAKBE_` y fecha del respaldo, por ejemplo `SAKBE_20261125T101500` |
| `fecha_respaldo` | Fecha y hora del respaldo, con zona horaria |
| `archivo` | Nombre del archivo comprimido (`sakbe_cache_<fecha>.sqlite.gz`) |
| `huella_archivo` | Huella SHA-256 del archivo comprimido |
| `huella_contenido` | Huella de las respuestas guardadas; es la que registra el manifiesto de cada corrida |
| `respuestas`, `exitosas` | Respuestas guardadas y cuántas traen ruta |
| `primera_consulta`, `ultima_consulta` | Fechas de la primera y la última consulta a SAKBÉ |
| `notas` | Observaciones; vacío si no hay |
