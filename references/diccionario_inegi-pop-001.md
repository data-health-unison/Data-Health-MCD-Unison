# Diccionario de datos: INEGI-POP-001

Localidades de Sonora del Censo de Población y Vivienda 2020, tomadas del ITER de INEGI. Una fila por localidad.

- Fuente: INEGI, Censo de Población y Vivienda 2020, Principales resultados por localidad (ITER)
- Página: https://www.inegi.org.mx/app/scitel/Default?ev=9
- Descarga: https://www.inegi.org.mx/contenidos/programas/ccpv/iter/zip/iter2020/iter_26csv20.zip
- Descriptor: https://www.inegi.org.mx/app/scitel/doc/descriptor/fd_iter_cpv2020.pdf (cuarta edición, 2022)
- Fecha de descarga: 11/10/2026
- Archivo crudo: `data/raw/iter_26csv20.zip`, que trae `ITER_26CSV20.csv`
- Script: `src/health_data/processing/inegi_pop_001.py`
- Archivo procesado: `data/processed/inegi-pop-001_localidades.parquet`
- Generación en Bash: `PYTHONPATH=src python -m health_data.processing.inegi_pop_001`
- Generación en PowerShell: `$env:PYTHONPATH="src"; python -m health_data.processing.inegi_pop_001`

## Selección de registros

- El archivo trae 7,500 filas: 7,300 localidades y 200 de totales y acumulados. Se quitan los totales y acumulados, y se conservan todas las localidades, también las confidenciales y las no disponibles.
- Por disponibilidad: COMPLETA 1,853, CONFIDENCIAL 5,416 y NO DISPONIBLE 31.

## Columnas

| Columna | Tipo | Descripción | Valores posibles | Columna original | Denominador | Rol |
|---|---|---|---|---|---|---|
| cvegeo | texto | Clave geográfica de la localidad, de 9 dígitos: entidad, municipio y localidad. Sirve para unir con CLUES y el Marco Geoestadístico. | 7,300 claves únicas. Empieza con 26. | Derivada de ENTIDAD, MUN y LOC | | clave |
| cve_ent | texto | Clave de la entidad, 2 dígitos. | 26 | ENTIDAD | | clave |
| cve_mun | texto | Clave del municipio, 3 dígitos. | 001 a 072 | MUN | | clave |
| municipio | texto | Nombre del municipio. | 72 municipios. | NOM_MUN | | ubicación |
| cve_loc | texto | Clave de la localidad, 4 dígitos. | 0001 a 4133 | LOC | | clave |
| localidad | texto | Nombre de la localidad, sin espacios sobrantes. No sirve como llave. | Texto libre. | NOM_LOC | | ubicación |
| localidad_original | texto | Nombre de la localidad tal como viene. | Texto libre. Distinto de localidad en 8. | NOM_LOC | | ubicación |
| latitud | decimal | Latitud en grados decimales. | 26.31 a 32.49 | LATITUD | | ubicación |
| longitud | decimal | Longitud en grados decimales. | −115.02 a −108.48 | LONGITUD | | ubicación |
| tamano_localidad | entero | Rango de tamaño de la localidad según su población, del descriptor. | De 1 (1 a 249 habitantes) a 14 (1,000,000 o más). Hay del 1 al 13, sin el 8. | TAMLOC | | población |
| disponibilidad | texto | Si la localidad trae sus indicadores. | COMPLETA (1,853): los trae todos. CONFIDENCIAL (5,416): "*" en el crudo; localidades de 1 o 2 viviendas habitadas. NO DISPONIBLE (31): "N/D" en el crudo; no se pudieron censar. | Derivada de los conteos con "*" o "N/D" | | marca |
| vivienda_colectiva | booleano | Más de 10 personas por vivienda habitada. Señal de penales, campos agrícolas o lugares parecidos. | Verdadero en 48 localidades, con 8,138 personas. | Derivada de POBTOT y TVIVHAB | viviendas_habitadas | marca |
| poblacion_total | entero | Población total. | 1 a 855,563. Suma 2,944,840. | POBTOT | | población y denominador |
| poblacion_60_y_mas | entero | Personas de 60 años y más. | 0 a 97,155. Vacía en 5,447. | P_60YMAS | poblacion_total | indicador de vulnerabilidad demográfica |
| pct_60_y_mas | decimal | Porcentaje de personas de 60 años y más. | 0 a 100. Vacío en 5,447. | Derivada de P_60YMAS y POBTOT | poblacion_total | indicador de vulnerabilidad demográfica |
| poblacion_con_discapacidad | entero | Personas con discapacidad. | 0 a 37,201. Vacía en 5,447. | PCON_DISC | poblacion_total | indicador de vulnerabilidad demográfica |
| pct_con_discapacidad | decimal | Porcentaje de personas con discapacidad. | 0 a 66.67. Vacío en 5,447. | Derivada de PCON_DISC y POBTOT | poblacion_total | indicador de vulnerabilidad demográfica |
| poblacion_sin_afiliacion | entero | Personas sin afiliación a servicios de salud. | 0 a 141,866. Vacía en 5,447. | PSINDER | poblacion_total | indicador de vulnerabilidad demográfica |
| pct_sin_afiliacion | decimal | Porcentaje de personas sin afiliación a servicios de salud. | 0 a 100. Vacío en 5,447. | Derivada de PSINDER y POBTOT | poblacion_total | indicador de vulnerabilidad demográfica |
| poblacion_3_y_mas | entero | Personas de 3 años y más. | 3 a 822,892. Vacía en 5,447. | P_3YMAS | | denominador |
| poblacion_lengua_indigena | entero | Personas de 3 años y más que hablan una lengua indígena. | 0 a 4,012. Vacía en 5,447. | P3YM_HLI | poblacion_3_y_mas | indicador de vulnerabilidad demográfica |
| pct_lengua_indigena | decimal | Porcentaje de personas de 3 años y más que hablan una lengua indígena. | 0 a 100. Vacío en 5,447. | Derivada de P3YM_HLI y P_3YMAS | poblacion_3_y_mas | indicador de vulnerabilidad demográfica |
| viviendas_habitadas | entero | Viviendas particulares y colectivas habitadas. | 1 a 258,273. | TVIVHAB | | confidencialidad y vivienda colectiva |
| viviendas_con_caracteristicas | entero | Viviendas particulares habitadas a las que el censo les captó sus características; no incluye locales no construidos para habitación, viviendas móviles ni refugios. Es la base de los indicadores de vivienda. | 0 a 257,997. Vacía en 5,447. | VIVPARH_CV | | denominador |
| viviendas_sin_auto_ni_moto | entero | Viviendas particulares habitadas sin automóvil o camioneta, ni motocicleta o motoneta. | 0 a 73,109. Vacía en 5,447. | VPH_NDACMM | viviendas_con_caracteristicas | indicador de movilidad |
| pct_viviendas_sin_auto_ni_moto | decimal | Porcentaje de viviendas sin automóvil o camioneta, ni motocicleta o motoneta. | 0 a 100. Vacío en 5,450: 5,447 sin datos y 3 con viviendas_con_caracteristicas en 0. | Derivada de VPH_NDACMM y VIVPARH_CV | viviendas_con_caracteristicas | indicador de movilidad |

Los conteos vacíos (5,447) son las 5,416 localidades confidenciales y las 31 no disponibles.

## Reglas de limpieza

- Filas: se quitan los totales y acumulados (LOC 0000, 9998 y 9999). Quedan todas las localidades.
- Columnas: se conservan 17 de las 286 y se renombran con nombres descriptivos. El código del ITER está en "Columna original".
- Marcas: "*" y "N/D" pasan a vacío. La marca queda en disponibilidad.
- Conteos y tamaño de localidad: enteros que admiten vacíos.
- Coordenadas: de grados, minutos y segundos a grados decimales. La longitud queda negativa por estar al oeste.
- Nombres: localidad y municipio sin espacios al inicio ni al final, y con un solo espacio entre palabras. El nombre de la localidad tal como viene queda en localidad_original. No se corrigen acentos.
- Porcentajes: conteo entre su denominador por 100, sin redondear. Quedan vacíos si falta el conteo o si el denominador es 0.
- vivienda_colectiva: más de 10 personas por vivienda habitada. Solo es una marca; no cambia la población.
- No se aplica un mínimo de habitantes. Los porcentajes están en todas las localidades con indicadores.

## Reglas de calidad

Están en `tests/test_inegi_pop_001.py`. Si falta el archivo procesado se omiten todas; si falta el crudo, solo las que lo usan. No usan conteos fijos, como las 7,300 localidades: los toman del crudo.

- Las mismas localidades que el crudo sin totales ni acumulados.
- cvegeo única, de 9 dígitos, que empieza con 26 y une cve_ent, cve_mun y cve_loc.
- Los mismos municipios que los totales municipales del crudo.
- poblacion_total suma lo mismo que el POBTOT del total estatal.
- En cada municipio, poblacion_total suma lo mismo que el POBTOT de su total municipal.
- En el crudo, los conteos solo traen dígitos, "*" o "N/D". POBTOT y TVIVHAB solo traen dígitos.
- Ningún conteo es negativo.
- disponibilidad corresponde a la marca del crudo. Los conteos solo están vacíos si no es COMPLETA.
- Son CONFIDENCIAL exactamente las localidades con 1 o 2 viviendas habitadas.
- Ningún conteo pasa a su denominador.
- Los porcentajes van de 0 a 100 y son el conteo entre su denominador por 100. Solo están vacíos si falta el conteo o si el denominador es 0.
- Las coordenadas existen, caen en la caja de Sonora (latitud 26.0 a 32.6 y longitud −115.2 a −108.3) y no se repiten.
- poblacion_total cae dentro del rango de su tamano_localidad.
- vivienda_colectiva es verdadera justo en las localidades con más de 10 personas por vivienda habitada.
- localidad no tiene espacios al inicio, al final ni dobles, y solo cambia en espacios respecto a localidad_original.
- Sin nulos en cvegeo, cve_ent, cve_mun, cve_loc, municipio, localidad, localidad_original, latitud, longitud, tamano_localidad, poblacion_total, viviendas_habitadas, disponibilidad y vivienda_colectiva.

## Preguntas sobre los datos

Cada cifra dice de dónde sale: de la salida del script, de una sección del EDA (`notebooks/1.0-vh-eda-inegi-pop-001.ipynb`) o de la fila y las columnas del ITER.

### Qué queda fuera

- ¿Qué filas se quitan? Las 200 de totales y acumulados (salida del script). Son las filas del ITER con LOC 0000 (1 total estatal y 72 municipales), 9998 (68) y 9999 (59). Repiten a las localidades, así que no se pierde población.
- ¿Qué columnas no se conservan? 269: las 286 del ITER menos las 17 que renombra el script. Son temas que no responden la pregunta del proyecto, como sexo, educación, empleo, religión y servicios de la vivienda.
- ¿Dónde están los indicadores de las localidades confidenciales? Solo en las filas 9998 y 9999, sumados por municipio, y esas filas no se conservan. Son 4,578 localidades con una vivienda habitada y 838 con dos (EDA, sección 3; ITER, TVIVHAB igual a 1 o 2). En 16 de los 125 acumulados municipales también hay "*", porque suman menos de tres viviendas; ahí, 20 localidades con 49 personas no tienen indicadores ni sumados (ITER, filas 9998 y 9999 con "*").

### Qué significa un vacío

Un vacío no es cero: el dato no se publica o no se pudo captar. Tomarlo como cero hace ver a la localidad con 0 % en sus indicadores. Además, la suma de un conteo no da el total del estado, porque faltan las localidades sin indicadores.

- Conteo vacío en una localidad CONFIDENCIAL: el crudo traía "*". El censo no publica los indicadores de las localidades de una o dos viviendas, para proteger a quienes viven ahí. Son 5,416 localidades (salida del script).
- Conteo vacío en una localidad NO DISPONIBLE: el crudo traía "N/D". No se pudieron censar; solo hay una estimación de su población y sus viviendas. Son 31 localidades (salida del script) con 658 personas, 30 en Hermosillo y 1 en Guaymas (EDA, sección 5).
- Porcentaje vacío con su conteo presente: el denominador es 0. Pasa en 3 localidades con viviendas_con_caracteristicas en 0 (salida del script).

### Interpretaciones equivocadas posibles

- Porcentajes de localidades muy chicas: con pocos habitantes, una persona cambia mucho el valor. Las localidades con indicadores y 50 habitantes o más reúnen el 98.6 % de la población (EDA, sección 10: suma de POBTOT de esas localidades entre el POBTOT del total estatal). No se aplica ese mínimo porque el equipo aún no lo aprueba.
- Porcentaje de un grupo de localidades: el conteo y el denominador se suman solo en las localidades COMPLETA. poblacion_total viene en todas, así que sumar también la de las localidades sin indicadores baja el porcentaje. En las localidades de menos de 250 habitantes, el 19.9 % de la población vive en localidades sin indicadores, y el porcentaje de 60 años y más bajaría de 17.7 % a 14.2 % (ITER, POBTOT y P_60YMAS de las localidades con TAMLOC 1).
- pct_sin_afiliacion no se mide solo sobre quienes respondieron. El denominador es la población total, que incluye a 5,634 personas que no dijeron si están afiliadas (total estatal: POBTOT − PSINDER − PDER_SS).
- pct_lengua_indigena mide hablantes, no población indígena. En el estado hay 62,808 hablantes de 3 años y más y 126,644 personas en hogares indígenas, que son los hogares donde la persona de referencia, su cónyuge o alguno de sus ascendientes habla una lengua indígena (total estatal: P3YM_HLI y PHOG_IND).
- vivienda_colectiva es una aproximación propia, no una clasificación del censo. La tienen 48 localidades (salida del script; EDA, sección 11).
- La población de las localidades NO DISPONIBLE es una estimación, no un conteo.
- Las coordenadas son un punto, no el área de la localidad. La ciudad de Hermosillo, con 855,563 habitantes, es un solo punto (ITER, POBTOT de MUN 030 y LOC 0001).
- Los datos son de 2020; no reflejan cambios posteriores en la población, la afiliación ni los vehículos de las viviendas.
- El nombre no identifica a la localidad: 62 se llaman "Ninguno" y 605 comparten nombre con otra del mismo municipio (ITER, NOM_LOC dentro de cada MUN; EDA, sección 11). Por eso la llave es cvegeo.

### Errores y descuadres de la fuente

- 8 nombres de localidad traen espacios dobles (salida del script). Se corrigen en localidad; el nombre tal como viene queda en localidad_original.
- "Niños Heroés" trae el acento mal puesto, en 1 localidad (ITER, NOM_LOC; cvegeo 260303047). No se corrige.
- En Hermosillo, las personas de 60 años y más del total municipal (104,402) son 1 más que la suma de sus localidades (104,005) y sus acumulados (280 y 116). No tiene causa clara y no afecta la tabla, que no usa totales (ITER, MUN 030, P_60YMAS en las filas LOC 0000, 9998 y 9999 contra la suma de las localidades; EDA, sección 3).
