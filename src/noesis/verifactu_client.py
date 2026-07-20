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
    ("pruebas", "persona"): (
        "https://prewww1.aeat.es/wlpl/TIKE-CONT/ws/"
        "SistemaFacturacion/VerifactuSOAP"
    ),
    ("produccion", "persona"): (
        "https://www1.agenciatributaria.gob.es/wlpl/TIKE-CONT/ws/"
        "SistemaFacturacion/VerifactuSOAP"
    ),
    ("pruebas", "sello"): (
        "https://prewww10.aeat.es/wlpl/TIKE-CONT/ws/"
        "SistemaFacturacion/VerifactuSOAP"
    ),
    ("produccion", "sello"): (
        "https://www10.agenciatributaria.gob.es/wlpl/TIKE-CONT/ws/"
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
    if config.VERIFACTU_AEAT_ENV not in {"pruebas", "produccion"}:
        errors.append("entorno AEAT (pruebas o produccion)")
    if config.VERIFACTU_CERT_TYPE not in {"persona", "sello"}:
        errors.append("tipo de certificado (persona o sello)")
    if not config.VERIFACTU_CERT_PATH:
        errors.append("certificado Veri*Factu")
    if not config.VERIFACTU_KEY_PATH:
        errors.append("clave privada Veri*Factu")
    if config.VERIFACTU_CERT_PATH and not Path(
        config.VERIFACTU_CERT_PATH
    ).is_file():
        errors.append("archivo de certificado Veri*Factu")
    if config.VERIFACTU_KEY_PATH and not Path(
        config.VERIFACTU_KEY_PATH
    ).is_file():
        errors.append("archivo de clave privada Veri*Factu")
    if not 1024 <= config.VERIFACTU_MAX_RESPONSE_BYTES <= 10 * 1024 * 1024:
        errors.append("límite seguro de respuesta AEAT")
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
        detail = f"{code}: {description}" if code else description
        raise VerifactuTransportError(
            f"La AEAT devolvió un error SOAP temporal o de configuración: {detail}"
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
    status = statuses[official_status]
    duplicate_status = _first_text(line, "EstadoRegistroDuplicado")
    if official_status == "Incorrecto" and duplicate_status in {
        "Correcta", "AceptadaConErrores"
    }:
        # Un timeout puede ocultar una aceptación y provocar un reenvío. Si la
        # AEAT confirma que el registro idéntico ya consta, la cola queda cerrada
        # como aceptada en vez de generar un falso rechazo permanente.
        status = (
            "aceptado" if duplicate_status == "Correcta"
            else "aceptado_con_errores"
        )
    return SubmissionResult(
        status=status,
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

    endpoint = urlsplit(AEAT_ENDPOINTS[
        (config.VERIFACTU_AEAT_ENV, config.VERIFACTU_CERT_TYPE)
    ])
    context = ssl.create_default_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    try:
        context.load_cert_chain(
            str(cert_path),
            str(key_path),
            password=config.VERIFACTU_KEY_PASSWORD or None,
        )
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
        response_payload = response.read(config.VERIFACTU_MAX_RESPONSE_BYTES + 1)
    except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
        raise VerifactuTransportError(
            "No se pudo conectar con el servicio Veri*Factu de la AEAT."
        ) from exc
    finally:
        connection.close()

    if len(response_payload) > config.VERIFACTU_MAX_RESPONSE_BYTES:
        raise VerifactuTransportError(
            "La respuesta de la AEAT supera el límite de seguridad."
        )
    if response.status >= 400 and b"Fault" not in response_payload:
        raise VerifactuTransportError(
            f"La AEAT respondió por HTTP con estado {response.status}."
        )
    return parse_response(response_payload)
