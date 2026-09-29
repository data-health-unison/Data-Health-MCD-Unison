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
- Plotly y Streamlit
- pytest y Ruff
- Docker y Docker Compose

No se utiliza Django, PostgreSQL, GeoPandas ni Shapely.

## Uso con Docker

### Construir la imagen

```powershell
docker compose build
```

### Ejecutar el pipeline

```powershell
docker compose run --rm app python -m health_data.pipeline
```

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
nearest_primary_clues
primary_distance_km
primary_time_min
nearest_secondary_clues
secondary_distance_km
secondary_time_min
routing_status
```

## Estado

- [x] Problema y alcance definidos.
- [x] Estructura Cookiecutter Data Science.
- [x] Configuración inicial de Docker.
- [ ] Catálogo de fuentes.
- [ ] Ingesta de datos.
- [ ] Limpieza y validación.
- [ ] Integración con SAKBÉ.
- [ ] Dataset final.
- [ ] Dashboard.

## Alcance y limitaciones

El proyecto mide accesibilidad geográfica potencial. No mide costos, calidad, capacidad hospitalaria, disponibilidad de medicamentos, transporte público ni tiempos de espera.

## Equipo

Proyecto académico de la Maestría en Ciencia de Datos de la Universidad de Sonora.