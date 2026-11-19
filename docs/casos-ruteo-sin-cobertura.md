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

## Evidencia necesaria para cerrar los casos

La copia utilizada para integrar las fuentes complementarias no contiene la
caché SAKBÉ histórica. Su tabla reconstruida contiene estimaciones y no permite
identificar de forma fiable las 58 localidades históricas ni verificar sus
resultados individuales. Los totales anteriores son históricos, no un resultado
recalculado en esta copia.

Para cerrar el seguimiento se necesita recuperar la caché o tabla original con
identificadores y resultados de consulta, o volver a consultar SAKBÉ con una
credencial válida. Para cada localidad se debe registrar clave geográfica,
población, nivel afectado, fecha, resultado y motivo de la consulta, método de
respaldo y evidencia de revisión. Los casos sin carretera o sin conexión no deben
presentarse como rutas medidas; su cierre requiere justificar una alternativa
de transporte o mantener explícitamente la limitación.

Con los insumos y credenciales configurados, `make rutas` consulta SAKBÉ y puede
reanudarse al agotarse la cuota; `make data` reconstruye usando la caché local.
Antes de sustituir resultados existentes, conservar una copia y verificar los
recuentos, los métodos por nivel y las localidades excluidas. Las credenciales y
la caché no deben incluirse en el repositorio.
