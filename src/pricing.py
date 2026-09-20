from decimal import Decimal, getcontext


# Use high precision for on-chain price calculations
getcontext().prec = 50


# ============================================================
# Uniswap V3
# ============================================================

def uniswap_v3_token1_per_token0(
    sqrt_price_x96: int,
    token0_decimals: int,
    token1_decimals: int,
) -> Decimal:
    """
    Convert Uniswap V3 sqrtPriceX96 into the human-readable
    price of token1 in terms of token0.

    Example:
        token0 = USDC
        token1 = WETH

    Returns:
        WETH per USDC
    """

    sqrt_price = Decimal(sqrt_price_x96)

    # Raw token1 / token0 price
    raw_price = (
        sqrt_price ** 2
        / Decimal(2 ** 192)
    )

    # Adjust for token decimals
    decimal_adjustment = Decimal(10) ** (
        token0_decimals - token1_decimals
    )

    return raw_price * decimal_adjustment


def uniswap_v3_token0_per_token1(
    sqrt_price_x96: int,
    token0_decimals: int,
    token1_decimals: int,
) -> Decimal:
    """
    Return the human-readable price of token0 in terms of token1.

    Example:
        token0 = USDC
        token1 = WETH

    Returns:
        USDC per WETH
    """

    token1_per_token0 = uniswap_v3_token1_per_token0(
        sqrt_price_x96=sqrt_price_x96,
        token0_decimals=token0_decimals,
        token1_decimals=token1_decimals,
    )

    if token1_per_token0 == 0:
        raise ValueError("Uniswap V3 price cannot be zero.")

    return Decimal(1) / token1_per_token0


# ============================================================
# SushiSwap V2
# ============================================================

def sushiswap_v2_token1_per_token0(
    reserve0: int,
    reserve1: int,
    token0_decimals: int,
    token1_decimals: int,
) -> Decimal:
    """
    Convert SushiSwap V2 reserves into the human-readable
    price of token1 in terms of token0.

    Example:
        token0 = USDC
        token1 = WETH

    Returns:
        WETH per USDC
    """

    reserve0_normalized = (
        Decimal(reserve0)
        / Decimal(10 ** token0_decimals)
    )

    reserve1_normalized = (
        Decimal(reserve1)
        / Decimal(10 ** token1_decimals)
    )

    if reserve0_normalized == 0:
        raise ValueError("SushiSwap reserve0 cannot be zero.")

    return reserve1_normalized / reserve0_normalized


def sushiswap_v2_token0_per_token1(
    reserve0: int,
    reserve1: int,
    token0_decimals: int,
    token1_decimals: int,
) -> Decimal:
    """
    Return the human-readable price of token0 in terms of token1.

    Example:
        token0 = USDC
        token1 = WETH

    Returns:
        USDC per WETH
    """

    token1_per_token0 = sushiswap_v2_token1_per_token0(
        reserve0=reserve0,
        reserve1=reserve1,
        token0_decimals=token0_decimals,
        token1_decimals=token1_decimals,
    )

    if token1_per_token0 == 0:
        raise ValueError("SushiSwap V2 price cannot be zero.")

    return Decimal(1) / token1_per_token0