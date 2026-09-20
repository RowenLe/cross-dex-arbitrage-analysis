from web3 import Web3


# ============================================================
# Minimal ABIs
# ============================================================

UNISWAP_V3_FACTORY_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "tokenA", "type": "address"},
            {"internalType": "address", "name": "tokenB", "type": "address"},
            {"internalType": "uint24", "name": "fee", "type": "uint24"},
        ],
        "name": "getPool",
        "outputs": [
            {"internalType": "address", "name": "pool", "type": "address"}
        ],
        "stateMutability": "view",
        "type": "function",
    }
]


UNISWAP_V3_POOL_ABI = [
    {
        "inputs": [],
        "name": "token0",
        "outputs": [
            {"internalType": "address", "name": "", "type": "address"}
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "token1",
        "outputs": [
            {"internalType": "address", "name": "", "type": "address"}
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "fee",
        "outputs": [
            {"internalType": "uint24", "name": "", "type": "uint24"}
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "liquidity",
        "outputs": [
            {"internalType": "uint128", "name": "", "type": "uint128"}
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "slot0",
        "outputs": [
            {
                "internalType": "uint160",
                "name": "sqrtPriceX96",
                "type": "uint160",
            },
            {
                "internalType": "int24",
                "name": "tick",
                "type": "int24",
            },
            {
                "internalType": "uint16",
                "name": "observationIndex",
                "type": "uint16",
            },
            {
                "internalType": "uint16",
                "name": "observationCardinality",
                "type": "uint16",
            },
            {
                "internalType": "uint16",
                "name": "observationCardinalityNext",
                "type": "uint16",
            },
            {
                "internalType": "uint8",
                "name": "feeProtocol",
                "type": "uint8",
            },
            {
                "internalType": "bool",
                "name": "unlocked",
                "type": "bool",
            },
        ],
        "stateMutability": "view",
        "type": "function",
    },
]


UNISWAP_V3_QUOTER_V2_ABI = [
    {
        "inputs": [
            {
                "components": [
                    {
                        "internalType": "address",
                        "name": "tokenIn",
                        "type": "address",
                    },
                    {
                        "internalType": "address",
                        "name": "tokenOut",
                        "type": "address",
                    },
                    {
                        "internalType": "uint256",
                        "name": "amountIn",
                        "type": "uint256",
                    },
                    {
                        "internalType": "uint24",
                        "name": "fee",
                        "type": "uint24",
                    },
                    {
                        "internalType": "uint160",
                        "name": "sqrtPriceLimitX96",
                        "type": "uint160",
                    },
                ],
                "internalType": "struct IQuoterV2.QuoteExactInputSingleParams",
                "name": "params",
                "type": "tuple",
            }
        ],
        "name": "quoteExactInputSingle",
        "outputs": [
            {
                "internalType": "uint256",
                "name": "amountOut",
                "type": "uint256",
            },
            {
                "internalType": "uint160",
                "name": "sqrtPriceX96After",
                "type": "uint160",
            },
            {
                "internalType": "uint32",
                "name": "initializedTicksCrossed",
                "type": "uint32",
            },
            {
                "internalType": "uint256",
                "name": "gasEstimate",
                "type": "uint256",
            },
        ],
        "stateMutability": "nonpayable",
        "type": "function",
    }
]


ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


# ============================================================
# Pool discovery
# ============================================================

def get_pool_address(
    w3: Web3,
    factory_address: str,
    token_a: str,
    token_b: str,
    fee: int,
    block_number: int,
) -> str | None:
    """
    Return the Uniswap V3 pool address
    for a token pair and fee tier.
    """

    factory = w3.eth.contract(
        address=Web3.to_checksum_address(factory_address),
        abi=UNISWAP_V3_FACTORY_ABI,
    )

    pool_address = factory.functions.getPool(
        Web3.to_checksum_address(token_a),
        Web3.to_checksum_address(token_b),
        fee,
    ).call(
        block_identifier=block_number
    )

    if pool_address == ZERO_ADDRESS:
        return None

    return Web3.to_checksum_address(pool_address)


# ============================================================
# Pool state
# ============================================================

def get_pool_snapshot(
    w3: Web3,
    factory_address: str,
    token_a: str,
    token_b: str,
    fee: int,
    block_number: int,
) -> dict | None:
    """
    Read the main state variables
    of a Uniswap V3 pool.
    """

    pool_address = get_pool_address(
        w3=w3,
        factory_address=factory_address,
        token_a=token_a,
        token_b=token_b,
        fee=fee,
        block_number=block_number,
    )

    if pool_address is None:
        return None

    pool = w3.eth.contract(
        address=pool_address,
        abi=UNISWAP_V3_POOL_ABI,
    )

    token0 = pool.functions.token0().call(
        block_identifier=block_number
    )

    token1 = pool.functions.token1().call(
        block_identifier=block_number
    )

    pool_fee = pool.functions.fee().call(
        block_identifier=block_number
    )

    liquidity = pool.functions.liquidity().call(
        block_identifier=block_number
    )

    slot0 = pool.functions.slot0().call(
        block_identifier=block_number
    )

    return {
        "block": block_number,
        "pool": pool_address,
        "token0": token0,
        "token1": token1,
        "fee": pool_fee,
        "liquidity": liquidity,
        "sqrtPriceX96": slot0[0],
        "tick": slot0[1],
    }


# ============================================================
# Quoter V2
# ============================================================

def quote_exact_input_single(
    w3: Web3,
    quoter_address: str,
    token_in: str,
    token_out: str,
    amount_in: int,
    fee: int,
    block_number: int,
    sqrt_price_limit_x96: int = 0,
) -> dict:
    """
    Quote an exact-input Uniswap V3 swap using QuoterV2.

    amount_in and amount_out are raw token units.

    Example:
        token_in  = WETH
        token_out = USDC
        amount_in = WETH amount in wei

    Returns:
        amount_out
        sqrtPriceX96After
        initializedTicksCrossed
        gasEstimate
    """

    if amount_in <= 0:
        raise ValueError(
            "amount_in must be greater than zero."
        )

    quoter = w3.eth.contract(
        address=Web3.to_checksum_address(quoter_address),
        abi=UNISWAP_V3_QUOTER_V2_ABI,
    )

    params = (
        Web3.to_checksum_address(token_in),
        Web3.to_checksum_address(token_out),
        amount_in,
        fee,
        sqrt_price_limit_x96,
    )

    result = quoter.functions.quoteExactInputSingle(
        params
    ).call(
        block_identifier=block_number
    )

    return {
        "amount_out": result[0],
        "sqrtPriceX96After": result[1],
        "initializedTicksCrossed": result[2],
        "gasEstimate": result[3],
    }