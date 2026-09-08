"""Estimación offline de copias completas; no lee datos, secretos ni proveedores."""

import argparse
import json
from decimal import Decimal, InvalidOperation


RATE_DATE = "2026-09-06"
S3_GIB_MONTH_USD = Decimal("0.023")
RAILWAY_GB_OUT_USD = Decimal("0.05")
PUT_USD = Decimal("0.000005")


def estimate(*, set_gib, copies_per_day=1, elapsed_days=365, retention_days=None):
    """Coste mensual equivalente al volumen final, no factura del primer mes."""
    try:
        size = Decimal(str(set_gib))
    except InvalidOperation as exc:
        raise ValueError("El tamaño debe ser numérico.") from exc
    if not size.is_finite() or size <= 0:
        raise ValueError("El tamaño debe ser positivo y finito.")
    for value in (copies_per_day, elapsed_days, retention_days):
        if value is not None and (type(value) is not int or value <= 0):
            raise ValueError("Frecuencia y días deben ser enteros positivos.")
    days = min(elapsed_days, retention_days) if retention_days else elapsed_days
    retained = size * copies_per_day * days
    if retained > 50 * 1024:
        raise ValueError("Más de 50 TiB: recalcular con los tramos oficiales.")
    monthly_upload_gib = size * copies_per_day * 30
    storage = retained * S3_GIB_MONTH_USD
    requests = Decimal(copies_per_day * 30 * 2) * PUT_USD
    # Margen conservador: convertir GiB a GB decimales para la salida de Railway.
    egress = monthly_upload_gib * Decimal(2**30) / Decimal(10**9) * RAILWAY_GB_OUT_USD
    return {
        "tariff_date": RATE_DATE,
        "currency": "USD",
        "retained_gib": str(retained),
        "monthly_upload_gib": str(monthly_upload_gib),
        "s3_storage_usd": str(storage),
        "s3_put_usd": str(requests),
        "railway_egress_estimate_usd": str(egress),
        "monthly_run_rate_usd": str(storage + requests + egress),
        "deletion_policy_assumed": retention_days is not None,
        "warning": "Simulación, no factura ni límite de gasto. No configura borrado. "
        "Excluye IVA, cambio de moneda, restauraciones, reintentos, CPU, disco local, "
        "monitorización y soporte. Tamaño constante, dos objetos por juego, mes de 30 días.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--set-gib", required=True, help="BD comprimida + ZIP, en GiB")
    parser.add_argument("--copies-per-day", type=int, default=1)
    parser.add_argument("--elapsed-days", type=int, default=365)
    parser.add_argument("--retention-days", type=int, help="SOLO simula borrado aprobado")
    args = parser.parse_args()
    try:
        result = estimate(**vars(args))
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
