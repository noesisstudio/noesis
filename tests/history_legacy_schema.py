"""Conserva fixtures de contratos históricos previos a guards72, sin nuevos imports."""

from functools import wraps
from noesis import migrations


def legacy_history71(test):
    @wraps(test)
    def run(self):
        original_version = migrations.current_version()
        migrations.downgrade(71)
        try:
            return test(self)
        finally:
            # La subida conserva bytes/hashes y las defensas de lectura previas.
            migrations.upgrade(original_version)

    return run
