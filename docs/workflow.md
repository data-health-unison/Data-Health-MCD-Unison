1. Buscar fuente.
2. Revisar si ya existe en catalog/datasets.csv.
3. Si no existe, agregarla con status=proposed.
4. Otro integrante revisa la fuente.
5. Si sirve, cambiar status a approved.
6. Ejecutar ingesta.
7. Descargar el archivo sin modificar a data/raw/ con `make download FUENTE=<dataset_id>`.
   La fuente debe estar en config/fuentes_health.yaml (URL, archivo y descripción).
8. La descarga queda registrada sola en catalog/ingestions.csv, con su huella SHA-256,
   y descrita en references/fuentes_descargadas.md. No se editan a mano.
