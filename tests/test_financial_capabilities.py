"""Registry único y contrato puro de consumo futuro, sin activación."""

from dataclasses import replace
import unittest

from noesis.financial_activation.capabilities import (
    COMMAND_CAPABILITIES, REGISTRY, capability_for_command, dependencies_for,
    require_command_capability, specification,
)
from noesis.financial_activation.contracts import (
    Capability as C, CapabilityResult as CR, DEPENDENCIES, Profile,
)
from noesis.financial_operations.contracts import CommandType, StateError


class CapabilityContracts(unittest.TestCase):
    def test_one_catalog_all_commands_mapped_exactly(self):
        self.assertEqual(set(COMMAND_CAPABILITIES), set(CommandType))
        self.assertEqual(set(REGISTRY), set(C))
        self.assertEqual(len(REGISTRY), 15)
        for command in CommandType:
            spec = specification(capability_for_command(command))
            self.assertEqual(spec.capability.value, command.value)
            self.assertEqual(spec.command, command)
            self.assertEqual(spec.dependencies, DEPENDENCIES[spec.capability])
            self.assertTrue(spec.implemented)
            self.assertIsNotNone(spec.producer)
        self.assertEqual(specification(C.FISCAL_CANCEL).producer,
                         "fiscal_cancellation_capture.FiscalCancellationCapture")

    def test_unknown_commands_capabilities_versions_fail_closed(self):
        for command in ("quote.accepted", "supplier_payment.made", "anything", None):
            with self.assertRaises((ValueError, KeyError, TypeError)):
                capability_for_command(command)
        with self.assertRaises(ValueError):
            specification("anything")
        for version in (2, True, "1"):
            with self.assertRaises(ValueError):
                specification(C.WEB, version=version)

    def test_dependencies_identical_to_a_and_fiscal_closure(self):
        for capability in C:
            self.assertEqual(dependencies_for(capability, fiscal_cancel_required=False),
                             tuple(sorted(DEPENDENCIES[capability], key=lambda c: c.value)))
        needed, _ = Profile((C.INVOICE_ISSUE,)).closure(fiscal_cancel_required=True)
        self.assertTrue({C.INVOICE_RECTIFY, C.FISCAL_CANCEL, C.AEAT, C.WEB} <= set(needed))

    def test_dependency_blocked_or_absent_blocks_consumer(self):
        granted = dict.fromkeys(C, CR.ELIGIBLE)
        self.assertEqual(require_command_capability(CommandType.INVOICE_ISSUE, granted,
                                                   fiscal_cancel_required=True), C.INVOICE_ISSUE)
        for dependency in (C.INVOICE_RECTIFY, C.FISCAL_CANCEL, C.AEAT, C.WEB):
            with self.assertRaises(StateError):
                require_command_capability(CommandType.INVOICE_ISSUE, dict(granted, **{dependency.value: CR.BLOCKED}),
                                           fiscal_cancel_required=True)
        with self.assertRaises(StateError):
            require_command_capability(CommandType.INVOICE_ISSUE, {}, fiscal_cancel_required=True)

    def test_not_applicable_and_not_requested_never_granted(self):
        for result in (CR.NOT_APPLICABLE, CR.NOT_REQUESTED):
            granted = dict.fromkeys(C, CR.ELIGIBLE)
            granted[C.AEAT] = result
            with self.assertRaises(StateError):
                require_command_capability("invoice.fiscal_cancel", granted, fiscal_cancel_required=True)
        with self.assertRaises(ValueError):
            require_command_capability("invoice.issue", {"unknown": "eligible"}, fiscal_cancel_required=False)

    def test_registry_immutable_and_not_an_activation_receipt(self):
        with self.assertRaises(TypeError):
            REGISTRY[C.FISCAL_CANCEL] = replace(REGISTRY[C.FISCAL_CANCEL], implemented=False)
        spec = specification(C.FISCAL_CANCEL)
        self.assertIn("human_confirmation", spec.requirements)
        self.assertIn("activation_generation", spec.requirements)
        self.assertIn("durable_verified_fiscal_antecedent", spec.requirements)
