"""Simple trade journal for tracking win rate, P/L ratio, and daily drawdown."""
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from pathlib import Path
from typing import Optional

JOURNAL_FILE = Path(__file__).parent.parent / "data" / "trade_journal.jsonl"


@dataclass
class TradeRecord:
    entry_time: str
    exit_time: str
    direction: str              # 'L' or 'S'
    entry_price: float
    exit_price: float
    pnl: float                  # Absolute P&L
    pnl_r: float                # P&L in R multiples
    result: str                 # 'WIN' / 'LOSS' / 'BREAKEVEN'
    signal_type: str = ""
    notes: str = ""


@dataclass
class DailyStats:
    date: str
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    breakevens: int = 0
    pnl_abs: float = 0.0
    pnl_r: float = 0.0


class TradeJournal:
    def __init__(self, filepath: str = None):
        self._path = Path(filepath or JOURNAL_FILE)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._records: list[TradeRecord] = []
        self._load()

    def _load(self):
        if not self._path.exists():
            return
        try:
            with open(self._path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self._records.append(TradeRecord(**json.loads(line)))
        except Exception:
            pass

    def _save(self):
        try:
            with open(self._path, 'w', encoding='utf-8') as f:
                for r in self._records:
                    f.write(json.dumps(asdict(r), ensure_ascii=False) + '\n')
        except Exception:
            pass

    def add_trade(self, record: TradeRecord):
        self._records.append(record)
        self._save()

    def get_all(self) -> list[TradeRecord]:
        return list(self._records)

    def get_recent(self, n: int = 50) -> list[TradeRecord]:
        return self._records[-n:]

    def win_rate(self, n: int = 0) -> float:
        """Win rate for last N trades (0 = all)."""
        trades = self._records[-n:] if n > 0 else self._records
        if not trades:
            return 0.0
        wins = sum(1 for t in trades if t.result == 'WIN')
        return wins / len(trades)

    def profit_factor(self, n: int = 0) -> float:
        """Gross profit / gross loss."""
        trades = self._records[-n:] if n > 0 else self._records
        gross_profit = sum(t.pnl for t in trades if t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in trades if t.pnl < 0))
        if gross_loss == 0:
            return gross_profit if gross_profit > 0 else 0.0
        return gross_profit / gross_loss

    def avg_win(self, n: int = 0) -> float:
        trades = self._records[-n:] if n > 0 else self._records
        wins = [t.pnl for t in trades if t.pnl > 0]
        return sum(wins) / len(wins) if wins else 0.0

    def avg_loss(self, n: int = 0) -> float:
        trades = self._records[-n:] if n > 0 else self._records
        losses = [t.pnl for t in trades if t.pnl < 0]
        return sum(losses) / len(losses) if losses else 0.0

    def daily_pnl(self, day: date = None) -> float:
        """Total P&L for a given day (default: today)."""
        if day is None:
            day = date.today()
        day_str = day.isoformat()
        return sum(t.pnl for t in self._records
                   if t.exit_time[:10] == day_str)

    def daily_loss_pct(self, balance: float, day: date = None) -> float:
        """Daily P&L as percentage of balance (for risk limit check)."""
        pnl = self.daily_pnl(day)
        if balance <= 0:
            return 0.0
        return abs(min(pnl, 0)) / balance * 100

    def daily_stats(self, day: date = None) -> DailyStats:
        if day is None:
            day = date.today()
        day_str = day.isoformat()
        day_trades = [t for t in self._records if t.exit_time[:10] == day_str]
        wins = sum(1 for t in day_trades if t.result == 'WIN')
        losses = sum(1 for t in day_trades if t.result == 'LOSS')
        bes = sum(1 for t in day_trades if t.result == 'BREAKEVEN')
        return DailyStats(
            date=day_str,
            total_trades=len(day_trades),
            wins=wins, losses=losses, breakevens=bes,
            pnl_abs=sum(t.pnl for t in day_trades),
            pnl_r=sum(t.pnl_r for t in day_trades),
        )

    def total_trades(self) -> int:
        return len(self._records)
