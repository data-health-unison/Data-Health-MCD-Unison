1. Buscar fuente.
2. Revisar si ya existe en catalog/datasets.csv.
3. Si no existe, agregarla con status=proposed.
4. Otro integrante revisa la fuente.
5. Si sirve, cambiar status a approved.
6. Ejecutar ingesta.
7. Descargar el archivo sin modificar a data/raw/ con `make download FUENTE=<dataset_id>`.
   La fuente debe estar en config/fuentes_health.yaml (URL, archivo y descripción).
8. La descarga queda registrada sola en catalog/ingestions.csv, con su huella SHA-256,
   y descrita en references/fuentes_descargadas.md. No se editan a mano.

## Fuentes complementarias para el EDA de accesibilidad

Con la imagen de Docker construida, estos comandos descargan los archivos originales
y preparan los dos insumos por localidad sin ejecutar el ruteo.

```powershell
docker compose run --rm app python -m health_data.ingestion.descarga INEGI-RESLOC-001
docker compose run --rm app python -m health_data.ingestion.descarga CONAPO-MARG-001
docker compose run --rm app python -m health_data.processing.inegi_resloc_001
docker compose run --rm app python -m health_data.processing.conapo_marg_001
```

| Fuente | Insumo preparado |
| --- | --- |
| Características de las Localidades de INEGI, Sonora 2020 | `data/processed/inegi-resloc-001_localidades.parquet`. Disponibilidad de transporte foráneo, medios que llegan a la cabecera, frecuencia y tiempo a la cabecera municipal. |
| Índice de Marginación por Localidad de CONAPO, 2020 | `data/processed/conapo-marg-001_localidades.parquet`. Grado e índice de marginación e indicadores de carencias sociodemográficas. |

Los dos Parquet usan `cvegeo`, la clave de localidad de nueve dígitos. Para el EDA,
el cruce con la tabla de accesibilidad se hace mediante `locality_id`. Para el número
de habitantes se usa ITER. Una localidad sin coincidencia en RESLOC tiene cobertura
desconocida, mientras que `transporte_foraneo = NO` indica ausencia de servicio reportada
por la fuente. Si falta una coincidencia en marginación, el grado se deja vacío.
El pipeline general también genera las dos tablas cuando dispone de los crudos.

Las otras dos descargas se ejecutan por separado.

```powershell
docker compose run --rm app python -m health_data.ingestion.descarga SONORA-URG-001
docker compose run --rm app python -m health_data.ingestion.descarga INEGI-RNC-001
```

`SONORA-URG-001` corresponde al archivo 2018–2022, con licencia de uso no comercial en la
ficha del recurso. El libro contiene registros de 17 municipios e incluye `CLUES`, mes,
año y `Total_Urgencias`.
Sirve para estudiar volumen de atención. Para estimar espera se necesitaría una fuente
con las horas de llegada y primera atención.
Su [diccionario](https://datos.sonora.gob.mx/dataset/318b9551-47a1-4e6b-a194-232ea5a08d43/resource/355da8aa-8544-4f32-b942-f54e007dd49b/download/diccionario-atencion-de-urgencias.csv)
documenta los campos para la revisión posterior.

`INEGI-RNC-001` guarda el ZIP nacional de la [Red Nacional de Caminos 2025](https://rnc.imt.mx/).
El GeoPackage está en `conjunto_de_datos/rnc2025.gpkg` dentro del ZIP. El recorte por región
y la preparación del ruteo se pueden hacer en el análisis posterior.

El [inventario SINERHIAS](https://sinba.salud.gob.mx/SSASINERHIAS) queda como propuesta
en el catálogo hasta conseguir un corte público reciente de recursos hospitalarios por CLUES.

## Libretas del EDA complementario

| Libreta | Insumos y análisis |
| --- | --- |
| [Accesibilidad, transporte y marginación](../notebooks/3.0-eda-accesibilidad-transporte-marginacion.ipynb) | Tabla de accesibilidad, RESLOC y CONAPO. Cobertura del cruce, doble barrera, mapa, ranking municipal y sensibilidad al umbral. |
| [Urgencias en Sonora](../notebooks/3.1-eda-urgencias-sonora.ipynb) | XLSX de urgencias y cruce con destinos hospitalarios si existe la tabla de accesibilidad. Serie mensual y rankings de unidades, municipios y diagnósticos. |
| [Red vial y acceso hospitalario](../notebooks/3.2-eda-red-vial-acceso-hospitalario.ipynb) | ZIP de la RNC, CLUES y tabla de accesibilidad. Grafo regional y simulación de cierre para Yécora. |

Para repetir las libretas, instala las dependencias del proyecto y las de Jupyter
en el mismo entorno de Python.

```powershell
python -m pip install -r requirements.txt jupyterlab matplotlib scipy
jupyter lab
```

La tabla de accesibilidad registra el método utilizado en cada localidad. Si la caché
de SAKBÉ no está disponible, el ruteo del proyecto puede generar tiempos estimados.
La libreta muestra la cobertura por método para interpretar sus resultados.
La primera ejecución de la libreta vial extrae el GeoPackage en `data/interim/`
y necesita unos 2.4 GB de espacio adicional.

En el tablero, **Transporte y marginación** usa el umbral hospitalario y el filtro municipal
de la barra lateral. **Urgencias** y **Red vial** leen los archivos que generan las últimas
celdas de las libretas 3.1 y 3.2 en `data/processed/`. Vuelve a ejecutar la libreta
correspondiente después de actualizar sus insumos.
