"""Pruebas del cliente SAKBÉ con una sesión HTTP simulada (sin red ni cuota real)."""

from __future__ import annotations

import pytest
import requests

from health_data.ingestion import sakbe
from health_data.ingestion.sakbe import (
    ClienteSakbe,
    SakbeConexionError,
    SakbeCuotaAgotada,
    SakbeSinRuta,
    SakbeTokenError,
)

TOKEN = "token-secreto-de-prueba"

LINEA_OK = {
    "response": {"success": True, "message": "OK"},
    "data": {"id_routing_net": 10, "source": 1, "target": 2, "nombre": "Carr. 15", "geojson": "{}"},
}
RUTA_OK = {
    "response": {"success": True, "message": "OK"},
    "data": {
        "long_km": "135.2",
        "tiempo_min": "98.5",
        "peaje": "t",
        "costo_caseta": 120,
        "advertencia": "",
        "geojson": "{...}",
    },
}


class RespuestaFalsa:
    def __init__(self, cuerpo: dict | None = None, status_code: int = 200) -> None:
        self._cuerpo = cuerpo
        self.status_code = status_code
        self.text = str(cuerpo)

    def json(self) -> dict:
        if self._cuerpo is None:
            raise ValueError("no json")
        return self._cuerpo


class SesionFalsa:
    """Devuelve respuestas por endpoint; registra cada POST."""

    def __init__(self, respuestas: dict[str, list]) -> None:
        self.respuestas = respuestas
        self.llamadas: list[tuple[str, dict]] = []

    def post(self, url: str, data: dict, timeout: float) -> RespuestaFalsa:
        endpoint = url.rsplit("/", 1)[-1]
        self.llamadas.append((endpoint, data))
        cola = self.respuestas[endpoint]
        siguiente = cola.pop(0) if len(cola) > 1 else cola[0]
        if isinstance(siguiente, Exception):
            raise siguiente
        return siguiente

    def close(self) -> None:
        pass


def _cliente(tmp_path, sesion, **kwargs) -> ClienteSakbe:
    return ClienteSakbe(
        TOKEN,
        url_base="https://ejemplo/sakbe/",
        ruta_cache=tmp_path / "cache.sqlite",
        sesion=sesion,
        espera_base=0,
        **kwargs,
    )


def _sesion_ok() -> SesionFalsa:
    return SesionFalsa(
        {"buscalinea": [RespuestaFalsa(LINEA_OK)], "optima": [RespuestaFalsa(RUTA_OK)]}
    )


@pytest.fixture
def sin_tokens_en_entorno(monkeypatch, tmp_path):
    monkeypatch.delenv("SAKBE_TOKEN", raising=False)
    monkeypatch.delenv("SAKBE_TOKENS", raising=False)
    monkeypatch.setattr(sakbe, "PROJECT_ROOT", tmp_path)
    return tmp_path


def test_token_ausente(sin_tokens_en_entorno) -> None:
    with pytest.raises(SakbeTokenError):
        sakbe.obtener_tokens()


def test_token_unico_desde_env_archivo(sin_tokens_en_entorno) -> None:
    (sin_tokens_en_entorno / ".env").write_text(
        "# comentario\nSAKBE_TOKEN='abc123'\n", encoding="utf-8"
    )
    assert sakbe.obtener_tokens() == ["abc123"]


def test_varios_tokens_sin_duplicados(sin_tokens_en_entorno, monkeypatch) -> None:
    monkeypatch.setenv("SAKBE_TOKENS", " aaa, bbb ,aaa,, ccc")
    assert sakbe.obtener_tokens() == ["aaa", "bbb", "ccc"]


def test_ruta_entre_coordenadas(tmp_path) -> None:
    sesion = _sesion_ok()
    with _cliente(tmp_path, sesion) as cliente:
        ruta = cliente.ruta_entre_coordenadas(29.0729, -110.9559, 27.9178, -110.9089)

    assert ruta.long_km == pytest.approx(135.2)
    assert ruta.tiempo_min == pytest.approx(98.5)
    assert ruta.peaje is True
    assert not ruta.desde_cache
    assert [e for e, _ in sesion.llamadas] == ["buscalinea", "buscalinea", "optima"]
    endpoint, datos = sesion.llamadas[-1]
    assert datos["key"] == TOKEN and datos["type"] == "json"
    assert (datos["id_i"], datos["source_i"], datos["target_i"]) == (10, 1, 2)


def test_cache_evita_repetir_consultas(tmp_path) -> None:
    sesion = _sesion_ok()
    with _cliente(tmp_path, sesion) as cliente:
        cliente.ruta_entre_coordenadas(29.0729, -110.9559, 27.9178, -110.9089)
    n_llamadas = len(sesion.llamadas)

    #Nueva instancia: la caché persiste en disco
    with _cliente(tmp_path, sesion) as cliente:
        ruta = cliente.ruta_entre_coordenadas(29.072900001, -110.9559, 27.9178, -110.9089)
        assert cliente.consultas_sesion == 0

    assert ruta.desde_cache
    assert len(sesion.llamadas) == n_llamadas


def test_token_y_geojson_no_se_guardan(tmp_path) -> None:
    with _cliente(tmp_path, _sesion_ok()) as cliente:
        cliente.ruta_entre_coordenadas(29.0, -110.9, 27.9, -110.9)
    contenido = (tmp_path / "cache.sqlite").read_bytes()
    assert TOKEN.encode() not in contenido
    assert b"geojson" not in contenido


def test_cuota_agotada(tmp_path) -> None:
    sesion = _sesion_ok()
    with _cliente(tmp_path, sesion, limite_diario=2) as cliente:
        with pytest.raises(SakbeCuotaAgotada):
            cliente.ruta_entre_coordenadas(29.0, -110.9, 27.9, -110.9)
        assert cliente.consultas_hoy() == 2
        assert cliente.consultas_restantes() == 0
    assert len(sesion.llamadas) == 2


def test_rota_tokens_al_agotar_cuota_local(tmp_path) -> None:
    sesion = _sesion_ok()
    cliente = ClienteSakbe(
        ["tok-a", "tok-b"],
        url_base="https://ejemplo/sakbe/",
        ruta_cache=tmp_path / "cache.sqlite",
        sesion=sesion,
        espera_base=0,
        limite_diario=2,
    )
    with cliente:
        cliente.ruta_entre_coordenadas(29.0, -110.9, 27.9, -110.9)
        assert cliente.consultas_restantes() == 1
    assert [d["key"] for _, d in sesion.llamadas] == ["tok-a", "tok-a", "tok-b"]


def test_rota_tokens_si_el_servidor_reporta_cuota(tmp_path) -> None:
    agotado = {"response": {"success": False, "message": "Ha excedido el límite de consultas"}}
    sesion = SesionFalsa(
        {"buscalinea": [RespuestaFalsa(agotado), RespuestaFalsa(LINEA_OK)]}
    )
    cliente = ClienteSakbe(
        ["tok-a", "tok-b"],
        url_base="https://ejemplo/sakbe/",
        ruta_cache=tmp_path / "cache.sqlite",
        sesion=sesion,
        espera_base=0,
    )
    with cliente:
        linea = cliente.buscar_linea(29.0, -110.9)
        huella_a, usadas_a, _ = cliente.estado_tokens()[0]
        assert usadas_a == cliente.limite_diario
    assert linea.id_routing_net == 10
    assert [d["key"] for _, d in sesion.llamadas] == ["tok-a", "tok-b"]


def test_rota_tokens_si_uno_es_rechazado(tmp_path) -> None:
    rechazo = {"response": {"success": False, "message": "Clave NO autorizada."}}
    sesion = SesionFalsa(
        {"buscalinea": [RespuestaFalsa(rechazo), RespuestaFalsa(LINEA_OK)]}
    )
    cliente = ClienteSakbe(
        ["tok-malo", "tok-bueno"],
        url_base="https://ejemplo/sakbe/",
        ruta_cache=tmp_path / "cache.sqlite",
        sesion=sesion,
        espera_base=0,
    )
    with cliente:
        cliente.buscar_linea(29.0, -110.9)
        cliente.buscar_linea(28.0, -110.0)
        assert [r for _, _, r in cliente.estado_tokens()] == [True, False]
    assert [d["key"] for _, d in sesion.llamadas] == ["tok-malo", "tok-bueno", "tok-bueno"]


def test_reintenta_errores_transitorios(tmp_path) -> None:
    sesion = SesionFalsa(
        {
            "buscalinea": [
                requests.ConnectionError("caída"),
                RespuestaFalsa(status_code=503),
                RespuestaFalsa(LINEA_OK),
            ]
        }
    )
    with _cliente(tmp_path, sesion) as cliente:
        linea = cliente.buscar_linea(29.0, -110.9)
        assert cliente.consultas_hoy() == 3
    assert linea.id_routing_net == 10


def test_error_de_conexion_tras_reintentos(tmp_path) -> None:
    sesion = SesionFalsa({"buscalinea": [RespuestaFalsa(status_code=500)]})
    with _cliente(tmp_path, sesion, reintentos=2) as cliente:
        with pytest.raises(SakbeConexionError):
            cliente.buscar_linea(29.0, -110.9)
    assert len(sesion.llamadas) == 2


def test_http_401_es_error_de_token(tmp_path) -> None:
    sesion = SesionFalsa({"buscalinea": [RespuestaFalsa(status_code=401)]})
    with _cliente(tmp_path, sesion) as cliente:
        with pytest.raises(SakbeTokenError):
            cliente.buscar_linea(29.0, -110.9)
    assert len(sesion.llamadas) == 1


def test_token_rechazado_no_se_cachea(tmp_path) -> None:
    rechazo = {"response": {"succes": False, "message": "Clave NO autorizada."}, "data": None}
    sesion = SesionFalsa({"buscalinea": [RespuestaFalsa(rechazo)]})
    with _cliente(tmp_path, sesion) as cliente:
        for _ in range(2):
            with pytest.raises(SakbeTokenError):
                cliente.buscar_linea(29.0, -110.9)
        assert cliente.cache.total_respuestas() == 0
    #Tras el rechazo el token ya no se vuelve a usar en la sesión
    assert len(sesion.llamadas) == 1


def test_sin_ruta_se_cachea(tmp_path) -> None:
    sin_ruta = {"response": {"success": False, "message": "No se encontró ruta"}}
    sesion = SesionFalsa({"buscalinea": [RespuestaFalsa(sin_ruta)]})
    with _cliente(tmp_path, sesion) as cliente:
        for _ in range(2):
            with pytest.raises(SakbeSinRuta):
                cliente.buscar_linea(29.0, -110.9, escala=50_000)
    assert len(sesion.llamadas) == 1


def test_tipo_de_ruta_invalido(tmp_path) -> None:
    with _cliente(tmp_path, _sesion_ok()) as cliente:
        linea = cliente.buscar_linea(29.0, -110.9)
        with pytest.raises(ValueError):
            cliente.calcular_ruta(linea, linea, tipo="rapida")


def test_amplia_escala_si_no_hay_tramo(tmp_path) -> None:
    sin_linea = {"response": {"success": False, "message": "No se encontró línea de red, intenta con otra escala"}}
    sesion = SesionFalsa(
        {"buscalinea": [RespuestaFalsa(sin_linea), RespuestaFalsa(LINEA_OK)]}
    )
    with _cliente(tmp_path, sesion) as cliente:
        linea = cliente.buscar_linea(27.9178, -110.9089)
        cliente.buscar_linea(27.9178, -110.9089)
    assert linea.id_routing_net == 10
    assert [d["escala"] for _, d in sesion.llamadas] == [50_000, 250_000]
