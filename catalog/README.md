# Como usar datasets.csv

Si encuentras un dataset, recopila la siguiente informacion:

dataset_id
name,
description,
source,
source_url,
access_type,
format,
geographic_level,
start_year,
end_year,
owner,
status : {proposed, approved, rejected}
notes

Se manejaran este tipo de estados para el dataset encontrado

Ejemplo:

INEGI-001
Población por municipio
Población total desagregada por municipio
INEGI
https://...
download
CSV
municipio
2020
2020
NULL
David
proposed
NULL
NULL
Datos del Censo 2020

Una vez tengas esta información recopilada, agrégala al datasets.csv en este formato:

 - dataset_id,name,description,source,source_url,access_type,format,geographic_level,start_year,end_year,owner,status,notes

# Como usar ingestions.csv

Lo llena el script de descarga, una fila por archivo guardado en data/raw:

make download FUENTE=SALUD-001

No se edita a mano. Columnas:

ingestion_id: dataset_id y fecha de descarga, por ejemplo SALUD-001_20261011T085529
dataset_id: el mismo de datasets.csv
retrieved_at: fecha y hora de la descarga, con zona horaria
raw_path: ruta del archivo dentro del proyecto
checksum: huella SHA-256 del archivo, con el prefijo sha256:
status: ok si el archivo paso la validacion
notes: observaciones de la descarga, vacio si no hay
download_url: enlace directo usado en la descarga. Es distinto del source_url de datasets.csv, que lleva a la pagina de la fuente
