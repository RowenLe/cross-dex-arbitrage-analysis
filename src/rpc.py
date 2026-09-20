from datetime import datetime, timezone

from web3 import Web3

from config.config import ETH_RPC_URL, CHAIN_ID


def get_web3() -> Web3:
    """Create and validate an Ethereum Mainnet RPC connection."""

    if not ETH_RPC_URL:
        raise ValueError(
            "ETH_RPC_URL is not set. Please add it to the .env file."
        )

    w3 = Web3(
        Web3.HTTPProvider(
            ETH_RPC_URL,
            request_kwargs={"timeout": 20},
        )
    )

    if not w3.is_connected():
        raise ConnectionError("Failed to connect to Ethereum RPC.")

    actual_chain_id = w3.eth.chain_id

    if actual_chain_id != CHAIN_ID:
        raise ValueError(
            f"Wrong network: expected chain ID {CHAIN_ID}, "
            f"got {actual_chain_id}."
        )

    return w3


def get_latest_block(w3: Web3) -> int:
    """Return the latest Ethereum block number."""

    return w3.eth.block_number


def get_block_timestamp(
    w3: Web3,
    block_number: int,
) -> datetime:
    """Return the UTC timestamp of a block."""

    block = w3.eth.get_block(block_number)

    return datetime.fromtimestamp(
        block["timestamp"],
        tz=timezone.utc,
    )