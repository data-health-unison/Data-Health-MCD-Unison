PYTHON ?= $(shell which python3.12 2>/dev/null || which python3)
VENV   := .venv
PY     := $(VENV)/bin/python

.PHONY: help install venv data reprocesar rutas download respaldo-sakbe restaurar-sakbe app test lint fmt clean clean-data \
        docker-build docker-app docker-data docker-reprocesar docker-rutas docker-download docker-respaldo-sakbe \
        docker-restaurar-sakbe docker-test docker-lint \
        docker-shell docker-down

help:
	@echo "Comandos locales:"
	@echo "  make install       Crea el entorno e instala dependencias"
	@echo "  make data          Ejecuta el pipeline"
	@echo "  make reprocesar    Ejecuta el pipeline regenerando lo procesado (sin descargar)"
	@echo "  make rutas         Consulta SAKBÉ (gasta cuota; reanudable)"
	@echo "  make download      Descarga una fuente (FUENTE=SALUD-001)"
	@echo "  make respaldo-sakbe  Respalda el caché de SAKBÉ en data/respaldos/"
	@echo "  make restaurar-sakbe Restaura un respaldo (ARCHIVO=ruta/al/respaldo.sqlite.gz)"
	@echo "  make app           Levanta el tablero Streamlit"
	@echo "  make test          Ejecuta las pruebas"
	@echo "  make lint          Revisa el código con Ruff"
	@echo "  make fmt           Corrige el código con Ruff"
	@echo ""
	@echo "Comandos Docker:"
	@echo "  make docker-build  Construye la imagen"
	@echo "  make docker-app    Levanta Streamlit"
	@echo "  make docker-data   Ejecuta el pipeline"
	@echo "  make docker-reprocesar Ejecuta el pipeline regenerando lo procesado"
	@echo "  make docker-rutas  Consulta SAKBÉ"
	@echo "  make docker-download Descarga una fuente (FUENTE=SALUD-001)"
	@echo "  make docker-respaldo-sakbe  Respalda el caché de SAKBÉ"
	@echo "  make docker-restaurar-sakbe Restaura un respaldo (ARCHIVO=...)"
	@echo "  make docker-test   Ejecuta las pruebas"
	@echo "  make docker-lint   Revisa el código"
	@echo "  make docker-shell  Abre una terminal"
	@echo "  make docker-down   Detiene el contenedor"

venv:
	@if [ ! -x "$(PY)" ]; then \
		echo "Creando entorno virtual con $(PYTHON)"; \
		$(PYTHON) -m venv $(VENV); \
	fi

install: venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r requirements.txt
	PYTHONPATH=src $(PY) -m health_data.visualization.exportar

data: install
	PYTHONPATH=src $(PY) -m health_data.pipeline

reprocesar: install
	PYTHONPATH=src $(PY) -m health_data.pipeline --reprocesar

rutas: install
	PYTHONPATH=src $(PY) -m health_data.processing.ruteo --sakbe

download: install
	PYTHONPATH=src $(PY) -m health_data.ingestion.descarga $(FUENTE)

respaldo-sakbe: install
	PYTHONPATH=src $(PY) -m health_data.ingestion.respaldo_sakbe respaldar

restaurar-sakbe: install
	PYTHONPATH=src $(PY) -m health_data.ingestion.respaldo_sakbe restaurar "$(ARCHIVO)" $(if $(FORZAR),--forzar)

app: install
	PYTHONPATH=src $(VENV)/bin/streamlit run app.py

test: install
	PYTHONPATH=src $(PY) -m pytest tests/ -v

lint: install
	$(VENV)/bin/ruff check src/ tests/ app.py

fmt: install
	$(VENV)/bin/ruff check --fix src/ tests/ app.py
	$(VENV)/bin/ruff format src/ tests/ app.py

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache
	find . -type d -name .ipynb_checkpoints -prune -exec rm -rf {} + 2>/dev/null || true

# Conserva el caché de SAKBÉ (días de cuota) y los respaldos; esos se borran a mano si de verdad se quiere
clean-data:
	rm -rf data/raw/*
	find data/interim -mindepth 1 ! -name .gitkeep ! -name 'sakbe_cache*.sqlite' -exec rm -rf {} +
	rm -rf data/processed/*
	@echo "Se conservaron el caché de SAKBÉ (data/interim/sakbe_cache.sqlite) y data/respaldos/."

docker-build:
	docker compose build

docker-rutas:
	docker compose run --rm app python -m health_data.processing.ruteo --sakbe

docker-app:
	docker compose up --build app

docker-data:
	docker compose run --rm app python -m health_data.pipeline

docker-reprocesar:
	docker compose run --rm app python -m health_data.pipeline --reprocesar

docker-download:
	docker compose run --rm app python -m health_data.ingestion.descarga $(FUENTE)

docker-respaldo-sakbe:
	docker compose run --rm app python -m health_data.ingestion.respaldo_sakbe respaldar

docker-restaurar-sakbe:
	docker compose run --rm app python -m health_data.ingestion.respaldo_sakbe restaurar "$(ARCHIVO)" $(if $(FORZAR),--forzar)

docker-test:
	docker compose run --rm app python -m pytest tests/ -v

docker-lint:
	docker compose run --rm app ruff check src/ tests/ app.py

docker-shell:
	docker compose run --rm app bash

docker-down:
	docker compose down