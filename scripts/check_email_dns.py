#!/usr/bin/env python3
"""Comprueba si el dominio está preparado para que su correo no caiga en spam.

Mira las tres cosas que deciden si un servidor de destino se fía de un correo:

- **SPF**: qué servidores pueden enviar en nombre del dominio.
- **DKIM**: la firma criptográfica que demuestra que el mensaje no se ha tocado.
- **DMARC**: qué hacer cuando algo de lo anterior falla, y a quién avisar.

No sustituye a enviar un correo de prueba y leer sus cabeceras: esto comprueba lo
que está publicado, no lo que el servidor hace de verdad al enviar. Sirve para lo
contrario de lo que parece —para descartar el DNS— porque cuando el correo cae en
spam lo primero que uno toca es el DNS, y casi nunca es el DNS.

Uso:
    python scripts/check_email_dns.py [dominio] [--proveedor hostinger|brevo|ambos]

Necesita `dig` (viene en macOS y en cualquier Linux). Sin red no puede funcionar.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys

# Selectores que publican los proveedores que usa o puede usar Bynoesis. No es una
# lista exhaustiva de internet: es la de aquí, para que un selector nuevo se añada
# a propósito y no por copiar de un blog.
SELECTORES = {
    "hostinger": ("hostingermail-a", "hostingermail-b", "hostingermail-c"),
    "brevo": ("mail", "brevo"),
    "google": ("google",),
    "otros": ("default", "selector1", "selector2", "k1", "s1", "s2", "dkim"),
}

OK, AVISO, FALLO = "OK", "AVISO", "FALLO"


def _dig(tipo: str, nombre: str) -> list[str]:
    """Una consulta DNS. Devuelve las respuestas sin comillas ni troceo."""
    try:
        salida = subprocess.run(
            ["dig", "+short", tipo, nombre],
            capture_output=True, text=True, timeout=15, check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    respuestas = []
    for linea in salida.splitlines():
        linea = linea.strip()
        if not linea:
            continue
        # Un TXT largo llega troceado en varias cadenas entrecomilladas: se unen
        # sin separador, que es como lo lee un servidor de correo.
        respuestas.append("".join(re.findall(r'"([^"]*)"', linea)) or linea)
    return respuestas


# ------------------------------------------------------------------- SPF ----
def revisar_spf(registros: list[str]) -> list[tuple[str, str]]:
    """Un SPF de más, o un `+all`, valen por todo lo demás mal configurado."""
    spf = [r for r in registros if r.lower().startswith("v=spf1")]
    if not spf:
        return [(FALLO, "No hay registro SPF: cualquiera puede enviar en tu nombre "
                        "y los filtros no tienen con qué comprobar nada.")]
    if len(spf) > 1:
        return [(FALLO, f"Hay {len(spf)} registros SPF. Con más de uno el resultado "
                        "es PERMERROR y falla igual que si no hubiera ninguno: "
                        "deja uno solo, con todos los include dentro.")]
    registro = spf[0]
    hallazgos = []
    if "+all" in registro:
        hallazgos.append((FALLO, "El SPF acaba en `+all`: autoriza a todo internet "
                                 "a enviar en tu nombre. Cámbialo por `~all`."))
    elif not re.search(r"[~\-?]all", registro):
        hallazgos.append((AVISO, "El SPF no termina en `all`. Añade `~all` al final."))
    includes = re.findall(r"include:(\S+)", registro)
    if len(includes) > 8:
        hallazgos.append((AVISO, f"{len(includes)} include: el límite son 10 "
                                 "consultas DNS y al pasarse el SPF falla entero."))
    hallazgos.append((OK, f"SPF publicado y único. Autoriza: "
                          f"{', '.join(includes) or 'ningún include'}."))
    return hallazgos


def spf_autoriza(registros: list[str], aguja: str) -> bool:
    return any(aguja in r for r in registros if r.lower().startswith("v=spf1"))


# ------------------------------------------------------------------ DKIM ----
def clave_dkim(registro: str) -> str | None:
    """Devuelve la clave pública si el registro tiene una de verdad.

    Un selector con `p=` vacío no es un error: es una clave revocada, y los
    proveedores que rotan claves dejan varios así a propósito.
    """
    if "v=dkim1" not in registro.lower():
        return None
    clave = re.search(r"p=([A-Za-z0-9+/=]*)", registro)
    return clave.group(1) or None


def buscar_dkim(dominio: str, familias: tuple[str, ...]) -> dict[str, str]:
    """Selectores con clave viva, por familia de proveedor."""
    encontrados = {}
    for familia in familias:
        for selector in SELECTORES[familia]:
            nombre = f"{selector}._domainkey.{dominio}"
            for registro in _dig("TXT", nombre) + _dig("CNAME", nombre):
                if registro.endswith("."):  # un CNAME: hay que seguirlo
                    for destino in _dig("TXT", registro.rstrip(".")):
                        if clave_dkim(destino):
                            encontrados[selector] = clave_dkim(destino)
                elif clave_dkim(registro):
                    encontrados[selector] = clave_dkim(registro)
    return encontrados


def revisar_dkim(claves: dict[str, str], proveedor: str) -> list[tuple[str, str]]:
    if not claves:
        return [(FALLO, f"No hay ninguna firma DKIM viva para {proveedor}. Sin ella "
                        "el destinatario no puede comprobar que el correo es tuyo, "
                        "y Gmail manda a spam casi todo lo que no está firmado.")]
    hallazgos = []
    for selector, clave in sorted(claves.items()):
        # ~216 caracteres de base64 son 1024 bits; ~392 son 2048.
        bits = 2048 if len(clave) > 300 else 1024
        nivel = OK if bits >= 2048 else AVISO
        detalle = "" if bits >= 2048 else " Una clave de 1024 bits ya se considera débil."
        hallazgos.append((nivel, f"DKIM `{selector}` publicado, clave de ~{bits} "
                                 f"bits.{detalle}"))
    return hallazgos


# ----------------------------------------------------------------- DMARC ----
def revisar_dmarc(registros: list[str], dominio: str) -> list[tuple[str, str]]:
    dmarc = [r for r in registros if r.lower().startswith("v=dmarc1")]
    if not dmarc:
        return [(FALLO, "No hay DMARC. Sin él nadie sabe qué hacer cuando SPF o "
                        "DKIM fallan, y no te enteras de quién envía en tu nombre.")]
    if len(dmarc) > 1:
        return [(FALLO, "Hay más de un registro DMARC; con más de uno se ignoran "
                        "todos.")]
    registro = dmarc[0]
    etiquetas = dict(
        (t.strip().lower(), v.strip())
        for t, _, v in (p.partition("=") for p in registro.split(";")) if t.strip()
    )
    hallazgos = []
    politica = etiquetas.get("p", "none")
    if politica == "none":
        hallazgos.append((AVISO, "La política es `p=none`: solo observa, no pide "
                                 "nada. Está bien para empezar; pasa a "
                                 "`p=quarantine` cuando los informes salgan limpios "
                                 "dos semanas seguidas."))
    else:
        hallazgos.append((OK, f"Política `p={politica}`."))
    rua = etiquetas.get("rua", "")
    if not rua:
        hallazgos.append((FALLO, "El DMARC no tiene `rua`: nadie recibe los "
                                 "informes, así que estás ciego."))
    elif f"@{dominio}" not in rua and ".{}".format(dominio) not in rua:
        hallazgos.append((AVISO, f"Los informes van solo a {rua.replace('mailto:', '')}, "
                                 f"que no es tuyo. Añade una dirección de "
                                 f"@{dominio} para verlos tú también."))
    else:
        hallazgos.append((OK, "Los informes llegan a una dirección tuya."))
    return hallazgos


# --------------------------------------------------------------- Por donde sale ---
def rangos_de_salida(registros: list[str], profundidad: int = 2
                     ) -> tuple[list[str], set[str]]:
    """Sigue los `include:` del SPF hasta dar con las IP que envían de verdad.

    Importa porque la reputación de esas IP **no es tuya**: en un hosting
    compartido sales por el mismo relay que miles de cuentas más, y eso pesa
    aunque tu dominio esté perfecto.
    """
    rangos: list[str] = []
    pendientes, vistos = list(registros), set()
    while pendientes and profundidad >= 0:
        siguientes = []
        for registro in pendientes:
            if not registro.lower().startswith("v=spf1"):
                continue
            rangos.extend(re.findall(r"ip4:(\S+)", registro))
            for incluido in re.findall(r"include:(\S+)", registro):
                if incluido not in vistos:
                    vistos.add(incluido)
                    siguientes.extend(_dig("TXT", incluido))
        pendientes = siguientes
        profundidad -= 1
    return rangos, vistos


def _primera_ip(rango: str) -> str:
    """Una IP de muestra que esté **dentro** del rango.

    Con `/32` la muestra tiene que ser esa misma IP: cambiar el último octeto
    comprobaría una dirección que el SPF no autoriza, y el resultado no diría nada
    sobre la que de verdad envía.
    """
    base, _, mascara = rango.partition("/")
    partes = base.split(".")
    # Sin máscara, `ip4:` es una sola dirección: se comprueba tal cual.
    if len(partes) != 4 or not mascara or int(mascara) > 24:
        return base
    partes[3] = "10"  # dentro del rango y sin ser la dirección de red
    return ".".join(partes)


def revisar_salida(rangos: list[str], incluidos: set[str]
                   ) -> list[tuple[str, str]]:
    """Mira una muestra de cada rango en Spamhaus. Es una muestra, no un censo."""
    if not rangos:
        return [(AVISO, "No he podido averiguar por dónde sale tu correo.")]
    hallazgos = [(OK, f"Sales por {len(rangos)} rango(s): "
                      f"{', '.join(rangos[:6])}{'…' if len(rangos) > 6 else ''}.")]
    listadas = []
    for rango in rangos[:8]:
        ip = _primera_ip(rango)
        invertida = ".".join(reversed(ip.split(".")))
        if _dig("A", f"{invertida}.zen.spamhaus.org"):
            listadas.append(rango)
    if listadas:
        hallazgos.append((FALLO, "Hay rangos de salida en Spamhaus: "
                                 f"{', '.join(listadas)}. Tus correos salen por "
                                 "una infraestructura con mala reputación y no lo "
                                 "arreglas desde tu dominio."))
    else:
        hallazgos.append((OK, "Ninguna muestra de esos rangos aparece en Spamhaus."))
    # El nombre del relay está en los `include`, no en las IP: buscarlo entre las
    # IP no encuentra nada nunca.
    if any("mailchannels" in i.lower() for i in incluidos):
        hallazgos.append((AVISO, "mailchannels"))
    return hallazgos


# ----------------------------------------------------------------- Salida ---
def analizar(dominio: str, proveedor: str) -> tuple[list, list]:
    """Devuelve (hallazgos, acciones). Separadas porque se leen distinto."""
    raiz = _dig("TXT", dominio)
    hallazgos: list[tuple[str, str, str]] = []
    acciones: list[str] = []

    for nivel, texto in revisar_spf(raiz):
        hallazgos.append(("SPF", nivel, texto))

    if proveedor in ("hostinger", "ambos"):
        claves = buscar_dkim(dominio, ("hostinger",))
        for nivel, texto in revisar_dkim(claves, "Hostinger"):
            hallazgos.append(("DKIM", nivel, texto))
        if not spf_autoriza(raiz, "hostinger"):
            hallazgos.append(("SPF", FALLO, "Hostinger no está en el SPF."))
            acciones.append("Añade `include:_spf.mail.hostinger.com` al SPF.")

    if proveedor in ("brevo", "ambos"):
        claves = buscar_dkim(dominio, ("brevo",))
        for nivel, texto in revisar_dkim(claves, "Brevo"):
            hallazgos.append(("DKIM", nivel, texto))
        if not claves:
            acciones.append(
                "Termina la autenticación de Brevo: en su panel, Senders & IP → "
                "Domains, copia el registro DKIM y publícalo en el DNS.")
        if not spf_autoriza(raiz, "sendinblue") and not spf_autoriza(raiz, "brevo"):
            hallazgos.append(("SPF", AVISO, "Brevo no está en el SPF."))
            acciones.append("Añade `include:spf.brevo.com` al SPF, en el mismo "
                            "registro que ya existe (nunca en uno nuevo).")

    # La incoherencia que más veces he visto: el dominio verificado en Brevo pero
    # la firma sin publicar. Verificar la propiedad no autentica nada.
    if any("brevo-code" in r for r in raiz) and not buscar_dkim(dominio, ("brevo",)):
        hallazgos.append(("Brevo", AVISO,
                          "El dominio está verificado en Brevo (`brevo-code`) pero "
                          "no hay firma DKIM suya: la configuración se quedó a "
                          "medias y lo que salga por Brevo irá sin autenticar."))

    for nivel, texto in revisar_dmarc(_dig("TXT", f"_dmarc.{dominio}"), dominio):
        hallazgos.append(("DMARC", nivel, texto))

    rangos, incluidos = rangos_de_salida(raiz)
    for nivel, texto in revisar_salida(rangos, incluidos):
        if texto == "mailchannels":
            hallazgos.append(("Salida", AVISO,
                              "Sales por un relay compartido (MailChannels, el que "
                              "usa el correo de Hostinger). Tu dominio puede estar "
                              "perfecto y aun así compartes reputación de IP con "
                              "miles de cuentas de hosting. Si tras calentar el "
                              "dominio los correos siguen cayendo, el salto que "
                              "queda es mover el buzón a un proveedor con IP "
                              "propia bien reputada."))
        else:
            hallazgos.append(("Salida", nivel, texto))

    return hallazgos, acciones


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dominio", nargs="?", default="bynoesis.com")
    parser.add_argument("--proveedor", default="ambos",
                        choices=("hostinger", "brevo", "ambos"))
    args = parser.parse_args(argv)

    if not shutil.which("dig"):
        print("No encuentro `dig`. En macOS y Linux viene de serie; sin él esto "
              "no puede consultar el DNS.", file=sys.stderr)
        return 2

    hallazgos, acciones = analizar(args.dominio, args.proveedor)
    print(f"\nCorreo de {args.dominio} — lo que hay publicado en el DNS\n")
    for area, nivel, texto in hallazgos:
        marca = {OK: "  ok ", AVISO: "aviso", FALLO: "FALLO"}[nivel]
        print(f"[{marca}] {area:6} {texto}")
    if acciones:
        print("\nQué falta por hacer:\n")
        for accion in acciones:
            print(f"  · {accion}")
    fallos = sum(1 for _a, nivel, _t in hallazgos if nivel == FALLO)
    print(f"\n{fallos} fallo(s). Esto comprueba lo publicado, no lo que hace tu "
          "servidor al enviar: para eso, manda un correo de prueba y lee sus "
          "cabeceras.\n")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
