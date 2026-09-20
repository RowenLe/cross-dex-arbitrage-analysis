import os
from pathlib import Path

from dotenv import load_dotenv


# ============================================================
# Project paths
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

RESULTS_DIR = BASE_DIR / "results"


# ============================================================
# Environment variables
# ============================================================

load_dotenv(BASE_DIR / ".env")

ETH_RPC_URL = os.getenv("ETH_RPC_URL")


# ============================================================
# Ethereum
# ============================================================

CHAIN_ID = 1


# ============================================================
# Tokens - Ethereum Mainnet
# ============================================================

WETH_ADDRESS = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"

USDC_ADDRESS = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"


# ============================================================
# Uniswap V3 - Ethereum Mainnet
# ============================================================

UNISWAP_V3_FACTORY = (
    "0x1F98431c8aD98523631AE4a59f267346ea31F984"
)

UNISWAP_V3_QUOTER_V2 = (
    "0x61fFE014bA17989E743c5F6cB21bF9697530B21e"
)


# ============================================================
# SushiSwap V2 - Ethereum Mainnet
# ============================================================

SUSHISWAP_V2_FACTORY = (
    "0xC0AEe478e3658e2610c5F7A4A2E1777cE9e4f2Ac"
)


# ============================================================
# Default research pair
# ============================================================

TOKEN_A = WETH_ADDRESS
TOKEN_B = USDC_ADDRESS