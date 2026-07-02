"""Cliente SOAP ligero para la remisión Veri*Factu a la AEAT.

No se realiza ninguna conexión si faltan el entorno, el certificado o la clave.
Los endpoints proceden del WSDL oficial ``SistemaFacturacion.wsdl``.
"""

from __future__ import annotations

import http.client
import ssl
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET

from . import config, verifactu

SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"
AEAT_ENDPOINTS = {
    "pruebas": (
        "https://prewww1.aeat.es/wlpl/TIKE-CONT/ws/"
        "SistemaFacturacion/VerifactuSOAP"
    ),
    "produccion": (
        "https://www1.agenciatributaria.gob.es/wlpl/TIKE-CONT/ws/"
        "SistemaFacturacion/VerifactuSOAP"
    ),
}

ET.register_namespace("soapenv", SOAP_NS)


class VerifactuTransportError(RuntimeError):
    """Fallo temporal de red, TLS o respuesta ilegible."""


@dataclass(frozen=True)
class SubmissionResult:
    status: str
    csv: str | None
    wait_seconds: int
    error_code: str | None
    error_description: str | None
    global_status: str | None
    raw_response: str


def configuration_errors() -> list[str]:
    """Explica por qué la remisión está desactivada o mal configurada."""
    errors = []
    if config.VERIFACTU_AEAT_ENV not in AEAT_ENDPOINTS:
        errors.append("entorno AEAT (pruebas o produccion)")
    if not config.VERIFACTU_CERT_PATH:
        errors.append("certificado Veri*Factu")
    if not config.VERIFACTU_KEY_PATH:
        errors.append("clave privada Veri*Factu")
    return errors


def is_enabled() -> bool:
    """Solo habilita red cuando las tres opciones obligatorias están presentes."""
    return not configuration_errors()


def build_soap_envelope(business: dict, records: list[dict]) -> bytes:
    """Envuelve el mensaje RegFactuSistemaFacturacion en SOAP 1.1."""
    message = ET.fromstring(verifactu.build_aeat_xml(business, records))
    envelope = ET.Element(f"{{{SOAP_NS}}}Envelope")
    ET.SubElement(envelope, f"{{{SOAP_NS}}}Header")
    body = ET.SubElement(envelope, f"{{{SOAP_NS}}}Body")
    body.append(message)
    return ET.tostring(envelope, encoding="utf-8", xml_declaration=True)


def _local_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _first_text(root: ET.Element, name: str) -> str | None:
    for element in root.iter():
        if _local_name(element) == name and element.text:
            return element.text.strip()
    return None


def parse_response(payload: bytes) -> SubmissionResult:
    """Interpreta la respuesta oficial, incluida una SOAP Fault estructural."""
    raw = payload.decode("utf-8", errors="replace")
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise VerifactuTransportError(
            "La AEAT devolvió una respuesta XML ilegible."
        ) from exc

    fault = next(
        (element for element in root.iter() if _local_name(element) == "Fault"),
        None,
    )
    if fault is not None:
        code = _first_text(fault, "faultcode")
        description = _first_text(fault, "faultstring") or "SOAP Fault de la AEAT."
        return SubmissionResult(
            status="rechazado",
            csv=None,
            wait_seconds=0,
            error_code=code,
            error_description=description,
            global_status="Incorrecto",
            raw_response=raw,
        )

    line = next(
        (
            element
            for element in root.iter()
            if _local_name(element) == "RespuestaLinea"
        ),
        None,
    )
    if line is None:
        raise VerifactuTransportError(
            "La respuesta de la AEAT no contiene el resultado del registro."
        )
    official_status = _first_text(line, "EstadoRegistro")
    statuses = {
        "Correcto": "aceptado",
        "AceptadoConErrores": "aceptado_con_errores",
        "Incorrecto": "rechazado",
    }
    if official_status not in statuses:
        raise VerifactuTransportError(
            "La respuesta de la AEAT contiene un estado desconocido."
        )
    wait_text = _first_text(root, "TiempoEsperaEnvio") or "0"
    try:
        wait_seconds = max(0, int(wait_text))
    except ValueError:
        wait_seconds = 0
    return SubmissionResult(
        status=statuses[official_status],
        csv=_first_text(root, "CSV"),
        wait_seconds=wait_seconds,
        error_code=_first_text(line, "CodigoErrorRegistro"),
        error_description=_first_text(line, "DescripcionErrorRegistro"),
        global_status=_first_text(root, "EstadoEnvio"),
        raw_response=raw,
    )


def submit_records(business: dict, records: list[dict]) -> SubmissionResult:
    """Remite uno o más registros con mTLS y devuelve su resultado oficial."""
    if not is_enabled():
        raise VerifactuTransportError(
            "La remisión Veri*Factu está desactivada o incompleta."
        )
    if not records:
        raise ValueError("No hay registros Veri*Factu para remitir.")

    cert_path = Path(config.VERIFACTU_CERT_PATH)
    key_path = Path(config.VERIFACTU_KEY_PATH)
    if not cert_path.is_file() or not key_path.is_file():
        raise VerifactuTransportError(
            "No se encuentra el certificado o la clave privada Veri*Factu."
        )

    endpoint = urlsplit(AEAT_ENDPOINTS[config.VERIFACTU_AEAT_ENV])
    context = ssl.create_default_context()
    try:
        context.load_cert_chain(str(cert_path), str(key_path))
    except (OSError, ssl.SSLError) as exc:
        raise VerifactuTransportError(
            "No se pudo cargar el certificado digital Veri*Factu."
        ) from exc

    connection = http.client.HTTPSConnection(
        endpoint.hostname,
        endpoint.port or 443,
        timeout=config.VERIFACTU_HTTP_TIMEOUT_SECONDS,
        context=context,
    )
    payload = build_soap_envelope(business, records)
    path = endpoint.path + (f"?{endpoint.query}" if endpoint.query else "")
    try:
        connection.request(
            "POST",
            path,
            body=payload,
            headers={
                "Content-Type": "text/xml; charset=utf-8",
                "SOAPAction": '""',
                "Accept": "text/xml",
            },
        )
        response = connection.getresponse()
        response_payload = response.read()
    except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
        raise VerifactuTransportError(
            "No se pudo conectar con el servicio Veri*Factu de la AEAT."
        ) from exc
    finally:
        connection.close()

    if response.status >= 400 and b"Fault" not in response_payload:
        raise VerifactuTransportError(
            f"La AEAT respondió por HTTP con estado {response.status}."
        )
    return parse_response(response_payload)
