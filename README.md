# Accesibilidad a Servicios de Salud en Sonora

Proyecto de ciencia de datos para identificar localidades de Sonora con mayores tiempos de traslado por carretera hacia establecimientos de salud de primer y segundo nivel.

## Objetivo

Para cada localidad de Sonora se busca obtener:

- Establecimiento operativo de primer nivel más cercano.
- Distancia y tiempo de traslado al primer nivel.
- Establecimiento operativo de segundo nivel más cercano.
- Distancia y tiempo de traslado al segundo nivel.

Los resultados se relacionarán con población, edad, discapacidad, movilidad y disponibilidad de vehículo.

## Pregunta principal

> ¿Dónde se concentran las poblaciones de Sonora con menor accesibilidad geográfica a servicios de salud?

## Fuentes de datos

- **ITER 2020, INEGI:** población y características de las localidades.
- **CLUES, Secretaría de Salud:** ubicación, nivel y estado de los establecimientos.
- **Marco Geoestadístico, INEGI:** límites territoriales y validación de coordenadas.
- **SAKBÉ, INEGI:** distancias y tiempos de traslado por carretera.
- **GACP 2020, CONEVAL:** grado de aislamiento de las localidades; respaldo cuando SAKBÉ no encuentra ruta.

Cada fuente tiene su diccionario en `references/`. Las descargas quedan registradas, con su huella SHA-256, en
`catalog/ingestions.csv`, y descritas en `references/fuentes_descargadas.md`.

## Flujo de datos

```text
Fuentes
  ↓
data/raw        Datos originales
  ↓
data/interim    Datos limpios y validados
  ↓
Routing         Distancias y tiempos
  ↓
data/processed  Dataset final por localidad
  ↓
Streamlit       Mapas e indicadores
```

## Estructura

```text
Data-Health-MCD-Unison/
├── catalog/                 # Catálogo de fuentes
├── data/
│   ├── raw/                 # Datos originales
│   ├── interim/             # Datos limpios
│   └── processed/           # Datos finales
├── docs/                    # Documentación
├── notebooks/               # Exploración y análisis
├── reports/figures/         # Gráficas y mapas
├── src/health_data/
│   ├── ingestion/           # Descarga y lectura
│   ├── processing/          # Limpieza, validación y routing
│   └── visualization/       # Mapas y gráficas
├── tests/                   # Pruebas
├── app.py                   # Tablero Streamlit
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Tecnologías

- Python 3.12
- pandas y NumPy
- PyArrow y Parquet
- GeoPandas
- Plotly y Streamlit
- pytest y Ruff
- Docker y Docker Compose

No se utiliza Django ni PostgreSQL.

## Uso con Docker

### Construir la imagen

```powershell
docker compose build
```

### Ejecutar el pipeline

```powershell
docker compose run --rm app python -m health_data.pipeline
```

### Descargar una sola fuente

```powershell
make download FUENTE=SALUD-001          # local
make docker-download FUENTE=SALUD-001   # con Docker
```

La descarga se valida y queda registrada en `catalog/ingestions.csv`. Si el archivo ya existe, no se vuelve a
descargar; si su huella no coincide con la registrada, se detiene.

### Ejecutar las pruebas

```powershell
docker compose run --rm app python -m pytest tests -v
```

### Levantar el tablero

```powershell
docker compose up app
```

Abrir:

```text
http://localhost:8501
```

### Detener el proyecto

```powershell
docker compose down
```

## Resultados

Con el ruteo completo (18 de octubre de 2026). Una localidad tiene **acceso comprometido** si está a más de
60 min de un centro de salud o a más de 120 min de un hospital; los umbrales están en
`config/fuentes_health.yaml`.

- **21,567 personas (0.73 % del estado) en 883 localidades tienen acceso comprometido**, en 53 de los 72
  municipios.
- **La brecha está en el hospital.** El 99.45 % de la población vive a 30 min o menos de un centro de salud,
  pero 20,520 personas viven a más de 2 horas de un hospital y 9,822 a más de 3. El 85 % de las personas con
  acceso comprometido tiene un centro de salud cerca y el hospital lejos.
- **Se concentra en la sierra y en el desierto.** Yécora (4,793), Pitiquito (3,371), Sáric (2,042), Álamos
  (1,211) y Suaqui Grande (1,114) reúnen el 58 %. En Yécora, Suaqui Grande, Onavas y San Javier afecta a toda la
  población del municipio.
- **No son solo ranchos aislados.** 40 localidades de 100 habitantes o más tienen acceso comprometido, como
  Puerto Libertad (2,750 habitantes, 172 min al hospital), Yécora (2,453; 182 min) y Sásabe (977; 199 min).
- **Los grupos vulnerables están sobrerrepresentados.** Frente al 0.73 % de la población general, tiene acceso
  comprometido el 1.48 % de los hablantes de lengua indígena (el doble), el 1.09 % de quienes no tienen
  afiliación a servicios de salud, el 0.98 % de las personas de 60 años y más y el 0.91 % de las personas con
  discapacidad.
- **El resultado depende del umbral.** Con 90 min al hospital serían 39,840 personas; con 60 min, 99,333.

Dónde verlo:

- **Tablero:** `make app` (o `docker compose up app`) y abrir http://localhost:8501.
- **Análisis completo:** `notebooks/2.0-dd-analisis-accesibilidad.ipynb`.
- **Tabla final:** `data/processed/accesibilidad_localidades.parquet`, una fila por localidad (7,297) con el
  establecimiento de 1er y 2do nivel más cercano, la distancia y el tiempo a cada uno, el origen del tiempo y
  las variables de vulnerabilidad. Sus 34 columnas están descritas en
  `references/diccionario_accesibilidad_localidades.md`.

Fuente de los tiempos: INEGI, API de Ruteo SAKBÉ v3.1 (consultas del 16 al 18 de octubre de 2026). Son para
automóvil en condiciones óptimas.

## Estado

- [x] Problema y alcance definidos.
- [x] Estructura Cookiecutter Data Science.
- [x] Configuración de Docker y tablero Streamlit.
- [x] Catálogo de fuentes e ingesta configurable.
- [x] Limpieza y validación de ITER, CONEVAL y CLUES.
- [x] Dataset consolidado por localidad.
- [x] Cliente de la API SAKBÉ (token, caché, cuota y reintentos).
- [x] Integración de SAKBÉ en el cálculo de ruteo (completo: 7,213 de 7,297 localidades con ambos niveles medidos, el 99.99 % de la población).
- [x] Indicadores de accesibilidad y vulnerabilidad (`src/health_data/analisis.py` y `notebooks/2.0-dd-analisis-accesibilidad.ipynb`).
- [x] Revisión manual de coordenadas de CLUES (58 verificadas, 12 fuera de operación).
- [x] Registro de descargas con huella SHA-256 (`catalog/ingestions.csv`).
- [x] Validación de la estimación por línea recta y del respaldo CONEVAL contra las rutas reales.
- [x] Diccionario de la tabla final (`references/diccionario_accesibilidad_localidades.md`).
- [ ] Recalibrar la estimación por línea recta (solo se usa en localidades aún no consultadas).
- [ ] Tiempo dentro del establecimiento (espera y atención).

### API SAKBÉ

El cliente está en `src/health_data/ingestion/sakbe.py`. Requiere un token de
INEGI ([solicitarlo aquí](https://gaia.inegi.org.mx/sakbe_v3.1/genera_token.jsp)):

```bash
cp .env.example .env   #colocar SAKBE_TOKENS=<token1>,<token2>
docker compose run --rm app python -m health_data.ingestion.sakbe           #estado de cuota y caché
docker compose run --rm app python -m health_data.ingestion.sakbe --probar  #ruta de prueba
```

- Las respuestas se guardan en `data/interim/sakbe_cache.sqlite`; una consulta
  repetida (incluso si no hubo ruta) no vuelve a gastar cuota.
- Cada petición real se contabiliza por día y por token. Al llegar a
  `limite_diario` (`config/fuentes_health.yaml`, 10,000 por token), o si el
  servidor rechaza un token, el cliente pasa al siguiente. Cuando todos se
  agotan se detiene con `SakbeCuotaAgotada`.
- Cada ruta guarda su fecha de consulta (`consultado_en`), ya que la red se
  actualiza cada año.

### Estado actual del ruteo

Para cada localidad se eligen los **2 establecimientos más cercanos en línea
recta** por nivel de atención y se mide con SAKBÉ la ruta real por carretera a
cada uno; se conserva el de menor tiempo. Las localidades se procesan de mayor a
menor población.

```bash
make rutas         # consulta SAKBÉ hasta agotar la cuota del día; reanudable
make data          # reconstruye la tabla usando solo rutas en caché (sin gastar cuota)
```

El ruteo está completo (18 de octubre de 2026): 7,213 localidades tienen ambos
niveles medidos con SAKBÉ, 28 solo uno y 56 ninguno porque no tienen carretera
cercana. A esas 84 localidades (397 habitantes) se les asigna con CONEVAL el
nivel que falta (ver abajo). La estimación por línea recta solo queda para
localidades aún no consultadas. La columna `routing_status` indica el origen de
cada fila:

| Valor | Significado |
|---|---|
| `ok` | Ambos niveles medidos con SAKBÉ |
| `parcial` | Solo un nivel medido con SAKBÉ (SAKBÉ no ubica en su red a los candidatos del otro); el otro, con CONEVAL |
| `sin_ruta` | SAKBÉ no encontró carretera cercana; tiempo asignado con CONEVAL |
| `estimado` | Aún no consultada; se usa la estimación |

**Localidades excluidas.** Las 3 localidades de la Isla del Tiburón (16 habitantes) se excluyen del ruteo y
del análisis: no tienen acceso por carretera y parecen campamentos de pesca, no localidades permanentes. La
lista y el motivo están en `config/fuentes_health.yaml` (`localidades_excluidas`).

**Respaldo con CONEVAL.** A los niveles sin ruta SAKBÉ de las localidades `sin_ruta` y `parcial` se les
asigna la mediana del tiempo y la distancia medidos con SAKBÉ en las localidades del mismo municipio y con la
misma categoría de tiempo al centro de servicios de CONEVAL (si son menos de 5, la mediana estatal de esa
categoría). Validado contra las rutas reales excluyendo a cada localidad de su mediana: en localidades a 2 km
o más de carretera pavimentada acierta el lado del umbral en ~91 % (hospital, 120 min) y ~84 % (centro de
salud, 60 min), contra ~72 % de la estimación por línea recta, que subestima ~40 y ~17 min.

`primary_method` y `secondary_method` indican `sakbe`, `coneval` o `estimado` por nivel, y
`routing_consulted_at` la fecha de consulta. La validación
`cobertura_ruteo_sakbe` exige al menos 70 % de localidades en `ok`.

## Alcance y limitaciones

El proyecto mide accesibilidad geográfica potencial: el tiempo de traslado en automóvil en condiciones óptimas
al establecimiento más cercano. No mide costos, calidad, capacidad hospitalaria, disponibilidad de medicamentos,
transporte público ni el tiempo dentro del establecimiento (espera y atención), que se analizará después. Para
quien no tiene vehículo, el tiempo real es mayor.

Las 84 localidades sin ruta SAKBÉ en algún nivel (397 habitantes) usan un respaldo con CONEVAL, que es una
aproximación, y se excluyen 3 localidades de la Isla del Tiburón sin acceso por carretera. Los resultados
difundidos deben citar a INEGI y a la API de Ruteo, como piden sus condiciones de uso.

## Equipo

Proyecto académico de la Maestría en Ciencia de Datos de la Universidad de Sonora.
