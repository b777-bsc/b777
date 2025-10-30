from dataclasses import dataclass
from typing import Literal

@dataclass
class PaymentResult:
    success: bool
    tx_hash: str | None = None
    error: str | None = None
    payer: str = ""
    recipient: str = ""
    amount: str = ""
    token: str = ""

TokenType = Literal["USD1", "USDT", "USDC"]
NetworkType = Literal["mainnet", "testnet"]
