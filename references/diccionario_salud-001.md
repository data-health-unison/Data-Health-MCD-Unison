# Diccionario de datos: SALUD-001

Establecimientos de salud de Sonora en operación, tomados del catálogo CLUES de la Secretaría de Salud. Una fila por establecimiento.

- Fuente: Secretaría de Salud, gobi.salud.gob.mx
- Descarga: https://gobi.salud.gob.mx/gobi/catalogos/catalogosmaestros/ESTABLECIMIENTO_SALUD_202608.xlsx?v=2026.09.23
- Fecha de descarga: 07/10/2026
- Archivo crudo: `data/raw/ESTABLECIMIENTO_SALUD_202608.xlsx`, hoja `CLUES_202608`
- Revisión manual de coordenadas: `references/salud-001_coordenadas_verificadas.csv`, con las columnas clues, motivo, resultado, latitud, longitud y nota
- Script: `src/health_data/processing/salud_001.py`
- Archivo procesado: `data/processed/salud-001_establecimientos.parquet`
- Generación en Bash: `PYTHONPATH=src python -m health_data.processing.salud_001`
- Generación en PowerShell: `$env:PYTHONPATH="src"; python -m health_data.processing.salud_001`

El nombre del archivo dice 202608, pero trae movimientos hasta el 22/09/2026.

## Selección de registros

- Sonora (clave de entidad 26) en operación: 943.
- Sin unidades móviles (tipologías P, UMM, X y HM): 929. En este corte, las 14 móviles son de tipología P.
- Sin los 12 que, según la revisión del equipo, ya no operan aunque CLUES los marca en operación: 917.
- Las cifras cambian con cada descarga.

## Columnas

| Columna | Tipo | Descripción | Valores posibles | Columna original |
|---|---|---|---|---|
| clues | texto | Clave única del establecimiento: 5 letras (entidad e institución) y 6 dígitos. | Empieza con SR. Sin nulos ni repetidos. | CLUES |
| nombre_unidad | texto | Nombre de la unidad. | Texto libre. | NOMBRE DE LA UNIDAD |
| nombre_comercial | texto | Nombre comercial, por ejemplo la cadena de farmacias. | Texto libre. | NOMBRE COMERCIAL |
| clave_institucion | texto | Clave de la institución. | 12 valores. SMP es servicios médicos privados. | CLAVE DE LA INSTITUCION |
| institucion | texto | Institución a la que pertenece el establecimiento. | 12 valores. Los más comunes: SERVICIOS MEDICOS PRIVADOS (341), SERVICIOS DE SALUD IMSS BIENESTAR (272) y SECRETARIA DE SALUD (130). | NOMBRE DE LA INSTITUCION |
| sector | texto | Sector de la institución. | PUBLICO (576), PRIVADO (341). PRIVADO cuando clave_institucion es SMP. | Derivada de CLAVE DE LA INSTITUCION |
| institucion_administradora | texto | Quién administra el establecimiento. | 14 valores, por ejemplo FUNDACION BEST A. C. (196) y BENAVIDES (64). Nula en 81. | NOMBRE DE LA INS ADM |
| tipo_establecimiento | texto | Tipo de establecimiento. | DE CONSULTA EXTERNA (764), DE HOSPITALIZACION (101), DE APOYO (47), DE ASISTENCIA SOCIAL (5). | NOMBRE TIPO ESTABLECIMIENTO |
| tipologia | texto | Tipología del establecimiento. | 47 valores. La más común es CONSULTORIO ADYACENTE A FARMACIA (267). Nula en 83. | NOMBRE DE TIPOLOGIA |
| nivel_atencion | texto | Nivel de atención. | PRIMER NIVEL (756): consulta externa básica y prevención. SEGUNDO NIVEL (103): hospitales generales y clínicas de especialidades. TERCER NIVEL (6): alta especialidad. NO APLICA (52): sin atención médica directa. | NIVEL ATENCION |
| estrato | texto | Estrato de la unidad. | URBANO (692), RURAL (225). | ESTRATO UNIDAD |
| jurisdiccion | texto | Jurisdicción sanitaria. | HERMOSILLO, CABORCA, SANTA ANA, CIUDAD OBREGON, NAVOJOA, SAN LUIS RIO COLORADO. | JURISDICCION |
| cvegeo | texto | Clave geográfica de la localidad, de 9 dígitos: entidad, municipio y localidad. Sirve para unir con el ITER y el Marco Geoestadístico. | 316 localidades. Empieza con 26. | Derivada de las tres claves geográficas |
| cve_ent | texto | Clave de la entidad, 2 dígitos. | 26 | CLAVE DE LA ENTIDAD |
| cve_mun | texto | Clave del municipio, 3 dígitos. | 001 a 072 | CLAVE DEL MUNICIPIO |
| municipio | texto | Nombre del municipio. | 72 municipios. | MUNICIPIO |
| cve_loc | texto | Clave de la localidad, 4 dígitos. | Con ceros a la izquierda, por ejemplo 0001. | CLAVE DE LA LOCALIDAD |
| localidad | texto | Nombre de la localidad. | Texto libre. | LOCALIDAD |
| vialidad | texto | Calle. | Texto libre. Nula en 160. | VIALIDAD |
| numero_exterior | texto | Número exterior. | Texto libre. Nulo en 589. | NUMERO EXTERIOR |
| asentamiento | texto | Colonia o asentamiento. | Texto libre. | ASENTAMIENTO |
| codigo_postal | texto | Código postal, 5 dígitos. | 82100 a 85990. Nulo en 5. | CODIGO POSTAL |
| fecha_inicio_operacion | fecha | Fecha de inicio de operación. | 01/02/1950 a 10/06/2026. Nula en 7. | FECHA DE INICIO DE OPERACION |
| latitud | decimal | Latitud en grados decimales: la de CLUES si es válida, o la verificada por el equipo. | 26.37 a 32.48. Sin nulos. | Derivada de LATITUD y de la revisión manual |
| longitud | decimal | Longitud en grados decimales: la de CLUES si es válida, o la verificada por el equipo. | −115.00 a −108.59. Sin nulos. | Derivada de LONGITUD y de la revisión manual |
| fuente_coordenada | texto | Origen de latitud y longitud. | CLUES (859): viene del catálogo y cae en Sonora. VERIFICADA (58): revisada a mano por el equipo; la de CLUES estaba vacía (7), fuera de Sonora (50) o fuera de su municipio (1). INVALIDA (0): vacía o fuera de Sonora y sin revisión manual. | Derivada de LATITUD, LONGITUD y la revisión manual |
| latitud_original | decimal | Latitud tal como viene. Trae de 2 a 7 decimales. | Nula en 7. | LATITUD |
| longitud_original | decimal | Longitud tal como viene. | Nula en 7. | LONGITUD |
| observaciones | texto | Notas del registro sobre altas, bajas y traspasos. | Texto libre. Nula en 123. | OBSERVACIONES AL REGISTRO |
| comentarios_validacion | texto | Comentarios de la validación del registro. | Texto libre. Nulo en 435. | COMENTARIOS DE LA VALIDACION |

Los 8 establecimientos de especialidad sin hospitalización son los que tienen tipo DE CONSULTA EXTERNA y nivel SEGUNDO NIVEL.

## Reglas de limpieza

- Textos: sin espacios al inicio ni al final, y con un solo espacio entre palabras.
- Pasan a nulo: "NO ESPECIFICADO", "SIN NÚMERO", "SIN NUMERO", "S/N", "SIN NOMBRE", los textos vacíos y el código postal 99999.
- Categorías (sector, institucion, institucion_administradora, nivel_atencion, tipo_establecimiento, tipologia, estrato, jurisdiccion y fuente_coordenada): en mayúsculas, sin acentos (Á, É, Í, Ó, Ú y Ü) y con un solo espacio. La Ñ se conserva. Así un mismo valor no se parte en dos por cómo se escribió, como HOSPITALIZACIÓN y HOSPITALIZACION (ejemplo hipotético). En este corte ninguna categoría se unificó, pero cambió la escritura de 28 valores, por ejemplo DE HOSPITALIZACIÓN y CIUDAD OBREGÓN.
- Nombres y textos libres (nombre_unidad, nombre_comercial, municipio, localidad, vialidad, numero_exterior, asentamiento, observaciones y comentarios_validacion): como vienen, solo sin espacios sobrantes.
- Claves geográficas y código postal: texto con sus ceros a la izquierda.
- Coordenadas: válidas si caen en la caja de latitud 26.0 a 32.6 y longitud −115.2 a −108.3. La caja es aproximada, no el límite real del estado. Las originales quedan en latitud_original y longitud_original.
- Revisión manual: se quitan los establecimientos con resultado FUERA DE OPERACION. En los de resultado VERIFICADA, latitud y longitud se toman del archivo y fuente_coordenada vale VERIFICADA; latitud_original y longitud_original no cambian. Una coordenada inválida que no esté en el archivo sigue como INVALIDA.
- Si el archivo de revisión trae una CLUES que no está entre los establecimientos de Sonora en operación sin unidades móviles, el script se detiene con un error.
- Columnas descartadas: RFC, teléfonos, unidad móvil, subtipología, estatus de operación (es constante), bajas, movimientos, obra e inmueble, entre otras.

## Reglas de calidad

Están en `tests/test_salud_001.py` y se omiten si falta el archivo procesado.

- CLUES únicas.
- Al menos un registro, y no más que los establecimientos de Sonora en operación del crudo (943 en este corte).
- Ninguna CLUES con resultado FUERA DE OPERACION en la tabla, y todas las VERIFICADA presentes. El resultado solo puede ser VERIFICADA o FUERA DE OPERACION.
- cvegeo de 9 dígitos que empieza con 26.
- fuente_coordenada solo vale CLUES, VERIFICADA o INVALIDA.
- Coordenadas con fuente CLUES o VERIFICADA dentro de la caja de Sonora; las de fuente INVALIDA, vacías.
- Coordenadas VERIFICADA idénticas a las del archivo de revisión.
- latitud_original y longitud_original iguales a las del crudo.
- Sin nulos en clues, cvegeo, cve_ent, cve_mun, cve_loc, municipio, localidad, institucion, sector, nivel_atencion, tipo_establecimiento y fuente_coordenada.

## Preguntas sobre los datos

- ¿De dónde salen las coordenadas VERIFICADA? De una búsqueda manual en Google Maps que hizo el equipo el 13/10/2026, no de CLUES.
- ¿Por qué hay 917 y no 929? El equipo no encontró 12 establecimientos en Google Maps e indicó que ya no operan, aunque CLUES los marca en operación. Se quitan de la tabla.
- ¿cvegeo indica dónde está el establecimiento? No siempre: es la localidad que registra CLUES. Por ejemplo, la coordenada verificada de SRSMP001310 cae en Miguel Alemán (La Doce), pero CLUES lo registra en la ciudad de Hermosillo (cvegeo 260300001). Para ubicar un establecimiento conviene usar latitud y longitud.
