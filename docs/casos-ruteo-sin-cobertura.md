# Cierre del ruteo SAKBÉ en Sonora

El corte de consultas SAKBÉ del 16 al 18 de octubre de 2026 se reprodujo
localmente con las 37,555 respuestas de `data/interim/sakbe_cache.sqlite`.
El ruteo se ejecutó en modo solo caché.

| Estado | Localidades | Habitantes de ITER 2020 |
| --- | ---: | ---: |
| Cobertura en ambos niveles | 7,239 | 2,944,583 |
| Cobertura parcial | 2 | 6 |
| Sin ruta en ambos niveles | 56 | 235 |
| Con consulta pendiente | 0 | 0 |
| Total analizado | 7,297 | 2,944,824 |

La cobertura en ambos niveles alcanza el 99.21 % de las localidades y el
99.99 % de la población analizada. El primer nivel tiene 7,095 rutas óptimas
y 144 trayectos locales aproximados usando tramos de SAKBÉ. El segundo nivel
tiene 7,241 rutas óptimas. SAKBÉ es el servicio de ruteo del INEGI.

Los 114 niveles afectados de 58 localidades (241 habitantes) tienen un
tiempo de respaldo CONEVAL. El respaldo se calcula con medianas de tiempos
de localidades de referencia. El indicador de primer nivel conserva la
regla de acotarse al tiempo al hospital si es menor, porque ese
establecimiento también brinda atención básica.

El ruteo excluye tres localidades de Isla del Tiburón sin acceso por
carretera (16 habitantes en total). Las claves `260302192`, `260303379` y
`260303436` están configuradas en
[fuentes_health.yaml](../config/fuentes_health.yaml) y la auditoría comprobó su
ausencia de la tabla final.

## Localidades sin ruta confirmada en algún nivel

«Origen sin tramo» indica que `buscalinea` no encontró un tramo cercano
a la localidad con las escalas probadas. «Candidatos sin ruta» indica
que no se obtuvo ruta hacia los establecimientos evaluados. La fecha es
la de la última respuesta sin resultado del nivel afectado, en la hora
local registrada por la caché. El padrón CSV conserva una fila por nivel
con su fecha y el tiempo imputado.

| Clave | Localidad | Municipio | Habitantes | Nivel afectado | Resultado en SAKBÉ | Fecha en caché |
| --- | --- | --- | ---: | --- | --- | --- |
| `260030032` | Barumico | Alamos | 2 | Ambos | Origen sin tramo | 2026-10-17 19:16:22 |
| `260030071` | La Concepción | Alamos | 3 | Ambos | Origen sin tramo | 2026-10-17 18:23:09 |
| `260030943` | La Cañada del Agua | Alamos | 1 | Ambos | Origen sin tramo | 2026-10-18 00:57:16 |
| `260040063` | San Carlos | Altar | 3 | Primer nivel | Candidatos sin ruta | 2026-10-18 18:58:29 |
| `260040071` | San Joaquín | Altar | 3 | Primer nivel | Candidatos sin ruta | 2026-10-18 18:58:52 |
| `260060342` | Pellacia | Arizpe | 2 | Ambos | Origen sin tramo | 2026-10-17 19:20:13 |
| `260120536` | San Benito (Delfino Angüis) | Bácum | 1 | Ambos | Origen sin tramo | 2026-10-18 01:03:53 |
| `260140153` | Ninguno | Baviácora | 1 | Ambos | Origen sin tramo | 2026-10-18 01:04:30 |
| `260200106` | La Reata | Carbó | 1 | Ambos | Origen sin tramo | 2026-10-18 01:28:23 |
| `260200201` | San Alfonso | Carbó | 4 | Ambos | Origen sin tramo | 2026-10-17 17:54:47 |
| `260200254` | Rancho Sesenta | Carbó | 11 | Ambos | Origen sin tramo | 2026-10-16 22:21:13 |
| `260290433` | El Rincón | Guaymas | 3 | Ambos | Origen sin tramo | 2026-10-17 18:44:24 |
| `260291402` | Los Pelones | Guaymas | 2 | Ambos | Origen sin tramo | 2026-10-18 00:13:55 |
| `260291693` | Sencuabampo | Guaymas | 3 | Ambos | Origen sin tramo | 2026-10-17 18:45:47 |
| `260303455` | El Salado | Hermosillo | 3 | Ambos | Origen sin tramo | 2026-10-17 18:50:04 |
| `260360454` | Lizárraga (La Galera) | Magdalena | 1 | Ambos | Origen sin tramo | 2026-10-18 01:52:29 |
| `260440108` | Bajío Largo | Onavas | 1 | Ambos | Origen sin tramo | 2026-10-18 02:00:33 |
| `260440123` | Las Piedras Bolas | Onavas | 1 | Ambos | Origen sin tramo | 2026-10-18 02:00:33 |
| `260440126` | Rancho Nuevo | Onavas | 4 | Ambos | Origen sin tramo | 2026-10-17 18:11:03 |
| `260450345` | Los Sauces | Opodepe | 2 | Ambos | Origen sin tramo | 2026-10-18 00:31:00 |
| `260460018` | San Pascual | Oquitoa | 3 | Ambos | Origen sin tramo | 2026-10-17 19:00:53 |
| `260470356` | Jesús Manuel Arellanez | Pitiquito | 1 | Ambos | Origen sin tramo | 2026-10-18 02:07:36 |
| `260470521` | Santa Rosalía | Pitiquito | 1 | Ambos | Origen sin tramo | 2026-10-18 02:08:58 |
| `260470522` | La Sierra | Pitiquito | 1 | Ambos | Origen sin tramo | 2026-10-18 02:08:58 |
| `260470525` | La Inmaculada [Carbonera] | Pitiquito | 1 | Ambos | Origen sin tramo | 2026-10-18 02:09:05 |
| `260490056` | El Maquipo | Quiriego | 1 | Ambos | Origen sin tramo | 2026-10-18 02:11:04 |
| `260490295` | NCPE la Laguna | Quiriego | 4 | Ambos | Origen sin tramo | 2026-10-17 18:12:46 |
| `260490319` | La Vinata | Quiriego | 1 | Ambos | Origen sin tramo | 2026-10-18 02:12:59 |
| `260490338` | El Frijolar | Quiriego | 23 | Ambos | Origen sin tramo | 2026-10-16 21:13:32 |
| `260490339` | El Puerto | Quiriego | 51 | Ambos | Origen sin tramo | 2026-10-16 20:55:46 |
| `260490344` | El Peñasco | Quiriego | 5 | Ambos | Origen sin tramo | 2026-10-17 17:32:30 |
| `260490350` | El Pino | Quiriego | 8 | Ambos | Origen sin tramo | 2026-10-16 22:44:59 |
| `260490354` | Basicorepa | Quiriego | 5 | Ambos | Origen sin tramo | 2026-10-17 17:32:30 |
| `260490383` | Burobampo | Quiriego | 2 | Ambos | Origen sin tramo | 2026-10-18 00:34:03 |
| `260490390` | Mesa las Escobas | Quiriego | 1 | Ambos | Origen sin tramo | 2026-10-18 02:13:35 |
| `260490399` | El Rincón de los Platanos | Quiriego | 16 | Ambos | Origen sin tramo | 2026-10-16 22:06:20 |
| `260510229` | La Ciénega | Rosario | 1 | Ambos | Origen sin tramo | 2026-10-18 02:14:39 |
| `260510736` | Alisoso | Rosario | 12 | Ambos | Origen sin tramo | 2026-10-16 22:18:37 |
| `260510793` | La Poza | Rosario | 4 | Ambos | Origen sin tramo | 2026-10-17 18:13:24 |
| `260510800` | Soledad | Rosario | 4 | Ambos | Origen sin tramo | 2026-10-17 18:13:25 |
| `260510810` | Vaniri | Rosario | 2 | Ambos | Origen sin tramo | 2026-10-18 00:36:11 |
| `260510906` | La Ciénega | Rosario | 3 | Ambos | Origen sin tramo | 2026-10-17 19:03:23 |
| `260510931` | El Nacimiento | Rosario | 2 | Ambos | Origen sin tramo | 2026-10-18 00:36:20 |
| `260520527` | Los Amoles | Sahuaripa | 2 | Ambos | Origen sin tramo | 2026-10-18 00:36:29 |
| `260570163` | Notechape | San Pedro de la Cueva | 2 | Ambos | Origen sin tramo | 2026-10-18 00:42:59 |
| `260570334` | Hierba del Manzo | San Pedro de la Cueva | 1 | Ambos | Origen sin tramo | 2026-10-18 02:23:07 |
| `260580198` | El Tule (El Cazadero) | Santa Ana | 2 | Ambos | Origen sin tramo | 2026-10-18 00:43:53 |
| `260660085` | Los Tanques | Ures | 5 | Ambos | Origen sin tramo | 2026-10-17 17:37:24 |
| `260660261` | El Carrizalito | Ures | 4 | Ambos | Origen sin tramo | 2026-10-17 18:18:49 |
| `260660280` | El Encinalito | Ures | 3 | Ambos | Origen sin tramo | 2026-10-17 19:11:52 |
| `260660306` | Los Peñascos | Ures | 3 | Ambos | Origen sin tramo | 2026-10-17 19:11:56 |
| `260660405` | El Injerto | Ures | 2 | Ambos | Origen sin tramo | 2026-10-18 00:48:53 |
| `260690302` | El Tule | Yécora | 6 | Ambos | Origen sin tramo | 2026-10-16 23:20:12 |
| `260690368` | Las Escobas | Yécora | 1 | Ambos | Origen sin tramo | 2026-10-18 02:31:44 |
| `260690553` | Los Corralitos | Yécora | 2 | Ambos | Origen sin tramo | 2026-10-18 00:50:54 |
| `260700084` | Campiña Dos | General Plutarco Elías Calles | 1 | Ambos | Origen sin tramo | 2026-10-18 02:32:26 |
| `260700222` | El Culichi | General Plutarco Elías Calles | 2 | Ambos | Origen sin tramo | 2026-10-18 00:51:44 |
| `260700223` | Las Peñitas del Juchuri | General Plutarco Elías Calles | 1 | Ambos | Origen sin tramo | 2026-10-18 02:32:39 |

## Reproducción y control de calidad

Desde el checkout que contiene los insumos procesados y la caché:

```powershell
$env:PYTHONPATH = "src"
python -m health_data.processing.ruteo
python -m health_data.validacion
python -m health_data.auditoria
```

La tabla conserva `primary_sakbe_*` y `secondary_sakbe_*` con estado,
motivo y fecha por nivel. El JSON en `data/processed/calidad/` incluye los
recuentos por localidad y nivel. El padrón del mismo directorio y la vista
**Calidad de datos** del tablero muestran los casos individuales. La caché
y los archivos procesados se mantienen locales.

## Validación del corte

- El validador de la tabla final pasó las nueve comprobaciones, incluidas
  las dos de trazabilidad por nivel.
- Se ejecutaron en Jupyter las libretas 2.0 y 3.0 a 3.3 con los insumos
  del corte. La libreta principal y el tablero coinciden en 882 localidades
  y 21,560 habitantes con acceso comprometido a alguno de los dos niveles,
  con los umbrales de 60 y 120 minutos.
- La vista de transporte y marginación y su libreta coinciden en 379
  localidades y 8,237 habitantes con tiempo hospitalario superior a 120
  minutos y sin transporte foráneo reportado.
- Se probaron las diez vistas del tablero con los datos locales. La vista
  **Calidad de datos** mostró las 114 filas del padrón, las fechas y los
  motivos por nivel. Se comprobó la descarga disponible y el filtro por
  municipio y método.
