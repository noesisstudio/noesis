"""Formato técnico Veri*Factu publicado por la AEAT.

Genera huella, QR y el cuerpo XML que ``verifactu_client`` remite por SOAP/mTLS.
El orden de campos de la huella y los nombres XML no deben cambiarse sin revisar
primero la versión de las especificaciones técnicas configurada.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from urllib.parse import urlencode
from xml.etree import ElementTree as ET

from . import config

NS_LR = (
    "https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/"
    "aplicaciones/es/aeat/tike/cont/ws/SuministroLR.xsd"
)
NS_INFO = (
    "https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/"
    "aplicaciones/es/aeat/tike/cont/ws/SuministroInformacion.xsd"
)

ET.register_namespace("sum", NS_LR)
ET.register_namespace("sum1", NS_INFO)


def aeat_amount(value) -> str:
    """Normaliza un importe como lo trata la especificación de huella AEAT."""
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("El importe Veri*Factu no es válido.") from exc
    if not number.is_finite():
        raise ValueError("El importe Veri*Factu no es finito.")
    rendered = format(number, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"


def aeat_date(value: str | date | datetime) -> str:
    """Devuelve la fecha oficial DD-MM-AAAA."""
    if isinstance(value, datetime):
        parsed = value.date()
    elif isinstance(value, date):
        parsed = value
    else:
        text = str(value).strip()
        try:
            if len(text) == 10 and text[2] == "-" and text[5] == "-":
                parsed = datetime.strptime(text, "%d-%m-%Y").date()
            else:
                parsed = (
                    datetime.fromisoformat(text).date()
                    if "T" in text or " " in text
                    else date.fromisoformat(text)
                )
        except ValueError as exc:
            raise ValueError("La fecha Veri*Factu no es válida.") from exc
    return parsed.strftime("%d-%m-%Y")


def generated_at_with_timezone() -> str:
    """Fecha, hora y huso local en el formato dateTime del XSD."""
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def invoice_hash_input(
    *,
    issuer_nif: str,
    invoice_number: str,
    issue_date: str,
    invoice_type: str,
    vat_total,
    invoice_total,
    previous_hash: str | None,
    generated_at: str,
) -> str:
    """Cadena oficial del registro de alta, en el orden exacto de la AEAT."""
    fields = (
        ("IDEmisorFactura", issuer_nif.strip()),
        ("NumSerieFactura", invoice_number.strip()),
        ("FechaExpedicionFactura", aeat_date(issue_date)),
        ("TipoFactura", invoice_type.strip()),
        ("CuotaTotal", aeat_amount(vat_total)),
        ("ImporteTotal", aeat_amount(invoice_total)),
        ("Huella", (previous_hash or "").strip()),
        ("FechaHoraHusoGenRegistro", generated_at.strip()),
    )
    return "&".join(f"{name}={value}" for name, value in fields)


def invoice_record_hash(*, algorithm: str | None = None, **values) -> str:
    payload = invoice_hash_input(**values).encode("utf-8")
    try:
        digest = hashlib.new(
            algorithm or config.VERIFACTU_HASH_ALGORITHM, payload
        )
    except ValueError as exc:
        raise ValueError("El algoritmo de huella Veri*Factu no está disponible.") from exc
    return digest.hexdigest().upper()


def cancellation_hash_input(
    *,
    issuer_nif: str,
    invoice_number: str,
    issue_date: str,
    previous_hash: str | None,
    generated_at: str,
) -> str:
    """Cadena oficial del registro de anulación, en el orden de la AEAT."""
    fields = (
        ("IDEmisorFacturaAnulada", issuer_nif.strip()),
        ("NumSerieFacturaAnulada", invoice_number.strip()),
        ("FechaExpedicionFacturaAnulada", aeat_date(issue_date)),
        ("Huella", (previous_hash or "").strip()),
        ("FechaHoraHusoGenRegistro", generated_at.strip()),
    )
    return "&".join(f"{name}={value}" for name, value in fields)


def cancellation_record_hash(*, algorithm: str | None = None, **values) -> str:
    payload = cancellation_hash_input(**values).encode("utf-8")
    try:
        digest = hashlib.new(
            algorithm or config.VERIFACTU_HASH_ALGORITHM, payload
        )
    except ValueError as exc:
        raise ValueError("El algoritmo de huella Veri*Factu no está disponible.") from exc
    return digest.hexdigest().upper()


def qr_url(*, issuer_nif: str, invoice_number: str, issue_date: str, total) -> str:
    """URL de cotejo con los cuatro parámetros obligatorios y en su orden."""
    query = urlencode(
        (
            ("nif", issuer_nif.strip()),
            ("numserie", invoice_number.strip()),
            ("fecha", aeat_date(issue_date)),
            ("importe", aeat_amount(total)),
        ),
        encoding="utf-8",
        errors="strict",
    )
    return f"{config.VERIFACTU_QR_BASE_URL}?{query}"


def qr_png(url: str) -> bytes:
    """Genera un QR ISO/IEC 18004 con corrección M, como exige la AEAT."""
    import qrcode

    code = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=4,
    )
    code.add_data(url)
    code.make(fit=True)
    image = code.make_image(fill_color="black", back_color="white")
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _sub(parent: ET.Element, namespace: str, name: str, value=None) -> ET.Element:
    element = ET.SubElement(parent, f"{{{namespace}}}{name}")
    if value is not None:
        element.text = str(value)
    return element


def _system_xml(parent: ET.Element, record: dict) -> None:
    system = _sub(parent, NS_INFO, "SistemaInformatico")
    _sub(system, NS_INFO, "NombreRazon", record["producer_name"])
    _sub(system, NS_INFO, "NIF", record["producer_nif"])
    _sub(system, NS_INFO, "NombreSistemaInformatico", record["system_name"])
    _sub(system, NS_INFO, "IdSistemaInformatico", record["system_id"])
    _sub(system, NS_INFO, "Version", record["system_version"])
    _sub(system, NS_INFO, "NumeroInstalacion", record["installation_id"])
    _sub(system, NS_INFO, "TipoUsoPosibleSoloVerifactu", "N")
    _sub(system, NS_INFO, "TipoUsoPosibleMultiOT", "S")
    _sub(system, NS_INFO, "IndicadorMultiplesOT", "S")


def build_aeat_xml(business: dict, records: list[dict]) -> bytes:
    """Exporta el mensaje XML estándar RegFactuSistemaFacturacion.

    No añade envoltura SOAP ni lo transmite: es el cuerpo validable por los XSD
    SuministroLR y SuministroInformacion publicado por la AEAT.
    """
    root = ET.Element(f"{{{NS_LR}}}RegFactuSistemaFacturacion")
    header = _sub(root, NS_LR, "Cabecera")
    obliged = _sub(header, NS_INFO, "ObligadoEmision")
    _sub(obliged, NS_INFO, "NombreRazon", business["name"])
    _sub(obliged, NS_INFO, "NIF", business["nif"])

    for record in records:
        wrapper = _sub(root, NS_LR, "RegistroFactura")
        if record.get("record_type") == "anulacion":
            cancellation = _sub(wrapper, NS_INFO, "RegistroAnulacion")
            _sub(cancellation, NS_INFO, "IDVersion", record["record_version"])
            invoice_id = _sub(cancellation, NS_INFO, "IDFactura")
            _sub(
                invoice_id, NS_INFO, "IDEmisorFacturaAnulada",
                record["issuer_nif"],
            )
            _sub(
                invoice_id, NS_INFO, "NumSerieFacturaAnulada",
                record["invoice_number"],
            )
            _sub(
                invoice_id, NS_INFO, "FechaExpedicionFacturaAnulada",
                record["issue_date"],
            )
            chain = _sub(cancellation, NS_INFO, "Encadenamiento")
            if record.get("previous_hash"):
                previous = _sub(chain, NS_INFO, "RegistroAnterior")
                _sub(
                    previous, NS_INFO, "IDEmisorFactura",
                    record["previous_issuer_nif"],
                )
                _sub(
                    previous, NS_INFO, "NumSerieFactura",
                    record["previous_invoice_number"],
                )
                _sub(
                    previous, NS_INFO, "FechaExpedicionFactura",
                    record["previous_issue_date"],
                )
                _sub(previous, NS_INFO, "Huella", record["previous_hash"])
            else:
                _sub(chain, NS_INFO, "PrimerRegistro", "S")
            _system_xml(cancellation, record)
            _sub(
                cancellation, NS_INFO, "FechaHoraHusoGenRegistro",
                record["generated_at"],
            )
            _sub(cancellation, NS_INFO, "TipoHuella", record["hash_type"])
            _sub(cancellation, NS_INFO, "Huella", record["record_hash"])
            continue
        alta = _sub(wrapper, NS_INFO, "RegistroAlta")
        _sub(alta, NS_INFO, "IDVersion", record["record_version"])
        invoice_id = _sub(alta, NS_INFO, "IDFactura")
        _sub(invoice_id, NS_INFO, "IDEmisorFactura", record["issuer_nif"])
        _sub(invoice_id, NS_INFO, "NumSerieFactura", record["invoice_number"])
        _sub(invoice_id, NS_INFO, "FechaExpedicionFactura", record["issue_date"])
        _sub(alta, NS_INFO, "NombreRazonEmisor", record["issuer_name"])
        _sub(alta, NS_INFO, "TipoFactura", record["invoice_type"])

        if record["invoice_type"].startswith("R"):
            _sub(
                alta, NS_INFO, "TipoRectificativa",
                record.get("rectification_type") or "I",
            )
            rectified = _sub(alta, NS_INFO, "FacturasRectificadas")
            rectified_id = _sub(rectified, NS_INFO, "IDFacturaRectificada")
            _sub(
                rectified_id, NS_INFO, "IDEmisorFactura",
                record["rectified_issuer_nif"],
            )
            _sub(
                rectified_id, NS_INFO, "NumSerieFactura",
                record["rectified_invoice_number"],
            )
            _sub(
                rectified_id, NS_INFO, "FechaExpedicionFactura",
                record["rectified_issue_date"],
            )

        if record.get("operation_date"):
            _sub(alta, NS_INFO, "FechaOperacion", record["operation_date"])
        _sub(alta, NS_INFO, "DescripcionOperacion", record["description"])
        if record.get("recipient_nif"):
            recipients = _sub(alta, NS_INFO, "Destinatarios")
            recipient = _sub(recipients, NS_INFO, "IDDestinatario")
            _sub(recipient, NS_INFO, "NombreRazon", record["recipient_name"])
            _sub(recipient, NS_INFO, "NIF", record["recipient_nif"])

        breakdown = _sub(alta, NS_INFO, "Desglose")
        for item in json.loads(record["breakdown_json"]):
            detail = _sub(breakdown, NS_INFO, "DetalleDesglose")
            _sub(detail, NS_INFO, "Impuesto", "01")
            _sub(detail, NS_INFO, "ClaveRegimen", "01")
            _sub(detail, NS_INFO, "CalificacionOperacion", "S1")
            _sub(detail, NS_INFO, "TipoImpositivo", aeat_amount(item["vat_rate"]))
            _sub(
                detail, NS_INFO, "BaseImponibleOimporteNoSujeto",
                aeat_amount(item["base"]),
            )
            _sub(
                detail, NS_INFO, "CuotaRepercutida",
                aeat_amount(item["vat_amount"]),
            )

        _sub(alta, NS_INFO, "CuotaTotal", aeat_amount(record["vat_total"]))
        _sub(alta, NS_INFO, "ImporteTotal", aeat_amount(record["invoice_total"]))
        chain = _sub(alta, NS_INFO, "Encadenamiento")
        if record.get("previous_hash"):
            previous = _sub(chain, NS_INFO, "RegistroAnterior")
            _sub(
                previous, NS_INFO, "IDEmisorFactura",
                record["previous_issuer_nif"],
            )
            _sub(
                previous, NS_INFO, "NumSerieFactura",
                record["previous_invoice_number"],
            )
            _sub(
                previous, NS_INFO, "FechaExpedicionFactura",
                record["previous_issue_date"],
            )
            _sub(previous, NS_INFO, "Huella", record["previous_hash"])
        else:
            _sub(chain, NS_INFO, "PrimerRegistro", "S")

        _system_xml(alta, record)
        _sub(
            alta, NS_INFO, "FechaHoraHusoGenRegistro", record["generated_at"]
        )
        _sub(alta, NS_INFO, "TipoHuella", record["hash_type"])
        _sub(alta, NS_INFO, "Huella", record["record_hash"])

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)
