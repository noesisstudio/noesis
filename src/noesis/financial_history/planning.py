"""Contratos diagnósticos semánticos: la observación se audita en el manifest.

Los bytes v1 de 1.9A permanecen intactos. Estas dos representaciones nuevas
excluyen solo el instante de observación para que otro run del mismo raw produzca
el mismo plan. Ningún candidato de diagnóstico es importable.
"""

import json

from .canonical import canonical_bytes
from .contracts import HistoricalCandidate, HistoricalEvidence


def source_dates(dates):
    return {name: getattr(dates, name) for name in (
        'legacy_kind', 'legacy_representation', 'civil_date', 'economic_date', 'occurred_at')}


class InventoryEvidence(HistoricalEvidence):
    __slots__ = ()

    def canonical_bytes(self):
        return canonical_bytes({'canonical_version': 1, 'contract': 'InventoryEvidence', 'value': {
            'source': self.source, 'revision': self.revision, 'basis': self.basis,
            'dates': source_dates(self.dates), 'money': self.money, 'references': self.references,
        }})


class DiagnosticCandidate(HistoricalCandidate):
    __slots__ = ()

    def canonical_bytes(self):
        return canonical_bytes({'canonical_version': 1, 'contract': 'DiagnosticCandidate', 'value': {
            'identity': self.identity, 'event_payload': self.event_payload,
            'evidence': json.loads(self.evidence.canonical_bytes()), 'dates': source_dates(self.dates),
            'assessment': self.assessment, 'dependencies': self.dependencies,
            'existing_coverage': self.existing_coverage,
            'eligible_for_import': False, 'certifiable': False,
        }})

    @property
    def importable(self):
        return False
