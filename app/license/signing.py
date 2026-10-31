"""Firma licencias .lic del POS de escritorio (mismo formato que npm run licencia)."""

import base64
import json
import os
import re
from calendar import monthrange
from datetime import date, datetime
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat, load_pem_private_key, load_pem_public_key

from shared.clock import now_bogota
from shared.exceptions import ValidationError

PUBLIC_PEM = """-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAMwSYyUQx/O8Mo4Rq69iSQ7PV1GPLI2QnPIec6n+vLl4=
-----END PUBLIC KEY-----
"""

EQUIPO_RE = re.compile(r"^[0-9A-F]{4}(-[0-9A-F]{4}){3}$")
FECHA_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PERIODOS_LICENCIA = {
    "mensual": 1,
    "trimestral": 3,
    "anual": 12,
}


class LicenseKeyError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def llave_publica() -> Ed25519PublicKey:
    key = load_pem_public_key(PUBLIC_PEM.encode())
    if not isinstance(key, Ed25519PublicKey):
        raise LicenseKeyError("La llave pública del escritorio no es válida.")
    return key


def _rutas_candidatas() -> list[Path]:
    from shared.config.settings import ROOT_DIR

    program_files = Path(os.environ.get("ProgramFiles") or r"C:\Program Files")
    return [
        Path.home() / "Promethixia-POS-Privado" / "1-llave-secreta" / "licencia-privada.pem",
        program_files / "Promethixia-POS-Privado" / "1-llave-secreta" / "licencia-privada.pem",
        ROOT_DIR.parent / "Sistema-Pos-Escritorio" / "llaves" / "licencia-privada.pem",
    ]


def _leer_pem() -> bytes:
    from shared.config.settings import settings

    raw = settings.license_private_key.strip()
    if raw:
        return raw.replace("\\n", "\n").encode()
    configured = settings.license_private_key_path.strip()
    if configured:
        path = Path(configured)
        if not path.is_file():
            raise LicenseKeyError(f"No encuentro la llave privada en {path}.")
        return path.read_bytes()
    for path in _rutas_candidatas():
        if path.is_file():
            return path.read_bytes()
    destino = Path.home() / "Promethixia-POS-Privado" / "1-llave-secreta" / "licencia-privada.pem"
    raise LicenseKeyError(
        "No encuentro la llave privada de licencias. "
        f"Copia licencia-privada.pem a {destino} "
        "o configura LICENSE_PRIVATE_KEY_PATH."
    )


def cargar_llave_privada() -> Ed25519PrivateKey:
    try:
        key = load_pem_private_key(_leer_pem(), password=None)
    except LicenseKeyError:
        raise
    except (OSError, TypeError, ValueError) as exc:
        raise LicenseKeyError("No pude leer la llave privada de licencias.") from exc
    if not isinstance(key, Ed25519PrivateKey):
        raise LicenseKeyError("La llave privada de licencias no es Ed25519.")
    return key


def llave_corresponde(privada: Ed25519PrivateKey) -> bool:
    esperada = llave_publica().public_bytes(Encoding.Raw, PublicFormat.Raw)
    actual = privada.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return actual == esperada


def estado_llave() -> tuple[bool, str]:
    try:
        privada = cargar_llave_privada()
    except LicenseKeyError as exc:
        return False, exc.message
    if not llave_corresponde(privada):
        return False, "La llave privada no corresponde a la del programa de escritorio."
    return True, ""


def normalizar_cliente(valor: str) -> str:
    cliente = (valor or "").strip()
    if not cliente:
        raise ValidationError("Escribe el nombre del negocio.")
    if len(cliente) > 200:
        raise ValidationError("El nombre del negocio es demasiado largo.")
    if any(ord(caracter) < 32 for caracter in cliente):
        raise ValidationError("El nombre del negocio tiene caracteres no válidos.")
    return cliente


def normalizar_equipo(valor: str | None, cualquier_equipo: bool = False) -> str | None:
    if cualquier_equipo:
        return None
    equipo = re.sub(r"\s+", "", valor or "").upper()
    if not equipo:
        raise ValidationError("Escribe el código del equipo. Sale en la pantalla del POS.")
    if not EQUIPO_RE.fullmatch(equipo):
        raise ValidationError("El código de equipo no es válido. Debe verse así: 00E8-B682-7EC7-9CEC")
    return equipo


def normalizar_hasta(valor: str) -> str:
    texto = (valor or "").strip()
    if not FECHA_RE.fullmatch(texto):
        raise ValidationError("La fecha no es válida. Debe verse así: 2027-10-24")
    try:
        datetime.strptime(texto, "%Y-%m-%d")
    except ValueError as exc:
        raise ValidationError("La fecha no es válida. Debe verse así: 2027-10-24") from exc
    return texto


def normalizar_periodo(valor: str | None) -> str:
    raw = re.sub(r"[\s_]+", "-", (valor or "").strip().lower())
    aliases = {
        "mensual": "mensual",
        "mensualidad": "mensual",
        "mes": "mensual",
        "1": "mensual",
        "1-mes": "mensual",
        "trimestral": "trimestral",
        "trimestre": "trimestral",
        "tres-meses": "trimestral",
        "3": "trimestral",
        "3-meses": "trimestral",
        "anual": "anual",
        "anualidad": "anual",
        "anio": "anual",
        "año": "anual",
        "12": "anual",
        "1-ano": "anual",
        "1-año": "anual",
    }
    periodo = aliases.get(raw)
    if periodo not in PERIODOS_LICENCIA:
        raise ValidationError("Elige mensualidad, tres meses o anualidad.")
    return periodo


def sumar_meses(inicio: date, meses: int) -> date:
    month = inicio.month - 1 + meses
    year = inicio.year + month // 12
    month = month % 12 + 1
    day = min(inicio.day, monthrange(year, month)[1])
    return date(year, month, day)


def hasta_por_periodo(periodo: str, desde: date | None = None) -> str:
    clave = normalizar_periodo(periodo)
    return sumar_meses(desde or now_bogota().date(), PERIODOS_LICENCIA[clave]).isoformat()


def nombre_archivo(cliente: str, equipo: str | None) -> str:
    slug = re.sub(r"[^\w-]+", "_", cliente, flags=re.ASCII).strip("_") or "licencia"
    sufijo = equipo[:4] if equipo else "PRUEBAS"
    return f"{slug}_{sufijo}.lic"


def construir_licencia(privada: Ed25519PrivateKey, cliente: str, equipo: str | None, hasta: str, emitida: str) -> str:
    if not llave_corresponde(privada):
        raise LicenseKeyError("La llave privada no corresponde a la del programa de escritorio.")
    datos = {"cliente": cliente, "equipo": equipo, "actualizacionesHasta": hasta, "emitida": emitida}
    payload = json.dumps(datos, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    texto = payload.encode("utf-8")
    firma = privada.sign(texto)
    try:
        llave_publica().verify(firma, texto)
    except InvalidSignature as exc:
        raise LicenseKeyError("La llave privada no corresponde a la del programa de escritorio.") from exc
    return json.dumps(
        {
            "datos": base64.b64encode(texto).decode("ascii"),
            "firma": base64.b64encode(firma).decode("ascii"),
        },
        indent=2,
    )


def emitir(cliente: str, equipo: str | None, hasta: str) -> tuple[str, str, str]:
    emitida = now_bogota().date().isoformat()
    cuerpo = construir_licencia(cargar_llave_privada(), cliente, equipo, hasta, emitida)
    return cuerpo, emitida, nombre_archivo(cliente, equipo)
