"""
MT5 worker — runs in a subprocess to isolate C-level crashes from the GUI.
Reads config from a JSON file (passed as command-line argument).
Outputs results as JSON to stdout.

Actions:
  fetch_data     — fetch bars + account info + open positions
  execute_trade  — place market order with SL/TP
  set_sl_tp      — modify existing position's SL/TP
"""
import sys
import json
import traceback


def _get_tf_map():
    import MetaTrader5 as mt5
    return {
        "M1": mt5.TIMEFRAME_M1, "M2": mt5.TIMEFRAME_M2,
        "M3": mt5.TIMEFRAME_M3, "M4": mt5.TIMEFRAME_M4,
        "M5": mt5.TIMEFRAME_M5, "M6": mt5.TIMEFRAME_M6,
        "M10": mt5.TIMEFRAME_M10, "M12": mt5.TIMEFRAME_M12,
        "M15": mt5.TIMEFRAME_M15, "M20": mt5.TIMEFRAME_M20,
        "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4, "D1": mt5.TIMEFRAME_D1,
    }


def _get_account(mt5):
    acc = mt5.account_info()
    if not acc:
        return None
    return {
        "login": int(acc.login),
        "balance": float(acc.balance),
        "equity": float(acc.equity),
        "margin": float(acc.margin),
        "margin_free": float(acc.margin_free),
        "profit": float(acc.profit),
        "currency": str(acc.currency),
        "leverage": int(acc.leverage),
        "name": str(acc.name),
        "server": str(acc.server),
    }


def _get_positions(mt5, symbol: str) -> list:
    """Return open positions for symbol as dicts."""
    positions = mt5.positions_get(symbol=symbol)
    if not positions:
        return []
    result = []
    for pos in positions:
        result.append({
            "ticket": int(pos.ticket),
            "symbol": str(pos.symbol),
            "type": "BUY" if int(pos.type) == 0 else "SELL",
            "volume": float(pos.volume),
            "price_open": float(pos.price_open),
            "sl": float(pos.sl),
            "tp": float(pos.tp),
            "profit": float(pos.profit),
            "comment": str(pos.comment),
        })
    return result


def _fetch_data(config):
    symbol = config['symbol']
    timeframes = config['timeframes']
    history_bars = config['history_bars']

    import MetaTrader5 as mt5

    if not mt5.initialize():
        error = str(mt5.last_error())
        mt5.shutdown()
        return {"ok": False, "error": f"MT5 init failed: {error}"}

    account_data = _get_account(mt5)
    positions = _get_positions(mt5, symbol)

    tf_map = _get_tf_map()
    result_bars = {}
    for tf_str in timeframes:
        tf = tf_map.get(tf_str)
        if tf is None:
            continue
        try:
            rates = mt5.copy_rates_from_pos(symbol, tf, 0, history_bars)
            if rates is not None and len(rates) > 0:
                bars_list = []
                for r in rates:
                    bars_list.append({
                        'time': int(r['time']),
                        'open': float(r['open']),
                        'high': float(r['high']),
                        'low': float(r['low']),
                        'close': float(r['close']),
                        'tick_volume': float(r['tick_volume']),
                        'spread': float(r['spread']),
                    })
                result_bars[tf_str] = bars_list
        except Exception as e:
            print(f"[worker] load {tf_str} error: {e}", file=sys.stderr)

    mt5.shutdown()
    return {
        "ok": True,
        "account": account_data,
        "bars": result_bars,
        "positions": positions,
    }


def _execute_trade(config):
    symbol = config['symbol']
    direction = config['direction']
    volume = float(config['volume'])
    sl_price = float(config['sl_price'])
    tp_price = float(config['tp_price'])
    comment = config.get('comment', 'Brooks Signal')

    import MetaTrader5 as mt5

    if not mt5.initialize():
        error = str(mt5.last_error())
        mt5.shutdown()
        return {"ok": False, "error": f"MT5 init failed: {error}"}

    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        mt5.shutdown()
        return {"ok": False, "error": f"Symbol not found: {symbol}"}

    if not symbol_info.visible:
        if not mt5.symbol_select(symbol, True):
            mt5.shutdown()
            return {"ok": False, "error": f"Failed to select symbol: {symbol}"}

    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        mt5.shutdown()
        return {"ok": False, "error": "Failed to get tick data"}

    order_type = mt5.ORDER_TYPE_BUY if direction == 'L' else mt5.ORDER_TYPE_SELL
    price = tick.ask if direction == 'L' else tick.bid
    filling_mode = symbol_info.filling_mode

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": order_type,
        "price": price,
        "sl": sl_price,
        "tp": tp_price,
        "deviation": 30,
        "magic": 123456,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result is None:
        mt5.shutdown()
        return {"ok": False, "error": "order_send returned None"}

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        if filling_mode & mt5.ORDER_FILLING_RETURN:
            request["type_filling"] = mt5.ORDER_FILLING_RETURN
            result = mt5.order_send(request)

    mt5.shutdown()

    if result is None:
        return {"ok": False, "error": "order_send returned None"}

    if result.retcode == mt5.TRADE_RETCODE_DONE:
        return {
            "ok": True,
            "order_id": int(result.order),
            "volume": volume,
            "entry_price": float(result.price),
            "sl_price": sl_price,
            "tp_price": tp_price,
            "direction": direction,
            "comment": comment,
        }
    else:
        return {
            "ok": False,
            "error": f"Order failed: retcode={result.retcode}, comment={result.comment}",
            "retcode": int(result.retcode),
            "comment": str(result.comment),
        }


def _set_sl_tp(config):
    """Modify an existing position to add SL/TP."""
    ticket = int(config['ticket'])
    sl_price = float(config['sl_price'])
    tp_price = float(config['tp_price'])
    symbol = config.get('symbol', '')

    import MetaTrader5 as mt5

    if not mt5.initialize():
        error = str(mt5.last_error())
        mt5.shutdown()
        return {"ok": False, "error": f"MT5 init failed: {error}"}

    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "position": ticket,
        "sl": sl_price,
        "tp": tp_price,
    }
    if symbol:
        request["symbol"] = symbol

    result = mt5.order_send(request)
    mt5.shutdown()

    if result is None:
        return {"ok": False, "error": "order_send returned None"}

    if result.retcode == mt5.TRADE_RETCODE_DONE:
        return {
            "ok": True,
            "ticket": ticket,
            "sl_price": sl_price,
            "tp_price": tp_price,
        }
    else:
        return {
            "ok": False,
            "error": f"SL/TP failed: retcode={result.retcode}, comment={result.comment}",
            "retcode": int(result.retcode),
        }


def main():
    try:
        if len(sys.argv) < 2:
            print(json.dumps({"ok": False, "error": "Usage: _mt5_worker.py <config.json>"}))
            sys.exit(1)

        config_path = sys.argv[1]
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        action = config.get('action', 'fetch_data')

        if action == 'execute_trade':
            result = _execute_trade(config)
        elif action == 'set_sl_tp':
            result = _set_sl_tp(config)
        else:
            result = _fetch_data(config)

        print(json.dumps(result))

    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e), "traceback": traceback.format_exc()}))
        sys.exit(1)


if __name__ == '__main__':
    main()
