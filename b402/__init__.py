"""B402 SDK for Python - Gasless crypto payments on BSC"""

from .client import B402, pay
from .types import PaymentResult
from .approval import check_approval, approve_token, ensure_approval

__version__ = "1.2.1"
__all__ = ["B402", "pay", "PaymentResult", "check_approval", "approve_token", "ensure_approval"]
