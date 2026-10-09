"""Lectura local explícita: huellas HMAC, jamás tokens o paths en evidencia."""

import hashlib
import hmac
import ssl
from pathlib import Path

from noesis import config
from noesis.financial_activation.configuration_snapshot import PRODUCER_FIELDS
from noesis.financial_activation.contracts import canonical
from .contracts import Provider, Implementation, Environment


def keyed(label, value):
    key = hmac.digest(config.SECRET_KEY.encode(), b"noesis.financial-providers.v1", "sha256")
    return hmac.new(key, label.encode() + b"\0" + canonical(value).encode(), hashlib.sha256).hexdigest()


def snapshot(session, business_id, provider):
    """Sólo llamada explícita al control plane/dispatch, nunca al importar el módulo."""
    provider = Provider(provider)
    business = session.borrowed_connection.execute_exact("SELECT * FROM businesses WHERE id=?", (business_id,)).fetchone()
    if not business:
        raise ValueError("Negocio no disponible.")
    public_cert = None
    env, valid = Environment.PRODUCTION, False
    settings, credentials = {}, {}
    if provider == Provider.AEAT:
        from noesis.verifactu_client import configuration_errors
        impl = Implementation.AEAT
        env = {"pruebas": Environment.SANDBOX, "produccion": Environment.PRODUCTION}.get(config.VERIFACTU_AEAT_ENV, Environment.LOCAL)
        settings = {name: getattr(config, name, "") for name in PRODUCER_FIELDS}
        settings.update(environment=config.VERIFACTU_AEAT_ENV, cert_type=config.VERIFACTU_CERT_TYPE,
                        timeout=config.VERIFACTU_HTTP_TIMEOUT_SECONDS, response_limit=config.VERIFACTU_MAX_RESPONSE_BYTES,
                        issuer={k: business[k] for k in ("name", "nif", "address", "verifactu_enabled")},
                        cert_path=config.VERIFACTU_CERT_PATH, key_path=config.VERIFACTU_KEY_PATH)
        valid = not configuration_errors() and 1 <= config.VERIFACTU_HTTP_TIMEOUT_SECONDS <= 120 and all(business[k] for k in ("name", "nif", "address"))
        try:
            cert = Path(config.VERIFACTU_CERT_PATH).read_bytes() if config.VERIFACTU_CERT_PATH else b""
            key = Path(config.VERIFACTU_KEY_PATH).read_bytes() if config.VERIFACTU_KEY_PATH else b""
        except OSError:
            cert, key, valid = b"", b"", False
        public_cert = hashlib.sha256(cert).hexdigest() if cert else None
        credentials = dict(key=key.hex(), password=config.VERIFACTU_KEY_PASSWORD, public_cert=public_cert)
        valid = bool(valid and cert and key)
        if valid:
            try:
                context = ssl.create_default_context()
                context.minimum_version = ssl.TLSVersion.TLSv1_2
                context.load_cert_chain(config.VERIFACTU_CERT_PATH, config.VERIFACTU_KEY_PATH,
                                        password=config.VERIFACTU_KEY_PASSWORD or None)
            except (OSError, ssl.SSLError):
                valid = False
    elif provider == Provider.META:
        impl = Implementation.META
        rows = session.borrowed_connection.execute_exact("SELECT * FROM whatsapp_connections WHERE business_id=? ORDER BY id", (business_id,)).fetchall()
        active = [r for r in rows if r["status"] == "active" and r["outbound_enabled"]]
        from noesis.web import whatsapp
        from noesis.financial_history.reconciliation_verifier import storage_hash
        settings = dict(connection_hashes=[storage_hash(dict(r)) for r in rows], central_phone=whatsapp._PHONE_ID,
                        graph_version=config.META_GRAPH_VERSION, timeout_seconds=10)
        credentials = dict(token=whatsapp._TOKEN)
        # La conexión empresarial exacta es obligatoria: el canal central no acredita otro negocio.
        valid = len(active) == 1 and bool(active[0]["phone_number_id"] and credentials["token"])
    else:
        from noesis.adapters.email import _api_available, _sender
        rows = session.borrowed_connection.execute_exact("SELECT * FROM oauth_credentials WHERE business_id=? AND provider='google' ORDER BY provider", (business_id,)).fetchall()
        active = [r for r in rows if r["status"] == "active"]
        if active:
            impl = Implementation.GMAIL
            from noesis.financial_history.reconciliation_verifier import storage_hash
            settings = dict(account_hashes=[storage_hash({k: v for k, v in dict(r).items() if k not in ("refresh_token", "access_token")}) for r in active],
                            sender_name=business['name'], timeout_seconds=20)
            from noesis import secret_box
            credentials = dict(tokens=[{k: secret_box.leer(r[k]) for k in ("refresh_token", "access_token")} for r in active],
                               client_id=getattr(config, "GOOGLE_CLIENT_ID", ""), client_secret=getattr(config, "GOOGLE_CLIENT_SECRET", ""))
            valid = len(active) == 1 and bool(credentials['tokens'][0]['refresh_token'] and active[0]['account_email'] and credentials["client_id"] and credentials["client_secret"]
                                           and 'https://www.googleapis.com/auth/gmail.send' in (active[0]['scope'] or '').split())
        elif _api_available():
            impl = Implementation.BREVO
            settings = dict(sender=_sender(), endpoint=config.BREVO_API_URL, timeout=config.BREVO_TIMEOUT_SECONDS)
            credentials = dict(key=config.BREVO_API_KEY)
            valid = bool(settings["sender"]["email"] and str(settings["endpoint"]).startswith("https://") and 1 <= settings["timeout"] <= 120)
        else:
            impl = Implementation.SMTP
            settings = dict(host=config.SMTP_HOST, port=config.SMTP_PORT, sender=config.SMTP_FROM, user=config.SMTP_USER, timeout_seconds=15)
            credentials = dict(password=config.SMTP_PASS)
            valid = bool(settings["host"] and settings["user"] and settings["sender"] and credentials["password"] and settings["port"] in (465, 587))
    return dict(provider=provider.value, implementation=impl.value, environment=env.value,
                configuration_fingerprint=keyed("configuration:" + str(business_id), settings),
                credential_fingerprint=keyed("credentials:" + str(business_id), credentials),
                configuration_valid=bool(valid), certificate_sha256=public_cert)
