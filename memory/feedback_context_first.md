---
name: context-first-principle
description: Market context determines everything — only trade within the current background
metadata: 
  node_type: memory
  type: feedback
  originSessionId: fc75185d-dc2a-49a1-b8d6-c9093b71a4e5
---

**Rule**: 背景最重要 (Context is everything). Always determine the market state FIRST, then only take trades that are appropriate for that background. Never trade against the context.

**Why**: User's core trading philosophy — "我们在当前背景下做大概率的事情" (we do high-probability things within the current context). This is the foundation of Al Brooks price action.

**How to apply**: 
- Before ANY signal generation, market state MUST be classified: TREND (STRONG_TREND/WEAK_TREND) vs TRADING_RANGE vs CHANNEL
- TR boundary fade signals ONLY fire in TRADING_RANGE — never fade boundaries in a trend
- EMA pullback + strong trend K ONLY fire in trend — never chase pullbacks in a range
- Always In direction gates all trend-following entries
- When in doubt about context → NO trade
- Context is determined by `analyze_context()` which combines: EMA slope, HH/HL structure, overlap ratio, Always In direction
- Every signal function checks `state` and `ai_dir` as the first condition, before evaluating any other criteria
