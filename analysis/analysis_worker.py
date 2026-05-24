"""
Analysis worker — runs in a subprocess to isolate any potential C-level crashes.
Reads bar data + config from a JSON file, runs all analysis, writes results to JSON.
"""
import sys
import json
import os
import traceback
import pandas as pd
import numpy as np


def main():
    try:
        if len(sys.argv) < 2:
            print(json.dumps({"ok": False, "error": "Usage: analysis_worker.py <input.json>"}))
            sys.exit(1)

        input_path = sys.argv[1]
        output_path = sys.argv[2] if len(sys.argv) > 2 else input_path.replace('.json', '_out.json')

        with open(input_path, 'r', encoding='utf-8') as f:
            payload = json.load(f)

        symbol = payload['symbol']
        timeframe = payload['timeframe']
        bar_list = payload['bars']
        lookback_for_avg = payload.get('lookback_for_avg', 20)
        ema_period = payload.get('ema_period', 20)
        swing_order = payload.get('swing_order', 5)
        round_step = payload.get('round_step', 50)
        always_in_threshold = payload.get('always_in_threshold', 0.3)
        range_lookback = payload.get('range_lookback', 20)
        range_touch_min = payload.get('range_touch_min', 2)
        confluence_threshold_pct = payload.get('confluence_threshold_pct', 0.3)

        # Build DataFrame
        df = pd.DataFrame(bar_list)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)
        df = df[['open', 'high', 'low', 'close', 'tick_volume', 'spread']]
        df.rename(columns={'tick_volume': 'volume'}, inplace=True)

        from analysis.signal_k import analyze_signal_k
        from analysis.support_resistance import analyze_support_resistance
        from analysis.key_zones import analyze_key_zones
        from analysis.market_context import analyze_context
        from analysis.trade_signals import compute_trade_signals

        # Step 1: Signal K
        signal_k_results = analyze_signal_k(df, lookback_for_avg)
        latest_sk = signal_k_results.iloc[-1] if len(signal_k_results) > 0 else None

        # Step 2: S/R
        sr_result = analyze_support_resistance(df, ema_period, swing_order, round_step)

        # Step 3: Context
        context_result = analyze_context(
            df, signal_k_results.apply(lambda x: x.score),
            ema_period, always_in_threshold
        )

        # Step 4: Zones
        zones_result = analyze_key_zones(
            df, sr_result.levels, range_lookback, range_touch_min, confluence_threshold_pct
        )

        # Step 5: Trade signals
        trade_signals = compute_trade_signals(
            df, latest_sk, signal_k_results.apply(lambda x: x.score),
            context_result, zones_result
        )

        # Serialize results
        current_bar = {
            'open': float(df.iloc[-1]['open']),
            'high': float(df.iloc[-1]['high']),
            'low': float(df.iloc[-1]['low']),
            'close': float(df.iloc[-1]['close']),
            'volume': float(df.iloc[-1]['volume']),
        }

        sk_out = None
        if latest_sk is not None:
            sk_out = {
                'bar_type': latest_sk.bar_type.name,
                'score': float(latest_sk.score),
                'is_bullish': bool(latest_sk.is_bullish),
                'body_ratio': float(latest_sk.body_ratio) if hasattr(latest_sk, 'body_ratio') else 0,
                'close_position': float(latest_sk.close_position) if hasattr(latest_sk, 'close_position') else 0.5,
                'upper_wick': float(latest_sk.upper_wick) if hasattr(latest_sk, 'upper_wick') else 0,
                'lower_wick': float(latest_sk.lower_wick) if hasattr(latest_sk, 'lower_wick') else 0,
            }

        sr_out = [{
            'price': float(l.price),
            'label': str(l.label),
            'level_type': str(l.level_type),
            'strength': float(l.strength),
        } for l in sr_result.levels]

        ctx_out = {
            'state': str(context_result.state),
            'always_in_direction': str(context_result.always_in.direction),
            'always_in_confidence': float(context_result.always_in.confidence),
            'ema_slope': float(context_result.always_in.ema_slope),
            'price_ema_score': float(context_result.always_in.price_ema_score),
            'momentum_score': float(context_result.always_in.momentum_score),
            'overlap_ratio': float(context_result.overlap_ratio),
            'trend_bar_ratio': float(context_result.trend_bar_ratio),
        }

        zones_out = [{
            'name': str(z.name),
            'lower': float(z.lower),
            'upper': float(z.upper),
            'touches': int(z.touches) if hasattr(z, 'touches') else 0,
            'strength': float(z.strength) if hasattr(z, 'strength') else 0.5,
        } for z in zones_result.zones]

        signals_out = [{
            'signal_type': str(ts.signal_type.value),
            'direction': str(ts.direction),
            'entry_price': float(ts.entry_price),
            'stop_price': float(ts.stop_price),
            'target_price': float(ts.target_price),
            'confidence': float(ts.confidence),
            'quality': float(ts.quality),
            'strength': ts.strength.name,
        } for ts in trade_signals]

        output = {
            'ok': True,
            'timestamp': str(df.index[-1]),
            'current_bar': current_bar,
            'signal_k': sk_out,
            'sr': sr_out,
            'context': ctx_out,
            'zones': zones_out,
            'trade_signals': signals_out,
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False)

        print(json.dumps({"ok": True, "output_file": output_path}))

    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e), "traceback": traceback.format_exc()}))
        sys.exit(1)


if __name__ == '__main__':
    main()
