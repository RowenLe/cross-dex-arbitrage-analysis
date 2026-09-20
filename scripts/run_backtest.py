from decimal import Decimal
import time

import pandas as pd

from src.rpc import (
    get_web3,
    get_latest_block,
)

from src.backtest import analyze_block

from config.config import (
    PROCESSED_DATA_DIR,
)


# ============================================================
# Settings
# ============================================================

TRADE_SIZES_USDC = [
    Decimal("100"),
    Decimal("500"),
    Decimal("1000"),
    Decimal("5000"),
    Decimal("10000"),
]

N_BLOCKS = 500

# Gas assumptions
GAS_UNITS = 300_000
PRIORITY_FEE_GWEI = Decimal("1.0")

# Progress
PROGRESS_EVERY = 50

# Retry temporary RPC failures
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2

OUTPUT_FILE = (
    PROCESSED_DATA_DIR
    / f"arbitrage_multisize_{N_BLOCKS}blocks_with_gas.csv"
)


# ============================================================
# Helpers
# ============================================================

def serialize_result(result: dict) -> dict:
    """
    Convert Decimal values to float before storing
    results in pandas.
    """

    serialized = {}

    for key, value in result.items():
        if isinstance(value, Decimal):
            serialized[key] = float(value)
        else:
            serialized[key] = value

    return serialized


def analyze_with_retry(
    w3,
    block_number: int,
    trade_size: Decimal,
):
    """
    Run analyze_block with simple retry handling
    for temporary RPC / network failures.
    """

    last_error = None

    for attempt in range(
        1,
        MAX_RETRIES + 1,
    ):
        try:
            return analyze_block(
                w3=w3,
                block_number=block_number,
                trade_size_usdc=trade_size,
                gas_units=GAS_UNITS,
                priority_fee_gwei=PRIORITY_FEE_GWEI,
            )

        except Exception as exc:
            last_error = exc

            if attempt < MAX_RETRIES:
                time.sleep(
                    RETRY_DELAY_SECONDS
                )

    raise last_error


# ============================================================
# Main
# ============================================================

def main():
    w3 = get_web3()

    # --------------------------------------------------------
    # 1. Historical block range
    # --------------------------------------------------------

    latest_block = get_latest_block(w3)

    start_block = (
        latest_block
        - N_BLOCKS
        + 1
    )

    end_block = latest_block

    total_runs = (
        N_BLOCKS
        * len(TRADE_SIZES_USDC)
    )

    print(
        "\n=== Historical Cross-DEX "
        "Arbitrage Backtest ==="
    )

    print(
        f"\nBlock range: "
        f"{start_block} -> {end_block}"
    )

    print(
        f"Number of blocks: "
        f"{N_BLOCKS}"
    )

    print(
        "Trade sizes: "
        + ", ".join(
            f"{size:.0f}"
            for size in TRADE_SIZES_USDC
        )
        + " USDC"
    )

    print(
        f"Total simulations: "
        f"{total_runs}"
    )

    print(
        f"Gas units assumption: "
        f"{GAS_UNITS:,}"
    )

    print(
        f"Priority fee assumption: "
        f"{PRIORITY_FEE_GWEI} gwei"
    )

    # --------------------------------------------------------
    # 2. Run historical simulations
    # --------------------------------------------------------

    results = []
    failed_runs = []

    for block_index, block_number in enumerate(
        range(
            start_block,
            end_block + 1,
        ),
        start=1,
    ):
        for trade_size in TRADE_SIZES_USDC:
            try:
                result = analyze_with_retry(
                    w3=w3,
                    block_number=block_number,
                    trade_size=trade_size,
                )

                results.append(
                    serialize_result(
                        result
                    )
                )

            except Exception as exc:
                failed_runs.append(
                    {
                        "block": block_number,
                        "trade_size_usdc": float(
                            trade_size
                        ),
                        "error": str(exc),
                    }
                )

        # ----------------------------------------------------
        # Progress
        # ----------------------------------------------------

        if (
            block_index % PROGRESS_EVERY == 0
            or block_index == N_BLOCKS
        ):
            completed_runs = (
                block_index
                * len(TRADE_SIZES_USDC)
            )

            print(
                f"[{block_index}/{N_BLOCKS}] "
                f"blocks completed | "
                f"{completed_runs}/{total_runs} "
                f"simulations"
            )

    # --------------------------------------------------------
    # 3. Validate
    # --------------------------------------------------------

    if not results:
        raise RuntimeError(
            "No simulations completed successfully."
        )

    # --------------------------------------------------------
    # 4. DataFrame
    # --------------------------------------------------------

    df = pd.DataFrame(
        results
    )

    df = df.sort_values(
        [
            "block",
            "trade_size_usdc",
        ]
    ).reset_index(
        drop=True
    )

    # One row per block for block-level statistics
    block_df = (
        df.sort_values("block")
        .drop_duplicates(
            subset=["block"]
        )
    )

    # --------------------------------------------------------
    # 5. Save complete dataset
    # --------------------------------------------------------

    PROCESSED_DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    df.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    # --------------------------------------------------------
    # 6. Before-gas statistics
    # --------------------------------------------------------

    before_gas_df = df[
        df["profitable_before_gas"]
    ].copy()

    before_gas_count = len(
        before_gas_df
    )

    before_gas_ratio = (
        before_gas_count
        / len(df)
        * 100
    )

    before_gas_blocks = (
        before_gas_df["block"]
        .nunique()
        if before_gas_count > 0
        else 0
    )

    # --------------------------------------------------------
    # 7. After-gas statistics
    # --------------------------------------------------------

    after_gas_df = df[
        df["profitable_after_gas"]
    ].copy()

    after_gas_count = len(
        after_gas_df
    )

    after_gas_ratio = (
        after_gas_count
        / len(df)
        * 100
    )

    after_gas_blocks = (
        after_gas_df["block"]
        .nunique()
        if after_gas_count > 0
        else 0
    )

    # --------------------------------------------------------
    # 8. Overall summary
    # --------------------------------------------------------

    print("\n=== Overall Summary ===")

    print(
        f"\nSuccessful simulations: "
        f"{len(df)}"
    )

    print(
        f"Failed simulations: "
        f"{len(failed_runs)}"
    )

    print(
        f"Average spot spread: "
        f"{block_df['relative_spread_pct'].mean():.6f}%"
    )

    print(
        f"Maximum spot spread: "
        f"{block_df['relative_spread_pct'].max():.6f}%"
    )

    # --------------------------------------------------------
    # Before gas
    # --------------------------------------------------------

    print("\n=== Before Gas ===")

    print(
        f"\nProfitable simulations: "
        f"{before_gas_count}"
    )

    print(
        f"Profitable ratio: "
        f"{before_gas_ratio:.4f}%"
    )

    print(
        f"Distinct profitable blocks: "
        f"{before_gas_blocks}"
    )

    print(
        f"Average best PnL before gas: "
        f"{df['best_pnl_before_gas'].mean():.6f} USDC"
    )

    print(
        f"Maximum best PnL before gas: "
        f"{df['best_pnl_before_gas'].max():.6f} USDC"
    )

    # --------------------------------------------------------
    # Gas
    # --------------------------------------------------------

    print("\n=== Gas ===")

    print(
        f"\nGas units assumption: "
        f"{GAS_UNITS:,}"
    )

    print(
        f"Priority fee assumption: "
        f"{PRIORITY_FEE_GWEI} gwei"
    )

    print(
        f"Average base fee: "
        f"{block_df['base_fee_gwei'].mean():.6f} gwei"
    )

    print(
        f"Maximum base fee: "
        f"{block_df['base_fee_gwei'].max():.6f} gwei"
    )

    print(
        f"Average effective gas price: "
        f"{block_df['effective_gas_price_gwei'].mean():.6f} gwei"
    )

    print(
        f"Average gas cost: "
        f"{block_df['gas_cost_usdc'].mean():.6f} USDC"
    )

    print(
        f"Minimum gas cost: "
        f"{block_df['gas_cost_usdc'].min():.6f} USDC"
    )

    print(
        f"Maximum gas cost: "
        f"{block_df['gas_cost_usdc'].max():.6f} USDC"
    )

    # --------------------------------------------------------
    # After gas
    # --------------------------------------------------------

    print("\n=== After Gas ===")

    print(
        f"\nProfitable simulations: "
        f"{after_gas_count}"
    )

    print(
        f"Profitable ratio: "
        f"{after_gas_ratio:.4f}%"
    )

    print(
        f"Distinct profitable blocks: "
        f"{after_gas_blocks}"
    )

    print(
        f"Average net PnL: "
        f"{df['best_net_pnl_usdc'].mean():.6f} USDC"
    )

    print(
        f"Maximum net PnL: "
        f"{df['best_net_pnl_usdc'].max():.6f} USDC"
    )

    # --------------------------------------------------------
    # 9. Summary by trade size
    # --------------------------------------------------------

    summary = (
        df.groupby(
            "trade_size_usdc"
        )
        .agg(
            simulations=(
                "block",
                "count",
            ),

            avg_spread_pct=(
                "relative_spread_pct",
                "mean",
            ),

            avg_pnl_before_gas=(
                "best_pnl_before_gas",
                "mean",
            ),

            max_pnl_before_gas=(
                "best_pnl_before_gas",
                "max",
            ),

            avg_gas_cost_usdc=(
                "gas_cost_usdc",
                "mean",
            ),

            avg_net_pnl=(
                "best_net_pnl_usdc",
                "mean",
            ),

            max_net_pnl=(
                "best_net_pnl_usdc",
                "max",
            ),

            avg_net_return_pct=(
                "best_net_return_pct",
                "mean",
            ),

            max_net_return_pct=(
                "best_net_return_pct",
                "max",
            ),

            profitable_before_gas=(
                "profitable_before_gas",
                "sum",
            ),

            profitable_after_gas=(
                "profitable_after_gas",
                "sum",
            ),
        )
        .reset_index()
    )

    summary[
        "profitable_before_gas_pct"
    ] = (
        summary["profitable_before_gas"]
        / summary["simulations"]
        * 100
    )

    summary[
        "profitable_after_gas_pct"
    ] = (
        summary["profitable_after_gas"]
        / summary["simulations"]
        * 100
    )

    print(
        "\n=== Summary by Trade Size ===\n"
    )

    print(
        summary.to_string(
            index=False,
            formatters={
                "trade_size_usdc":
                    lambda x: f"{x:.0f}",

                "avg_spread_pct":
                    lambda x: f"{x:.6f}",

                "avg_pnl_before_gas":
                    lambda x: f"{x:.6f}",

                "max_pnl_before_gas":
                    lambda x: f"{x:.6f}",

                "avg_gas_cost_usdc":
                    lambda x: f"{x:.6f}",

                "avg_net_pnl":
                    lambda x: f"{x:.6f}",

                "max_net_pnl":
                    lambda x: f"{x:.6f}",

                "avg_net_return_pct":
                    lambda x: f"{x:.6f}",

                "max_net_return_pct":
                    lambda x: f"{x:.6f}",

                "profitable_before_gas_pct":
                    lambda x: f"{x:.2f}",

                "profitable_after_gas_pct":
                    lambda x: f"{x:.2f}",
            },
        )
    )

    # --------------------------------------------------------
    # 10. Best before-gas simulation
    # --------------------------------------------------------

    best_before_index = (
        df["best_pnl_before_gas"]
        .idxmax()
    )

    best_before = df.loc[
        best_before_index
    ]

    print(
        "\n=== Best Before-Gas Simulation ==="
    )

    print(
        f"\nBlock: "
        f"{int(best_before['block'])}"
    )

    print(
        f"Trade size: "
        f"{best_before['trade_size_usdc']:.0f} USDC"
    )

    print(
        f"Spot spread: "
        f"{best_before['relative_spread_pct']:.6f}%"
    )

    print(
        f"Route: "
        f"{best_before['best_route_before_gas']}"
    )

    print(
        f"PnL before gas: "
        f"{best_before['best_pnl_before_gas']:.6f} USDC"
    )

    print(
        f"Return before gas: "
        f"{best_before['best_return_before_gas_pct']:.6f}%"
    )

    # --------------------------------------------------------
    # 11. Best after-gas simulation
    # --------------------------------------------------------

    best_after_index = (
        df["best_net_pnl_usdc"]
        .idxmax()
    )

    best_after = df.loc[
        best_after_index
    ]

    print(
        "\n=== Best After-Gas Simulation ==="
    )

    print(
        f"\nBlock: "
        f"{int(best_after['block'])}"
    )

    print(
        f"Trade size: "
        f"{best_after['trade_size_usdc']:.0f} USDC"
    )

    print(
        f"Spot spread: "
        f"{best_after['relative_spread_pct']:.6f}%"
    )

    print(
        f"Route: "
        f"{best_after['best_route_after_gas']}"
    )

    print(
        f"PnL before gas: "
        f"{best_after['best_pnl_before_gas']:.6f} USDC"
    )

    print(
        f"Gas cost: "
        f"{best_after['gas_cost_usdc']:.6f} USDC"
    )

    print(
        f"Net PnL: "
        f"{best_after['best_net_pnl_usdc']:.6f} USDC"
    )

    print(
        f"Net return: "
        f"{best_after['best_net_return_pct']:.6f}%"
    )

    print(
        f"Profitable after gas: "
        f"{best_after['profitable_after_gas']}"
    )

    # --------------------------------------------------------
    # 12. Before-gas candidates
    # --------------------------------------------------------

    print(
        "\n=== Profitable Before-Gas Candidates ==="
    )

    if before_gas_df.empty:
        print(
            "\nNo profitable before-gas opportunities "
            "were found."
        )

    else:
        before_gas_df = (
            before_gas_df
            .sort_values(
                "best_pnl_before_gas",
                ascending=False,
            )
        )

        before_columns = [
            "block",
            "timestamp",
            "trade_size_usdc",
            "relative_spread_pct",
            "best_route_before_gas",
            "best_pnl_before_gas",
            "best_return_before_gas_pct",
        ]

        print("\nTop 10:\n")

        print(
            before_gas_df[
                before_columns
            ]
            .head(10)
            .to_string(
                index=False,
            )
        )

    # --------------------------------------------------------
    # 13. After-gas candidates
    # --------------------------------------------------------

    print(
        "\n=== Profitable After-Gas Candidates ==="
    )

    if after_gas_df.empty:
        print(
            "\nNo profitable after-gas opportunities "
            "were found."
        )

    else:
        after_gas_df = (
            after_gas_df
            .sort_values(
                "best_net_pnl_usdc",
                ascending=False,
            )
        )

        after_columns = [
            "block",
            "timestamp",
            "trade_size_usdc",
            "relative_spread_pct",
            "best_route_after_gas",
            "best_pnl_before_gas",
            "gas_cost_usdc",
            "best_net_pnl_usdc",
            "best_net_return_pct",
        ]

        print("\nTop 10:\n")

        print(
            after_gas_df[
                after_columns
            ]
            .head(10)
            .to_string(
                index=False,
            )
        )

    # --------------------------------------------------------
    # 14. Failed simulations
    # --------------------------------------------------------

    if failed_runs:
        print(
            "\n=== Failed Simulations ==="
        )

        print(
            f"\nTotal failed: "
            f"{len(failed_runs)}"
        )

        for failure in failed_runs[:10]:
            print(
                f"Block {failure['block']} | "
                f"{failure['trade_size_usdc']:.0f} USDC | "
                f"{failure['error']}"
            )

        if len(failed_runs) > 10:
            print(
                f"... and "
                f"{len(failed_runs) - 10} more."
            )

    # --------------------------------------------------------
    # 15. Output
    # --------------------------------------------------------

    print(
        f"\nSaved to:\n{OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()