"""DPI (Digital Public Infrastructure) Adapter Registry for BharatSetu AI.
Selects mock vs real implementations based on DPI_MODE environment variable.
Enforces explicit consent tracking in the audit log for all data queries.
"""
from typing import Dict, Any
from .. import config
from .base import DPIAdapter
from .account_aggregator import AccountAggregatorAdapter
from .gst_sandbox import GSTSandboxAdapter
from .digilocker import DigiLockerAdapter
from .udyam import UdyamAdapter
from .einvoicing import EInvoicingAdapter
from .upi import UPIPaymentAdapter
from .ulip import ULIPAdapter
from .treds import TReDSAdapter

IS_MOCK = config.DPI_MODE != "real"

ADAPTERS: Dict[str, DPIAdapter] = {
    "account_aggregator": AccountAggregatorAdapter(is_mock=IS_MOCK),
    "gst": GSTSandboxAdapter(is_mock=IS_MOCK),
    "digilocker": DigiLockerAdapter(is_mock=IS_MOCK),
    "udyam": UdyamAdapter(is_mock=IS_MOCK),
    "einvoicing": EInvoicingAdapter(is_mock=IS_MOCK),
    "upi": UPIPaymentAdapter(is_mock=IS_MOCK),
    "ulip": ULIPAdapter(is_mock=IS_MOCK),
    "treds": TReDSAdapter(is_mock=IS_MOCK)
}

def get_adapter(name: str) -> DPIAdapter:
    key = name.lower()
    if key not in ADAPTERS:
        raise ValueError(f"Unknown DPI adapter '{name}'. Available: {list(ADAPTERS.keys())}")
    return ADAPTERS[key]

__all__ = [
    "DPIAdapter",
    "get_adapter",
    "AccountAggregatorAdapter",
    "GSTSandboxAdapter",
    "DigiLockerAdapter",
    "UdyamAdapter",
    "EInvoicingAdapter",
    "UPIPaymentAdapter",
    "ULIPAdapter",
    "TReDSAdapter"
]
