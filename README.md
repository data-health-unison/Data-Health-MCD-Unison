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
- [x] Configuración de Docker y tablero Streamlit.
- [x] Catálogo de fuentes e ingesta configurable.
- [x] Limpieza y validación de ITER, CONEVAL y CLUES.
- [x] Dataset consolidado por localidad.
- [x] Cliente de la API SAKBÉ (token, caché, cuota y reintentos).
- [x] Integración de SAKBÉ en el cálculo de ruteo (consultas en curso).
- [ ] Validación de tiempos mediante rutas reales.

### API SAKBÉ

El cliente está en `src/health_data/ingestion/sakbe.py`. Requiere un token de
INEGI ([solicitarlo aquí](https://www.inegi.org.mx/servicios/Ruteo/)):

```bash
cp .env.example .env   #colocar SAKBE_TOKENS=<token1>,<token2>
docker compose run --rm app python -m health_data.ingestion.sakbe           #estado de cuota y caché
docker compose run --rm app python -m health_data.ingestion.sakbe --probar  #ruta de prueba
```

- Las respuestas se guardan en `data/interim/sakbe_cache.sqlite`; una consulta
  repetida (incluso si no hubo ruta) no vuelve a gastar cuota.
- Cada petición real se contabiliza por día y por token. Al llegar a
  `limite_diario` (`config/fuentes_health.yaml`, 2500 por omisión), o si el
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

Completar las ~7,300 localidades requiere unas 37,000 consultas (~5 días con 3
tokens). Mientras tanto, las localidades sin ruta conservan la estimación por
línea recta, factor de sinuosidad y velocidad promedio. La columna
`routing_status` indica el origen de cada fila:

| Valor | Significado |
|---|---|
| `ok` | Ambos niveles medidos con SAKBÉ |
| `parcial` | Solo un nivel medido con SAKBÉ |
| `sin_ruta` | SAKBÉ no encontró carretera o ruta; se usa la estimación |
| `estimado` | Aún no consultada; se usa la estimación |

`primary_method` y `secondary_method` indican `sakbe` o `estimado` por nivel, y
`routing_consulted_at` la fecha de consulta. La validación
`cobertura_ruteo_sakbe` exige al menos 70 % de localidades en `ok`.

## Alcance y limitaciones

El proyecto mide accesibilidad geográfica potencial. No mide costos, calidad, capacidad hospitalaria, disponibilidad de medicamentos, transporte público ni tiempos de espera.

## Equipo

Proyecto académico de la Maestría en Ciencia de Datos de la Universidad de Sonora.