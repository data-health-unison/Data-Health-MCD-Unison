import pandas as pd

from health_data.auditoria import auditar_tabla, revisar_union
from health_data.calidad_ruteo import (
    comparar_con_estimacion, padron_provisional, sensibilidad, tiempos_por_nivel,
)
from health_data.processing.ruteo import excluir_localidades


def test_padron_provisional_y_sensibilidad_por_nivel():
    tabla = pd.DataFrame({
        "locality_id": ["260010001", "260010002", "260010003", "260010004"],
        "municipality_name": ["A"] * 4,
        "population": [20, 10, 6, 1],
        "routing_status": ["parcial", "estimado", "sin_ruta", "estimado"],
        "primary_method": ["sakbe", "estimado", "coneval", None],
        "secondary_method": ["coneval", "estimado", "coneval", None],
        "primary_time_min": [60, 75, 45, None],
        "secondary_time_min": [120, 135, 105, float("inf")],
    })
    datos = tiempos_por_nivel(tabla)
    padron = padron_provisional(datos)
    assert len(padron) == 7
    assert set(padron["metodo"]) == {"coneval", "estimado", "sin_dato"}
    resumen, casos = sensibilidad(datos)
    assert resumen["cambia_umbral_menor"].sum() == 2
    assert resumen["cambia_umbral_mayor"].sum() == 2
    assert resumen["poblacion_cambia"].sum() == 60
    assert set(casos["locality_id"]) == {"260010001", "260010002"}


def test_auditoria_detecta_datos_invalidos_y_exclusion():
    tabla = pd.DataFrame({"cvegeo": ["260010001", "260010001", "260010002", "123"],
                          "latitud": [30, 90, 29, 30], "poblacion_total": [2, 3, 4, -1],
                          "routing_status": ["ok", "sin_ruta", "estimado", "invalido"],
                          "primary_method": ["sakbe", "coneval", "estimado", "otro"],
                          "secondary_method": ["estimado"] * 4,
                          "primary_time_min": [10, 10, 20, -1]})
    validacion = auditar_tabla(tabla, ("cvegeo",))
    assert validacion["filas_con_clave_duplicada"] == 2
    assert set(validacion["reglas"].values()) == {1, 2, 0}
    assert validacion["reglas"]["estado_incoherente_con_metodos"] == 2
    assert validacion["pct_clave_valida"]["cvegeo"] == 75
    poblacion = tabla.assign(localidad=["A", "A", "Isla", "B"])
    assert "260010002" not in excluir_localidades(poblacion, {"260010002": "isla"})["cvegeo"].values


def test_union_distingue_duplicados_nulos_y_discrepancias():
    izquierda = pd.DataFrame({"id": ["A", "B", "B", "C", None], "latitud": [30] * 5})
    derecha = pd.DataFrame({"id": ["A", "B", "B", "D", None], "latitud": [31] * 5})
    reporte = revisar_union(izquierda, derecha, "id", "id")
    assert reporte["filas_left_join"] == 7
    assert reporte["claves_sin_correspondencia_izquierda"] == ["C"]
    assert reporte["claves_sin_correspondencia_derecha"] == ["D"]
    assert reporte["claves_repetidas_derecha"] == ["B"]
    assert reporte["claves_nulas_izquierda"] == 1
    assert reporte["conflictos_en_claves_unicas"] == {"latitud": ["A"]}


def test_sensibilidad_empareja_respaldo_con_estimacion_al_mismo_clues():
    tabla = pd.DataFrame({
        "locality_id": ["260010001"], "population": [20],
        "latitude": [29.0], "longitude": [-110.0],
        "nearest_primary_clues": ["C1"], "nearest_secondary_clues": ["H1"],
        "primary_time_min": [90], "secondary_time_min": [150],
        "primary_method": ["coneval"], "secondary_method": ["sakbe"],
    })
    salud = pd.DataFrame({"clues": ["C1"], "latitud": [29.0], "longitud": [-110.0]})
    pares = comparar_con_estimacion(tabla, salud)
    assert pares["metodo"].tolist() == ["coneval"]
    assert pares["cambia_clasificacion"].tolist() == [True]
    assert pares["poblacion_cambia"].tolist() == [20]
