"""Pipeline principal de Data Health MCD Unison."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
INTERIM_DATA_DIR = PROJECT_ROOT / "data" / "interim"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"


def ensure_directories() -> None:
    """Crea los directorios de datos cuando no existen."""
    directories = [
        RAW_DATA_DIR,
        INTERIM_DATA_DIR,
        PROCESSED_DATA_DIR,
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)


def run_pipeline() -> None:
    """Ejecuta las etapas principales del pipeline."""
    ensure_directories()

    print("Data Health MCD Unison")
    print("Directorios del proyecto verificados.")
    print(f"Datos crudos: {RAW_DATA_DIR}")
    print(f"Datos intermedios: {INTERIM_DATA_DIR}")
    print(f"Datos procesados: {PROCESSED_DATA_DIR}")

    # Etapas futuras:
    # 1. Descargar o cargar fuentes.
    # 2. Validar los datos originales.
    # 3. Limpiar y transformar.
    # 4. Guardar resultados en Parquet.
    # 5. Calcular indicadores.


def main() -> None:
    """Punto de entrada del pipeline."""
    run_pipeline()


if __name__ == "__main__":
    main()