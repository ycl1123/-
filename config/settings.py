from dataclasses import dataclass, field
from pathlib import Path
import yaml

@dataclass
class SignalKConfig:
    strong_trend_body_ratio: float = 0.70
    strong_trend_size_multiplier: float = 1.5
    doji_body_ratio: float = 0.10
    pin_bar_wick_multiplier: float = 3.0
    lookback_for_avg: int = 5

@dataclass
class SupportResistanceConfig:
    swing_order: int = 5
    ema_period: int = 20
    round_number_step: float = 50

@dataclass
class KeyZonesConfig:
    range_lookback: int = 20
    range_touch_min: int = 2
    confluence_threshold_pct: float = 0.05

@dataclass
class MarketContextConfig:
    always_in_threshold: float = 0.3
    ema_slope_lookback: int = 20
    momentum_lookback: int = 5

@dataclass
class ContradictionConfig:
    """矛盾论参数"""
    lookback: int = 20
    bar_strength_decay_threshold: float = 0.6
    pullback_deepening_threshold: float = 0.6
    momentum_divergence_threshold: float = 0.5
    climax_atr_multiplier: float = 1.8
    climax_min_count: int = 3
    sr_proximity_pct: float = 0.002
    ema_proximity_pct: float = 0.0015

@dataclass
class GuerrillaConfig:
    """游击战参数"""
    resonance_strong_threshold: int = 3    # ≥3 共振 = STRONG 信号
    resonance_offense_threshold: int = 4   # ≥4 共振 = 战略进攻(压倒性优势)
    resonance_defense_threshold: int = 1   # ≥1 共振 = 至少战略防御
    contradiction_downgrade: bool = True   # 矛盾转化中降级信号强度
    max_risk_defense_pct: float = 0.5      # 防御时仓位减半
    max_risk_offense_pct: float = 1.0      # 进攻时正常仓位

@dataclass
class PracticeConfig:
    """实践论参数"""
    journal_path: str = "data/practice_log.jsonl"
    cycle_size: int = 10                   # 每N笔交易做一次再认识复盘
    min_records_for_insight: int = 5

@dataclass
class AnalysisConfig:
    signal_k: SignalKConfig = field(default_factory=SignalKConfig)
    support_resistance: SupportResistanceConfig = field(default_factory=SupportResistanceConfig)
    key_zones: KeyZonesConfig = field(default_factory=KeyZonesConfig)
    market_context: MarketContextConfig = field(default_factory=MarketContextConfig)
    contradiction: ContradictionConfig = field(default_factory=ContradictionConfig)
    guerrilla: GuerrillaConfig = field(default_factory=GuerrillaConfig)
    practice: PracticeConfig = field(default_factory=PracticeConfig)

@dataclass
class MT5Config:
    polling_interval_ms: int = 5000
    history_bars: int = 500
    lot_size: float = 0.01
    risk_pct: float = 0.03              # 3% per trade risk
    daily_profit_target_pct: float = 0.15  # 15% daily profit target
    contract_size: int = 100            # XAUUSD standard lot = 100 oz

@dataclass
class GUIConfig:
    theme: str = "dark"
    window_title: str = "XAUUSD 信号面板"
    window_width: int = 1000
    window_height: int = 700
    alert_max_rows: int = 500

@dataclass
class AppConfig:
    symbol: str = "XAUUSD"
    timeframes: dict = field(default_factory=lambda: {"primary": "M5", "secondary": ["M15", "H1"]})
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    mt5: MT5Config = field(default_factory=MT5Config)
    gui: GUIConfig = field(default_factory=GUIConfig)

def load_config(path: str = None) -> AppConfig:
    if path is None:
        path = Path(__file__).parent.parent / "config.yaml"
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    cfg = AppConfig()
    if "symbol" in data:
        cfg.symbol = data["symbol"]
    if "timeframes" in data:
        cfg.timeframes = data["timeframes"]

    if "analysis" in data:
        a = data["analysis"]
        if "signal_k" in a:
            cfg.analysis.signal_k = SignalKConfig(**a["signal_k"])
        if "support_resistance" in a:
            cfg.analysis.support_resistance = SupportResistanceConfig(**a["support_resistance"])
        if "key_zones" in a:
            cfg.analysis.key_zones = KeyZonesConfig(**a["key_zones"])
        if "market_context" in a:
            cfg.analysis.market_context = MarketContextConfig(**a["market_context"])
        if "contradiction" in a:
            cfg.analysis.contradiction = ContradictionConfig(**a["contradiction"])
        if "guerrilla" in a:
            cfg.analysis.guerrilla = GuerrillaConfig(**a["guerrilla"])
        if "practice" in a:
            cfg.analysis.practice = PracticeConfig(**a["practice"])

    if "mt5" in data:
        cfg.mt5 = MT5Config(**data["mt5"])

    if "gui" in data:
        cfg.gui = GUIConfig(**data["gui"])

    return cfg
