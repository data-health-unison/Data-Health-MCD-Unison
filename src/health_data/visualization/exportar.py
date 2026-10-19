"""Exportación de figuras de Plotly a PNG con kaleido.

kaleido 0.2.1, la versión compatible con Plotly 5, falla en macOS y Linux si la ruta del
entorno tiene espacios (por ejemplo, "Proyectos MCD"): su lanzador hace ``cd $DIR`` y
``./bin/kaleido $@`` sin comillas. ``preparar_kaleido`` agrega solo esas comillas al lanzador
instalado. No hace nada si ya están o si kaleido no está instalado. En Windows kaleido usa
``kaleido.cmd``, que no tiene el problema.

Uso: se llama desde ``make install`` y al inicio del notebook de análisis.
"""

from __future__ import annotations

from pathlib import Path

CORRECCIONES = (
    ("cd $DIR\n", 'cd "$DIR"\n'),
    ("./bin/kaleido $@", './bin/kaleido "$@"'),
)


def _lanzador_instalado() -> Path | None:
    try:
        import kaleido
    except ImportError:
        return None
    return Path(kaleido.__file__).parent / "executable" / "kaleido"


def preparar_kaleido(lanzador: Path | None = None) -> bool:
    """Corrige el lanzador de kaleido para rutas con espacios. Devuelve True si quedó listo."""
    lanzador = lanzador or _lanzador_instalado()
    if lanzador is None:
        return False
    if not lanzador.exists():
        return True
    texto = lanzador.read_text()
    corregido = texto
    for viejo, nuevo in CORRECCIONES:
        corregido = corregido.replace(viejo, nuevo)
    if corregido != texto:
        lanzador.write_text(corregido)
    return True


if __name__ == "__main__":
    print("kaleido listo" if preparar_kaleido() else "kaleido no está instalado")
