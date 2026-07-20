import unittest

from noesis.adapters import invoicing


class NativeInvoicingDecisionTests(unittest.TestCase):
    def test_provider_is_always_noesis_native(self):
        provider = invoicing.get_provider()

        self.assertIsInstance(provider, invoicing.InternalInvoicingProvider)
        self.assertFalse(hasattr(invoicing, "HoldedInvoicingProvider"))


if __name__ == "__main__":
    unittest.main()
