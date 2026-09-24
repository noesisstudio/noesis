"""¿Puede Bynoesis enviar un correo ahora mismo? Y si no, qué falta exactamente.

Comprueba la configuración del servidor y, si se le da una dirección, manda un
correo de prueba **de verdad** con un PDF adjunto, que es la única forma de saber
que la cadena entera funciona: credenciales, remitente, adjunto y entrega.

    python scripts/check_email.py
    python scripts/check_email.py tu-cuenta@gmail.com

Hermano de `check_email_dns.py`, que mira el DNS. Este mira el envío. Los dos
hacen falta: uno dice si puedes enviar, el otro si llegará a la bandeja de
entrada en vez de a spam.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from noesis import config  # noqa: E402
from noesis.adapters import email as email_adapter  # noqa: E402

VERDE, ROJO, AMARILLO, FIN = "\033[32m", "\033[31m", "\033[33m", "\033[0m"


def _marca(ok: bool) -> str:
    return f"{VERDE}✓{FIN}" if ok else f"{ROJO}✗{FIN}"


def _tapado(valor: str) -> str:
    """Muestra que hay algo sin enseñarlo: esto se ejecuta en un servidor."""
    if not valor:
        return f"{ROJO}(vacío){FIN}"
    return f"{VERDE}(puesto, {len(valor)} caracteres){FIN}"


def diagnostico() -> bool:
    """Imprime el estado y devuelve si se puede enviar."""
    brevo = bool(config.BREVO_API_KEY)
    smtp_completo = bool(config.SMTP_HOST and config.SMTP_USER and config.SMTP_PASS)

    print("\n== Proveedor de correo ==")
    print(f"  {_marca(brevo)} BREVO_API_KEY   {_tapado(config.BREVO_API_KEY)}")
    print(f"  {_marca(bool(config.SMTP_HOST))} SMTP_HOST       "
          f"{config.SMTP_HOST or f'{ROJO}(vacío){FIN}'}")
    print(f"  {_marca(bool(config.SMTP_USER))} SMTP_USER       "
          f"{config.SMTP_USER or f'{ROJO}(vacío){FIN}'}")
    print(f"  {_marca(bool(config.SMTP_PASS))} SMTP_PASS       "
          f"{_tapado(config.SMTP_PASS)}")
    print(f"    SMTP_PORT       {config.SMTP_PORT}")

    print("\n== Quién firma el correo ==")
    remitente = email_adapter._sender()
    print(f"    SMTP_FROM       {config.SMTP_FROM}")
    print(f"    Tu cliente verá: {remitente['name']} <{remitente['email']}>")
    if "no-reply" in remitente["email"]:
        print(f"  {AMARILLO}⚠{FIN}  Es una dirección «no-reply»: si tu cliente "
              "responde a la factura, esa respuesta no le llega a nadie.")

    puede = email_adapter.available()
    print("\n== Resultado ==")
    if puede:
        via = "Brevo (API)" if brevo else "SMTP"
        print(f"  {VERDE}Bynoesis puede enviar correo por {via}.{FIN}")
    elif brevo or config.SMTP_HOST or config.SMTP_USER:
        print(f"  {ROJO}La configuración está a medias: no se puede enviar.{FIN}")
        if not brevo and not smtp_completo:
            faltan = [n for n, v in (("SMTP_HOST", config.SMTP_HOST),
                                     ("SMTP_USER", config.SMTP_USER),
                                     ("SMTP_PASS", config.SMTP_PASS)) if not v]
            print(f"  Con SMTP hacen falta las tres. Falta: {', '.join(faltan)}.")
    else:
        print(f"  {ROJO}No hay ningún proveedor configurado: no se envía nada.{FIN}")
        print("  Pon BREVO_API_KEY, o SMTP_HOST + SMTP_USER + SMTP_PASS.")
    return puede


def prueba(destino: str) -> int:
    """Manda un correo real con un PDF adjunto de mentira, para probar la cadena."""
    pdf = (b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
           b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
           b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 100]>>endobj\n"
           b"trailer<</Root 1 0 R>>\n%%EOF\n")
    print(f"\n== Enviando una prueba a {destino} ==")
    try:
        enviado = email_adapter.send_email(
            destino,
            "Prueba de envío de Bynoesis",
            "Si lees esto, Bynoesis puede enviar correo.\n\n"
            "Comprueba dos cosas:\n"
            "1. Que este correo esté en tu bandeja de entrada y no en spam.\n"
            "2. En «Mostrar original», que DKIM diga bynoesis.com.\n",
            attachments=[("prueba.pdf", pdf, "application", "pdf")],
        )
    except Exception as exc:  # noqa: BLE001 - el motivo es lo único que sirve
        print(f"  {ROJO}Falló: {type(exc).__name__}: {exc}{FIN}")
        return 1
    if not enviado:
        print(f"  {ROJO}El proveedor no confirmó el envío.{FIN}")
        return 1
    print(f"  {VERDE}Aceptado por el proveedor.{FIN}")
    print(f"  {AMARILLO}Que lo acepten no es que llegue.{FIN} Mira ahora tu buzón:")
    print("   • ¿Está en la bandeja de entrada o en spam?")
    print("   • En «Mostrar original», ¿DKIM dice bynoesis.com?")
    print("   • ¿Lleva el PDF adjunto?")
    return 0


def main(argv: list[str]) -> int:
    puede = diagnostico()
    destino = argv[1] if len(argv) > 1 else ""
    if not destino:
        print("\nPara probar un envío real:  python scripts/check_email.py "
              "tu-cuenta@gmail.com\n")
        return 0 if puede else 1
    if not puede:
        print(f"\n  {ROJO}No se prueba el envío: no hay proveedor configurado.{FIN}\n")
        return 1
    return prueba(destino)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
