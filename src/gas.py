from decimal import Decimal

from web3 import Web3


# ============================================================
# Constants
# ============================================================

WEI_PER_ETH = Decimal(10 ** 18)
GWEI_TO_WEI = Decimal(10 ** 9)


# ============================================================
# Historical gas data
# ============================================================

def get_block_base_fee_wei(
    w3: Web3,
    block_number: int,
) -> int:
    """
    Return the historical EIP-1559 base fee
    for a specific Ethereum block.

    The value is returned in wei per gas.
    """

    block = w3.eth.get_block(
        block_number
    )

    base_fee_wei = block.get(
        "baseFeePerGas"
    )

    if base_fee_wei is None:
        raise ValueError(
            f"Block {block_number} does not contain "
            "baseFeePerGas."
        )

    return int(
        base_fee_wei
    )


def get_block_base_fee_gwei(
    w3: Web3,
    block_number: int,
) -> Decimal:
    """
    Return the historical block base fee
    in gwei per gas.
    """

    base_fee_wei = get_block_base_fee_wei(
        w3=w3,
        block_number=block_number,
    )

    return (
        Decimal(base_fee_wei)
        / GWEI_TO_WEI
    )


# ============================================================
# Gas cost calculation
# ============================================================

def estimate_gas_cost(
    gas_units: int,
    base_fee_wei: int,
    priority_fee_gwei: Decimal,
    eth_price_usdc: Decimal,
) -> dict:
    """
    Estimate transaction gas cost in both ETH and USDC.

    Parameters
    ----------
    gas_units:
        Assumed total gas used by the atomic arbitrage
        transaction.

    base_fee_wei:
        Historical block base fee in wei per gas.

    priority_fee_gwei:
        Assumed miner / validator priority fee in gwei.

    eth_price_usdc:
        Historical ETH price in USDC.

    Returns
    -------
    dict
        Gas cost breakdown.
    """

    if gas_units <= 0:
        raise ValueError(
            "gas_units must be greater than zero."
        )

    if base_fee_wei < 0:
        raise ValueError(
            "base_fee_wei cannot be negative."
        )

    if priority_fee_gwei < 0:
        raise ValueError(
            "priority_fee_gwei cannot be negative."
        )

    if eth_price_usdc <= 0:
        raise ValueError(
            "eth_price_usdc must be greater than zero."
        )

    # --------------------------------------------------------
    # 1. Convert priority fee to wei
    # --------------------------------------------------------

    priority_fee_wei = (
        priority_fee_gwei
        * GWEI_TO_WEI
    )

    # --------------------------------------------------------
    # 2. Effective gas price
    # --------------------------------------------------------

    effective_gas_price_wei = (
        Decimal(base_fee_wei)
        + priority_fee_wei
    )

    effective_gas_price_gwei = (
        effective_gas_price_wei
        / GWEI_TO_WEI
    )

    # --------------------------------------------------------
    # 3. Gas cost in ETH
    # --------------------------------------------------------

    gas_cost_wei = (
        Decimal(gas_units)
        * effective_gas_price_wei
    )

    gas_cost_eth = (
        gas_cost_wei
        / WEI_PER_ETH
    )

    # --------------------------------------------------------
    # 4. Gas cost in USDC
    # --------------------------------------------------------

    gas_cost_usdc = (
        gas_cost_eth
        * eth_price_usdc
    )

    return {
        "gas_units": gas_units,

        "base_fee_wei": int(
            base_fee_wei
        ),

        "base_fee_gwei": (
            Decimal(base_fee_wei)
            / GWEI_TO_WEI
        ),

        "priority_fee_gwei": (
            priority_fee_gwei
        ),

        "effective_gas_price_gwei": (
            effective_gas_price_gwei
        ),

        "gas_cost_eth": (
            gas_cost_eth
        ),

        "gas_cost_usdc": (
            gas_cost_usdc
        ),
    }


# ============================================================
# Historical block gas estimate
# ============================================================

def estimate_block_gas_cost(
    w3: Web3,
    block_number: int,
    gas_units: int,
    priority_fee_gwei: Decimal,
    eth_price_usdc: Decimal,
) -> dict:
    """
    Estimate arbitrage gas cost for a historical block.

    This combines:
        historical base fee
        + assumed priority fee
        + assumed gas usage
        + historical ETH/USDC price
    """

    base_fee_wei = get_block_base_fee_wei(
        w3=w3,
        block_number=block_number,
    )

    result = estimate_gas_cost(
        gas_units=gas_units,
        base_fee_wei=base_fee_wei,
        priority_fee_gwei=priority_fee_gwei,
        eth_price_usdc=eth_price_usdc,
    )

    return {
        "block": block_number,
        **result,
    }