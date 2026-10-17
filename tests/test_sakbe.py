"""Pruebas aisladas del cliente SAKBÉ; no realizan llamadas de red."""

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from health_data.processing.sakbe import (
    SakbeClient,
    SakbeError,
    SakbeQuotaExceeded,
)


class FakeResponse:
    def __init__(self, payload: dict[str, Any], status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict[str, Any]:
        return self.payload


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.closed = False

    def post(
        self, url: str, *, data: dict[str, Any], timeout: tuple[int, int]
    ) -> FakeResponse:
        self.calls.append((url, data))
        return self.responses.pop(0)

    def close(self) -> None:
        self.closed = True


def ok(data: list[dict[str, Any]]) -> FakeResponse:
    return FakeResponse({"response": {"success": True}, "data": data})


def test_calcular_ruta_usa_api_optima_y_cachea_resultados(tmp_path: Path) -> None:
    respuestas = [
        ok([{"id_routing_net": 1, "source": 2, "target": 3}]),
        ok([{"id_routing_net": 4, "source": 5, "target": 6}]),
        ok([{"long_km": 12.5, "tiempo_min": 18.0}]),
    ]
    session = FakeSession(respuestas)
    cliente = SakbeClient(
        token="token-secreto",
        cache_path=tmp_path / "sakbe.sqlite3",
        daily_limit=3,
        session=session,
    )

    ruta = cliente.calcular_ruta((29.0, -110.0), (29.1, -110.1))
    ruta_en_cache = cliente.calcular_ruta((29.0, -110.0), (29.1, -110.1))

    assert ruta is not None
    assert (ruta.distance_km, ruta.time_min) == (12.5, 18.0)
    assert ruta_en_cache == ruta
    assert len(session.calls) == 3
    assert session.calls[0][0].endswith("/buscalinea")
    assert session.calls[2][0].endswith("/optima")
    assert session.calls[2][1]["v"] == 1
    assert session.calls[2][1]["id_i"] == 1
    assert session.calls[2][1]["id_f"] == 4

    with sqlite3.connect(cliente._cache_path) as db:
        contenido = " ".join(
            str(celda)
            for fila in db.execute("SELECT * FROM sakbe_cache")
            for celda in fila
        )
    assert "token-secreto" not in contenido
    cliente.cerrar()
    assert session.closed


def test_consulta_rechazada_por_cuota_no_llama_a_la_api(tmp_path: Path) -> None:
    session = FakeSession([ok([{"id_routing_net": 1, "source": 2, "target": 3}])])
    cliente = SakbeClient(
        token="token",
        cache_path=tmp_path / "sakbe.sqlite3",
        daily_limit=1,
        session=session,
    )

    assert cliente._buscar_linea(29.0, -110.0) is not None
    with pytest.raises(SakbeQuotaExceeded):
        cliente._buscar_linea(29.1, -110.1)
    assert len(session.calls) == 1


def test_falla_clara_si_api_rechaza_el_token(tmp_path: Path) -> None:
    session = FakeSession(
        [FakeResponse({"response": {"succes": False, "message": "Invalid key"}})]
    )
    cliente = SakbeClient(
        token="token",
        cache_path=tmp_path / "sakbe.sqlite3",
        daily_limit=3,
        session=session,
    )
    with pytest.raises(SakbeError, match="SAKBÉ rechazó buscalinea"):
        cliente._buscar_linea(29.0, -110.0)
    assert len(session.calls) == 1


def test_respuesta_sin_linea_se_interpreta_como_sin_ruta(tmp_path: Path) -> None:
    cliente = SakbeClient(
        token="token",
        cache_path=tmp_path / "sakbe.sqlite3",
        daily_limit=3,
        session=FakeSession([ok([])]),
    )
    assert cliente._buscar_linea(29.0, -110.0) is None


def test_http_429_detiene_consultas_tras_reintentos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("health_data.processing.sakbe.time.sleep", lambda _: None)
    session = FakeSession(
        [FakeResponse({}, status_code=429) for _ in range(3)]
    )
    cliente = SakbeClient(
        token="token",
        cache_path=tmp_path / "sakbe.sqlite3",
        daily_limit=3,
        session=session,
    )
    with pytest.raises(SakbeQuotaExceeded, match="HTTP 429"):
        cliente._buscar_linea(29.0, -110.0)
    assert len(session.calls) == 3
