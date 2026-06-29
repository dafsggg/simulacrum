"""小组赛控分分析：识别球队的控分动机并给比分预测加入偏差。

核心思路：
1. 小组赛最后轮次（第3轮）最容易发生控分——球队可能已确定出线/淘汰，
   或需要特定比分来刷净胜球/避开强敌。
2. 通过模拟小组赛前2轮所有可能结果，计算每支球队在第3轮不同比分下的
   出线概率和净胜球优势，从而量化控分动机。
3. 当检测到强控分动机时，给比分分布加上对应的"控分偏差"：
   - 确保出线型：增加 0-0/1-0 等保守比分概率
   - 刷净胜球型：增加 3-0/3-1 等进攻比分概率
   - 故意平局型：增加 1-1/2-2 等平局比分概率
   - 必须取胜型：增加 2-1/3-1 等胜负分明比分概率

数据来源：matches.json（赛程+比分）+ teams.json（球队信息）
"""

from __future__ import annotations

import json
import random
from itertools import combinations
from pathlib import Path

from .tournament import GROUPS

from ._paths import ROOT


def load_matches() -> list:
    return json.loads((ROOT / "data" / "matches.json").read_text(encoding="utf-8"))


def load_teams() -> dict:
    return {
        t["code"]: dict(t)
        for t in json.loads((ROOT / "data" / "teams.json").read_text(encoding="utf-8"))["teams"]
    }


def _compute_group_standing(
    teams_in_group: list,
    results: list,
) -> list:
    """根据比赛结果计算小组排名（积分→净胜球→进球→随机）"""
    table = {t["code"]: {"pts": 0, "gf": 0, "ga": 0} for t in teams_in_group}
    for home, away, gh, ga in results:
        table[home]["gf"] += gh
        table[home]["ga"] += ga
        table[away]["gf"] += ga
        table[away]["ga"] += gh
        if gh > ga:
            table[home]["pts"] += 3
        elif ga > gh:
            table[away]["pts"] += 3
        else:
            table[home]["pts"] += 1
            table[away]["pts"] += 1
    rows = [(code, t["pts"], t["gf"] - t["ga"], t["gf"]) for code, t in table.items()]
    rows.sort(key=lambda r: (r[1], r[2], r[3]), reverse=True)
    return rows


def _simulate_remaining(
    group_code, teams, results_so_far, remaining_matches, test_score=None, n_sims=500
):
    """模拟剩余比赛，评估控分动机。（保留原接口）"""
    import random
    rng = random.Random(hash(group_code) + len(results_so_far))
    rank_counts = {t['code']: {i + 1: 0 for i in range(len(teams))} for t in teams}
    for _ in range(n_sims):
        sim_results = list(results_so_far)
        for m in remaining_matches:
            gh = rng.randint(0, 4)
            ga = rng.randint(0, 4)
            sim_results.append((m['home'], m['away'], gh, ga))
        standings = _compute_group_standing(teams, sim_results)
        for rank, (code, _, _, _) in enumerate(standings, 1):
            rank_counts[code][rank] += 1
    probs = {}
    for code in rank_counts:
        total = sum(rank_counts[code].values())
        probs[code] = {r: c / total for r, c in rank_counts[code].items()}
    return probs


def analyze_group_control(state):
    """分析小组赛第3轮的控分动机。"""
    matches = state['matches']
    by_code = state['by_code']

    group_matches = {g: [] for g in GROUPS}
    for m in matches:
        if m.get('stage') == 'group' and m.get('home') and m.get('away'):
            team = by_code.get(m['home'])
            if team:
                group_matches[team['group']].append(m)

    insights = {}

    for group_code, g_matches in group_matches.items():
        g_matches_sorted = sorted(g_matches, key=lambda m: m.get('date_utc', ''))
        round3_matches = [m for m in g_matches_sorted if m.get('round') == '3' or
                          (len(g_matches_sorted) >= 3 and g_matches_sorted.index(m) >= len(g_matches_sorted) - 2)]

        for m in round3_matches:
            if not (m.get('home') and m.get('away')):
                continue
            if m.get('score'):
                continue
            home_code = m['home']
            away_code = m['away']
            home = by_code.get(home_code)
            away = by_code.get(away_code)
            if not home or not away:
                continue
            group_teams = [t for t in by_code.values() if t.get('group') == group_code]
            group_results = []
            for gm in g_matches_sorted:
                if gm.get('score') and gm.get('home') and gm.get('away') and gm['match'] != m['match']:
                    group_results.append((gm['home'], gm['away'], gm['score'][0], gm['score'][1]))

            test_scores = [(0,0),(1,0),(0,1),(1,1),(2,0),(0,2),(2,1),(1,2),(3,0),(2,2),(0,3),(1,3),(3,1),(3,2),(2,3)]
            best_adj = 0
            best_type = None
            best_desc = ''

            for gh, ga in test_scores:
                sim_results = list(group_results) + [(home_code, away_code, gh, ga)]
                standings = _compute_group_standing(group_teams, sim_results)
                home_rank = away_rank = None
                for i, (code, pts, gd, gf) in enumerate(standings):
                    if code == home_code:
                        home_rank = i + 1
                    if code == away_code:
                        away_rank = i + 1
                adj = 0
                ctrl = None
                desc = ''
                if home_rank is not None:
                    if home_rank <= 1:
                        adj -= 0.5
                        ctrl = 'ensure_qualify'
                        desc = '%s 已锁定小组前2，可能保守控分' % home.get('name_zh', home_code)
                    elif home_rank >= 3:
                        adj -= 0.3
                        if not ctrl:
                            ctrl = 'ensure_qualify'
                            desc = '%s 基本淘汰，轮换阵容减少失球' % home.get('name_zh', home_code)
                if away_rank is not None:
                    if away_rank <= 1 and not ctrl:
                        adj -= 0.5
                        ctrl = 'ensure_qualify'
                    elif away_rank >= 3 and not ctrl:
                        adj -= 0.3
                        ctrl = 'ensure_qualify'
                if home_rank and home_rank <= 2:
                    home_pts = standings[home_rank - 1][1]
                    for i, (code, pts, gd, gf) in enumerate(standings):
                        if code != home_code and abs(pts - home_pts) <= 1 and i < 2:
                            adj += 0.4
                            ctrl = 'brush_gs'
                            desc = '%s 需要刷净胜球确保小组前2' % home.get('name_zh', home_code)
                            break
                if home_rank is not None and away_rank is not None:
                    if home_rank <= 2 and away_rank <= 2 and gh == ga:
                        adj -= 0.3
                        if not ctrl:
                            ctrl = 'force_draw'
                            desc = '双方握手言和，携手出线'
                if home_rank is not None and home_rank == 3:
                    adj += 0.3
                    if not ctrl:
                        ctrl = 'must_win'
                        desc = '%s 必须取胜争夺最佳小组第3' % home.get('name_zh', home_code)
                if best_type is None or abs(adj) > abs(best_adj):
                    best_adj = adj
                    best_type = ctrl
                    best_desc = desc

            if best_type:
                typ_map = {'ensure_qualify':['0-0','1-0','0-1'],'brush_gs':['3-0','3-1','2-0'],
                           'force_draw':['1-1','0-0','2-2'],'must_win':['2-1','3-1','2-0']}
                typical = typ_map.get(best_type, [])
                insights[(home_code, away_code)] = {
                    'control_type': best_type,
                    'control_probability': min(abs(best_adj) / 0.5, 1.0),
                    'expected_goal_adjustment': round(best_adj, 2),
                    'typical_scores': typical,
                    'description': best_desc,
                }
            else:
                insights[(home_code, away_code)] = {
                    'control_type': None, 'control_probability': 0.0,
                    'expected_goal_adjustment': 0.0, 'typical_scores': [], 'description': '',
                }

    return insights


if __name__ == '__main__':
    from .state import build_state
    state = build_state()
    results = analyze_group_control(state)
    for key, val in results.items():
        if val['control_type']:
            print('%s vs %s: %s (%.0f%%)' % (key[0], key[1], val['control_type'], val['control_probability']*100))
            print('  %s' % val['description'])
            print('  典型比分: %s' % ', '.join(val['typical_scores']))
