"""Cliente del API de ruteo SAKBÉ de INEGI."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import requests

log = logging.getLogger(__name__)

URL_BASE = "https://gaia.inegi.org.mx/sakbe_v3.1"
REINTENTOS = 3
TIMEOUT = (5, 30)


class SakbeResponseLike(Protocol):
    """Parte de la respuesta HTTP usada por el cliente."""

    status_code: int

    def raise_for_status(self) -> None: ...

    def json(self) -> Any: ...


class SakbeSessionLike(Protocol):
    """Parte de la sesión HTTP usada por el cliente."""

    def post(
        self,
        url: str,
        *,
        data: dict[str, object],
        timeout: tuple[int, int],
    ) -> SakbeResponseLike: ...

    def close(self) -> None: ...


class SakbeError(RuntimeError):
    """Error al consultar o interpretar la API SAKBÉ."""


class SakbeQuotaExceeded(SakbeError):
    """Se alcanzó el límite diario local de consultas SAKBÉ."""


class SakbeFatalError(SakbeError):
    """La API rechazó la autenticación o la forma de la consulta."""


@dataclass(frozen=True)
class RouteResult:
    """Distancia y duración devueltas por SAKBÉ."""

    distance_km: float
    time_min: float


class SakbeClient:
    """Cliente con caché persistente y control local de cuota diaria."""

    def __init__(
        self,
        *,
        token: str,
        cache_path: Path,
        daily_limit: int,
        base_url: str = URL_BASE,
        session: SakbeSessionLike | None = None,
    ) -> None:
        if not token:
            raise ValueError("Falta el token de SAKBÉ.")
        if daily_limit < 1:
            raise ValueError("El límite diario de SAKBÉ debe ser positivo.")
        self._token = token
        self._cache_path = cache_path
        self._daily_limit = daily_limit
        self._base_url = base_url.rstrip("/")
        self._session = session or requests.Session()
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS sakbe_cache (
                    cache_key TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS sakbe_quota (
                    utc_date TEXT PRIMARY KEY,
                    request_count INTEGER NOT NULL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._cache_path, timeout=30)

    def _consumir_cuota(self) -> None:
        utc_date = datetime.now(UTC).date().isoformat()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            fila = db.execute(
                "SELECT request_count FROM sakbe_quota WHERE utc_date = ?",
                (utc_date,),
            ).fetchone()
            actuales = int(fila[0]) if fila else 0
            if actuales >= self._daily_limit:
                raise SakbeQuotaExceeded(
                    f"Se alcanzó el límite local de {self._daily_limit} consultas "
                    f"SAKBÉ para {utc_date} UTC."
                )
            db.execute(
                """
                INSERT INTO sakbe_quota (utc_date, request_count)
                VALUES (?, 1)
                ON CONFLICT (utc_date)
                DO UPDATE SET request_count = request_count + 1
                """,
                (utc_date,),
            )

    def _post(self, endpoint: str, params: dict[str, object]) -> list[dict[str, Any]]:
        cache_material = json.dumps(
            {
                "base_url": self._base_url,
                "network_year": datetime.now(UTC).year,
                "endpoint": endpoint,
                "params": params,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        cache_key = hashlib.sha256(cache_material.encode("utf-8")).hexdigest()
        with self._connect() as db:
            cached = db.execute(
                "SELECT payload FROM sakbe_cache WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()
        if cached:
            return json.loads(cached[0])

        request_params = {**params, "key": self._token, "type": "json"}
        url = f"{self._base_url}/{endpoint}"
        for intento in range(1, REINTENTOS + 1):
            self._consumir_cuota()
            try:
                response = self._session.post(
                    url, data=request_params, timeout=TIMEOUT
                )
                if response.status_code == 429:
                    if intento < REINTENTOS:
                        time.sleep(2 ** (intento - 1))
                        continue
                    raise SakbeQuotaExceeded(
                        "INEGI respondió HTTP 429; se detienen las consultas "
                        "para respetar la cuota del servicio."
                    )
                if response.status_code >= 500:
                    if intento < REINTENTOS:
                        time.sleep(2 ** (intento - 1))
                        continue
                response.raise_for_status()
                resultado = response.json()
            except requests.HTTPError as exc:
                codigo = exc.response.status_code if exc.response is not None else "?"
                if codigo == 429:
                    raise SakbeQuotaExceeded(
                        "INEGI respondió HTTP 429; se detienen las consultas "
                        "para respetar la cuota del servicio."
                    ) from exc
                error = SakbeFatalError if codigo in (400, 401, 403, 404) else SakbeError
                raise error(f"SAKBÉ devolvió HTTP {codigo} para {endpoint}.") from exc
            except requests.RequestException as exc:
                if intento < REINTENTOS:
                    time.sleep(2 ** (intento - 1))
                    continue
                raise SakbeError(
                    f"Falló la consulta SAKBÉ a {endpoint} tras "
                    f"{REINTENTOS} intentos."
                ) from exc
            except ValueError as exc:
                raise SakbeFatalError(
                    f"SAKBÉ devolvió JSON inválido para {endpoint}."
                ) from exc

            if not isinstance(resultado, dict):
                raise SakbeFatalError(f"Respuesta SAKBÉ inválida para {endpoint}.")
            estado = resultado.get("response")
            if not isinstance(estado, dict):
                raise SakbeFatalError(
                    f"Falta el estado de respuesta SAKBÉ para {endpoint}."
                )
            correcto = estado.get("success", estado.get("succes"))
            if correcto is not True:
                mensaje = str(estado.get("message", "Error sin detalle"))
                mensaje_normalizado = mensaje.casefold()
                if "ruta" in mensaje_normalizado and any(
                    termino in mensaje_normalizado
                    for termino in ("no ", "sin ", "imposible", "not ")
                ):
                    datos = []
                else:
                    raise SakbeFatalError(
                        f"SAKBÉ rechazó {endpoint}: {mensaje}"
                    )
            else:
                datos = resultado.get("data")
            if isinstance(datos, dict):
                datos = [datos]
            if not isinstance(datos, list) or any(
                not isinstance(fila, dict) for fila in datos
            ):
                raise SakbeFatalError(f"Datos SAKBÉ inválidos para {endpoint}.")
            with self._connect() as db:
                db.execute(
                    "INSERT OR REPLACE INTO sakbe_cache (cache_key, payload) VALUES (?, ?)",
                    (cache_key, json.dumps(datos, ensure_ascii=False)),
                )
            return datos

        raise SakbeError(f"Falló la consulta SAKBÉ a {endpoint}.")

    def _buscar_linea(self, latitude: float, longitude: float) -> dict[str, Any] | None:
        filas = self._post(
            "buscalinea",
            {
                "escala": 1_000_000,
                "x": float(longitude),
                "y": float(latitude),
                "proj": "GRS80",
            },
        )
        if not filas:
            return None
        linea = filas[0]
        requeridos = ("id_routing_net", "source", "target")
        if any(linea.get(campo) is None for campo in requeridos):
            raise SakbeError("SAKBÉ devolvió una línea sin identificadores de red.")
        return linea

    def calcular_ruta(
        self,
        origen: tuple[float, float],
        destino: tuple[float, float],
    ) -> RouteResult | None:
        """Calcula ruta óptima para automóvil; None indica que no hay ruta."""
        linea_origen = self._buscar_linea(*origen)
        if linea_origen is None:
            return None
        linea_destino = self._buscar_linea(*destino)
        if linea_destino is None:
            return None

        filas = self._post(
            "optima",
            {
                "id_i": linea_origen["id_routing_net"],
                "source_i": linea_origen["source"],
                "target_i": linea_origen["target"],
                "id_f": linea_destino["id_routing_net"],
                "source_f": linea_destino["source"],
                "target_f": linea_destino["target"],
                "v": 1,
                "e": 0,
                "proj": "GRS80",
            },
        )
        if not filas:
            return None
        try:
            distancia = float(filas[0]["long_km"])
            tiempo = float(filas[0]["tiempo_min"])
        except (KeyError, TypeError, ValueError) as exc:
            raise SakbeError(
                "SAKBÉ no devolvió distancia y tiempo numéricos."
            ) from exc
        if (
            not (distancia >= 0 and tiempo >= 0)
            or not (distancia < float("inf") and tiempo < float("inf"))
        ):
            raise SakbeError("SAKBÉ devolvió una distancia o tiempo inválidos.")
        return RouteResult(distance_km=distancia, time_min=tiempo)

    def cerrar(self) -> None:
        """Cierra la sesión HTTP si fue creada por el cliente."""
        self._session.close()


def crear_cliente_desde_entorno(
    cache_path: Path,
    daily_limit: int,
    base_url: str = URL_BASE,
    token_env: str = "SAKBE_TOKEN",
) -> SakbeClient:
    """Crea el cliente leyendo el token desde la variable configurada."""
    token = os.environ.get(token_env, "").strip()
    if not token:
        raise ValueError(
            f"El modo SAKBÉ requiere definir el token INEGI en la variable "
            f"de entorno {token_env}."
        )
    return SakbeClient(
        token=token,
        cache_path=cache_path,
        daily_limit=daily_limit,
        base_url=base_url,
    )
