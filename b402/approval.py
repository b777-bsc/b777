"""Token approval utilities for B402 payments"""

from web3 import Web3
from eth_account import Account

# Minimal ERC-20 ABI
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [
            {"name": "owner", "type": "address"},
            {"name": "spender", "type": "address"}
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "amount", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    }
]

RPC_URLS = {
    "mainnet": "https://bsc-dataseed1.binance.org",
    "testnet": "https://data-seed-prebsc-1-s1.binance.org:8545"
}


def check_approval(
    private_key: str,
    token_address: str,
    spender_address: str,
    network: str = "mainnet",
    min_amount: int = 0
) -> tuple[bool, int]:
    """
    Check if token is approved for spender.

    Args:
        private_key: Wallet private key
        token_address: Token contract address
        spender_address: Spender (relayer) address
        network: "mainnet" or "testnet"
        min_amount: Minimum allowance required (default: any amount)

    Returns:
        (is_approved, current_allowance)
    """
    w3 = Web3(Web3.HTTPProvider(RPC_URLS[network]))
    account = Account.from_key(private_key)

    token = w3.eth.contract(
        address=Web3.to_checksum_address(token_address),
        abi=ERC20_ABI
    )

    allowance = token.functions.allowance(
        Web3.to_checksum_address(account.address),
        Web3.to_checksum_address(spender_address)
    ).call()

    return (allowance >= min_amount, allowance)


def approve_token(
    private_key: str,
    token_address: str,
    spender_address: str,
    network: str = "mainnet",
    amount: int | None = None
) -> str:
    """
    Approve token for spender.

    Args:
        private_key: Wallet private key
        token_address: Token contract address
        spender_address: Spender (relayer) address
        network: "mainnet" or "testnet"
        amount: Amount to approve in wei (defaults to $10,000 worth)

    Returns:
        Transaction hash
    """
    w3 = Web3(Web3.HTTPProvider(RPC_URLS[network]))
    account = Account.from_key(private_key)

    token = w3.eth.contract(
        address=Web3.to_checksum_address(token_address),
        abi=ERC20_ABI
    )

    # Default to $10,000 worth (reasonable cap, not infinite)
    # 10,000 * 10^18 = 10,000 tokens with 18 decimals
    if amount is None:
        amount = 10_000 * 10**18

    # Build transaction
    nonce = w3.eth.get_transaction_count(account.address)

    tx = token.functions.approve(
        Web3.to_checksum_address(spender_address),
        amount
    ).build_transaction({
        'from': account.address,
        'nonce': nonce,
        'gas': 100000,
        'gasPrice': w3.eth.gas_price,
    })

    # Sign and send
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)

    # Wait for confirmation
    w3.eth.wait_for_transaction_receipt(tx_hash)

    return "0x" + tx_hash.hex()


def ensure_approval(
    private_key: str,
    token_address: str,
    spender_address: str,
    network: str = "mainnet",
    auto_approve: bool = False
) -> dict:
    """
    Check approval and optionally approve if needed.

    Args:
        private_key: Wallet private key
        token_address: Token contract address
        spender_address: Spender (relayer) address
        network: "mainnet" or "testnet"
        auto_approve: If True, automatically approve if not approved

    Returns:
        {
            "approved": bool,
            "allowance": int,
            "tx_hash": str | None  # Set if approval was done
        }
    """
    is_approved, allowance = check_approval(
        private_key=private_key,
        token_address=token_address,
        spender_address=spender_address,
        network=network
    )

    if is_approved:
        return {
            "approved": True,
            "allowance": allowance,
            "tx_hash": None
        }

    if not auto_approve:
        return {
            "approved": False,
            "allowance": 0,
            "tx_hash": None
        }

    # Auto-approve
    tx_hash = approve_token(
        private_key=private_key,
        token_address=token_address,
        spender_address=spender_address,
        network=network
    )

    return {
        "approved": True,
        "allowance": 2**256 - 1,
        "tx_hash": tx_hash
    }
