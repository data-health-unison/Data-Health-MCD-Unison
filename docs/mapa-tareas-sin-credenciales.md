# Mapa de tareas ejecutables sin SAKBÉ ni caché histórica

Este mapa separa el trabajo que puede cerrarse con los insumos versionados o
presentes localmente del trabajo que requiere una nueva consulta a SAKBÉ o la
recuperación de su caché. El objetivo es avanzar sin presentar estimaciones como
rutas observadas.

## Se puede ejecutar ahora

| Área | Tarea | Insumos locales | Entregable verificable |
| --- | --- | --- | --- |
| Inventario | Construir un reporte de cobertura por fuente, fecha, filas, claves y nulos | `data/raw`, `data/processed`, catálogo | reporte de calidad y tabla de cobertura |
| Validación | Ejecutar validaciones de esquema, rangos, duplicados, coordenadas y claves geográficas | procesados actuales y `src/health_data/validacion.py` | informe de validación reproducible |
| Ruteo | Revisar la consistencia de `routing_status`, `primary_method`, `secondary_method` y tiempos | tabla de accesibilidad local | lista de filas estimadas, CONEVAL y SAKBÉ |
| Ruteo | Generar un padrón provisional de localidades que requieren revisión, sin afirmar que sean las 58 históricas | población, accesibilidad, CONEVAL | CSV o Parquet de seguimiento con motivo y prioridad |
| Respaldo | Medir sensibilidad de los umbrales usando tiempos CONEVAL y estimaciones | accesibilidad y CONEVAL | comparación de escenarios y conteo de cambios de clasificación |
| Calidad | Revisar consistencia entre accesibilidad, RESLOC, marginación y establecimientos | procesados complementarios | reporte de coincidencias y claves sin correspondencia |
| EDA | Analizar los casos con mayor incertidumbre por municipio, población y marginación | accesibilidad, población, CONAPO | notebook o sección del EDA con prioridades |
| Tablero | Añadir una vista de calidad que distinga medido, CONEVAL y estimado | Streamlit y procesados | filtros, métricas y descarga del padrón |
| Pruebas | Añadir pruebas para conteos, métodos permitidos, exclusiones y no regresión | `tests/` | suite automatizada para los reportes |
| Documentación | Actualizar diccionario y limitaciones con fecha de corte y método | `references/`, `docs/` | documentación lista para revisión |

## Requiere SAKBÉ o su caché histórica

| Área | Tarea bloqueada | Evidencia necesaria para cerrarla |
| --- | --- | --- |
| Identificación | Confirmar cuáles son exactamente las 58 localidades históricas | tabla/caché con clave de localidad y resultados por nivel |
| Reconsulta | Intentar una ruta nueva para cada candidato y sus respaldos | token válido, fecha y respuesta de SAKBÉ |
| Diagnóstico | Distinguir sin carretera, sin línea, establecimiento no ubicable y error de servicio | respuestas y mensajes de cada consulta |
| Cierre | Cambiar `coneval` o `estimado` por `sakbe` cuando exista ruta | resultado de ruta persistido y validado |
| Cobertura | Recalcular el porcentaje `ok` y la población cubierta | tabla final reconstruida con la caché |

## Secuencia recomendada

1. Ejecutar inventario y validaciones sobre los archivos locales.
2. Generar el padrón provisional y el análisis de sensibilidad.
3. Incorporar la vista de calidad al tablero y cubrirla con pruebas.
4. Recuperar caché o configurar SAKBÉ.
5. Reconsultar únicamente el padrón priorizado, reconstruir la tabla y repetir
   validaciones y EDA.

Mientras no exista evidencia de una consulta, conservar el método original y
mostrarlo explícitamente en el tablero y en las exportaciones.
