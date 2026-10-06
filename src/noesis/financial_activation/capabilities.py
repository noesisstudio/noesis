"""Catálogo central C: disponibilidad no concede activación ni autoridad."""

from dataclasses import dataclass
from types import MappingProxyType

from noesis.financial_operations.contracts import CommandType, StateError
from .contracts import Capability, CapabilityResult, DEPENDENCIES, Profile

REGISTRY_VERSION = 1


@dataclass(frozen=True, slots=True)
class CapabilitySpec:
    capability: Capability
    dependencies: tuple[Capability, ...]
    command: CommandType | None
    producer: str | None
    implemented: bool
    requirements: tuple[str, ...]
    registry_version: int = REGISTRY_VERSION


# Se reutiliza el Enum de A: no existe otro catálogo conceptual.
COMMAND_CAPABILITIES = MappingProxyType({c: Capability(c.value) for c in CommandType})
PRODUCERS = MappingProxyType({
    Capability.INVOICE_ISSUE: "invoice_capture.InvoiceCapture",
    Capability.INVOICE_RECTIFY: "invoice_capture.InvoiceCapture",
    Capability.CUSTOMER_PAYMENT_RECORD: "payment_capture.PaymentCapture",
    Capability.SUPPLIER_INVOICE_CONFIRM: "purchasing_capture.SupplierInvoiceCapture",
    Capability.SUPPLIER_INVOICE_CORRECT: "purchasing_capture.SupplierInvoiceCapture",
    Capability.SUPPLIER_INVOICE_VOID: "purchasing_capture.SupplierInvoiceCapture",
    Capability.EXPENSE_CONFIRM: "purchasing_capture.ExpenseCapture",
    Capability.EXPENSE_VOID: "purchasing_capture.ExpenseCapture",
    Capability.BANK_IMPORT: "bank_capture.BankCapture",
    Capability.BANK_MATCH: "bank_capture.BankCapture",
    Capability.FISCAL_CANCEL: "fiscal_cancellation_capture.FiscalCancellationCapture",
})
REGISTRY = MappingProxyType({
    capability: CapabilitySpec(
        capability, DEPENDENCIES[capability],
        next((cmd for cmd, cap in COMMAND_CAPABILITIES.items() if cap == capability), None),
        PRODUCERS.get(capability), True,
        ("human_confirmation", "privacy", "export", "continuity", "activation_generation")
        + (("durable_verified_fiscal_antecedent", "accepted_original_fiscal_record")
           if capability == Capability.FISCAL_CANCEL else ())
        if capability in PRODUCERS else ("preflight", "activation_generation"),
    ) for capability in Capability
})


def capability_for_command(command):
    """Contrato puro para D; nunca se conecta al routing en C."""
    return COMMAND_CAPABILITIES[CommandType(command)]


def specification(capability, *, version=REGISTRY_VERSION):
    if type(version) is not int or version != REGISTRY_VERSION:
        raise ValueError("Versión de capability registry desconocida.")
    return REGISTRY[Capability(capability)]


def dependencies_for(capability, *, fiscal_cancel_required):
    _, edges = Profile((Capability(capability),)).closure(
        fiscal_cancel_required=fiscal_cancel_required
    )
    return tuple(Capability(c) for c in edges[Capability(capability).value])


def require_command_capability(command, results, *, fiscal_cancel_required):
    """Solo predicado de consumo futuro: not_applicable jamás concede capability.

    El consumidor D deberá aportar grants revalidados por negocio/generación.
    Este mapping no es un recibo de activación ni autorización humana.
    """
    requested = capability_for_command(command)
    normalized = {}
    for capability, result in results.items():
        key = Capability(capability)
        if key in normalized:
            raise ValueError("Capability repetida.")
        normalized[key] = CapabilityResult(result)
    closure, _ = Profile((requested,)).closure(fiscal_cancel_required=fiscal_cancel_required)
    if any(normalized.get(c) != CapabilityResult.ELIGIBLE for c in closure):
        raise StateError("Capability o dependencia no concedida.")
    return requested
