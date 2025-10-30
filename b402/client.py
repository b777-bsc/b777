import os
import requests
from .types import PaymentResult, TokenType, NetworkType
from .wallet import process_payment
from .approval import check_approval, ensure_approval
from eth_account import Account

class B402:
    TOKENS = {
        "mainnet": {
            "USD1": "0x8d0d000ee44948fc98c9b98a4fa4921476f08b0d",
            "USDT": "0x55d398326f99059fF775485246999027B3197955",
            "USDC": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
        },
        "testnet": {
            "USDT": "0x337610d27c682E347C9cD60BD4b3b107C9d34dDd",
        }
    }
    
    RELAYERS = {
        "mainnet": "0xE1C2830d5DDd6B49E9c46EbE03a98Cb44CD8eA5a",
        "testnet": "0x62150F2c3A29fDA8bCf22c0F22Eb17270FCBb78A",
    }
    
    def __init__(self, network: NetworkType = "mainnet", facilitator_url: str = "https://facilitator.b402.ai", debug: bool = False):
        self.network = network
        self.facilitator_url = facilitator_url.rstrip("/")
        self.debug = debug
    
    def pay(
        self,
        amount: str,
        token: TokenType,
        recipient: str,
        timeout_seconds: int = 3600,
        auto_approve: bool = True
    ) -> PaymentResult:
        """
        Send payment (reads PRIVATE_KEY from environment).

        Auto-checks approval and prompts to approve if needed.

        Args:
            amount: Amount to send (e.g. "0.01")
            token: Token symbol (USD1, USDT, USDC)
            recipient: Recipient address
            timeout_seconds: Payment timeout (default: 3600)
            auto_approve: If True, automatically approve if needed (costs gas once)
        """

        private_key = os.environ.get("PRIVATE_KEY")
        if not private_key:
            return PaymentResult(
                success=False,
                error="PRIVATE_KEY environment variable not set",
                payer="",
                recipient=recipient,
                amount=amount,
                token=token
            )

        try:
            account = Account.from_key(private_key)

            # Get token details
            token_address = self.TOKENS[self.network].get(token)
            if not token_address:
                return PaymentResult(
                    success=False,
                    error=f"Token {token} not supported on {self.network}",
                    payer=account.address,
                    recipient=recipient,
                    amount=amount,
                    token=token
                )

            # Calculate amount in wei
            amount_wei = int(float(amount) * 10**18)

            # Check if we have enough allowance for this specific payment
            is_approved, current_allowance = check_approval(
                private_key=private_key,
                token_address=token_address,
                spender_address=self.RELAYERS[self.network],
                network=self.network,
                min_amount=amount_wei
            )

            # Handle approval if needed
            if not is_approved:
                if not auto_approve:
                    allowance_readable = current_allowance / 10**18
                    needed_readable = amount_wei / 10**18
                    return PaymentResult(
                        success=False,
                        error=f"Insufficient allowance. Have: {allowance_readable:.4f} {token}, Need: {needed_readable:.4f} {token}. Run: b402.setup('{token}') or pay(..., auto_approve=True)",
                        payer=account.address,
                        recipient=recipient,
                        amount=amount,
                        token=token
                    )

                # Auto-approve with reasonable cap ($10k default)
                if self.debug:
                    print(f"[DEBUG] Insufficient allowance ({current_allowance / 10**18:.4f} {token})")
                    print(f"[DEBUG] Auto-approving {token} for up to $10,000...")

                try:
                    from .approval import approve_token
                    # Approve $10k worth (or amount needed, whichever is larger)
                    approval_amount = max(amount_wei, 10_000 * 10**18)

                    tx_hash = approve_token(
                        private_key=private_key,
                        token_address=token_address,
                        spender_address=self.RELAYERS[self.network],
                        network=self.network,
                        amount=approval_amount
                    )
                    if self.debug:
                        print(f"[DEBUG] Approved {approval_amount / 10**18:.0f} {token}!")
                        print(f"[DEBUG] TX: {tx_hash}")
                except Exception as approve_error:
                    return PaymentResult(
                        success=False,
                        error=f"Auto-approval failed: {str(approve_error)}. Please run: b402.setup('{token}')",
                        payer=account.address,
                        recipient=recipient,
                        amount=amount,
                        token=token
                    )

            # Proceed with payment
            requirements = {
                "scheme": "exact",
                "asset": token_address,
                "payTo": recipient,
                "maxAmountRequired": str(amount_wei),
                "maxTimeoutSeconds": timeout_seconds,
                "network": "bsc" if self.network == "mainnet" else "bsc-testnet",
                "relayerContract": self.RELAYERS[self.network],
            }
            
            payload = process_payment(requirements, private_key)

            if self.debug:
                print(f"[DEBUG] Requirements: {requirements}")
                print(f"[DEBUG] Payload: {payload}")

            verify_response = requests.post(
                f"{self.facilitator_url}/verify",
                json={"paymentPayload": payload, "paymentRequirements": requirements}
            )

            if verify_response.status_code != 200:
                return PaymentResult(
                    success=False,
                    error=f"Verify request failed: HTTP {verify_response.status_code} - {verify_response.text}",
                    payer=account.address,
                    recipient=recipient,
                    amount=amount,
                    token=token
                )

            verify_data = verify_response.json()

            if self.debug:
                print(f"[DEBUG] Verify response: {verify_data}")

            if not verify_data.get("isValid"):
                error_msg = verify_data.get("invalidReason", "Invalid signature")
                # Include full response for debugging
                error_detail = f"{error_msg} | Response: {verify_data}"
                return PaymentResult(
                    success=False,
                    error=error_detail,
                    payer=account.address,
                    recipient=recipient,
                    amount=amount,
                    token=token
                )
            
            settle_response = requests.post(
                f"{self.facilitator_url}/settle",
                json={"paymentPayload": payload, "paymentRequirements": requirements}
            )

            if settle_response.status_code != 200:
                return PaymentResult(
                    success=False,
                    error=f"Settle request failed: HTTP {settle_response.status_code} - {settle_response.text}",
                    payer=account.address,
                    recipient=recipient,
                    amount=amount,
                    token=token
                )

            settle_data = settle_response.json()

            error_detail = None
            if not settle_data.get("success", False):
                error_detail = settle_data.get("errorReason", "Unknown error")
                # Include response for debugging
                if settle_data:
                    error_detail = f"{error_detail} | Response: {settle_data}"

            return PaymentResult(
                success=settle_data.get("success", False),
                tx_hash=settle_data.get("transaction"),
                error=error_detail,
                payer=account.address,
                recipient=recipient,
                amount=amount,
                token=token
            )
            
        except Exception as e:
            return PaymentResult(
                success=False,
                error=str(e),
                payer="",
                recipient=recipient,
                amount=amount,
                token=token
            )
    
    def get_supported_tokens(self) -> list[str]:
        return list(self.TOKENS[self.network].keys())
    
    def get_token_address(self, token: TokenType) -> str | None:
        return self.TOKENS[self.network].get(token)

    def check_approval(self, token: TokenType) -> tuple[bool, int]:
        """
        Check if token is approved for B402 relayer.

        Returns:
            (is_approved, current_allowance)

        Example:
            approved, allowance = B402().check_approval("USD1")
            if not approved:
                print("Need to run setup first")
        """
        private_key = os.environ.get("PRIVATE_KEY")
        if not private_key:
            raise ValueError("PRIVATE_KEY environment variable not set")

        token_address = self.TOKENS[self.network].get(token)
        if not token_address:
            raise ValueError(f"Token {token} not supported on {self.network}")

        return check_approval(
            private_key=private_key,
            token_address=token_address,
            spender_address=self.RELAYERS[self.network],
            network=self.network
        )

    def setup(self, token: TokenType, auto_approve: bool = True) -> dict:
        """
        One-time setup: approve relayer to spend tokens.

        Args:
            token: Token to approve (USD1, USDT, USDC)
            auto_approve: If True, automatically approve. If False, only check.

        Returns:
            {
                "approved": bool,
                "allowance": int,
                "tx_hash": str | None
            }

        Example:
            result = B402().setup("USD1")
            if result["tx_hash"]:
                print(f"Approved! TX: {result['tx_hash']}")
            else:
                print("Already approved")
        """
        private_key = os.environ.get("PRIVATE_KEY")
        if not private_key:
            raise ValueError("PRIVATE_KEY environment variable not set")

        token_address = self.TOKENS[self.network].get(token)
        if not token_address:
            raise ValueError(f"Token {token} not supported on {self.network}")

        return ensure_approval(
            private_key=private_key,
            token_address=token_address,
            spender_address=self.RELAYERS[self.network],
            network=self.network,
            auto_approve=auto_approve
        )


# Factory function for ultra-simple one-line usage
def pay(
    amount: str,
    token: TokenType,
    recipient: str,
    network: NetworkType = "mainnet",
    timeout_seconds: int = 3600,
    auto_approve: bool = True,
    debug: bool = False
) -> PaymentResult:
    """
    One-line payment function with automatic approval.

    Auto-checks approval and approves if needed (costs gas first time only).

    Usage:
        from b402 import pay

        # Simplest - handles everything automatically
        result = pay(amount="0.01", token="USD1", recipient="0x...")

        # Or disable auto-approval
        result = pay(amount="0.01", token="USD1", recipient="0x...", auto_approve=False)

    Args:
        amount: Amount to send (e.g. "0.01")
        token: Token symbol (USD1, USDT, USDC)
        recipient: Recipient address
        network: "mainnet" or "testnet" (default: mainnet)
        timeout_seconds: Payment timeout (default: 3600)
        auto_approve: Auto-approve if needed (default: True, costs gas once)
        debug: Show detailed logs (default: False)

    Returns:
        PaymentResult with success, tx_hash, error, etc.
    """
    client = B402(network=network, debug=debug)
    return client.pay(
        amount=amount,
        token=token,
        recipient=recipient,
        timeout_seconds=timeout_seconds,
        auto_approve=auto_approve
    )
