"""Pruebas de la configuración central de Data Health."""

from pathlib import Path

import pytest

from health_data.config import (
    ARCHIVO_CATALOGO,
    ESTADO_APROBADA,
    ESTADOS_FUENTE,
    PROCESSED_DATA_DIR,
    RAW_DATA_DIR,
    cargar_configuracion,
    ensure_directories,
    leer_catalogo,
)

ENCABEZADO_CATALOGO = (
    "id_fuente,nombre,descripcion,institucion,url_fuente,tipo_acceso,formato,nivel_geografico,"
    "anio_inicio,anio_fin,responsable,estado,notas,prioridad,version,licencia,decision"
)


def escribir_catalogo(ruta: Path, *filas: str) -> Path:
    """Catálogo de prueba con el encabezado real; cada fila es ``id,nombre,estado``."""
    lineas = [ENCABEZADO_CATALOGO]
    for fila in filas:
        id_fuente, nombre, estado = fila.split(",")
        lineas.append(f"{id_fuente},{nombre},,INEGI,,download,CSV,localidad,,,David,{estado},,alta,2020,,")
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8-sig")
    return ruta


def escribir_yaml(ruta: Path, *ids: str) -> Path:
    """Configuración de prueba con una descarga por fuente."""
    fuentes = "".join(f"  {i}:\n    url: https://example.org/{i}.zip\n    nombre_archivo: {i}.zip\n" for i in ids)
    ruta.write_text(f"fuentes:\n{fuentes}", encoding="utf-8")
    return ruta


def test_ensure_directories() -> None:
    """Verifica que los directorios se creen sin error."""
    ensure_directories()
    assert RAW_DATA_DIR.exists()
    assert PROCESSED_DATA_DIR.exists()


def test_cargar_configuracion() -> None:
    """Comprueba la carga del catálogo, de fuentes_health.yaml y de los umbrales."""
    cfg = cargar_configuracion()
    assert cfg.umbrales.tiempo_critico_min == 60
    assert cfg.umbrales.tiempo_muy_critico_min == 120
    fuente = cfg.fuente("CONEVAL-ACC-001")
    assert fuente.estado == ESTADO_APROBADA
    assert fuente.responsable == "Victor"
    assert fuente.descargable


def test_localidades_excluidas() -> None:
    """Las localidades de la Isla del Tiburón están excluidas, cada una con su motivo."""
    excluidas = cargar_configuracion().localidades_excluidas
    assert set(excluidas) == {"260302192", "260303379", "260303436"}
    assert all("Isla del Tiburón" in motivo for motivo in excluidas.values())


def test_catalogo_real_bien_formado() -> None:
    """El catálogo tiene estados válidos, y toda fuente aprobada de descarga se puede descargar."""
    catalogo = leer_catalogo()
    assert catalogo, f"No se leyó {ARCHIVO_CATALOGO}"
    fuentes = cargar_configuracion().fuentes
    for id_fuente, fila in catalogo.items():
        assert fila["estado"] in ESTADOS_FUENTE
        if fila["estado"] == ESTADO_APROBADA and fila["tipo_acceso"] == "download":
            assert fuentes[id_fuente].descargable, f"{id_fuente} no tiene url o nombre_archivo en el YAML"
        if fila["estado"] == ESTADO_APROBADA:
            assert fila["responsable"], f"{id_fuente} está aprobada y no tiene responsable"


def test_fuente_del_yaml_fuera_del_catalogo(tmp_path: Path) -> None:
    """Una fuente con datos de descarga que no está en el catálogo se rechaza."""
    catalogo = escribir_catalogo(tmp_path / "datasets.csv", "A-001,Fuente A,aprobada")
    config = escribir_yaml(tmp_path / "fuentes.yaml", "A-001", "B-001")
    with pytest.raises(ValueError, match="B-001"):
        cargar_configuracion(config, catalogo)


def test_estado_desconocido(tmp_path: Path) -> None:
    """Un estado fuera de la lista (por ejemplo, el viejo 'approved') se rechaza."""
    catalogo = escribir_catalogo(tmp_path / "datasets.csv", "A-001,Fuente A,approved")
    with pytest.raises(ValueError, match="approved"):
        leer_catalogo(catalogo)


def test_fuente_repetida(tmp_path: Path) -> None:
    catalogo = escribir_catalogo(tmp_path / "datasets.csv", "A-001,Fuente A,aprobada", "A-001,Otra,propuesta")
    with pytest.raises(ValueError, match="repetida"):
        leer_catalogo(catalogo)


def test_solo_se_descargan_las_aprobadas(tmp_path: Path) -> None:
    """El estado sale del catálogo: una fuente propuesta no se descarga aunque tenga enlace."""
    catalogo = escribir_catalogo(
        tmp_path / "datasets.csv", "A-001,Fuente A,aprobada", "B-001,Fuente B,propuesta", "C-001,Fuente C,diferida"
    )
    config = escribir_yaml(tmp_path / "fuentes.yaml", "A-001", "B-001")
    fuentes = cargar_configuracion(config, catalogo).fuentes
    assert set(fuentes) == {"A-001", "B-001", "C-001"}
    assert [i for i, f in fuentes.items() if f.descargable] == ["A-001"]
    assert fuentes["A-001"].nombre == "Fuente A" and fuentes["A-001"].version == "2020"
    assert fuentes["C-001"].url == ""
