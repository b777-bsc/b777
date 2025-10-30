import secrets
from eth_account import Account
from eth_account.messages import encode_typed_data
from eth_utils import to_checksum_address
import time

def process_payment(requirements: dict, private_key: str) -> dict:
    """Sign payment authorization with EIP-712"""
    
    account = Account.from_key(private_key)
    
    now = int(time.time())
    valid_before = now + requirements["maxTimeoutSeconds"]
    nonce = "0x" + secrets.token_hex(32)
    
    authorization = {
        "from": to_checksum_address(account.address),
        "to": to_checksum_address(requirements["payTo"]),
        "value": int(requirements["maxAmountRequired"]),
        "validAfter": 0,
        "validBefore": valid_before,
        "nonce": bytes.fromhex(nonce[2:]),
    }
    
    domain = {
        "name": "B402",
        "version": "1",
        "chainId": 56 if requirements["network"] == "bsc" else 97,
        "verifyingContract": to_checksum_address(requirements["relayerContract"]),
    }
    
    types = {
        "TransferWithAuthorization": [
            {"name": "from", "type": "address"},
            {"name": "to", "type": "address"},
            {"name": "value", "type": "uint256"},
            {"name": "validAfter", "type": "uint256"},
            {"name": "validBefore", "type": "uint256"},
            {"name": "nonce", "type": "bytes32"},
        ]
    }
    
    message = encode_typed_data(
        domain_data=domain,
        message_types=types,
        message_data=authorization
    )
    
    signed = account.sign_message(message)
    
    return {
        "x402Version": 1,
        "scheme": "exact",
        "network": requirements["network"],
        "token": requirements["asset"],
        "payload": {
            "authorization": {
                "from": authorization["from"],
                "to": authorization["to"],
                "value": str(authorization["value"]),
                "validAfter": str(authorization["validAfter"]),
                "validBefore": str(authorization["validBefore"]),
                "nonce": nonce,
            },
            "signature": "0x" + signed.signature.hex(),
        },
    }
