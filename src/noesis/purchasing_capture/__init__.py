"""Productores internos de recibidas y gastos; sin canales ni autoridad IA."""

from .service import ExpenseCapture, SupplierInvoiceCapture

__all__ = ["ExpenseCapture", "SupplierInvoiceCapture"]
