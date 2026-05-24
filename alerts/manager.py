from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from PyQt6.QtCore import QObject, pyqtSignal

class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    SIGNAL = "signal"
    STRATEGIC = "strategic"      # 战略层告警（矛盾转化/状态切换）
    TACTICAL = "tactical"        # 战术层告警（共振/兵力评估）

@dataclass
class Alert:
    time: datetime
    symbol: str
    timeframe: str
    message: str
    severity: AlertSeverity

class AlertManager(QObject):
    new_alert = pyqtSignal(Alert)

    def __init__(self):
        super().__init__()
        self._alerts: list[Alert] = []
        self._last_signal_k_time: dict[str, datetime] = {}
        self._last_context_direction: dict[str, str] = {}
        self._last_zone_alerts: set[str] = set()
        self._last_contradiction_state: dict[str, str] = {}
        self._last_transition_risk: dict[str, str] = {}
        self._last_resonance_level: dict[str, int] = {}

    def add(self, symbol: str, timeframe: str, message: str,
            severity: AlertSeverity = AlertSeverity.INFO):
        now = datetime.now()
        alert = Alert(time=now, symbol=symbol, timeframe=timeframe,
                      message=message, severity=severity)
        self._alerts.append(alert)
        self.new_alert.emit(alert)

    def add_signal_k(self, symbol: str, timeframe: str, message: str):
        """Deduplicate signal K alerts per bar."""
        key = f"{symbol}_{timeframe}"
        self.add(symbol, timeframe, message, AlertSeverity.SIGNAL)
        self._last_signal_k_time[key] = datetime.now()

    def add_context_change(self, symbol: str, timeframe: str, new_direction: str):
        """Alert when Always In changes."""
        key = f"{symbol}_{timeframe}"
        old = self._last_context_direction.get(key, "")
        if old != new_direction:
            self.add(symbol, timeframe,
                     f"Always In 变更: {old} → {new_direction}",
                     AlertSeverity.WARNING)
            self._last_context_direction[key] = new_direction

    def add_zone_touch(self, symbol: str, timeframe: str, zone_name: str, price: float):
        """Deduplicate zone touch alerts."""
        key = f"{symbol}_{timeframe}_{zone_name}"
        if key not in self._last_zone_alerts:
            self.add(symbol, timeframe,
                     f"触及关键区域: {zone_name} @ {price:.2f}",
                     AlertSeverity.WARNING)
            self._last_zone_alerts.add(key)
            # Keep set bounded
            if len(self._last_zone_alerts) > 50:
                self._last_zone_alerts.clear()

    def clear_zone_alerts(self):
        self._last_zone_alerts.clear()

    def get_recent(self, count: int = 100) -> list[Alert]:
        return self._alerts[-count:]

    # ============================================================
    # 战略层告警（矛盾论驱动）
    # ============================================================

    def add_contradiction_change(self, symbol: str, timeframe: str,
                                  contradiction_type: str, transformation_risk: str,
                                  transition: str, conditions_met: int):
        """矛盾结构变化告警 — 战略层最重要的事件。"""
        key = f"{symbol}_{timeframe}"
        old_type = self._last_contradiction_state.get(key, "")
        old_risk = self._last_transition_risk.get(key, "")

        # Only alert on meaningful changes
        if old_type != contradiction_type or old_risk != transformation_risk:
            severity = AlertSeverity.STRATEGIC

            if transformation_risk in ("HIGH", "高转化概率"):
                severity = AlertSeverity.STRATEGIC
                msg = (f"[矛盾转化] {contradiction_type} → 转化风险:{transformation_risk} | "
                       f"状态转换:{transition} | 条件满足:{conditions_met}/8")
            elif old_type != contradiction_type:
                severity = AlertSeverity.WARNING
                msg = (f"[矛盾结构] {old_type} → {contradiction_type} | "
                       f"状态转换:{transition}")
            else:
                severity = AlertSeverity.INFO
                msg = (f"[矛盾更新] {contradiction_type} | 转化置信度: "
                       f"{'高' if transformation_risk in ('HIGH','高转化概率') else '中低'} | "
                       f"条件:{conditions_met}/8")

            self.add(symbol, timeframe, msg, severity)
            self._last_contradiction_state[key] = contradiction_type
            self._last_transition_risk[key] = transformation_risk

    def add_resonance_alert(self, symbol: str, timeframe: str,
                            resonance_count: int, tactical_layer: str,
                            direction: str):
        """共振水平告警 — 游击战兵力评估。"""
        key = f"{symbol}_{timeframe}_res"
        old_level = self._last_resonance_level.get(key, -1)

        if resonance_count != old_level and resonance_count >= 3:
            severity = AlertSeverity.TACTICAL
            if resonance_count >= 4:
                msg = (f"[集中优势兵力] {direction}方向 共振{resonance_count}/5 | "
                       f"战术层级:{tactical_layer} — 压倒性优势")
            else:
                msg = (f"[兵力集中] {direction}方向 共振{resonance_count}/5 | "
                       f"战术层级:{tactical_layer}")

            self.add(symbol, timeframe, msg, severity)
            self._last_resonance_level[key] = resonance_count

    def add_guerrilla_alert(self, symbol: str, timeframe: str,
                            tactical_layer: str, reason: str):
        """游击战战术切换告警。"""
        severity = AlertSeverity.TACTICAL
        if tactical_layer == "战略转移":
            severity = AlertSeverity.WARNING
            msg = f"[灵活机动] {reason} — 进入战略转移(保存自己)"
        elif tactical_layer == "战略防御":
            msg = f"[保存自己] {reason} — 进入战略防御(小仓试探)"
        else:
            msg = f"[战略进攻] {reason}"

        self.add(symbol, timeframe, msg, severity)

    def add_practice_insight(self, symbol: str, timeframe: str, insight: str):
        """实践论洞察 — 从交易中提取的理性认识。"""
        self.add(symbol, timeframe, f"[实践认识] {insight}", AlertSeverity.INFO)
