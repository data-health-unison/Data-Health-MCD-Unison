"""Cliente de la API de Ruteo SAKBÉ v3.1 de INEGI.

Calcula distancia y tiempo por la red carretera entre dos coordenadas:
1. ``buscalinea`` ubica el tramo carretero más cercano a cada punto.
2. ``optima`` / ``libre`` / ``cuota`` calculan la ruta entre ambos tramos.

Características:
- Tokens leídos de ``SAKBE_TOKENS`` (varios, separados por coma) o ``SAKBE_TOKEN``,
  en el entorno o en el archivo ``.env``; nunca se escriben en caché ni en bitácoras.
- Rotación de tokens: cada token tiene su propia cuota diaria; al agotarse o ser
  rechazado se pasa al siguiente.
- Caché persistente en SQLite: una consulta ya hecha no vuelve a gastar cuota,
  incluidos los resultados negativos (punto sin carretera cercana o sin ruta).
- Control de cuota diaria por token: cuenta cada petición HTTP real y se detiene
  cuando todos los tokens alcanzan el límite configurado.
- Reintentos con retroceso exponencial ante errores transitorios (red, 429, 5xx).

Documentación oficial: https://www.inegi.org.mx/servicios/Ruteo/
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Sequence

import requests

from health_data.config import (
    INTERIM_DATA_DIR,
    PROJECT_ROOT,
    cargar_configuracion,
    ensure_directories,
)

log = logging.getLogger(__name__)

DATASET_ID = "INEGI-ROUTE-001"
URL_BASE = "https://gaia.inegi.org.mx/sakbe_v3.1/"
TOKEN_ENV = "SAKBE_TOKEN"
TOKENS_ENV = "SAKBE_TOKENS"
ARCHIVO_CACHE = INTERIM_DATA_DIR / "sakbe_cache.sqlite"

LIMITE_DIARIO = 2500
REINTENTOS = 3
TIMEOUT_SEG = 30
#Si no hay tramo a una escala, se amplía la búsqueda a la siguiente (cada intento se cachea).
#Con 10 000 fallaba ~87 % de los puntos de Sonora, por lo que se empieza en 50 000.
ESCALAS_BUSQUEDA = (50_000, 250_000, 1_000_000)
DECIMALES_COORD = 5  # ~1 m; evita fallos de caché por ruido de punto flotante

TIPOS_RUTA = ("optima", "libre", "cuota")
VEHICULO_AUTOMOVIL = 1
CODIGOS_TRANSITORIOS = {429, 500, 502, 503, 504}
PALABRAS_ERROR_TOKEN = ("key", "llave", "token", "clave", "autoriz")
RESPUESTA_VACIA = "respuesta vacía"
# Límite por token que indica el catálogo. Por encima de él, un error no reconocido se toma
# como límite real del servidor (no se guarda en caché) y se registra en limites_detectados.
LIMITE_DOCUMENTADO = 2500
MENSAJES_SIN_RESULTADO = ("no se encontró línea de red", "no deben ser el mismo", RESPUESTA_VACIA)
PALABRAS_CUOTA_SERVIDOR = ("límite", "limite", "excedi", "cuota", "agotad")


#--------------------------------------------------------------------------
# Errores
#--------------------------------------------------------------------------


class SakbeError(RuntimeError):
    """Error genérico de la API SAKBÉ."""


class SakbeTokenError(SakbeError):
    """Token ausente, inválido o sin autorización."""


class SakbeCuotaAgotada(SakbeError):
    """Se alcanzó el límite diario de consultas configurado."""


class SakbeSinRuta(SakbeError):
    """La API no encontró carretera cercana o ruta entre los puntos."""


class SakbeConexionError(SakbeError):
    """Fallo de red o del servidor tras agotar los reintentos."""


class SakbeNoEnCache(SakbeError):
    """En modo ``solo_cache`` la consulta no está en caché (no se llama a la API)."""


#--------------------------------------------------------------------------
# Resultados
#--------------------------------------------------------------------------


@dataclass(frozen=True)
class Linea:
    """Tramo de la red carretera devuelto por ``buscalinea``."""

    id_routing_net: int
    source: int
    target: int
    nombre: str = ""


@dataclass(frozen=True)
class Ruta:
    """Distancia y tiempo de una ruta calculada por SAKBÉ."""

    long_km: float
    tiempo_min: float
    peaje: bool
    costo_caseta: float
    advertencia: str
    consultado_en: str
    desde_cache: bool


#--------------------------------------------------------------------------
# Token
#--------------------------------------------------------------------------


def _leer_env_archivo(nombre: str, ruta: Path) -> str | None:
    """Lee una variable de un archivo .env simple (CLAVE=valor)."""
    if not ruta.exists():
        return None
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        if clave.strip().removeprefix("export ").strip() == nombre:
            return valor.strip().strip("'\"") or None
    return None


def _leer_variable(nombre: str) -> str | None:
    return os.environ.get(nombre) or _leer_env_archivo(nombre, PROJECT_ROOT / ".env")


def obtener_tokens() -> list[str]:
    """Tokens de SAKBÉ (sin duplicados) desde el entorno o el archivo .env del proyecto.

    Usa ``SAKBE_TOKENS`` (separados por coma) y, si no existe, ``SAKBE_TOKEN``.
    """
    bruto = _leer_variable(TOKENS_ENV) or _leer_variable(TOKEN_ENV) or ""
    tokens = list(dict.fromkeys(t.strip() for t in bruto.split(",") if t.strip()))
    if not tokens:
        raise SakbeTokenError(
            f"No se encontró ningún token de SAKBÉ. Defina {TOKENS_ENV} (varios, "
            f"separados por coma) o {TOKEN_ENV} en el entorno o en el archivo .env "
            f"(ver .env.example). Solicítelo en https://www.inegi.org.mx/servicios/Ruteo/"
        )
    return tokens


def huella_token(token: str) -> str:
    """Identificador no reversible de un token, para contar su consumo."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:12]


#--------------------------------------------------------------------------
# Caché y cuota
#--------------------------------------------------------------------------


class CacheSakbe:
    """Caché de respuestas y contador de consultas diarias en SQLite."""

    def __init__(self, ruta: Path) -> None:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        self.ruta = ruta
        self._con = sqlite3.connect(ruta)
        self._con.executescript(
            """
            CREATE TABLE IF NOT EXISTS respuestas (
                clave TEXT PRIMARY KEY,
                endpoint TEXT NOT NULL,
                parametros TEXT NOT NULL,
                exito INTEGER NOT NULL,
                respuesta TEXT NOT NULL,
                consultado_en TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS consumo_token (
                fecha TEXT NOT NULL,
                token TEXT NOT NULL,
                consultas INTEGER NOT NULL,
                PRIMARY KEY (fecha, token)
            );
            CREATE TABLE IF NOT EXISTS limites_detectados (
                momento TEXT NOT NULL,
                token TEXT NOT NULL,
                aceptadas INTEGER NOT NULL,
                http INTEGER,
                mensaje TEXT
            );
            """
        )
        self._con.commit()

    @staticmethod
    def clave(endpoint: str, parametros: dict[str, Any]) -> str:
        """Clave determinista de una consulta (sin incluir el token)."""
        bruto = json.dumps([endpoint, parametros], sort_keys=True, default=str)
        return hashlib.sha256(bruto.encode("utf-8")).hexdigest()

    def obtener(self, clave: str) -> tuple[bool, dict[str, Any], str] | None:
        fila = self._con.execute(
            "SELECT exito, respuesta, consultado_en FROM respuestas WHERE clave = ?",
            (clave,),
        ).fetchone()
        if fila is None:
            return None
        return bool(fila[0]), json.loads(fila[1]), fila[2]

    def guardar(
        self,
        clave: str,
        endpoint: str,
        parametros: dict[str, Any],
        exito: bool,
        respuesta: dict[str, Any],
        consultado_en: str,
    ) -> None:
        self._con.execute(
            "INSERT OR REPLACE INTO respuestas VALUES (?, ?, ?, ?, ?, ?)",
            (
                clave,
                endpoint,
                json.dumps(parametros, sort_keys=True, default=str),
                int(exito),
                json.dumps(respuesta, ensure_ascii=False),
                consultado_en,
            ),
        )
        self._con.commit()

    def consultas_del_dia(self, huella: str, dia: date | None = None) -> int:
        fila = self._con.execute(
            "SELECT consultas FROM consumo_token WHERE fecha = ? AND token = ?",
            ((dia or date.today()).isoformat(), huella),
        ).fetchone()
        return int(fila[0]) if fila else 0

    def registrar_consulta(self, huella: str, dia: date | None = None) -> None:
        self._con.execute(
            """
            INSERT INTO consumo_token (fecha, token, consultas) VALUES (?, ?, 1)
            ON CONFLICT(fecha, token) DO UPDATE SET consultas = consultas + 1
            """,
            ((dia or date.today()).isoformat(), huella),
        )
        self._con.commit()

    def registrar_limite(self, huella: str, aceptadas: int, http: int, mensaje: str) -> None:
        """Guarda cuántas consultas aceptó SAKBÉ a un token antes de rechazarlo."""
        self._con.execute(
            "INSERT INTO limites_detectados VALUES (?, ?, ?, ?, ?)",
            (datetime.now().isoformat(timespec="seconds"), huella, aceptadas, http, mensaje),
        )
        self._con.commit()

    def marcar_agotado(self, huella: str, limite: int, dia: date | None = None) -> None:
        """Marca un token como agotado hoy (el servidor reportó su cuota consumida)."""
        self._con.execute(
            """
            INSERT INTO consumo_token (fecha, token, consultas) VALUES (?, ?, ?)
            ON CONFLICT(fecha, token) DO UPDATE SET consultas = MAX(consultas, excluded.consultas)
            """,
            ((dia or date.today()).isoformat(), huella, limite),
        )
        self._con.commit()

    def total_respuestas(self) -> int:
        return int(self._con.execute("SELECT COUNT(*) FROM respuestas").fetchone()[0])

    def cerrar(self) -> None:
        self._con.close()


#--------------------------------------------------------------------------
# Cliente
#--------------------------------------------------------------------------


def _parametros_por_omision() -> tuple[str, int]:
    """URL base y límite diario desde config/fuentes_health.yaml, si existen."""
    config = cargar_configuracion()
    fuente = config.fuentes.get(DATASET_ID)
    url = (fuente.api_base if fuente and fuente.api_base else URL_BASE)
    limite = (
        fuente.limite_diario
        if fuente and fuente.limite_diario
        else config.umbrales.sakbe_limite_diario or LIMITE_DIARIO
    )
    return url, int(limite)


def _es_error_de_token(mensaje: str) -> bool:
    texto = mensaje.lower()
    return any(palabra in texto for palabra in PALABRAS_ERROR_TOKEN)


def _es_cuota_del_servidor(mensaje: str) -> bool:
    texto = mensaje.lower()
    return any(palabra in texto for palabra in PALABRAS_CUOTA_SERVIDOR)


def _exito(cuerpo: dict[str, Any]) -> tuple[bool, str]:
    """Lee ``response.success`` (la documentación oficial escribe "succes")."""
    estado = cuerpo.get("response") or {}
    exito = estado.get("success", estado.get("succes", True))
    if isinstance(exito, str):
        exito = exito.lower() == "true"
    return bool(exito), str(estado.get("message", ""))


def _a_float(valor: Any) -> float:
    try:
        return float(valor)
    except (TypeError, ValueError):
        return float("nan")


class ClienteSakbe:
    """Cliente con caché, rotación de tokens, control de cuota y reintentos para SAKBÉ v3.1.

    Ejemplo::

        with ClienteSakbe() as cliente:
            ruta = cliente.ruta_entre_coordenadas(29.0729, -110.9559, 27.9178, -110.9089)
            print(ruta.long_km, ruta.tiempo_min)
    """

    def __init__(
        self,
        tokens: str | Sequence[str] | None = None,
        *,
        url_base: str | None = None,
        ruta_cache: Path | None = None,
        limite_diario: int | None = None,
        sesion: requests.Session | None = None,
        timeout: float = TIMEOUT_SEG,
        reintentos: int = REINTENTOS,
        espera_base: float = 2.0,
        solo_cache: bool = False,
    ) -> None:
        url_config, limite_config = _parametros_por_omision()
        if isinstance(tokens, str):
            tokens = [tokens]
        # En modo solo_cache no se llama a la API, así que los tokens son opcionales
        self.solo_cache = solo_cache
        if tokens:
            self._tokens = list(dict.fromkeys(tokens))
        elif solo_cache:
            try:
                self._tokens = obtener_tokens()
            except SakbeTokenError:
                self._tokens = []
        else:
            self._tokens = obtener_tokens()
        self._huellas = [huella_token(t) for t in self._tokens]
        self._rechazados: set[str] = set()
        self.url_base = (url_base or url_config).rstrip("/") + "/"
        self.limite_diario = limite_diario if limite_diario is not None else limite_config
        self.timeout = timeout
        self.reintentos = max(1, reintentos)
        self.espera_base = espera_base
        self._sesion = sesion or requests.Session()
        if ruta_cache is None:
            ensure_directories()
        self.cache = CacheSakbe(ruta_cache or ARCHIVO_CACHE)
        self.consultas_sesion = 0
        self.aciertos_cache = 0

    #-- ciclo de vida ------------------------------------------------------

    def __enter__(self) -> ClienteSakbe:
        return self

    def __exit__(self, *_: object) -> None:
        self.cerrar()

    def cerrar(self) -> None:
        self.cache.cerrar()
        self._sesion.close()

    #-- cuota --------------------------------------------------------------

    @property
    def num_tokens(self) -> int:
        return len(self._tokens)

    def consultas_hoy(self) -> int:
        """Consultas realizadas hoy sumando todos los tokens."""
        return sum(self.cache.consultas_del_dia(h) for h in self._huellas)

    def consultas_restantes(self) -> int:
        """Consultas disponibles hoy sumando los tokens válidos."""
        return sum(
            max(0, self.limite_diario - self.cache.consultas_del_dia(h))
            for h in self._huellas
            if h not in self._rechazados
        )

    def estado_tokens(self) -> list[tuple[str, int, bool]]:
        """(huella, consultas de hoy, rechazado) por token; nunca expone el token."""
        return [
            (h, self.cache.consultas_del_dia(h), h in self._rechazados) for h in self._huellas
        ]

    def _token_disponible(self) -> tuple[str, str]:
        """Primer token no rechazado y con cuota; lanza error si no queda ninguno."""
        for token, huella in zip(self._tokens, self._huellas):
            if huella in self._rechazados:
                continue
            if self.cache.consultas_del_dia(huella) < self.limite_diario:
                return token, huella
        if len(self._rechazados) == len(self._tokens):
            raise SakbeTokenError("SAKBÉ rechazó todos los tokens configurados.")
        raise SakbeCuotaAgotada(
            f"Todos los tokens ({len(self._tokens)}) alcanzaron el límite diario de "
            f"{self.limite_diario} consultas. Las respuestas ya obtenidas quedan en caché; "
            f"reanude mañana."
        )

    #-- petición base ------------------------------------------------------

    def _limite_del_servidor(self, huella: str, http: int, mensaje: str, *, http_error: bool = False) -> bool:
        """True si el rechazo parece el límite real del servidor para este token.

        Solo aplica por encima de LIMITE_DOCUMENTADO y si el error no es un "sin resultado" conocido.
        Registra cuántas consultas aceptó el token y deja de usarlo por hoy.
        """
        if http_error and http not in (401, 403, 429):
            return False
        usadas = self.cache.consultas_del_dia(huella)
        if usadas <= LIMITE_DOCUMENTADO or any(m in mensaje.lower() for m in MENSAJES_SIN_RESULTADO):
            return False
        log.warning(
            "LÍMITE REAL: SAKBÉ rechazó el token %s tras %d consultas aceptadas hoy (HTTP %d): %s",
            huella, usadas - 1, http, mensaje[:300],
        )
        self.cache.registrar_limite(huella, usadas - 1, http, mensaje[:1000])
        self.cache.marcar_agotado(huella, self.limite_diario)
        return True

    def _consultar(self, endpoint: str, parametros: dict[str, Any]) -> tuple[dict[str, Any], str, bool]:
        """Ejecuta una consulta con caché. Devuelve (data, consultado_en, desde_cache).

        Lanza SakbeSinRuta si la API respondió success=false (también desde caché).
        """
        clave = CacheSakbe.clave(endpoint, parametros)
        guardado = self.cache.obtener(clave)
        if guardado is not None:
            self.aciertos_cache += 1
            exito, respuesta, consultado_en = guardado
            if not exito:
                raise SakbeSinRuta(respuesta.get("message", "Sin resultado (caché)"))
            return respuesta, consultado_en, True

        if self.solo_cache:
            raise SakbeNoEnCache(f"{endpoint} no está en caché (modo solo_cache).")
        cuerpo = self._post(endpoint, parametros)
        consultado_en = datetime.now().isoformat(timespec="seconds")

        exito, mensaje = _exito(cuerpo)
        if not exito:
            self.cache.guardar(clave, endpoint, parametros, False, {"message": mensaje}, consultado_en)
            raise SakbeSinRuta(mensaje or f"SAKBÉ no devolvió resultado en {endpoint}")

        data = cuerpo.get("data")
        if isinstance(data, list):
            data = data[0] if data else None
        if not data:
            self.cache.guardar(
                clave, endpoint, parametros, False, {"message": "Respuesta sin datos"}, consultado_en
            )
            raise SakbeSinRuta(f"SAKBÉ devolvió una respuesta vacía en {endpoint}")

        #La geometría puede pesar cientos de KB por ruta; no se usa en el análisis.
        data = {k: v for k, v in data.items() if k != "geojson"}
        self.cache.guardar(clave, endpoint, parametros, True, data, consultado_en)
        return data, consultado_en, False

    def _post(self, endpoint: str, parametros: dict[str, Any]) -> dict[str, Any]:
        """POST con rotación de tokens, control de cuota y reintentos.

        Nunca expone el token en errores. Un token rechazado o con la cuota agotada
        en el servidor se descarta y la consulta se repite con el siguiente.
        """
        url = self.url_base + endpoint
        ultimo_error = ""
        intento = 1

        while intento <= self.reintentos:
            token, huella = self._token_disponible()
            datos = {**parametros, "type": "json", "key": token}
            self.cache.registrar_consulta(huella)
            self.consultas_sesion += 1

            try:
                respuesta = self._sesion.post(url, data=datos, timeout=self.timeout)
            except requests.RequestException as exc:
                ultimo_error = f"{type(exc).__name__}"
            else:
                if respuesta.status_code in (401, 403):
                    log.warning(
                        "Token SAKBÉ %s rechazado (HTTP %d); se usa el siguiente.",
                        huella, respuesta.status_code,
                    )
                    self._rechazados.add(huella)
                    continue
                if self._limite_del_servidor(huella, respuesta.status_code, respuesta.text, http_error=True):
                    continue
                if respuesta.status_code in CODIGOS_TRANSITORIOS:
                    ultimo_error = f"HTTP {respuesta.status_code}"
                elif respuesta.status_code >= 400:
                    raise SakbeError(f"SAKBÉ respondió HTTP {respuesta.status_code} en {endpoint}.")
                elif not respuesta.content.strip():
                    # Para algunos pares origen-destino SAKBÉ responde siempre vacío; se reintenta
                    # por si es transitorio y, si persiste, se trata como "sin resultado".
                    ultimo_error = RESPUESTA_VACIA
                else:
                    try:
                        cuerpo = respuesta.json()
                    except ValueError as exc:
                        if self._limite_del_servidor(huella, respuesta.status_code, respuesta.text):
                            continue
                        raise SakbeError(
                            f"SAKBÉ devolvió una respuesta no JSON en {endpoint}: "
                            f"{respuesta.text[:200]!r}"
                        ) from exc
                    if not isinstance(cuerpo, dict):
                        raise SakbeError(f"Respuesta inesperada de SAKBÉ en {endpoint}.")
                    exito, mensaje = _exito(cuerpo)
                    if not exito and self._limite_del_servidor(huella, respuesta.status_code, mensaje):
                        continue
                    if not exito and _es_cuota_del_servidor(mensaje):
                        log.warning(
                            "Token SAKBÉ %s sin cuota en el servidor (%s); se usa el siguiente.",
                            huella, mensaje,
                        )
                        self.cache.marcar_agotado(huella, self.limite_diario)
                        continue
                    if not exito and _es_error_de_token(mensaje):
                        log.warning(
                            "Token SAKBÉ %s rechazado (%s); se usa el siguiente.", huella, mensaje
                        )
                        self._rechazados.add(huella)
                        continue
                    return cuerpo

            if intento < self.reintentos:
                espera = self.espera_base * 2 ** (intento - 1)
                log.warning(
                    "SAKBÉ %s falló (%s); reintento %d/%d en %.1f s",
                    endpoint, ultimo_error, intento, self.reintentos - 1, espera,
                )
                time.sleep(espera)
            intento += 1

        if ultimo_error == RESPUESTA_VACIA:
            return {"response": {"success": False, "message": f"SAKBÉ devolvió una {RESPUESTA_VACIA}"}}
        raise SakbeConexionError(
            f"SAKBÉ no respondió en {endpoint} tras {self.reintentos} intentos ({ultimo_error})."
        )

    #-- endpoints ----------------------------------------------------------

    def buscar_linea(self, lat: float, lon: float, escala: int | None = None) -> Linea:
        """Tramo carretero más cercano a una coordenada (WGS84 / GRS80).

        Sin ``escala`` se prueban ``ESCALAS_BUSQUEDA`` de menor a mayor hasta hallar
        un tramo; SAKBÉ responde "intenta con otra escala" en zonas sin vías cercanas.
        """
        escalas = (escala,) if escala is not None else ESCALAS_BUSQUEDA
        for i, esc in enumerate(escalas):
            parametros = {
                "x": round(float(lon), DECIMALES_COORD),
                "y": round(float(lat), DECIMALES_COORD),
                "escala": int(esc),
            }
            try:
                data, _, _ = self._consultar("buscalinea", parametros)
                break
            except SakbeSinRuta:
                if i == len(escalas) - 1:
                    raise
        try:
            return Linea(
                id_routing_net=int(data["id_routing_net"]),
                source=int(data["source"]),
                target=int(data["target"]),
                nombre=str(data.get("nombre") or ""),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SakbeError(f"Respuesta de buscalinea incompleta: {data}") from exc

    def calcular_ruta(
        self,
        origen: Linea,
        destino: Linea,
        *,
        tipo: str = "optima",
        vehiculo: int = VEHICULO_AUTOMOVIL,
    ) -> Ruta:
        """Ruta entre dos tramos obtenidos con :meth:`buscar_linea`."""
        if tipo not in TIPOS_RUTA:
            raise ValueError(f"tipo debe ser uno de {TIPOS_RUTA}, no {tipo!r}")
        parametros = {
            "id_i": origen.id_routing_net,
            "source_i": origen.source,
            "target_i": origen.target,
            "id_f": destino.id_routing_net,
            "source_f": destino.source,
            "target_f": destino.target,
            "v": int(vehiculo),
        }
        data, consultado_en, desde_cache = self._consultar(tipo, parametros)
        long_km = _a_float(data.get("long_km"))
        tiempo_min = _a_float(data.get("tiempo_min"))
        if long_km != long_km or tiempo_min != tiempo_min:  # NaN
            raise SakbeError(f"Respuesta de {tipo} sin long_km/tiempo_min: {data}")
        costo = _a_float(data.get("costo_caseta"))
        return Ruta(
            long_km=long_km,
            tiempo_min=tiempo_min,
            peaje=str(data.get("peaje", "f")).lower() in ("t", "true", "1"),
            costo_caseta=0.0 if costo != costo else costo,
            advertencia=str(data.get("advertencia") or ""),
            consultado_en=consultado_en,
            desde_cache=desde_cache,
        )

    def ruta_entre_coordenadas(
        self,
        lat_origen: float,
        lon_origen: float,
        lat_destino: float,
        lon_destino: float,
        *,
        tipo: str = "optima",
        vehiculo: int = VEHICULO_AUTOMOVIL,
        escala: int | None = None,
    ) -> Ruta:
        """Ruta por carretera entre dos coordenadas (consultas cacheadas)."""
        origen = self.buscar_linea(lat_origen, lon_origen, escala)
        destino = self.buscar_linea(lat_destino, lon_destino, escala)
        return self.calcular_ruta(origen, destino, tipo=tipo, vehiculo=vehiculo)


#--------------------------------------------------------------------------
# CLI
#--------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Diagnóstico: estado de cuota/caché y prueba de conexión opcional."""
    parser = argparse.ArgumentParser(description="Cliente de la API SAKBÉ de INEGI.")
    parser.add_argument(
        "--probar",
        action="store_true",
        help="Calcula la ruta Hermosillo → Guaymas (pocas consultas; luego queda en caché).",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    try:
        with ClienteSakbe() as cliente:
            print(f"URL base: {cliente.url_base}")
            print(
                f"Tokens: {cliente.num_tokens} · consultas hoy: {cliente.consultas_hoy()} · "
                f"restantes: {cliente.consultas_restantes()} ({cliente.limite_diario} por token)"
            )
            print(f"Respuestas en caché: {cliente.cache.total_respuestas()} ({cliente.cache.ruta})")
            if args.probar:
                ruta = cliente.ruta_entre_coordenadas(29.0729, -110.9559, 27.9178, -110.9089)
                origen = "caché" if ruta.desde_cache else "API"
                print(
                    f"Hermosillo → Guaymas: {ruta.long_km:.1f} km, {ruta.tiempo_min:.0f} min "
                    f"(desde {origen}, consultado {ruta.consultado_en})"
                )
                print(f"Consultas gastadas en esta ejecución: {cliente.consultas_sesion}")
                for huella, usadas, rechazado in cliente.estado_tokens():
                    estado = "RECHAZADO" if rechazado else "ok"
                    print(f"  token {huella}: {usadas} consultas hoy ({estado})")
    except SakbeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
