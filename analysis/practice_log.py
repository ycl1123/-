"""
Practice Log Module — 实践日志模块
==================================
Based on Mao's "On Practice" (实践论), this module implements the
practice-knowledge feedback loop:

  实践 (Practice) → 感性认识 (Perceptual Knowledge)
      → 理性认识 (Rational Knowledge)
          → 再实践 (Practice Again)
              → 再认识 (Deeper Knowledge)

Every trade is "practice material" (实践材料). The log captures:
1. Entry conditions — what was known at entry time
2. Outcome — what actually happened
3. Gap analysis — difference between judgment and reality
4. Pattern extraction — what can be learned for next time
"""
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class PracticeRecord:
    """A single trade record as practice material."""
    # Identity
    entry_time: str           # ISO format
    exit_time: str            # ISO format
    symbol: str
    timeframe: str

    # Pre-trade judgment (认识 — what you thought)
    market_state: str         # STRONG_TREND / WEAK_TREND / CHANNEL / TRADING_RANGE
    always_in: str            # LONG / SHORT / NEUTRAL
    signal_k_bar_type: str    # what type of signal K
    signal_k_quality: float   # 0-1 signal K quality score
    contradiction_type: str   # from contradiction analysis
    transformation_risk: str  # from contradiction analysis
    entry_reason: str         # why you entered

    # Execution parameters
    direction: str            # 'L' or 'S'
    entry_price: float
    stop_price: float
    target_price: float
    risk_reward_ratio: float
    risk_percent: float       # risk as % of account

    # Resonance check (游击战 — guerrilla tactics)
    resonance_count: int      # how many conditions aligned (0-5)
    tactical_layer: str       # "战略进攻" / "战略防御" / "战略转移"

    # Outcome (实践结果)
    result: str               # 'WIN' / 'LOSS' / 'BREAKEVEN'
    exit_reason: str          # '止盈' / '止损' / '前提消失' / '超时'
    pnl: float
    pnl_r: float              # PnL in R-multiples
    bars_held: int

    # Gap analysis (再认识 — the gap between judgment and reality)
    gap_analysis: str = ""    # free-text: what went differently from expectation
    lesson: str = ""          # what rule should be adjusted
    knowledge_upgrade: str = ""  # what changed in your understanding

    # Meta
    logged_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class CycleSummary:
    """Summary after every N trades — a "再认识" checkpoint."""
    cycle_start: str
    cycle_end: str
    total_trades: int
    wins: int
    losses: int
    win_rate: float
    avg_r: float              # average R-multiple per trade
    profit_factor: float
    best_signal_type: str     # which pattern worked best
    worst_signal_type: str    # which pattern worked worst
    avg_quality_wins: float   # average signal K quality of winning trades
    avg_quality_losses: float # average signal K quality of losing trades
    resonance_win_rate: dict  # win rate by resonance count
    key_insight: str          # the single most important insight from this cycle
    rule_changes: list        # rules that were added/modified/removed


class PracticeLog:
    """
    Trade journal implementing the practice→knowledge cycle.

    Usage:
        log = PracticeLog("path/to/journal.jsonl")

        # Before entry
        record = log.create_record(...)

        # After exit
        log.close_record(record, result='WIN', pnl=150.0, ...)

        # Every 10 trades
        summary = log.generate_cycle_summary()
    """

    def __init__(self, filepath: str = None):
        if filepath is None:
            filepath = Path(__file__).parent.parent / "data" / "practice_log.jsonl"
        self.filepath = Path(filepath)
        self.filepath.parent.mkdir(parents=True, exist_ok=True)

    def create_record(self, **kwargs) -> PracticeRecord:
        """Create a new practice record before entry."""
        return PracticeRecord(**kwargs)

    def save_record(self, record: PracticeRecord):
        """Append a completed record to the journal."""
        d = asdict(record)
        with open(self.filepath, 'a', encoding='utf-8') as f:
            f.write(json.dumps(d, ensure_ascii=False) + '\n')

    def load_records(self, limit: int = None) -> list[PracticeRecord]:
        """Load recent records for review."""
        if not self.filepath.exists():
            return []
        records = []
        with open(self.filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        d = json.loads(line)
                        records.append(PracticeRecord(**d))
                    except (json.JSONDecodeError, TypeError):
                        continue
        if limit:
            records = records[-limit:]
        return records

    def get_recent_n(self, n: int = 10) -> list[PracticeRecord]:
        """Get the last N trade records for cycle review."""
        return self.load_records(limit=n)

    def generate_cycle_summary(self, records: list[PracticeRecord] = None) -> Optional[CycleSummary]:
        """
        Generate a "再认识" checkpoint summary.

        This is the rational knowledge upgrade step in the practice cycle.
        After every ~10 trades, call this to extract patterns.
        """
        if records is None:
            records = self.get_recent_n(10)

        if len(records) < 3:
            return None

        wins = [r for r in records if r.result == 'WIN']
        losses = [r for r in records if r.result == 'LOSS']
        total = len(records)

        # Best/worst signal types
        signal_stats = {}
        for r in records:
            sig = r.signal_k_bar_type
            if sig not in signal_stats:
                signal_stats[sig] = {'wins': 0, 'total': 0}
            signal_stats[sig]['total'] += 1
            if r.result == 'WIN':
                signal_stats[sig]['wins'] += 1

        best_sig = max(signal_stats, key=lambda s: signal_stats[s]['wins'] / max(signal_stats[s]['total'], 1))
        worst_sig = min(signal_stats, key=lambda s: signal_stats[s]['wins'] / max(signal_stats[s]['total'], 1))

        # Resonance win rate
        resonance_stats = {}
        for r in records:
            rc = r.resonance_count
            if rc not in resonance_stats:
                resonance_stats[rc] = {'wins': 0, 'total': 0}
            resonance_stats[rc]['total'] += 1
            if r.result == 'WIN':
                resonance_stats[rc]['wins'] += 1

        resonance_win_rate = {
            k: round(v['wins'] / max(v['total'], 1), 3)
            for k, v in sorted(resonance_stats.items())
        }

        # Key insight extraction
        if len(wins) >= 2:
            avg_quality_wins = sum(w.signal_k_quality for w in wins) / len(wins)
        else:
            avg_quality_wins = 0

        if len(losses) >= 2:
            avg_quality_losses = sum(l.signal_k_quality for l in losses) / len(losses)
        else:
            avg_quality_losses = 0

        # Generate insight
        insights = []
        if avg_quality_wins > avg_quality_losses:
            insights.append("信号K质量与胜率正相关——继续严格执行最低质量阈值")
        else:
            insights.append("信号K质量与胜率不相关——检查是否过度依赖信号K而忽略市场状态")

        high_res_wr = {k: v for k, v in resonance_win_rate.items() if k >= 3}
        low_res_wr = {k: v for k, v in resonance_win_rate.items() if k < 3}
        avg_high = sum(high_res_wr.values()) / max(len(high_res_wr), 1)
        avg_low = sum(low_res_wr.values()) / max(len(low_res_wr), 1)
        if avg_high > avg_low:
            insights.append(f"共振≥3的胜率({avg_high:.0%})优于低共振({avg_low:.0%})——集中优势兵力有效")

        gross_profit = sum(r.pnl for r in wins) if wins else 0
        gross_loss = abs(sum(r.pnl for r in losses)) if losses else 1

        return CycleSummary(
            cycle_start=records[-1].entry_time,
            cycle_end=records[0].entry_time,
            total_trades=total,
            wins=len(wins),
            losses=len(losses),
            win_rate=round(len(wins) / total, 3),
            avg_r=round(sum(r.pnl_r for r in records) / total, 3),
            profit_factor=round(gross_profit / max(gross_loss, 1), 2),
            best_signal_type=best_sig,
            worst_signal_type=worst_sig,
            avg_quality_wins=round(avg_quality_wins, 3),
            avg_quality_losses=round(avg_quality_losses, 3),
            resonance_win_rate=resonance_win_rate,
            key_insight="; ".join(insights) if insights else "样本不足，继续积累实践材料",
            rule_changes=[],
        )

    def compute_insight(self, records: list[PracticeRecord]) -> str:
        """
        Extract the gap between judgment and reality.
        This is the core of 实践论: 认识 ↔ 实践的差距 = 认知盲区.
        """
        if len(records) < 5:
            return "实践材料不足，需要更多交易才能提取理性认识"

        insights = []

        # Check: did high-confidence setups actually perform better?
        high_conf = [r for r in records if r.signal_k_quality >= 0.7]
        low_conf = [r for r in records if r.signal_k_quality < 0.7]
        if len(high_conf) >= 3 and len(low_conf) >= 3:
            high_wr = sum(1 for r in high_conf if r.result == 'WIN') / len(high_conf)
            low_wr = sum(1 for r in low_conf if r.result == 'WIN') / len(low_conf)
            if high_wr > low_wr * 1.2:
                insights.append(f"高信号质量胜率({high_wr:.0%})显著优于低质量({low_wr:.0%})——质量阈值有效")
            elif low_wr > high_wr * 1.1:
                insights.append(f"信号质量与胜率无正相关——考虑降低质量权重，增加共振权重")

        # Check: trading at TR boundaries vs in the middle
        tr_trades = [r for r in records if 'TR' in (r.entry_reason or '')]
        trend_trades = [r for r in records if '趋势' in (r.entry_reason or '')]
        ema_trades = [r for r in records if 'EMA' in (r.entry_reason or '')]

        for name, trades in [("TR边界", tr_trades), ("趋势跟踪", trend_trades), ("EMA回调", ema_trades)]:
            if len(trades) >= 3:
                wr = sum(1 for t in trades if t.result == 'WIN') / len(trades)
                insights.append(f"{name}: {len(trades)}笔 胜率{wr:.0%}")

        # Check: premise消失 exits vs stop-loss exits
        premise_exits = [r for r in records if r.exit_reason == '前提消失']
        stop_exits = [r for r in records if r.exit_reason == '止损']
        if len(premise_exits) >= 2 and len(stop_exits) >= 2:
            prem_avg_loss = sum(abs(r.pnl) for r in premise_exits) / len(premise_exits)
            stop_avg_loss = sum(abs(r.pnl) for r in stop_exits) / len(stop_exits)
            if prem_avg_loss < stop_avg_loss * 0.8:
                insights.append(f"前提消失出场平均亏损({prem_avg_loss:.1f})<止损({stop_avg_loss:.1f})——主动撤退有效")

        return " | ".join(insights) if insights else "继续积累实践材料"
