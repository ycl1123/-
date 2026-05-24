---
name: brooks-signals-overview
description: "Al Brooks XAUUSD signal program — architecture, collaboration model, and key decisions"
metadata: 
  node_type: memory
  type: project
  originSessionId: fc75185d-dc2a-49a1-b8d6-c9093b71a4e5
---

# Brooks Signals — XAUUSD 信号面板

## 协作模式：半自动

| 环节 | 谁做 |
|---|---|
| 行情背景判断 | 用户（经验比程序准） |
| 信号识别+预警 | 程序（M2 K线最后5秒 ⏰ 收盘预警） |
| 开仓决策 | 用户在 MT5 手动下单 |
| 止损止盈 | 程序自动检测裸仓 → 挂 SL/TP |
| 手数 | 程序推荐（3%风险规则） |

## 用户核心原则

- **背景最重要** — 只做当前背景下的高概率交易 [[context-first-principle]]
- 主周期 M2（2分钟K线）
- 日盈利目标 15%
- 每笔风险 3%

## 技术架构

- PyQt6 GUI（深色主题，信号面板+告警）
- MT5 子进程隔离（QProcess → _mt5_worker.py）
- 4 信号策略：TR边界/EMA回调/强趋势K/TR强化（回测44% WR, 1.74 PF）
- 信号K线 + 支撑压力 + 关键区域 + 行情背景 四大面板
- 自动SL/TP：检测裸仓 → 同向信号用精准止损，否则ATR通用止损
- 日亏损/盈利双进度条

## 关键文件

- `d:\ai\brooks_signals\` — 项目根目录
- `gui/main_window.py` — 主窗口，含收盘预警、自动保护、手数推荐
- `mt5/_mt5_worker.py` — MT5子进程（fetch_data / set_sl_tp / execute_trade）
- `analysis/trade_signals.py` — 4信号策略
- `config.yaml` — 所有参数（手数、风险%、目标%）
