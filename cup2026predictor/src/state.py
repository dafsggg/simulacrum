"""动态赛事状态：基准 Elo + 已赛结果 → 当前 Elo / 模型战绩 / 条件模拟输入。

设计原则：
- 已赛预测结果存入 played_preds.json，之后不再重新计算（保持历史预测不变）
- Elo 更新和开放度调整仍对所有已赛场生效（用于锦标赛模拟）
- 未赛预测只更新最近 5 场，其余保持不变
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from . import odds
from .elo import update_elo
from .fetch import load_matches
from .model import (effective_elo, expected_goals, exact_score_prob,
                    match_probabilities, score_grid, style_scale,
                    win_expectancy)
from .tournament import GROUPS
from . import bookmaker, group_control

from ._paths import ROOT
LOCKED_PATH = ROOT / "data" / "locked_preds.json"
PLAYED_PREDS_PATH = ROOT / "data" / "played_preds.json"  # 已赛预测固定存档
MODEL_WEIGHT = 0.5   # 融合权重：模型 0.5 + 市场 0.5


OPEN_UPDATE_K = 0.08          # 赛中开放度学习率
OPEN_MIN, OPEN_MAX = 0.65, 1.5


def load_teams() -> dict[str, dict]:
    data = json.loads((ROOT / "data" / "teams.json").read_text(encoding="utf-8"))
    teams = {t["code"]: dict(t) for t in data["teams"]}
    spath = ROOT / "data" / "strengths.json"
    if spath.exists():
        strengths = json.loads(spath.read_text(encoding="utf-8"))
        for code, t in teams.items():
            t["open"] = strengths.get(code, {}).get("open", 1.0)
    return teams


def outcome_of(score) -> str:
    gh, ga = score
    return "H" if gh > ga else ("A" if ga > gh else "D")


def _load_locked() -> dict:
    if LOCKED_PATH.exists() and LOCKED_PATH.stat().st_size > 0:
        try:
            return json.loads(LOCKED_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _load_played_preds() -> dict:
    """加载已赛预测存档。格式: {match_id: {p_home, p_draw, p_away, pick, pred_score, top_scores, grid, p_actual_score, market, elo_home_before, elo_away_before}}"""
    if PLAYED_PREDS_PATH.exists() and PLAYED_PREDS_PATH.stat().st_size > 0:
        try:
            return json.loads(PLAYED_PREDS_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_played_preds(preds: dict) -> None:
    """保存已赛预测存档。"""
    PLAYED_PREDS_PATH.write_text(json.dumps(preds, ensure_ascii=False, indent=1),
                                encoding="utf-8")


def build_state() -> dict:
    """回放全部已赛比赛，返回当前完整状态。

    重要原则：
    - 已赛场的预测结果存入 played_preds.json，之后不再重新计算（保持历史预测不变）
    - Elo 更新和开放度调整仍对所有已赛场生效（用于锦标赛模拟）
    """
    by_code = load_teams()
    for t in by_code.values():
        t["elo_base"] = t["elo"]  # 保留开赛日快照，elo 字段动态演化

    matches = load_matches()
    played = [m for m in matches if m["score"] and m["home"] and m["away"]]
    played.sort(key=lambda m: (m["date_utc"], m["match"]))

    # 已赛预测存档（只增不减，保证历史预测不变）
    played_preds = _load_played_preds()

    # 赛前锁定的「模型+市场」融合预测（开赛前最后一次更新写入，赛后冻结）
    locked = _load_locked()

    # ---- 庄家思维 + 控分偏差分析 ----
    bookmaker_insights = bookmaker.compute_bookmaker_insights({
        "by_code": by_code,
        "matches": matches,
    })
    group_control_insights = group_control.analyze_group_control({
        "by_code": by_code,
        "matches": matches,
    })

    def _merge_shift(home_code, away_code):
        "融合庄家思维和控分偏差为一个 score_shift dict."
        bk = bookmaker_insights.get((home_code, away_code), {})
        gc = group_control_insights.get((home_code, away_code), {})
        bk_shift = bk.get("score_shift", {})
        ctrl = gc.get("control_type")
        ctrl_mag = gc.get("control_probability", 0)

        combined = {}
        if bk_shift:
            combined["shift_mode"] = bk_shift.get("shift_mode", "neutral")
            combined["magnitude"] = bk_shift.get("magnitude", 0)
        if ctrl:
            combined["control_type"] = ctrl
            combined["control_magnitude"] = round(min(ctrl_mag, 0.1), 4)
        return combined if combined else None

    n_outcome_hit = n_score_hit = 0
    brier_sum = 0.0

    records = []
    new_played_preds = {}  # 本轮新增的已赛预测
    for m in played:
        home, away = by_code[m["home"]], by_code[m["away"]]
        ko = m["stage"] != "group"
        lk = locked.get(str(m["match"]))
        we_o = lk["we"] if lk else None
        shift = _merge_shift(m["home"], m["away"])

        # 关键：已赛场从存档读取预测，保证历史预测不变
        match_id = str(m["match"])
        if match_id in played_preds:
            # 使用存档中的固定预测
            stored = played_preds[match_id]
            pred_record = {
                "p_home": stored["p_home"],
                "p_draw": stored["p_draw"],
                "p_away": stored["p_away"],
                "pick": stored["pick"],
                "pred_score": stored["pred_score"],
                "top_scores": stored["top_scores"],
                "grid": stored["grid"],
                "p_actual_score": stored["p_actual_score"],
                "market": stored.get("market"),
                "elo_home_before": stored["elo_home_before"],
                "elo_away_before": stored["elo_away_before"],
            }
            outcome_hit = stored["outcome_hit"]
            score_hit = stored["score_hit"]
            actual = outcome_of(m["score"])
            probs = {"H": stored["p_home"], "D": stored["p_draw"], "A": stored["p_away"]}
            predicted = max(probs, key=probs.get)
            # Brier score 用存档的概率重新计算（保持一致性）
            brier_sum += sum((probs[o] - (1.0 if o == actual else 0.0)) ** 2 for o in "HDA")
            n_outcome_hit += outcome_hit
            n_score_hit += score_hit
        else:
            # 新已赛：使用赛前 Elo 计算预测并存档（保证历史预测不变）
            # 使用 elo_base（赛前原始 Elo）而非当前已更新的 Elo
            home_before = home["elo_base"]
            away_before = away["elo_base"]
            
            # 创建临时副本用于赛前预测计算
            home_copy = {**home, "elo": home_before}
            away_copy = {**away, "elo": away_before}
            
            pred = match_probabilities(home_copy, away_copy, knockout=ko, we_override=we_o,
                                      score_shift=shift)
            top_score = pred["outcome_score"][0]
            actual = outcome_of(m["score"])
            probs = {"H": pred["p_win"], "D": pred["p_draw"], "A": pred["p_loss"]}
            predicted = max(probs, key=probs.get)
            outcome_hit = predicted == actual
            score_hit = list(top_score) == list(m["score"])
            n_outcome_hit += outcome_hit
            n_score_hit += score_hit
            brier_sum += sum((probs[o] - (1.0 if o == actual else 0.0)) ** 2
                             for o in "HDA")

            grid = score_grid(home_copy, away_copy, we_override=we_o, score_shift=shift)
            p_actual = exact_score_prob(home_copy, away_copy, *m["score"], we_override=we_o,
                                        score_shift=shift)
            stored = {
                "p_home": round(pred["p_win"], 4),
                "p_draw": round(pred["p_draw"], 4),
                "p_away": round(pred["p_loss"], 4),
                "pick": pred["outcome_pick"],
                "pred_score": list(top_score),
                "top_scores": [{"score": list(s), "p": round(p, 4)}
                               for s, p in pred["top_scores"][:5]],
                "grid": grid,
                "p_actual_score": round(p_actual, 4),
                "market": lk.get("market") if lk else None,
                "elo_home_before": round(home_before, 1),
                "elo_away_before": round(away_before, 1),
                "outcome_hit": outcome_hit,
                "score_hit": score_hit,
            }
            new_played_preds[match_id] = stored
            pred_record = stored

        records.append({
            "match": m["match"], "stage": m["stage"], "date_utc": m["date_utc"],
            "home": m["home"], "away": m["away"], "score": m["score"],
            "winner": m["winner"],
            **{k: v for k, v in pred_record.items()},
            "outcome_hit": outcome_hit,
            "score_hit": score_hit,
        })

        # 即使使用存档预测，Elo 更新和开放度调整仍对所有场生效
        home["elo"], away["elo"] = update_elo(
            home["elo"], away["elo"], tuple(m["score"]),
            home.get("host", False), away.get("host", False))

        # 开放度随实际总进球微调（场面比预期开放 → 双方 open 上浮）
        # 注意：这里需要重新计算 lambdas，即使预测来自存档
        lam_h, lam_a_ = expected_goals(win_expectancy(home["elo"], away["elo"]))
        lam_h = max(lam_h, 0.4)
        lam_a_ = max(lam_a_, 0.4)
        lam_h = lam_h * style_scale(home, away)
        lam_a_ = lam_a_ * style_scale(home, away)
        ratio = (sum(m["score"]) + 0.5) / (lam_h + lam_a_ + 0.5)
        for t in (home, away):
            t["open"] = min(max(t.get("open", 1.0) * ratio ** OPEN_UPDATE_K,
                                OPEN_MIN), OPEN_MAX)

    # 保存本轮新增的已赛预测（只添加新记录，绝不覆盖已有记录）
    if new_played_preds:
        # 双重校验：确保 new_played_preds 中没有已存在的记录
        existing_keys = set(played_preds.keys())
        new_keys = set(new_played_preds.keys())
        overlap = existing_keys & new_keys
        if overlap:
            print(f"  [state] 警告：检测到 {len(overlap)} 场已有比赛试图被覆盖，已跳过：{sorted(overlap)}")
            # 只保留真正新增的记录
            new_played_preds = {k: v for k, v in new_played_preds.items() if k not in existing_keys}
        
        if new_played_preds:
            all_played_preds = {**played_preds, **new_played_preds}
            _save_played_preds(all_played_preds)
            print(f"  [state] 已将 {len(new_played_preds)} 场新已赛预测存入 played_preds.json")
        else:
            print(f"  [state] 没有新的已赛预测需要保存")

    # ---- 市场赔率融合：为未赛对阵生成/刷新锁定预测 ----
    from datetime import datetime, timezone
    now_utc = datetime.now(timezone.utc)
    odds_cache = odds.load() or {}
    h2h = odds_cache.get("h2h", {})
    we_overrides = {}
    locked_dirty = False
    for m in matches:
        if not (m["home"] and m["away"]) or m["score"]:
            continue  # 对阵未定或已赛（已赛的锁档不再改动）
        kickoff = datetime.fromisoformat(
            m["date_utc"].replace(" ", "T")).astimezone(timezone.utc)
        if kickoff <= now_utc:
            # 已开球但比分未入库：滚球/赛后盘口严禁覆盖赛前锁档
            lk = locked.get(str(m["match"]))
            if lk:
                we_overrides[(m["home"], m["away"])] = lk["we"]
            continue
        mkt = h2h.get(f"{m['home']}|{m['away']}")
        if mkt:
            home, away = by_code[m["home"]], by_code[m["away"]]
            we_model = win_expectancy(effective_elo(home, away), effective_elo(away, home))
            we_mkt = mkt["p_home"] + 0.5 * mkt["p_draw"]
            we_blend = round(MODEL_WEIGHT * we_model
                             + (1 - MODEL_WEIGHT) * we_mkt, 4)
            locked[str(m["match"])] = {
                "we": we_blend, "market": mkt,
                "ts": time.strftime("%Y-%m-%d %H:%M"),
            }
            locked_dirty = True
        lk = locked.get(str(m["match"]))
        if lk:
            we_overrides[(m["home"], m["away"])] = lk["we"]
    if locked_dirty:
        LOCKED_PATH.write_text(json.dumps(locked, ensure_ascii=False, indent=1),
                               encoding="utf-8")

    # ---- 条件模拟所需的固定结果 ----
    group_results = {(m["home"], m["away"]): tuple(m["score"])
                     for m in played if m["stage"] == "group"}
    ko_teams = {m["match"]: (m["home"], m["away"])
                for m in matches
                if m["stage"] != "group" and m["home"] and m["away"]}
    ko_winners = {}
    for m in played:
        if m["stage"] == "group":
            continue
        gh, ga = m["score"]
        winner = (m["home"] if gh > ga else m["away"] if ga > gh
                  else m["winner"])  # 平局须由 winner 字段给出点球胜者
        if winner:
            ko_winners[m["match"]] = winner

    # ---- 小组实时积分表 ----
    live_tables = {g: {} for g in GROUPS}
    for code, t in by_code.items():
        live_tables[t["group"]][code] = {"pts": 0, "gf": 0, "ga": 0, "played": 0}
    for m in played:
        if m["stage"] != "group":
            continue
        gh, ga = m["score"]
        th = live_tables[by_code[m["home"]]["group"]][m["home"]]
        ta = live_tables[by_code[m["away"]]["group"]][m["away"]]
        th["gf"] += gh; th["ga"] += ga; th["played"] += 1
        ta["gf"] += ga; ta["ga"] += gh; ta["played"] += 1
        if gh > ga:
            th["pts"] += 3
        elif ga > gh:
            ta["pts"] += 3
        else:
            th["pts"] += 1; ta["pts"] += 1

    n = len(records)
    return {
        "by_code": by_code,
        "groups": {g: [t for t in by_code.values() if t["group"] == g]
                   for g in GROUPS},
        "matches": matches,
        "fixed": {"group_results": group_results,
                  "ko_teams": ko_teams,
                  "ko_winners": ko_winners,
                  "we_overrides": we_overrides},
        "locked": locked,
        "market_winner": odds_cache.get("winner", {}),
        "market_live": bool(we_overrides),
        "live_tables": live_tables,
        "records": records,
        "record_stats": {
            "n": n,
            "outcome_acc": round(n_outcome_hit / n, 4) if n else None,
            "score_acc": round(n_score_hit / n, 4) if n else None,
            "brier": round(brier_sum / n, 4) if n else None,
        },
    }





