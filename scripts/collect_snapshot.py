from decimal import Decimal

from src.rpc import (
    get_web3,
    get_latest_block,
    get_block_timestamp,
)

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

TRADE_SIZE_USDC = Decimal("1000")


# ============================================================
# Main
# ============================================================

def main():
    w3 = get_web3()

    # --------------------------------------------------------
    # 1. Fix one Ethereum block
    # --------------------------------------------------------

    block_number = get_latest_block(w3)

    timestamp = get_block_timestamp(
        w3,
        block_number,
    )

    # --------------------------------------------------------
    # 2. Read Uniswap V3 at block N
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
            "Uniswap V3 WETH/USDC pool not found."
        )

    # --------------------------------------------------------
    # 3. Read SushiSwap V2 at the same block N
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
            "SushiSwap V2 WETH/USDC pair not found."
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
    # 5. Calculate same-block spot prices
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
        amount_in_usdc=TRADE_SIZE_USDC,
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
        amount_in_usdc=TRADE_SIZE_USDC,
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
    # 9. Select better executable route
    # --------------------------------------------------------

    best_route = max(
        [route_a, route_b],
        key=lambda x: x["profit_before_gas_usdc"],
    )

    # --------------------------------------------------------
    # 10. Output
    # --------------------------------------------------------

    print("\n=== Cross-DEX Arbitrage Snapshot ===")

    print(f"\nBlock: {block_number}")
    print(f"Timestamp: {timestamp}")

    print("\nPair: WETH / USDC")
    print(f"Trade size: {TRADE_SIZE_USDC:.2f} USDC")

    # --------------------------------------------------------
    # Spot market
    # --------------------------------------------------------

    print("\n--- Spot Market ---")

    print(
        f"Uniswap V3: "
        f"{uni_price:.6f} USDC/WETH"
    )

    print(
        f"SushiSwap V2: "
        f"{sushi_price:.6f} USDC/WETH"
    )

    print(
        f"Absolute spread: "
        f"{spread['absolute_spread']:.6f} USDC/WETH"
    )

    print(
        f"Relative spread: "
        f"{spread['relative_spread_pct']:.6f}%"
    )

    print(
        f"Spot direction: "
        f"{spread['buy_dex']} -> {spread['sell_dex']}"
    )

    # --------------------------------------------------------
    # Route A
    # --------------------------------------------------------

    print("\n--- Route A: SushiSwap V2 -> Uniswap V3 ---")

    print(
        f"Sushi WETH out: "
        f"{route_a['sushi_weth_out']:.8f} WETH"
    )

    print(
        f"Sushi AMM price impact: "
        f"{route_a['sushi_amm_price_impact_pct']:.6f}%"
    )

    print(
        f"Uniswap ticks crossed: "
        f"{route_a['uniswap_ticks_crossed']}"
    )

    print(
        f"Final USDC: "
        f"{route_a['final_usdc']:.6f}"
    )

    print(
        f"PnL before gas: "
        f"{route_a['profit_before_gas_usdc']:.6f} USDC"
    )

    print(
        f"Return before gas: "
        f"{route_a['return_before_gas_pct']:.6f}%"
    )

    # --------------------------------------------------------
    # Route B
    # --------------------------------------------------------

    print("\n--- Route B: Uniswap V3 -> SushiSwap V2 ---")

    print(
        f"Uniswap WETH out: "
        f"{route_b['uniswap_weth_out']:.8f} WETH"
    )

    print(
        f"Uniswap ticks crossed: "
        f"{route_b['uniswap_ticks_crossed']}"
    )

    print(
        f"Final USDC: "
        f"{route_b['final_usdc']:.6f}"
    )

    print(
        f"PnL before gas: "
        f"{route_b['profit_before_gas_usdc']:.6f} USDC"
    )

    print(
        f"Return before gas: "
        f"{route_b['return_before_gas_pct']:.6f}%"
    )

    # --------------------------------------------------------
    # Best route
    # --------------------------------------------------------

    print("\n=== Best Executable Route ===")

    print(
        f"Route: "
        f"{best_route['route']}"
    )

    print(
        f"Final USDC: "
        f"{best_route['final_usdc']:.6f}"
    )

    print(
        f"PnL before gas: "
        f"{best_route['profit_before_gas_usdc']:.6f} USDC"
    )

    print(
        f"Return before gas: "
        f"{best_route['return_before_gas_pct']:.6f}%"
    )

    if best_route["profitable_before_gas"]:
        print("Profitable before gas: YES")
    else:
        print("Profitable before gas: NO")

    print(
        "\nNote: DEX fees and AMM execution effects "
        "are included. Full transaction gas cost "
        "is not included yet."
    )


if __name__ == "__main__":
    main()