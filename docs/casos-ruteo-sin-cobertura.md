# Casos de ruteo sin cobertura

## Resultado histórico y alcance

Según el resultado documentado el 18 de octubre de 2026, de 7,297 localidades
analizadas, 7,239 tenían rutas SAKBÉ para ambos niveles. En 56 localidades no se
encontró carretera cercana y en otras dos no se encontró ruta a los candidatos
de primer nivel. Estas 58 localidades sumaban 241 habitantes. Tres localidades
de Isla del Tiburón estaban excluidas del análisis por falta de acceso por carretera.

Los tiempos faltantes se rellenaron con el respaldo CONEVAL y, si este no está
disponible, con una estimación por línea recta. Son aproximaciones, no rutas
medidas. Los campos `routing_status`, `primary_method`, `secondary_method` y
`routing_consulted_at` permiten distinguir su procedencia. Una clasificación
`estimado` significa que no se dispone de una consulta, no que no exista ruta.

## Estado tras recuperar la caché

La caché histórica de SAKBÉ se recuperó localmente en
`data/interim/sakbe_cache.sqlite`. Contiene 37,555 respuestas y fue usada para
reconstruir `data/processed/accesibilidad_localidades.parquet` en modo solo
caché. La caché y los datos procesados permanecen ignorados por Git para no
publicar respuestas de la API ni resultados derivados pesados.

La reconstrucción conserva la procedencia por nivel en `primary_method`,
`secondary_method` y `routing_status`. El informe de calidad y el padrón
provisional deben regenerarse después de cada reconstrucción con:

```powershell
$env:PYTHONPATH = "src"
python -m health_data.processing.ruteo
python -m health_data.auditoria
```

## Evidencia necesaria para cerrar los casos

La caché permite verificar las respuestas históricas y distinguir una localidad
sin ruta de una localidad que aún no fue consultada. Para declarar cerrados los
casos individuales se debe generar el padrón desde la tabla reconstruida y
comprobar sus claves, nivel afectado, método y fecha de consulta. Los totales
publicados anteriormente deben sustituirse por los conteos del nuevo reporte.

Para cada localidad se debe registrar clave geográfica,
población, nivel afectado, fecha, resultado y motivo de la consulta, método de
respaldo y evidencia de revisión. Los casos sin carretera o sin conexión no deben
presentarse como rutas medidas; su cierre requiere justificar una alternativa
de transporte o mantener explícitamente la limitación.

Con los insumos y credenciales configurados, `make rutas` consulta SAKBÉ y puede
reanudarse al agotarse la cuota; `make data` reconstruye usando la caché local.
Antes de sustituir resultados existentes, conservar una copia y verificar los
recuentos, los métodos por nivel y las localidades excluidas. Las credenciales y
la caché no deben incluirse en el repositorio.
