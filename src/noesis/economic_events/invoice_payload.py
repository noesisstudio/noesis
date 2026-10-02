"""Evidencia cerrada v2 de emisión; no efectos ni cálculos fiscales nuevos."""

from collections.abc import Mapping
from decimal import Context, Decimal, localcontext
from types import MappingProxyType
import re

from noesis.core.money import parse_money
from .contracts import Field, _schema

PARTY = (Field("name", "text"), Field("nif", "text", nullable=True),
         Field("address", "text", nullable=True))
SERIES = (Field("id", "id"), Field("code", "text"), Field("document_type", "text"))
PROFILE = (Field("id", "id"), Field("version", "id"), Field("content_hash", "text"))
LINE = (Field("id", "id"), Field("position", "id"), Field("description", "text"),
        Field("kind", "text"), Field("base", "money"), Field("vat_amount", "money"),
        Field("total", "money"))
FISCAL = tuple(Field(k, "text", nullable=k in {"previous_hash", "recipient_nif"}) for k in (
    "record_hash", "previous_hash", "qr_url", "issuer_nif", "recipient_nif", "producer_name",
    "producer_nif", "system_name", "system_id", "system_version", "installation_id",
    "generated_at", "breakdown_json")) + (Field("id", "id"), Field("vat_total", "money"),
                                         Field("invoice_total", "money"))


def _decimal(value):
    if not isinstance(value, (str, Decimal)):
        raise TypeError("Decimal/string exacto requerido; ningún float.")
    return parse_money(value)


def _validate_evidence(raw):
    names = {"invoice_id", "client_id", "series", "issuer", "recipient", "lines", "irpf_rate",
             "document_profile", "fiscal_record", "source_fingerprint", "money_provenance"}
    if not isinstance(raw, Mapping) or set(raw) != names:
        raise ValueError("Evidencia v2 cerrada y completa requerida.")
    result = dict(_schema({k: raw[k] for k in ("invoice_id", "client_id", "source_fingerprint", "money_provenance")},
                         (Field("invoice_id", "id"), Field("client_id", "id"),
                          Field("source_fingerprint", "text"), Field("money_provenance", "text"))))
    if result["money_provenance"] != "legacy_binary_storage":
        raise ValueError("El documento legacy exige procedencia binaria explícita.")
    for key, schema in (("series", SERIES), ("issuer", PARTY), ("recipient", PARTY),
                        ("document_profile", PROFILE)):
        result[key] = _schema(raw[key], schema)
    for value in (result["source_fingerprint"], result["document_profile"]["content_hash"]):
        if not re.fullmatch(r"[0-9a-f]{64}", value):
            raise ValueError("Huella SHA-256 requerida.")
    result["fiscal_record"] = None if raw["fiscal_record"] is None else _schema(raw["fiscal_record"], FISCAL)
    result["irpf_rate"] = _decimal(raw["irpf_rate"])
    if result["irpf_rate"] not in (0, 7, 15):
        raise ValueError("IRPF no admitido.")
    if not isinstance(raw["lines"], (tuple, list)) or not 1 <= len(raw["lines"]) <= 256:
        raise ValueError("Líneas de documento requeridas.")
    lines = []
    for row in raw["lines"]:
        decimals = {"quantity", "unit_price", "discount_rate", "vat_rate"}
        if not isinstance(row, Mapping) or set(row) != {f.name for f in LINE} | decimals:
            raise ValueError("Línea v2 cerrada requerida.")
        line = dict(_schema({k: v for k, v in row.items() if k not in decimals}, LINE))
        line.update({k: _decimal(row[k]) for k in decimals})
        if line["vat_rate"] not in (0, 4, 10, 21) or line["quantity"] <= 0 or not 0 <= line["discount_rate"] <= 100:
            raise ValueError("Cantidad, IVA o descuento inválidos.")
        if line["total"] != line["base"] + line["vat_amount"]:
            raise ValueError("Desglose de línea incoherente.")
        lines.append(MappingProxyType(line))
    if len({r["id"] for r in lines}) != len(lines) or len({r["position"] for r in lines}) != len(lines):
        raise ValueError("Líneas duplicadas.")
    result["lines"] = tuple(lines)
    return MappingProxyType(result)


def validate_evidence(raw):
    with localcontext(Context(prec=50)):
        return _validate_evidence(raw)


def check_totals(payload):
    with localcontext(Context(prec=50)):
        evidence = payload["evidence"]
        for key in ("base", "vat_amount"):
            if sum((line[key] for line in evidence["lines"]), Decimal(0)) != payload[key]:
                raise ValueError("El evento no cuadra con las líneas legales congeladas.")
        fiscal = evidence["fiscal_record"]
        if fiscal and (fiscal["vat_total"] != payload["vat_amount"] or fiscal["invoice_total"] != payload["total"]):
            raise ValueError("El evento no cuadra con el registro fiscal congelado.")
