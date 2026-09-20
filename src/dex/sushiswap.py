from web3 import Web3


# ============================================================
# Minimal ABIs
# ============================================================

SUSHISWAP_V2_FACTORY_ABI = [
    {
        "inputs": [
            {
                "internalType": "address",
                "name": "tokenA",
                "type": "address",
            },
            {
                "internalType": "address",
                "name": "tokenB",
                "type": "address",
            },
        ],
        "name": "getPair",
        "outputs": [
            {
                "internalType": "address",
                "name": "pair",
                "type": "address",
            }
        ],
        "stateMutability": "view",
        "type": "function",
    }
]


SUSHISWAP_V2_PAIR_ABI = [
    {
        "inputs": [],
        "name": "token0",
        "outputs": [
            {
                "internalType": "address",
                "name": "",
                "type": "address",
            }
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "token1",
        "outputs": [
            {
                "internalType": "address",
                "name": "",
                "type": "address",
            }
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "getReserves",
        "outputs": [
            {
                "internalType": "uint112",
                "name": "_reserve0",
                "type": "uint112",
            },
            {
                "internalType": "uint112",
                "name": "_reserve1",
                "type": "uint112",
            },
            {
                "internalType": "uint32",
                "name": "_blockTimestampLast",
                "type": "uint32",
            },
        ],
        "stateMutability": "view",
        "type": "function",
    },
]


ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


# ============================================================
# Pair discovery
# ============================================================

def get_pair_address(
    w3: Web3,
    factory_address: str,
    token_a: str,
    token_b: str,
    block_number: int,
) -> str | None:
    """Return the SushiSwap V2 pair address for two tokens."""

    factory = w3.eth.contract(
        address=Web3.to_checksum_address(factory_address),
        abi=SUSHISWAP_V2_FACTORY_ABI,
    )

    pair_address = factory.functions.getPair(
        Web3.to_checksum_address(token_a),
        Web3.to_checksum_address(token_b),
    ).call(
        block_identifier=block_number
    )

    if pair_address == ZERO_ADDRESS:
        return None

    return Web3.to_checksum_address(pair_address)


# ============================================================
# Pair state
# ============================================================

def get_pair_snapshot(
    w3: Web3,
    factory_address: str,
    token_a: str,
    token_b: str,
    block_number: int,
) -> dict | None:
    """Read the main state variables of a SushiSwap V2 pair."""

    pair_address = get_pair_address(
        w3=w3,
        factory_address=factory_address,
        token_a=token_a,
        token_b=token_b,
        block_number=block_number,
    )

    if pair_address is None:
        return None

    pair = w3.eth.contract(
        address=pair_address,
        abi=SUSHISWAP_V2_PAIR_ABI,
    )

    token0 = pair.functions.token0().call(
        block_identifier=block_number
    )

    token1 = pair.functions.token1().call(
        block_identifier=block_number
    )

    reserves = pair.functions.getReserves().call(
        block_identifier=block_number
    )

    return {
        "block": block_number,
        "pair": pair_address,
        "token0": token0,
        "token1": token1,
        "reserve0": reserves[0],
        "reserve1": reserves[1],
        "blockTimestampLast": reserves[2],
    }