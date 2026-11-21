#!/bin/sh
set -eu

cd /project

if [ "${HEALTH_AUTO_PREPARE:-1}" = "1" ] && [ "${1:-}" = "streamlit" ]; then
    echo "==> Preparando datos del tablero"

    if [ ! -f data/interim/sakbe_cache.sqlite ]; then
        echo "ERROR: falta data/interim/sakbe_cache.sqlite" >&2
        echo "Coloque la caché SAKBÉ en esa ruta antes de iniciar Docker." >&2
        exit 1
    fi

    if [ ! -f data/processed/inegi-pop-001_localidades.parquet ] || \
       [ ! -f data/processed/salud-001_establecimientos.parquet ] || \
       [ ! -f data/processed/coneval-acc-001_localidades.parquet ]; then
        echo "==> Faltan tablas base; ejecutando pipeline"
        python -m health_data.pipeline
    fi

    for archivo in \
        data/processed/inegi-pop-001_localidades.parquet \
        data/processed/salud-001_establecimientos.parquet \
        data/processed/coneval-acc-001_localidades.parquet
    do
        if [ ! -f "$archivo" ]; then
            echo "ERROR: el pipeline no generó $archivo" >&2
            exit 1
        fi
    done

    echo "==> Reconstruyendo accesibilidad con la caché SAKBÉ"
    python -m health_data.processing.ruteo

    echo "==> Validando el corte de accesibilidad"
    python -m health_data.validacion

    echo "==> Generando reporte y padrón de calidad"
    python -m health_data.auditoria

    echo "==> Datos listos; iniciando tablero"
fi

exec "$@"
