"""Provider boundary reserved for verified integrations; no fake successful payments.

The first release records external settlement evidence entered by authorized staff.
Those records do NOT imply that DATUS contacted M-Pesa, a bank, or a card processor.
See docs/PAYMENTS.md for the lifecycle required before enabling a provider.
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class VerifiedSettlement:
    provider: str
    reference: str
    amount: Decimal
    currency: str
    merchant_account: str


class PaymentProvider(Protocol):
    def verify(self, reference: str) -> VerifiedSettlement:
        """Verify against the provider server; never trust the browser's success flag."""
        ...


class UnconfiguredProvider:
    def verify(self, reference: str) -> VerifiedSettlement:
        raise RuntimeError('No live payment provider is configured. Payment remains unverified.')
