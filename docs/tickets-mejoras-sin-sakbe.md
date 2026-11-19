# Tickets de mejora ejecutables sin SAKBÉ

Estos tickets se pueden trabajar con los archivos locales y el código actual. No
modifican rutas históricas ni convierten estimaciones en mediciones.

## TICKET-DATA-001 — Reporte automatizado de calidad y cobertura

**Prioridad:** Alta  
**Objetivo:** producir un reporte único por fuente con filas, periodo, claves,
nulos, duplicados, coordenadas fuera de rango y cobertura territorial.

**Criterios de aceptación**

- El reporte incluye todas las fuentes de `data/raw` y `data/processed`.
- Cada fuente muestra fecha de corte, número de filas y porcentaje de claves válidas.
- Las reglas fallidas identifican archivo, columna y conteo afectado.
- Se puede regenerar con un comando documentado.

## TICKET-ROUTING-001 — Padrón de localidades con incertidumbre

**Prioridad:** Alta  
**Objetivo:** generar un padrón provisional de localidades cuyos tiempos no son
medidos con SAKBÉ.

**Criterios de aceptación**

- Incluye clave geográfica, municipio, población, nivel afectado, método,
  tiempo, categoría CONEVAL y motivo de revisión.
- Distingue `coneval`, `estimado`, `parcial`, `sin_ruta` y `ok`.
- Se etiqueta como padrón provisional y no como la lista histórica de 58 casos.
- Se exporta a un formato descargable desde el tablero.

## TICKET-ROUTING-002 — Análisis de sensibilidad de umbrales

**Prioridad:** Alta  
**Objetivo:** cuantificar cuánto cambia la clasificación de accesibilidad cuando
se comparan los tiempos disponibles y sus respaldos.

**Criterios de aceptación**

- Compara umbrales de 60 minutos para primer nivel y 120 para hospital.
- Reporta cambios por método, municipio y población afectada.
- Identifica localidades cercanas al umbral y las ordena por prioridad.
- Se incorpora a un notebook reproducible.

## TICKET-DASH-001 — Vista de calidad de datos en el tablero

**Prioridad:** Media  
**Objetivo:** mostrar al usuario qué parte del resultado es medida, imputada o
estimada.

**Criterios de aceptación**

- Incluye métricas por método y por nivel de atención.
- Permite filtrar municipio y método.
- Muestra una tabla descargable de localidades con incertidumbre.
- Incluye una nota visible con la fecha de corte y la limitación de SAKBÉ.

## TICKET-DATA-002 — Revisión de correspondencias entre fuentes

**Prioridad:** Media  
**Objetivo:** detectar localidades o establecimientos que no encuentran
correspondencia entre población, RESLOC, CONAPO, CONEVAL y salud.

**Criterios de aceptación**

- Reporta claves sin correspondencia en cada unión.
- Reporta duplicados y conflictos de municipio o coordenadas.
- Incluye conteos antes y después de cada unión.
- No elimina filas silenciosamente; cada exclusión queda registrada.

## TICKET-TEST-001 — Pruebas de regresión para calidad y cobertura

**Prioridad:** Media  
**Objetivo:** evitar que nuevas ingestas oculten problemas de cobertura o
procedencia de los tiempos.

**Criterios de aceptación**

- Valida métodos permitidos y estados de ruteo.
- Valida que las localidades excluidas no reaparezcan en el análisis.
- Valida rangos de tiempos, población y coordenadas.
- Valida que el tablero pueda cargar un dataset con métodos mezclados.

## Orden sugerido

Implementar primero `TICKET-DATA-001`, `TICKET-ROUTING-001` y
`TICKET-ROUTING-002`. Después integrar `TICKET-DASH-001` y cerrar con las
pruebas y la revisión de correspondencias.
