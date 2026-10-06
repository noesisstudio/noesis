"""Identidad de configuración que no cambia por contadores ni nuevos borradores."""

from noesis import config
from noesis.financial_history.reconciliation_verifier import storage_hash
from .contracts import digest

PRODUCER_FIELDS = (
    'VERIFACTU_PRODUCER_NAME', 'VERIFACTU_PRODUCER_NIF', 'VERIFACTU_SYSTEM_NAME',
    'VERIFACTU_SYSTEM_ID', 'VERIFACTU_SYSTEM_VERSION', 'VERIFACTU_INSTALLATION_PREFIX',
    'VERIFACTU_RECORD_VERSION', 'VERIFACTU_HASH_ALGORITHM', 'VERIFACTU_HASH_TYPE',
    'VERIFACTU_HASH_SPEC_VERSION', 'VERIFACTU_AEAT_ENV',
)


def configuration_hash(session, business_id):
    business = session.execute('SELECT id,subscription_status,trial_ends_at,is_demo,verifactu_enabled,name,nif,address FROM businesses WHERE id=?', (business_id,)).fetchone()
    return digest(dict(business_hash=storage_hash(business),
                       producer_hash=digest({name: getattr(config, name, '') for name in PRODUCER_FIELDS})))
