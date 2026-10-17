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

Por defecto el pipeline genera estimaciones exploratorias, identificadas como
`routing_method=estimated`; no las presenta como cobertura SAKBÉ.

Para solicitar rutas reales, define el token de INEGI solo en la sesión actual
de PowerShell y elige SAKBÉ explícitamente:

```powershell
$env:SAKBE_TOKEN = "<token de INEGI>"
docker compose run --rm app python -m health_data.pipeline --ruteo sakbe
```

El cliente sigue la API documentada de INEGI (`buscalinea` y `optima` para
automóvil), registra las consultas diarias en una caché SQLite local bajo
`data/interim/` y respeta el límite diario configurado. Si se agota la cuota,
conserva los resultados obtenidos y marca las rutas pendientes; vuelve a
ejecutar el comando en otro día para continuar usando la caché. Los errores no
se sustituyen por tiempos estimados.

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

## Resultado esperado

El dataset final tendrá una fila por localidad e incluirá, como mínimo:

```text
locality_id
locality_name
municipality_name
population
latitude
longitude
primary_candidate_clues
primary_distance_km
primary_time_min
secondary_candidate_clues
secondary_distance_km
secondary_time_min
routing_status
```

Los estados globales son `estimated`, `sakbe_ok`, `partial`, `no_route`,
`api_error` y `quota_exceeded`; cada nivel conserva además su propio estado.
Los CLUES se guardan como candidatos geodésicos (`*_candidate_clues`), no se
afirman como el establecimiento de menor tiempo por carretera: SAKBÉ calcula
la ruta únicamente hasta ese candidato.

## Estado

- [x] Problema y alcance definidos.
- [x] Estructura Cookiecutter Data Science.
- [x] Configuración de Docker y tablero Streamlit.
- [x] Catálogo de fuentes e ingesta configurable.
- [x] Limpieza y validación de ITER, CONEVAL y CLUES.
- [x] Dataset consolidado por localidad.
- [x] Integración configurable con SAKBÉ y control local de cuota/caché.
- [ ] Validación de tiempos mediante rutas reales.

### Estado actual del ruteo

En modo `estimated`, se escoge el candidato por distancia geodésica y se calcula
una aproximación con factor de sinuosidad y velocidad promedio por tramo. En
modo `sakbe`, se consulta la API para ese candidato y se conservan por separado
la distancia y el tiempo devueltos para cada nivel. La selección del candidato
continúa siendo geodésica, por lo que todavía debe validarse si corresponde al
establecimiento con menor tiempo real de viaje. No se ejecuta SAKBÉ sin una
solicitud explícita y un token de INEGI.

## Alcance y limitaciones

El proyecto mide accesibilidad geográfica potencial. No mide costos, calidad, capacidad hospitalaria, disponibilidad de medicamentos, transporte público ni tiempos de espera.

## Equipo

Proyecto académico de la Maestría en Ciencia de Datos de la Universidad de Sonora.