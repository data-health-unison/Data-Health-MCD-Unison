1. Buscar fuente.
2. Revisar si ya existe en `catalog/datasets.csv`.
3. Si no existe, agregarla con `estado=propuesta` y su `responsable` (columnas en [catalog/README.md](../catalog/README.md)).
4. Otro integrante revisa la fuente.
5. Si sirve, cambiar `estado` a `aprobada`; si no, a `diferida` o `rechazada`, explicando por qué en `decision`.
6. Si se descarga, agregar en `config/fuentes_health.yaml` su enlace, el nombre del archivo y la descripción del archivo.
   Solo eso: nombre, estado y demás datos de la fuente van únicamente en el catálogo.
7. Descargar el archivo sin modificar a `data/raw/` con `make download FUENTE=<id_fuente>`.
8. La descarga queda registrada sola en `catalog/ingestions.csv`, con su huella SHA-256,
   y descrita en `references/fuentes_descargadas.md`. No se editan a mano.
