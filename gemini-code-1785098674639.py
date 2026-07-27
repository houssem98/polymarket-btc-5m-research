import os

# Define file contents
CLAUDE_MD = """# CLAUDE.md - Polymarket 5-Min BTC Trading Bot Rules

## 1. AGENT IDENTITY
You are an expert Quantitative Developer and Blockchain Engineer specializing in high-frequency trading on Polymarket's CLOB. Write asynchronous, typed, and error-resilient Python code.

## 2. GRAPH-LOOP WORKFLOW ARCHITECTURE
1. Plan & Audit Math -> 2. Code & Harden Agent -> 3. Self-Heal & Retry Loop -> 4. Self-Test & Verify EV

## 3. PROJECT DIRECTORY
- config.py
- data_feed.py
- strategy.py
- clob_execution.py
- risk_manager.py
- main.py

## 4. AGENT HARDENING & DEFENSIVE PROTOCOLS
- Clock Sync: Calculate market slugs deterministically: `btc-updown-5m-{window_ts}` where `window_ts = current_unix - (current_unix % 300)`.
- Execution Window: Fire trades between T-10s and T-5s prior to window closure.
- Minimum Order Size: 5 shares minimum per trade.
- Max Odds Cap: Odds <= 0.88 to prevent catastrophic asymmetric losses.
- Circuit Breakers: Cooldown after 3 consecutive losses.
"""

CONFIG_PY = """import os
from dotenv import load_dotenv

load_dotenv()

# Network & Credentials
PK = os.getenv("POLYGON_PRIVATE_KEY", "")
FUNDER = os.getenv("POLYMARKET_FUNDER_ADDRESS", "")
SIGNATURE_TYPE = int(os.getenv("SIGNATURE_TYPE", "2")) # 0=EOA, 1=Email/Magic, 2=Browser Wallet

# Bot Parameters
WINDOW_SIZE = 300 # 5 minutes in seconds
SNIPE_WINDOW_START = 10 # Start evaluating at T-10s
SNIPE_WINDOW_END = 3 # Stop at T-3s
MIN_SHARES = 5.0 # Polymarket minimum order size
MIN_EV = 0.05 # Minimum expected value per trade
MAX_ENTRY_PRICE = 0.88 # Do not buy tokens over 88 cents
DRY_RUN = os.getenv("DRY_RUN", "True").lower() == "true"
"""

DATA_FEED_PY = """import asyncio
import aiohttp
import logging

class BinanceDataFeed:
    def __init__(self):
        self.base_url = "https://api.binance.com/api/v3"

    async def get_current_btc_price(self) -> float:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.base_url}/ticker/price?symbol=BTCUSDT") as resp:
                data = await resp.json()
                return float(data["price"])

    async def get_klines(self, interval="1m", limit=14):
        async with aiohttp.ClientSession() as session:
            url = f"{self.base_url}/klines?symbol=BTCUSDT&interval={interval}&limit={limit}"
            async with session.get(url) as resp:
                data = await resp.json()
                # Parse close prices
                return [float(c[4]) for c in data]
"""

STRATEGY_PY = """import numpy as np

class StrategyEngine:
    @staticmethod
    def calculate_window_delta(current_price: float, open_price: float) -> float:
        if open_price == 0:
            return 0.0
        return ((current_price - open_price) / open_price) * 100.0

    @staticmethod
    def calculate_atr(klines_high_low_close) -> float:
        # Simplified ATR indicator check
        return np.std(klines_high_low_close)

    def evaluate_signals(self, current_price: float, window_open_price: float, klines: list):
        delta = self.calculate_window_delta(current_price, window_open_price)
        
        # Determine Direction
        side = "UP" if delta > 0 else "DOWN"
        abs_delta = abs(delta)
        
        # Calculate Win Probability based on Delta
        if abs_delta >= 0.10:
            p_win = 0.90
        elif abs_delta >= 0.05:
            p_win = 0.78
        elif abs_delta >= 0.02:
            p_win = 0.65
        else:
            p_win = 0.52

        return side, p_win, delta
"""

RISK_MANAGER_PY = """class RiskManager:
    def __init__(self, initial_bankroll: float = 100.0):
        self.bankroll = initial_bankroll
        self.loss_streak = 0
        self.circuit_breaker_active = False

    def calculate_position_size(self, p_win: float, odds: float) -> float:
        if self.circuit_breaker_active:
            return 0.0
            
        # Fractional Kelly Criterion (0.25x Kelly)
        b = (1.0 / odds) - 1.0
        q = 1.0 - p_win
        f_kelly = (b * p_win - q) / b if b > 0 else 0
        f_kelly = max(0.0, f_kelly * 0.25)
        
        stake = self.bankroll * f_kelly
        return stake

    def register_trade_outcome(self, is_win: bool, pnl: float):
        self.bankroll += pnl
        if not is_win:
            self.loss_streak += 1
            if self.loss_streak >= 3:
                self.circuit_breaker_active = True
        else:
            self.loss_streak = 0
"""

CLOB_EXECUTION_PY = """import logging
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY
import config

class PolymarketExecutor:
    def __init__(self):
        self.client = None
        if not config.DRY_RUN and config.PK:
            self.client = ClobClient(
                host="https://clob.polymarket.com",
                key=config.PK,
                chain_id=137,
                signature_type=config.SIGNATURE_TYPE,
                funder=config.FUNDER
            )
            self.client.set_api_creds(self.client.create_or_derive_api_creds())

    def get_slug(self, timestamp: int) -> str:
        # Deterministic slug format: btc-updown-5m-{window_ts}
        window_ts = timestamp - (timestamp % config.WINDOW_SIZE)
        return f"btc-updown-5m-{window_ts}"

    async def execute_trade(self, token_id: str, price: float, size: float):
        if config.DRY_RUN:
            logging.info(f"[DRY RUN] Placed Order: {size} shares of {token_id} at ${price}")
            return {"status": "SUCCESS_SIMULATED"}
        
        order_args = OrderArgs(price=price, size=size, side=BUY, token_id=token_id)
        signed_order = self.client.create_order(order_args)
        response = self.client.post_order(signed_order, OrderType.IOC)
        return response
"""

MAIN_PY = """import asyncio
import time
import logging
import config
from data_feed import BinanceDataFeed
from strategy import StrategyEngine
from risk_manager import RiskManager
from clob_execution import PolymarketExecutor

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

async def main_loop():
    data_feed = BinanceDataFeed()
    strategy = StrategyEngine()
    risk_mgr = RiskManager(initial_bankroll=200.0)
    executor = PolymarketExecutor()

    logging.info("Starting Polymarket 5-Min BTC Trading Engine...")
    
    while True:
        now = int(time.time())
        time_into_window = now % config.WINDOW_SIZE
        time_remaining = config.WINDOW_SIZE - time_into_window
        
        # Awaken in the execution window (T-10s to T-3s)
        if config.SNIPE_WINDOW_END <= time_remaining <= config.SNIPE_WINDOW_START:
            current_slug = executor.get_slug(now)
            logging.info(f"Snipe Window Active for Slug: {current_slug} | T-{time_remaining}s")
            
            # 1. Fetch Real-Time Data
            btc_price = await data_feed.get_current_btc_price()
            klines = await data_feed.get_klines()
            open_price = klines[-5] if len(klines) >= 5 else btc_price
            
            # 2. Compute Signals
            side, p_win, delta = strategy.evaluate_signals(btc_price, open_price, klines)
            logging.info(f"Signal: {side} | P(Win): {p_win:.2f} | Window Delta: {delta:.4f}%")
            
            # 3. Size and Execute
            target_price = 0.80 # Target mid-ask simulation
            stake = risk_mgr.calculate_position_size(p_win, target_price)
            shares = max(config.MIN_SHARES, stake / target_price)
            
            ev = (p_win * 1.00) - target_price
            if ev >= config.MIN_EV and target_price <= config.MAX_ENTRY_PRICE:
                logging.info(f"Executing Trade: Buying {shares:.1f} shares of {side} @ ${target_price}")
                # Simulated token ID
                token_id = "MOCK_TOKEN_ID_UP" if side == "UP" else "MOCK_TOKEN_ID_DOWN"
                await executor.execute_trade(token_id, target_price, shares)
            else:
                logging.info(f"Trade Skipped: Low EV ({ev:.3f}) or high odds.")
                
            # Sleep past the expiration mark
            await asyncio.sleep(time_remaining + 2)
        else:
            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main_loop())
"""

ENV_EXAMPLE = """POLYGON_PRIVATE_KEY=your_private_key_here
POLYMARKET_FUNDER_ADDRESS=your_proxy_wallet_address_here
SIGNATURE_TYPE=2
DRY_RUN=True
"""

REQUIREMENTS_TXT = """py-clob-client>=0.24.0
aiohttp>=3.8.0
numpy>=1.21.0
python-dotenv>=1.0.0
pytest>=7.0.0
"""

def setup_project():
    folder_name = "polymarket_btc_5m_bot"
    os.makedirs(folder_name, exist_ok=True)
    
    files = {
        "CLAUDE.md": CLAUDE_MD,
        "config.py": CONFIG_PY,
        "data_feed.py": DATA_FEED_PY,
        "strategy.py": STRATEGY_PY,
        "risk_manager.py": RISK_MANAGER_PY,
        "clob_execution.py": CLOB_EXECUTION_PY,
        "main.py": MAIN_PY,
        ".env.example": ENV_EXAMPLE,
        "requirements.txt": REQUIREMENTS_TXT,
    }
    
    for filename, content in files.items():
        filepath = os.path.join(folder_name, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
            
    print(f"Project directory successfully created at ./{folder_name}")

if __name__ == "__main__":
    setup_project()