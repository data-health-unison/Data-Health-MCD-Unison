PYTHON ?= $(shell which python3.12 2>/dev/null || which python3)
VENV   := .venv
PY     := $(VENV)/bin/python

.PHONY: help install venv data app test lint fmt clean clean-data \
        docker-build docker-app docker-data docker-test docker-lint \
        docker-shell docker-down

help:
	@echo "Comandos locales:"
	@echo "  make install       Crea el entorno e instala dependencias"
	@echo "  make data          Ejecuta el pipeline"
	@echo "  make app           Levanta el tablero Streamlit"
	@echo "  make test          Ejecuta las pruebas"
	@echo "  make lint          Revisa el código con Ruff"
	@echo "  make fmt           Corrige el código con Ruff"
	@echo ""
	@echo "Comandos Docker:"
	@echo "  make docker-build  Construye la imagen"
	@echo "  make docker-app    Levanta Streamlit"
	@echo "  make docker-data   Ejecuta el pipeline"
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

data: install
	PYTHONPATH=src $(PY) -m health_data.pipeline

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

clean-data:
	rm -rf data/raw/*
	rm -rf data/interim/*
	rm -rf data/processed/*

docker-build:
	docker compose build

docker-app:
	docker compose up --build app

docker-data:
	docker compose run --rm app python -m health_data.pipeline

docker-test:
	docker compose run --rm app python -m pytest tests/ -v

docker-lint:
	docker compose run --rm app ruff check src/ tests/ app.py

docker-shell:
	docker compose run --rm app bash

docker-down:
	docker compose down