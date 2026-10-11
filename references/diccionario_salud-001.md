# Diccionario de datos: SALUD-001

Establecimientos de salud de Sonora en operación, tomados del catálogo CLUES de la Secretaría de Salud. Una fila por establecimiento.

- Fuente: Secretaría de Salud, gobi.salud.gob.mx
- Descarga: https://gobi.salud.gob.mx/gobi/catalogos/catalogosmaestros/ESTABLECIMIENTO_SALUD_202608.xlsx?v=2026.09.23
- Fecha de descarga: 07/10/2026
- Archivo crudo: `data/raw/ESTABLECIMIENTO_SALUD_202608.xlsx`, hoja `CLUES_202608`
- Script: `src/health_data/processing/salud_001.py`
- Archivo procesado: `data/processed/salud-001_establecimientos.parquet`
- Generación en Bash: `PYTHONPATH=src python -m health_data.processing.salud_001`
- Generación en PowerShell: `$env:PYTHONPATH="src"; python -m health_data.processing.salud_001`

El nombre del archivo dice 202608, pero trae movimientos hasta el 22/09/2026.

## Selección de registros

- Sonora (clave de entidad 26) en operación: 943.
- Sin unidades móviles (tipologías P, UMM, X y HM): 929. En este corte, las 14 móviles son de tipología P.
- Las cifras cambian con cada descarga.

## Columnas

| Columna | Tipo | Descripción | Valores posibles | Columna original |
|---|---|---|---|---|
| clues | texto | Clave única del establecimiento: 5 letras (entidad e institución) y 6 dígitos. | Empieza con SR. Sin nulos ni repetidos. | CLUES |
| nombre_unidad | texto | Nombre de la unidad. | Texto libre. | NOMBRE DE LA UNIDAD |
| nombre_comercial | texto | Nombre comercial, por ejemplo la cadena de farmacias. | Texto libre. | NOMBRE COMERCIAL |
| clave_institucion | texto | Clave de la institución. | 12 valores. SMP es servicios médicos privados. | CLAVE DE LA INSTITUCION |
| institucion | texto | Institución a la que pertenece el establecimiento. | 12 valores. Los más comunes: SERVICIOS MEDICOS PRIVADOS (352), SERVICIOS DE SALUD IMSS BIENESTAR (272) y SECRETARIA DE SALUD (130). | NOMBRE DE LA INSTITUCION |
| sector | texto | Sector de la institución. | PUBLICO (577), PRIVADO (352). PRIVADO cuando clave_institucion es SMP. | Derivada de CLAVE DE LA INSTITUCION |
| institucion_administradora | texto | Quién administra el establecimiento. | 14 valores, por ejemplo FUNDACION BEST A. C. (201) y BENAVIDES (69). Nula en 82. | NOMBRE DE LA INS ADM |
| tipo_establecimiento | texto | Tipo de establecimiento. | DE CONSULTA EXTERNA (776), DE HOSPITALIZACION (101), DE APOYO (47), DE ASISTENCIA SOCIAL (5). | NOMBRE TIPO ESTABLECIMIENTO |
| tipologia | texto | Tipología del establecimiento. | 47 valores. La más común es CONSULTORIO ADYACENTE A FARMACIA (277). Nula en 85. | NOMBRE DE TIPOLOGIA |
| nivel_atencion | texto | Nivel de atención. | PRIMER NIVEL (768): consulta externa básica y prevención. SEGUNDO NIVEL (103): hospitales generales y clínicas de especialidades. TERCER NIVEL (6): alta especialidad. NO APLICA (52): sin atención médica directa. | NIVEL ATENCION |
| estrato | texto | Estrato de la unidad. | URBANO (704), RURAL (225). | ESTRATO UNIDAD |
| jurisdiccion | texto | Jurisdicción sanitaria. | HERMOSILLO, CABORCA, SANTA ANA, CIUDAD OBREGON, NAVOJOA, SAN LUIS RIO COLORADO. | JURISDICCION |
| cvegeo | texto | Clave geográfica de la localidad, de 9 dígitos: entidad, municipio y localidad. Sirve para unir con el ITER y el Marco Geoestadístico. | 316 localidades. Empieza con 26. | Derivada de las tres claves geográficas |
| cve_ent | texto | Clave de la entidad, 2 dígitos. | 26 | CLAVE DE LA ENTIDAD |
| cve_mun | texto | Clave del municipio, 3 dígitos. | 001 a 072 | CLAVE DEL MUNICIPIO |
| municipio | texto | Nombre del municipio. | 72 municipios. | MUNICIPIO |
| cve_loc | texto | Clave de la localidad, 4 dígitos. | Con ceros a la izquierda, por ejemplo 0001. | CLAVE DE LA LOCALIDAD |
| localidad | texto | Nombre de la localidad. | Texto libre. | LOCALIDAD |
| vialidad | texto | Calle. | Texto libre. Nula en 160. | VIALIDAD |
| numero_exterior | texto | Número exterior. | Texto libre. Nulo en 599. | NUMERO EXTERIOR |
| asentamiento | texto | Colonia o asentamiento. | Texto libre. | ASENTAMIENTO |
| codigo_postal | texto | Código postal, 5 dígitos. | 82100 a 85990. Nulo en 6. | CODIGO POSTAL |
| fecha_inicio_operacion | fecha | Fecha de inicio de operación. | 01/02/1950 a 10/06/2026. Nula en 7. | FECHA DE INICIO DE OPERACION |
| latitud | decimal | Latitud en grados decimales, solo si es válida. | 26.37 a 32.48. Nula en 67. | Derivada de LATITUD |
| longitud | decimal | Longitud en grados decimales, solo si es válida. | −115.00 a −108.59. Nula en 67. | Derivada de LONGITUD |
| fuente_coordenada | texto | Origen de latitud y longitud. | CLUES (862): viene del catálogo y cae en Sonora. INVALIDA (67): vacía (11) o fuera de Sonora (56). | Derivada de LATITUD y LONGITUD |
| latitud_original | decimal | Latitud tal como viene. Trae de 2 a 7 decimales. | Nula en 11. | LATITUD |
| longitud_original | decimal | Longitud tal como viene. | Nula en 11. | LONGITUD |
| observaciones | texto | Notas del registro sobre altas, bajas y traspasos. | Texto libre. Nula en 124. | OBSERVACIONES AL REGISTRO |
| comentarios_validacion | texto | Comentarios de la validación del registro. | Texto libre. Nulo en 447. | COMENTARIOS DE LA VALIDACION |

Los 8 establecimientos de especialidad sin hospitalización son los que tienen tipo DE CONSULTA EXTERNA y nivel SEGUNDO NIVEL.

## Reglas de limpieza

- Textos: sin espacios al inicio ni al final, y con un solo espacio entre palabras.
- Pasan a nulo: "NO ESPECIFICADO", "SIN NÚMERO", "SIN NUMERO", "S/N", "SIN NOMBRE", los textos vacíos y el código postal 99999.
- Categorías (sector, institucion, institucion_administradora, nivel_atencion, tipo_establecimiento, tipologia, estrato, jurisdiccion y fuente_coordenada): en mayúsculas, sin acentos (Á, É, Í, Ó, Ú y Ü) y con un solo espacio. La Ñ se conserva. Así un mismo valor no se parte en dos por cómo se escribió, como HOSPITALIZACIÓN y HOSPITALIZACION (ejemplo hipotético). En este corte ninguna categoría se unificó, pero cambió la escritura de 28 valores, por ejemplo DE HOSPITALIZACIÓN y CIUDAD OBREGÓN.
- Nombres y textos libres (nombre_unidad, nombre_comercial, municipio, localidad, vialidad, numero_exterior, asentamiento, observaciones y comentarios_validacion): como vienen, solo sin espacios sobrantes.
- Claves geográficas y código postal: texto con sus ceros a la izquierda.
- Coordenadas: válidas si caen en la caja de latitud 26.0 a 32.6 y longitud −115.2 a −108.3. La caja es aproximada, no el límite real del estado. Las originales quedan en latitud_original y longitud_original. Las inválidas se rellenarán después con las coordenadas del ITER.
- Columnas descartadas: RFC, teléfonos, unidad móvil, subtipología, estatus de operación (es constante), bajas, movimientos, obra e inmueble, entre otras.

## Reglas de calidad

Están en `tests/test_salud_001.py` y se omiten si falta el archivo procesado.

- CLUES únicas.
- Al menos un registro, y no más que los establecimientos de Sonora en operación del crudo (943 en este corte).
- cvegeo de 9 dígitos que empieza con 26.
- Coordenadas con fuente CLUES dentro de la caja de Sonora; las de fuente INVALIDA, vacías.
- Sin nulos en clues, cvegeo, cve_ent, cve_mun, cve_loc, municipio, localidad, institucion, sector, nivel_atencion, tipo_establecimiento y fuente_coordenada.
