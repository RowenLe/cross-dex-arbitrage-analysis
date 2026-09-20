from decimal import Decimal

from web3 import Web3

from src.dex.uniswap_v3 import quote_exact_input_single


# ============================================================
# Spot spread
# ============================================================

def analyze_spot_spread(
    uni_price: Decimal,
    sushi_price: Decimal,
) -> dict:
    """
    Compare same-block Uniswap V3 and SushiSwap V2 spot prices.

    Prices use:

        USDC per WETH

    signed_spread:
        SushiSwap price - Uniswap price

    relative_spread_pct:
        Absolute spread relative to the cheaper DEX.
    """

    if uni_price <= 0 or sushi_price <= 0:
        raise ValueError(
            "DEX prices must be greater than zero."
        )

    signed_spread = sushi_price - uni_price
    absolute_spread = abs(signed_spread)

    cheaper_price = min(
        uni_price,
        sushi_price,
    )

    relative_spread_pct = (
        absolute_spread
        / cheaper_price
        * Decimal(100)
    )

    if uni_price < sushi_price:
        buy_dex = "Uniswap V3"
        sell_dex = "SushiSwap V2"

    elif sushi_price < uni_price:
        buy_dex = "SushiSwap V2"
        sell_dex = "Uniswap V3"

    else:
        buy_dex = "None"
        sell_dex = "None"

    return {
        "signed_spread": signed_spread,
        "absolute_spread": absolute_spread,
        "relative_spread_pct": relative_spread_pct,
        "buy_dex": buy_dex,
        "sell_dex": sell_dex,
    }


# ============================================================
# Fee-only theoretical arbitrage
# ============================================================

def estimate_fee_only_arbitrage(
    amount_in_usdc: Decimal,
    uni_price: Decimal,
    sushi_price: Decimal,
    uni_fee_rate: Decimal,
    sushi_fee_rate: Decimal,
) -> dict:
    """
    Estimate two-leg arbitrage using spot prices and fees only.

    Does NOT include:
        - AMM price impact
        - gas
    """

    if amount_in_usdc <= 0:
        raise ValueError(
            "amount_in_usdc must be greater than zero."
        )

    for fee_rate in (
        uni_fee_rate,
        sushi_fee_rate,
    ):
        if fee_rate < 0 or fee_rate >= 1:
            raise ValueError(
                "Fee rate must be between 0 and 1."
            )

    spread = analyze_spot_spread(
        uni_price=uni_price,
        sushi_price=sushi_price,
    )

    if uni_price < sushi_price:
        buy_price = uni_price
        sell_price = sushi_price

        buy_dex = "Uniswap V3"
        sell_dex = "SushiSwap V2"

        buy_fee_rate = uni_fee_rate
        sell_fee_rate = sushi_fee_rate

    elif sushi_price < uni_price:
        buy_price = sushi_price
        sell_price = uni_price

        buy_dex = "SushiSwap V2"
        sell_dex = "Uniswap V3"

        buy_fee_rate = sushi_fee_rate
        sell_fee_rate = uni_fee_rate

    else:
        return {
            **spread,
            "amount_in_usdc": amount_in_usdc,
            "final_usdc": amount_in_usdc,
            "profit_usdc": Decimal(0),
            "return_pct": Decimal(0),
        }

    # --------------------------------------------------------
    # First leg: USDC -> WETH
    # --------------------------------------------------------

    usdc_after_buy_fee = (
        amount_in_usdc
        * (Decimal(1) - buy_fee_rate)
    )

    weth_received = (
        usdc_after_buy_fee
        / buy_price
    )

    # --------------------------------------------------------
    # Second leg: WETH -> USDC
    # --------------------------------------------------------

    weth_after_sell_fee = (
        weth_received
        * (Decimal(1) - sell_fee_rate)
    )

    final_usdc = (
        weth_after_sell_fee
        * sell_price
    )

    # --------------------------------------------------------
    # Profit
    # --------------------------------------------------------

    profit_usdc = (
        final_usdc
        - amount_in_usdc
    )

    return_pct = (
        profit_usdc
        / amount_in_usdc
        * Decimal(100)
    )

    return {
        **spread,
        "buy_dex": buy_dex,
        "sell_dex": sell_dex,
        "amount_in_usdc": amount_in_usdc,
        "buy_fee_rate": buy_fee_rate,
        "sell_fee_rate": sell_fee_rate,
        "weth_received": weth_received,
        "final_usdc": final_usdc,
        "profit_usdc": profit_usdc,
        "return_pct": return_pct,
    }


# ============================================================
# SushiSwap V2 exact constant-product quote
# ============================================================

def sushiswap_v2_amount_out(
    amount_in: int,
    reserve_in: int,
    reserve_out: int,
) -> int:
    """
    Exact SushiSwap V2 amountOut calculation.

    All values use raw token units.

    997 / 1000 already includes the
    SushiSwap V2 0.30% swap fee.
    """

    if amount_in <= 0:
        raise ValueError(
            "amount_in must be greater than zero."
        )

    if reserve_in <= 0 or reserve_out <= 0:
        raise ValueError(
            "Pool reserves must be greater than zero."
        )

    amount_in_with_fee = (
        amount_in * 997
    )

    numerator = (
        amount_in_with_fee
        * reserve_out
    )

    denominator = (
        reserve_in * 1000
        + amount_in_with_fee
    )

    return numerator // denominator


# ============================================================
# SushiSwap V2: USDC -> WETH
# ============================================================

def quote_sushiswap_usdc_to_weth(
    amount_in_usdc: Decimal,
    reserve_usdc: int,
    reserve_weth: int,
    usdc_decimals: int = 6,
    weth_decimals: int = 18,
) -> dict:
    """
    Quote SushiSwap V2:

        USDC -> WETH

    Includes:
        - 0.30% fee
        - AMM price impact

    Does NOT include:
        - gas
    """

    if amount_in_usdc <= 0:
        raise ValueError(
            "amount_in_usdc must be greater than zero."
        )

    amount_in_raw = int(
        amount_in_usdc
        * Decimal(10 ** usdc_decimals)
    )

    amount_out_raw = sushiswap_v2_amount_out(
        amount_in=amount_in_raw,
        reserve_in=reserve_usdc,
        reserve_out=reserve_weth,
    )

    weth_out = (
        Decimal(amount_out_raw)
        / Decimal(10 ** weth_decimals)
    )

    if weth_out <= 0:
        raise ValueError(
            "SushiSwap quote returned zero WETH."
        )

    # Pool spot price before trade
    reserve_usdc_normalized = (
        Decimal(reserve_usdc)
        / Decimal(10 ** usdc_decimals)
    )

    reserve_weth_normalized = (
        Decimal(reserve_weth)
        / Decimal(10 ** weth_decimals)
    )

    spot_price = (
        reserve_usdc_normalized
        / reserve_weth_normalized
    )

    # Actual average execution price
    effective_price = (
        amount_in_usdc
        / weth_out
    )

    # Infinite-liquidity benchmark with fee only
    fee_rate = Decimal("0.003")

    fee_only_weth = (
        amount_in_usdc
        * (Decimal(1) - fee_rate)
        / spot_price
    )

    # AMM curve impact excluding fee
    amm_price_impact_pct = (
        (fee_only_weth - weth_out)
        / fee_only_weth
        * Decimal(100)
    )

    # Total deterioration vs spot
    total_execution_impact_pct = (
        (
            effective_price
            / spot_price
        )
        - Decimal(1)
    ) * Decimal(100)

    return {
        "amount_in_usdc": amount_in_usdc,
        "amount_in_raw": amount_in_raw,
        "amount_out_raw": amount_out_raw,
        "weth_out": weth_out,
        "spot_price_usdc_per_weth": spot_price,
        "effective_price_usdc_per_weth": effective_price,
        "fee_only_weth": fee_only_weth,
        "amm_price_impact_pct": amm_price_impact_pct,
        "total_execution_impact_pct": total_execution_impact_pct,
    }


# ============================================================
# SushiSwap V2: WETH -> USDC
# ============================================================

def quote_sushiswap_weth_to_usdc(
    amount_in_weth: Decimal,
    reserve_weth: int,
    reserve_usdc: int,
    weth_decimals: int = 18,
    usdc_decimals: int = 6,
) -> dict:
    """
    Quote SushiSwap V2:

        WETH -> USDC

    Includes:
        - 0.30% fee
        - AMM price impact

    Does NOT include:
        - gas
    """

    if amount_in_weth <= 0:
        raise ValueError(
            "amount_in_weth must be greater than zero."
        )

    amount_in_raw = int(
        amount_in_weth
        * Decimal(10 ** weth_decimals)
    )

    amount_out_raw = sushiswap_v2_amount_out(
        amount_in=amount_in_raw,
        reserve_in=reserve_weth,
        reserve_out=reserve_usdc,
    )

    usdc_out = (
        Decimal(amount_out_raw)
        / Decimal(10 ** usdc_decimals)
    )

    if usdc_out <= 0:
        raise ValueError(
            "SushiSwap quote returned zero USDC."
        )

    return {
        "amount_in_weth": amount_in_weth,
        "amount_in_raw": amount_in_raw,
        "amount_out_raw": amount_out_raw,
        "usdc_out": usdc_out,
    }


# ============================================================
# Executable route A:
# SushiSwap V2 -> Uniswap V3
# ============================================================

def simulate_sushi_to_uniswap(
    w3: Web3,
    block_number: int,
    amount_in_usdc: Decimal,
    sushi_reserve_usdc: int,
    sushi_reserve_weth: int,
    uniswap_quoter_address: str,
    weth_address: str,
    usdc_address: str,
    uniswap_fee: int = 500,
    usdc_decimals: int = 6,
    weth_decimals: int = 18,
) -> dict:
    """
    Same-block executable simulation:

        USDC
          ↓
        SushiSwap V2
          ↓
        WETH
          ↓
        Uniswap V3
          ↓
        USDC

    Includes:
        - SushiSwap fee
        - SushiSwap price impact
        - Uniswap V3 fee
        - Uniswap V3 liquidity / tick effects

    Does NOT yet subtract:
        - gas
    """

    if amount_in_usdc <= 0:
        raise ValueError(
            "amount_in_usdc must be greater than zero."
        )

    # --------------------------------------------------------
    # Leg 1: SushiSwap
    # USDC -> WETH
    # --------------------------------------------------------

    sushi_quote = quote_sushiswap_usdc_to_weth(
        amount_in_usdc=amount_in_usdc,
        reserve_usdc=sushi_reserve_usdc,
        reserve_weth=sushi_reserve_weth,
        usdc_decimals=usdc_decimals,
        weth_decimals=weth_decimals,
    )

    weth_out_raw = sushi_quote["amount_out_raw"]
    weth_out = sushi_quote["weth_out"]

    # --------------------------------------------------------
    # Leg 2: Uniswap V3
    # WETH -> USDC
    # --------------------------------------------------------

    uni_quote = quote_exact_input_single(
        w3=w3,
        quoter_address=uniswap_quoter_address,
        token_in=weth_address,
        token_out=usdc_address,
        amount_in=weth_out_raw,
        fee=uniswap_fee,
        block_number=block_number,
    )

    final_usdc = (
        Decimal(uni_quote["amount_out"])
        / Decimal(10 ** usdc_decimals)
    )

    # --------------------------------------------------------
    # Two-leg PnL before gas
    # --------------------------------------------------------

    profit_before_gas_usdc = (
        final_usdc
        - amount_in_usdc
    )

    return_before_gas_pct = (
        profit_before_gas_usdc
        / amount_in_usdc
        * Decimal(100)
    )

    profitable_before_gas = (
        profit_before_gas_usdc > 0
    )

    return {
        "block": block_number,
        "route": "SushiSwap V2 -> Uniswap V3",
        "amount_in_usdc": amount_in_usdc,

        "sushi_weth_out": weth_out,
        "sushi_weth_out_raw": weth_out_raw,
        "sushi_effective_price": (
            sushi_quote["effective_price_usdc_per_weth"]
        ),
        "sushi_amm_price_impact_pct": (
            sushi_quote["amm_price_impact_pct"]
        ),
        "sushi_total_execution_impact_pct": (
            sushi_quote["total_execution_impact_pct"]
        ),

        "uniswap_usdc_out_raw": (
            uni_quote["amount_out"]
        ),
        "final_usdc": final_usdc,

        "uniswap_sqrtPriceX96_after": (
            uni_quote["sqrtPriceX96After"]
        ),
        "uniswap_ticks_crossed": (
            uni_quote["initializedTicksCrossed"]
        ),
        "uniswap_quote_gas_estimate": (
            uni_quote["gasEstimate"]
        ),

        "profit_before_gas_usdc": (
            profit_before_gas_usdc
        ),
        "return_before_gas_pct": (
            return_before_gas_pct
        ),
        "profitable_before_gas": (
            profitable_before_gas
        ),
    }


# ============================================================
# Executable route B:
# Uniswap V3 -> SushiSwap V2
# ============================================================

def simulate_uniswap_to_sushi(
    w3: Web3,
    block_number: int,
    amount_in_usdc: Decimal,
    sushi_reserve_usdc: int,
    sushi_reserve_weth: int,
    uniswap_quoter_address: str,
    weth_address: str,
    usdc_address: str,
    uniswap_fee: int = 500,
    usdc_decimals: int = 6,
    weth_decimals: int = 18,
) -> dict:
    """
    Same-block executable simulation:

        USDC
          ↓
        Uniswap V3
          ↓
        WETH
          ↓
        SushiSwap V2
          ↓
        USDC

    Includes:
        - Uniswap V3 fee
        - Uniswap V3 liquidity / tick effects
        - SushiSwap fee
        - SushiSwap price impact

    Does NOT yet subtract:
        - gas
    """

    if amount_in_usdc <= 0:
        raise ValueError(
            "amount_in_usdc must be greater than zero."
        )

    # --------------------------------------------------------
    # Convert USDC to raw units
    # --------------------------------------------------------

    amount_in_usdc_raw = int(
        amount_in_usdc
        * Decimal(10 ** usdc_decimals)
    )

    # --------------------------------------------------------
    # Leg 1: Uniswap V3
    # USDC -> WETH
    # --------------------------------------------------------

    uni_quote = quote_exact_input_single(
        w3=w3,
        quoter_address=uniswap_quoter_address,
        token_in=usdc_address,
        token_out=weth_address,
        amount_in=amount_in_usdc_raw,
        fee=uniswap_fee,
        block_number=block_number,
    )

    weth_out_raw = uni_quote["amount_out"]

    weth_out = (
        Decimal(weth_out_raw)
        / Decimal(10 ** weth_decimals)
    )

    if weth_out <= 0:
        raise ValueError(
            "Uniswap V3 quote returned zero WETH."
        )

    # --------------------------------------------------------
    # Leg 2: SushiSwap V2
    # WETH -> USDC
    # --------------------------------------------------------

    sushi_quote = quote_sushiswap_weth_to_usdc(
        amount_in_weth=weth_out,
        reserve_weth=sushi_reserve_weth,
        reserve_usdc=sushi_reserve_usdc,
        weth_decimals=weth_decimals,
        usdc_decimals=usdc_decimals,
    )

    final_usdc = sushi_quote["usdc_out"]

    # --------------------------------------------------------
    # Two-leg PnL before gas
    # --------------------------------------------------------

    profit_before_gas_usdc = (
        final_usdc
        - amount_in_usdc
    )

    return_before_gas_pct = (
        profit_before_gas_usdc
        / amount_in_usdc
        * Decimal(100)
    )

    profitable_before_gas = (
        profit_before_gas_usdc > 0
    )

    return {
        "block": block_number,
        "route": "Uniswap V3 -> SushiSwap V2",
        "amount_in_usdc": amount_in_usdc,

        "uniswap_weth_out": weth_out,
        "uniswap_weth_out_raw": weth_out_raw,
        "uniswap_sqrtPriceX96_after": (
            uni_quote["sqrtPriceX96After"]
        ),
        "uniswap_ticks_crossed": (
            uni_quote["initializedTicksCrossed"]
        ),
        "uniswap_quote_gas_estimate": (
            uni_quote["gasEstimate"]
        ),

        "sushi_usdc_out_raw": (
            sushi_quote["amount_out_raw"]
        ),
        "final_usdc": final_usdc,

        "profit_before_gas_usdc": (
            profit_before_gas_usdc
        ),
        "return_before_gas_pct": (
            return_before_gas_pct
        ),
        "profitable_before_gas": (
            profitable_before_gas
        ),
    }