"""蒙特卡洛模拟最近 N 场比赛的预测。"""\n\nimport json

import random
import time
from collections import Counter
from pathlib import Path
from typing import Dict, List, Any

from .state import build_state
from .model import simulate_group_match
from .fetch import load_matches

from ._paths import ROOT


def monte_carlo_predict_recent_matches(n: int = 10, sims: int = 300000) -> List[Dict[str, Any]]:
    """对最近 N 场未赛的小组赛进行蒙特卡洛模拟。"""
    state = build_state()
    by_code = state['by_code']
    matches = state['matches']
    
    unplayed = [m for m in matches 
                if m.get('score') is None 
                and m.get('stage') == 'group'
                and m.get('home') and m.get('away')]
    unplayed.sort(key=lambda m: m.get('date_utc', ''))
    recent_n = unplayed[:n]
    
    if not recent_n:
        print("没有未赛的小组赛需要模拟")
        return []
    
    print("蒙特卡洛模拟 %d 场比赛，每场 %d 万次..." % (n, sims//10000))
    t0 = time.time()
    
    results = []
    for m in recent_n:
        home = by_code[m['home']]
        away = by_code[m['away']]
        
        score_counts = Counter()
        win_counts = {'H': 0, 'D': 0, 'A': 0}
        
        rng = random.Random(hash(m['match']))
        for _ in range(sims):
            ga, gb = simulate_group_match(home, away, rng)
            score_counts[(ga, gb)] += 1
            
            if ga > gb:
                win_counts['H'] += 1
            elif ga == gb:
                win_counts['D'] += 1
            else:
                win_counts['A'] += 1
        
        elapsed = time.time() - t0
        print("  完成比赛 %d: %s vs %s (%.1fs)" % (m['match'], m['home'], m['away'], elapsed))
        
        results.append({
            'match_no': m['match'],
            'home': m['home'],
            'away': m['away'],
            'group': m.get('group', '-'),
            'date_utc': m['date_utc'],
            'elo_home': home['elo'],
            'elo_away': away['elo'],
            'win_counts': win_counts,
            'score_counts': score_counts,
            'total_sims': sims,
        })
    
    total_elapsed = time.time() - t0
    print("模拟完成，总耗时 %.1f 秒" % total_elapsed)
    return results


def update_data_js_with_mc_results(mc_results: List[Dict[str, Any]]) -> None:
    """将蒙特卡洛模拟结果更新到 web/data.js 文件中。"""
    if not mc_results:
        return
    
    data_path = ROOT / "web" / "data.js"
    content = data_path.read_text(encoding='utf-8')
    
    json_start = content.index('{')
    json_end = content.rindex('}') + 1
    json_str = content[json_start:json_end]
    data = json.loads(json_str)
    
    schedule = data.get('schedule', [])
    updated_count = 0
    
    for mc in mc_results:
        match_no = mc['match_no']
        n = mc['total_sims']
        
        p_home = mc['win_counts']['H'] / n
        p_draw = mc['win_counts']['D'] / n
        p_away = mc['win_counts']['A'] / n
        
        top_scores = mc['score_counts'].most_common(3)
        top_scores_formatted = [
            {"score": list(score), "p": round(count / n, 4)}
            for score, count in top_scores
        ]
        
        for s in schedule:
            if s.get('match') == match_no:
                if 'pred' in s:
                    s['pred']['p_home'] = round(p_home, 4)
                    s['pred']['p_draw'] = round(p_draw, 4)
                    s['pred']['p_away'] = round(p_away, 4)
                    s['pred']['top_scores'] = top_scores_formatted
                    s['pred']['mc_sims'] = n
                    updated_count += 1
                break
    
    if 'meta' in data:
        data['meta']['mc_updated'] = time.strftime("%Y-%m-%d %H:%M:%S")
        data['meta']['mc_matches'] = len(mc_results)
    
    new_content = content[:json_start] + json.dumps(data, ensure_ascii=False) + content[json_end:]
    data_path.write_text(new_content, encoding='utf-8')
    
    print("已更新 %d 场比赛的预测数据到 web/data.js" % updated_count)


if __name__ == "__main__":
    results = monte_carlo_predict_recent_matches(n=10, sims=300000)
    if results:
        for r in results:
            n = r['total_sims']
            print("\n比赛 %d: %s vs %s (小组%s)" % (r['match_no'], r['home'], r['away'], r['group']))
            print("  蒙特卡洛统计 (%d 万次模拟):" % (n//10000))
            print("    主胜: %d 次 (%.1f%%)" % (r['win_counts']['H'], r['win_counts']['H']/n*100))
            print("    平局: %d 次 (%.1f%%)" % (r['win_counts']['D'], r['win_counts']['D']/n*100))
            print("    客胜: %d 次 (%.1f%%)" % (r['win_counts']['A'], r['win_counts']['A']/n*100))
            
            top_scores = r['score_counts'].most_common(5)
            print("  Top 5 比分:")
            for i, ((ga, gb), cnt) in enumerate(top_scores, 1):
                print("    %d. %d-%d (%.1f%%, %d 次)" % (i, ga, gb, cnt/n*100, cnt))
        
        update_data_js_with_mc_results(results)

