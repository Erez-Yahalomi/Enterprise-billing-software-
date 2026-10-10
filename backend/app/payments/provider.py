class MockPaymentProvider:
    """Deterministic mock payment gateway. No real money ever moves.

    Used both for the local demo and in CI, matching the spec's requirement that no
    paid payment provider be required to run the demo or pass tests.
    """

    def charge(self, amount_cents: int) -> str:
        if amount_cents <= 0:
            return "failed"
        return "succeeded"


def get_payment_provider() -> MockPaymentProvider:
    return MockPaymentProvider()
