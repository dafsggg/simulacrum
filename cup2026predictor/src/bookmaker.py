"""庄家思维分析：融合外部赔率 + Elo 推断的比分预测偏差。

数据源优先级：
1. the-odds-api.com (如有 API key)
2. 中国体彩网 sporttery.cn (免费，无需 key)
3. Elo + 球队风格推断 (无外部数据时)

核心逻辑：
- 从赔率反推庄家对总进球的隐含预期
- 比较模型预测 vs 庄家预期，生成比分偏移建议
- 检测冷门风险
"""

from __future__ import annotations

import json
import math
import statistics
from pathlib import Path

from .fetch import NAME_TO_CODE

from ._paths import ROOT
CACHE = ROOT / 'data' / 'bookmaker_insights.json'
BASE = 'https://api.the-odds-api.com/v4/sports'
OU_MAX_AGE = 90 * 60


def _to_code(name):
    return NAME_TO_CODE.get(name)


def _api_key():
    import os
    key = os.environ.get('ODDS_API_KEY')
    if key:
        return key
    cfg = ROOT / 'data' / 'config.json'
    if cfg.exists():
        return json.loads(cfg.read_text(encoding='utf-8')).get('odds_api_key')
    return None


def _devig(price):
    if price and price > 1.0:
        return 1.0 / price
    return 0.0


def _fetch_over_under(key):
    import urllib.request
    events = json.loads(urllib.request.urlopen(
        urllib.request.Request(BASE + '/soccer_fifa_world_cup/odds/'
                               '?apiKey=' + key + '&regions=eu&markets=ou&oddsFormat=decimal',
                               headers={'User-Agent': 'Mozilla/5.0'}),
        timeout=25).read().decode('utf-8'))
    out = {}
    for ev in events:
        hc, ac = _to_code(ev['home_team']), _to_code(ev['away_team'])
        if not hc or not ac:
            continue
        totals = []
        for bk in ev.get('bookmakers', []):
            for mk in bk.get('markets', []):
                if mk['key'] != 'total':
                    continue
                for o in mk.get('outcomes', []):
                    if o['name'] == 'Over':
                        total_line = float(o.get('point', 2.5))
                        p_over = _devig(o.get('price', 0))
                        totals.append({'total': total_line, 'p_over': p_over})
        if len(totals) >= 3:
            total_lines = [t['total'] for t in totals]
            most_common_total = max(set(total_lines), key=total_lines.count)
            filtered = [t for t in totals if t['total'] == most_common_total]
            p_over_median = statistics.median([t['p_over'] for t in filtered])
            implied_total = most_common_total + (0.5 - p_over_median) * 1.2
            out[hc + '|' + ac] = {
                'total_line': most_common_total,
                'p_over': round(p_over_median, 4),
                'implied_total_goals': round(implied_total, 2),
            }
    return out


def _elo_implied_total(ea, eb, style):
    from .model import BASE_TOTAL_GOALS, TOTAL_MISMATCH, win_expectancy, expected_goals
    we = win_expectancy(ea, eb)
    lam_a, lam_b = expected_goals(we)
    base = (lam_a + lam_b) * style
    elo_gap = abs(ea - eb)
    if elo_gap > 250:
        return base * 0.90
    elif elo_gap > 150:
        return base * 0.95
    elif elo_gap < 50:
        return base * 1.06
    return base


def _infer_over_under(home, away, model_total, h2h):
    from .model import effective_elo, style_scale, win_expectancy
    ea = effective_elo(home, away)
    eb = effective_elo(away, home)
    style = style_scale(home, away)
    implied = _elo_implied_total(ea, eb, style)
    calibration = 0.0
    if h2h:
        we_model = win_expectancy(ea, eb)
        is_home_favored = we_model > 0.5
        mkt_p_favored = h2h.get('p_home', 0) if is_home_favored else h2h.get('p_away', 0)
        model_p_favored = we_model if is_home_favored else (1 - we_model)
        diff = mkt_p_favored - model_p_favored
        calibration += diff * 0.8
        draw_diff = h2h.get('p_draw', 0) - 0.25
        calibration -= draw_diff * 1.2
        implied += calibration
    home_open = home.get('open', 1.0)
    away_open = away.get('open', 1.0)
    avg_open = (home_open + away_open) / 2.0
    if avg_open > 1.15:
        implied += 0.15
    elif avg_open < 0.85:
        implied -= 0.15
    implied = max(implied, 1.5)
    total_line = round(implied / 0.5) * 0.5
    p_over = 1.0 / (1.0 + 2.0 ** ((total_line - implied) / 0.5))
    return {'total_line': total_line, 'p_over': round(p_over, 4),
            'implied_total_goals': round(implied, 2)}


def _upset_risk(home, away, we_model, h2h):
    if h2h:
        if we_model > 0.55:
            return max(0, (we_model - h2h.get('p_home', we_model)) / we_model)
        elif we_model < 0.45:
            return max(0, (1 - we_model - h2h.get('p_away', 1 - we_model)) / (1 - we_model))
        return 0.0
    else:
        gap = abs(home.get('elo', 1500) - away.get('elo', 1500))
        return min(gap / 1600.0, 0.30)


def compute_bookmaker_insights(state):
    from .model import expected_goals, win_expectancy, effective_elo, style_scale
    from . import odds
    from . import sporttery

    odds_cache = odds.load() or {}
    h2h_from_odds = odds_cache.get('h2h', {})
    
    sporttery_cache = sporttery.load() or {}
    h2h_from_sporttery = sporttery_cache.get('h2h', {})
    
    h2h_all = {}
    h2h_all.update(h2h_from_sporttery)
    h2h_all.update(h2h_from_odds)
    
    ou_data = {}
    
    by_code = state['by_code']
    insights = {}

    for m in state['matches']:
        if not (m['home'] and m['away']) or m.get('score'):
            continue

        home_code, away_code = m['home'], m['away']
        home = by_code.get(home_code)
        away = by_code.get(away_code)
        if not home or not away:
            continue

        ea = effective_elo(home, away)
        eb = effective_elo(away, home)
        we = win_expectancy(ea, eb)
        lam_a, lam_b = expected_goals(we)
        st = style_scale(home, away)
        model_total = (lam_a + lam_b) * st

        mkt_key = home_code + '|' + away_code
        mkt_data = h2h_all.get(mkt_key, {})
        
        if mkt_data:
            inferred = _infer_over_under(home, away, model_total, mkt_data)
            market_total = inferred['implied_total_goals']
            p_over = inferred['p_over']
        else:
            inferred = _infer_over_under(home, away, model_total, None)
            market_total = inferred['implied_total_goals']
            p_over = inferred['p_over']

        total_gap = market_total - model_total

        if total_gap > 0.2:
            bias = 'over'
        elif total_gap < -0.2:
            bias = 'under'
        else:
            bias = 'neutral'

        upset_risk = _upset_risk(home, away, we, mkt_data if mkt_data else None)

        score_shift = {}
        if bias == 'over':
            magnitude = min(abs(total_gap) / 1.5, 0.12)
            if bias == 'neutral' and abs(total_gap) > 0.05:
                magnitude = min(abs(total_gap) / 2.0, 0.06)
                bias = 'over' if total_gap > 0 else 'under'
            score_shift = {'shift_mode': bias,
                          'magnitude': max(magnitude, 0.02)}
        elif bias == 'under':
            magnitude = min(abs(total_gap) / 1.5, 0.12)
            score_shift = {'shift_mode': bias,
                          'magnitude': max(magnitude, 0.02)}

        insights[(home_code, away_code)] = {
            'model_total': round(model_total, 2),
            'market_total': round(market_total, 2),
            'total_gap': round(total_gap, 2),
            'bias': bias,
            'upset_risk': round(upset_risk, 3),
            'score_shift': score_shift,
        }

    return insights


def sync():
    key = _api_key()
    if key:
        try:
            cache = load() or {}
            now = __import__('time').time()
            if now - cache.get('ou_ts', 0) > OU_MAX_AGE:
                cache['ou'] = _fetch_over_under(key)
                cache['ou_ts'] = now
                print('  [bookmaker] 已更新大小球盘口 ' + str(len(cache['ou'])) + ' 场')
            CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding='utf-8')
        except Exception as exc:
            print('  [bookmaker] 抓取失败（' + str(exc) + '），沿用缓存')
    return load() or None


def load():
    if CACHE.exists():
        return json.loads(CACHE.read_text(encoding='utf-8'))
    return None


from . import odds
from . import sporttery


if __name__ == '__main__':
    sync()