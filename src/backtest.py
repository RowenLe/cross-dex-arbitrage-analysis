from decimal import Decimal

from src.rpc import get_block_timestamp

from src.dex.uniswap_v3 import get_pool_snapshot
from src.dex.sushiswap import get_pair_snapshot

from src.pricing import (
    uniswap_v3_token0_per_token1,
    sushiswap_v2_token0_per_token1,
)

from src.arbitrage import (
    analyze_spot_spread,
    simulate_sushi_to_uniswap,
    simulate_uniswap_to_sushi,
)

from src.gas import (
    estimate_block_gas_cost,
)

from config.config import (
    UNISWAP_V3_FACTORY,
    UNISWAP_V3_QUOTER_V2,
    SUSHISWAP_V2_FACTORY,
    WETH_ADDRESS,
    USDC_ADDRESS,
)


# ============================================================
# Settings
# ============================================================

UNISWAP_FEE_TIER = 500

USDC_DECIMALS = 6
WETH_DECIMALS = 18

# Default gas assumptions
DEFAULT_GAS_UNITS = 300_000
DEFAULT_PRIORITY_FEE_GWEI = Decimal("1.0")


# ============================================================
# Analyze one block
# ============================================================

def analyze_block(
    w3,
    block_number: int,
    trade_size_usdc: Decimal,
    gas_units: int = DEFAULT_GAS_UNITS,
    priority_fee_gwei: Decimal = DEFAULT_PRIORITY_FEE_GWEI,
) -> dict:
    """
    Analyze both cross-DEX arbitrage directions
    at one Ethereum block.

    Route A:
        SushiSwap V2 -> Uniswap V3

    Route B:
        Uniswap V3 -> SushiSwap V2

    The function calculates:
        - same-block spot prices
        - cross-DEX spread
        - executable PnL before gas
        - historical block gas cost
        - final net PnL after gas

    Gas assumptions:
        gas_units:
            assumed total gas used by the atomic
            arbitrage transaction

        priority_fee_gwei:
            assumed priority fee paid above the
            historical block base fee
    """

    # --------------------------------------------------------
    # 0. Validate inputs
    # --------------------------------------------------------

    if trade_size_usdc <= 0:
        raise ValueError(
            "trade_size_usdc must be greater than zero."
        )

    if gas_units <= 0:
        raise ValueError(
            "gas_units must be greater than zero."
        )

    if priority_fee_gwei < 0:
        raise ValueError(
            "priority_fee_gwei cannot be negative."
        )

    # --------------------------------------------------------
    # 1. Block timestamp
    # --------------------------------------------------------

    timestamp = get_block_timestamp(
        w3,
        block_number,
    )

    # --------------------------------------------------------
    # 2. Uniswap V3 pool state
    # --------------------------------------------------------

    uni_snapshot = get_pool_snapshot(
        w3=w3,
        factory_address=UNISWAP_V3_FACTORY,
        token_a=WETH_ADDRESS,
        token_b=USDC_ADDRESS,
        fee=UNISWAP_FEE_TIER,
        block_number=block_number,
    )

    if uni_snapshot is None:
        raise ValueError(
            f"Uniswap V3 pool not found "
            f"at block {block_number}."
        )

    # --------------------------------------------------------
    # 3. SushiSwap V2 pair state
    # --------------------------------------------------------

    sushi_snapshot = get_pair_snapshot(
        w3=w3,
        factory_address=SUSHISWAP_V2_FACTORY,
        token_a=WETH_ADDRESS,
        token_b=USDC_ADDRESS,
        block_number=block_number,
    )

    if sushi_snapshot is None:
        raise ValueError(
            f"SushiSwap V2 pair not found "
            f"at block {block_number}."
        )

    # --------------------------------------------------------
    # 4. Validate token ordering
    # --------------------------------------------------------

    expected_token0 = USDC_ADDRESS.lower()
    expected_token1 = WETH_ADDRESS.lower()

    if (
        uni_snapshot["token0"].lower() != expected_token0
        or uni_snapshot["token1"].lower() != expected_token1
    ):
        raise ValueError(
            "Unexpected Uniswap token ordering."
        )

    if (
        sushi_snapshot["token0"].lower() != expected_token0
        or sushi_snapshot["token1"].lower() != expected_token1
    ):
        raise ValueError(
            "Unexpected SushiSwap token ordering."
        )

    # --------------------------------------------------------
    # 5. Same-block spot prices
    # --------------------------------------------------------

    uni_price = uniswap_v3_token0_per_token1(
        sqrt_price_x96=uni_snapshot["sqrtPriceX96"],
        token0_decimals=USDC_DECIMALS,
        token1_decimals=WETH_DECIMALS,
    )

    sushi_price = sushiswap_v2_token0_per_token1(
        reserve0=sushi_snapshot["reserve0"],
        reserve1=sushi_snapshot["reserve1"],
        token0_decimals=USDC_DECIMALS,
        token1_decimals=WETH_DECIMALS,
    )

    # --------------------------------------------------------
    # 6. Spot spread
    # --------------------------------------------------------

    spread = analyze_spot_spread(
        uni_price=uni_price,
        sushi_price=sushi_price,
    )

    # --------------------------------------------------------
    # 7. Route A:
    # SushiSwap V2 -> Uniswap V3
    # --------------------------------------------------------

    route_a = simulate_sushi_to_uniswap(
        w3=w3,
        block_number=block_number,
        amount_in_usdc=trade_size_usdc,
        sushi_reserve_usdc=sushi_snapshot["reserve0"],
        sushi_reserve_weth=sushi_snapshot["reserve1"],
        uniswap_quoter_address=UNISWAP_V3_QUOTER_V2,
        weth_address=WETH_ADDRESS,
        usdc_address=USDC_ADDRESS,
        uniswap_fee=UNISWAP_FEE_TIER,
        usdc_decimals=USDC_DECIMALS,
        weth_decimals=WETH_DECIMALS,
    )

    # --------------------------------------------------------
    # 8. Route B:
    # Uniswap V3 -> SushiSwap V2
    # --------------------------------------------------------

    route_b = simulate_uniswap_to_sushi(
        w3=w3,
        block_number=block_number,
        amount_in_usdc=trade_size_usdc,
        sushi_reserve_usdc=sushi_snapshot["reserve0"],
        sushi_reserve_weth=sushi_snapshot["reserve1"],
        uniswap_quoter_address=UNISWAP_V3_QUOTER_V2,
        weth_address=WETH_ADDRESS,
        usdc_address=USDC_ADDRESS,
        uniswap_fee=UNISWAP_FEE_TIER,
        usdc_decimals=USDC_DECIMALS,
        weth_decimals=WETH_DECIMALS,
    )

    # --------------------------------------------------------
    # 9. Best route before gas
    # --------------------------------------------------------

    best_route = max(
        [route_a, route_b],
        key=lambda x: x["profit_before_gas_usdc"],
    )

    # --------------------------------------------------------
    # 10. Historical gas cost
    #
    # Use same-block Uniswap WETH/USDC spot price
    # as the ETH/USDC reference price.
    # --------------------------------------------------------

    gas = estimate_block_gas_cost(
        w3=w3,
        block_number=block_number,
        gas_units=gas_units,
        priority_fee_gwei=priority_fee_gwei,
        eth_price_usdc=uni_price,
    )

    gas_cost_usdc = gas["gas_cost_usdc"]

    # --------------------------------------------------------
    # 11. Route-level PnL after gas
    #
    # Current research assumption:
    # both routes use the same total gas_units.
    # --------------------------------------------------------

    route_a_net_pnl = (
        route_a["profit_before_gas_usdc"]
        - gas_cost_usdc
    )

    route_b_net_pnl = (
        route_b["profit_before_gas_usdc"]
        - gas_cost_usdc
    )

    route_a_net_return_pct = (
        route_a_net_pnl
        / trade_size_usdc
        * Decimal(100)
    )

    route_b_net_return_pct = (
        route_b_net_pnl
        / trade_size_usdc
        * Decimal(100)
    )

    # --------------------------------------------------------
    # 12. Best route after gas
    #
    # Since both routes currently use the same gas-cost
    # assumption, the ranking is normally unchanged.
    # We still calculate it explicitly.
    # --------------------------------------------------------

    if route_a_net_pnl >= route_b_net_pnl:
        best_route_after_gas = route_a
        best_net_pnl = route_a_net_pnl
        best_net_return_pct = (
            route_a_net_return_pct
        )
    else:
        best_route_after_gas = route_b
        best_net_pnl = route_b_net_pnl
        best_net_return_pct = (
            route_b_net_return_pct
        )

    profitable_after_gas = (
        best_net_pnl > 0
    )

    # --------------------------------------------------------
    # 13. Structured result
    # --------------------------------------------------------

    return {
        # ----------------------------------------------------
        # Block
        # ----------------------------------------------------

        "block": block_number,
        "timestamp": timestamp,

        # ----------------------------------------------------
        # Trade size
        # ----------------------------------------------------

        "trade_size_usdc": trade_size_usdc,

        # ----------------------------------------------------
        # Spot prices
        # ----------------------------------------------------

        "uniswap_price": uni_price,
        "sushiswap_price": sushi_price,

        # ----------------------------------------------------
        # Spread
        # ----------------------------------------------------

        "signed_spread": (
            spread["signed_spread"]
        ),

        "absolute_spread": (
            spread["absolute_spread"]
        ),

        "relative_spread_pct": (
            spread["relative_spread_pct"]
        ),

        "spot_buy_dex": (
            spread["buy_dex"]
        ),

        "spot_sell_dex": (
            spread["sell_dex"]
        ),

        # ----------------------------------------------------
        # Route A before gas
        # ----------------------------------------------------

        "route_a_pnl_before_gas": (
            route_a["profit_before_gas_usdc"]
        ),

        "route_a_return_before_gas_pct": (
            route_a["return_before_gas_pct"]
        ),

        # ----------------------------------------------------
        # Route B before gas
        # ----------------------------------------------------

        "route_b_pnl_before_gas": (
            route_b["profit_before_gas_usdc"]
        ),

        "route_b_return_before_gas_pct": (
            route_b["return_before_gas_pct"]
        ),

        # ----------------------------------------------------
        # Best route before gas
        # ----------------------------------------------------

        "best_route_before_gas": (
            best_route["route"]
        ),

        "best_final_usdc_before_gas": (
            best_route["final_usdc"]
        ),

        "best_pnl_before_gas": (
            best_route["profit_before_gas_usdc"]
        ),

        "best_return_before_gas_pct": (
            best_route["return_before_gas_pct"]
        ),

        "profitable_before_gas": (
            best_route["profitable_before_gas"]
        ),

        # ----------------------------------------------------
        # Gas
        # ----------------------------------------------------

        "gas_units": (
            gas["gas_units"]
        ),

        "base_fee_gwei": (
            gas["base_fee_gwei"]
        ),

        "priority_fee_gwei": (
            gas["priority_fee_gwei"]
        ),

        "effective_gas_price_gwei": (
            gas["effective_gas_price_gwei"]
        ),

        "gas_cost_eth": (
            gas["gas_cost_eth"]
        ),

        "gas_cost_usdc": (
            gas["gas_cost_usdc"]
        ),

        # ----------------------------------------------------
        # Route A after gas
        # ----------------------------------------------------

        "route_a_net_pnl": (
            route_a_net_pnl
        ),

        "route_a_net_return_pct": (
            route_a_net_return_pct
        ),

        # ----------------------------------------------------
        # Route B after gas
        # ----------------------------------------------------

        "route_b_net_pnl": (
            route_b_net_pnl
        ),

        "route_b_net_return_pct": (
            route_b_net_return_pct
        ),

        # ----------------------------------------------------
        # Best route after gas
        # ----------------------------------------------------

        "best_route_after_gas": (
            best_route_after_gas["route"]
        ),

        "best_net_pnl_usdc": (
            best_net_pnl
        ),

        "best_net_return_pct": (
            best_net_return_pct
        ),

        "profitable_after_gas": (
            profitable_after_gas
        ),
    }