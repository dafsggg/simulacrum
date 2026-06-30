"""每日更新管线：同步比分 → 回放更新 Elo → 条件蒙特卡洛 → 生成网站数据。

用法（项目根目录）：
    python3 -m src.update                        # 完整更新（默认 100 万次模拟）
    python3 -m src.update --sims 100000000       # 一亿次（多进程，约 20~30 分钟）
    python3 -m src.update --no-fetch             # 跳过联网，只用本地数据重算

每次运行会：
1. 同步 104 场赛程与最新比分（失败自动降级为本地数据）；
2. 按时间回放已赛比赛：先记录事前预测（来自 played_preds.json 固定存档），
   再按 eloratings 公式更新 Elo；
3. 以"已赛结果固定、未赛掷骰子"的方式做全程蒙特卡洛（自动多进程并行）；
4. 只对最近 5 场未赛重新生成预测，其余未赛预测保持不变；
5. 写 web/data.js、out/results.json，并在 data/history.json 追加当日夺冠概率快照。
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import random
import time
from collections import Counter
from pathlib import Path

from . import fetch, odds, report, bookmaker
from .model import match_probabilities, score_grid
from .state import build_state
from .tournament import GROUPS, simulate_tournament

from ._paths import ROOT
STAGES = ["r32", "r16", "qf", "sf", "final", "champion"]
STAGE_ZH = {"r32": "晋级32强", "r16": "进16强", "qf": "进8强",
            "sf": "进4强", "final": "进决赛", "champion": "夺冠"}


# ----------------------------------------------------------------- simulate --

def _run_chunk(state: dict, sims: int, seed: int) -> dict:
    """跑一段模拟，返回可合并的计数器（供单进程或子进程使用）。"""
    by_code, groups, fixed = state["by_code"], state["groups"], state["fixed"]
    rng = random.Random(seed)
    counts = {code: Counter() for code in by_code}
    group_pts = {code: 0.0 for code in by_code}
    group_rank = {code: Counter() for code in by_code}
    final_pairs: Counter = Counter()
    title_match: Counter = Counter()

    for _ in range(sims):
        result = simulate_tournament(groups, rng, fixed)
        for g in GROUPS:
            for rank, row in enumerate(result["standings"][g], start=1):
                code = row["team"]["code"]
                group_pts[code] += row["pts"]
                group_rank[code][rank] += 1
        for stage_key, codes in (("r32", result["r32"]), ("r16", result["r16"]),
                                 ("qf", result["qf"]), ("sf", result["sf"]),
                                 ("final", result["finalists"])):
            for code in codes:
                counts[code][stage_key] += 1
        counts[result["champion"]]["champion"] += 1
        final_pairs[tuple(sorted(result["finalists"]))] += 1
        title_match[(result["champion"], result["runner_up"])] += 1

    return {"counts": counts, "group_pts": group_pts,
            "group_rank": group_rank, "final_pairs": final_pairs,
            "title_match": title_match}


def _chunk_worker(args: tuple[int, int]) -> dict:
    """子进程入口：自行重建状态（由数据文件确定性推导）。"""
    sims, seed = args
    return _run_chunk(build_state(), sims, seed)


def _merge(parts: list[dict], by_code: dict) -> dict:
    merged = {"counts": {c: Counter() for c in by_code},
              "group_pts": {c: 0.0 for c in by_code},
              "group_rank": {c: Counter() for c in by_code},
              "final_pairs": Counter(), "title_match": Counter()}
    for p in parts:
        for c in by_code:
            merged["counts"][c].update(p["counts"][c])
            merged["group_pts"][c] += p["group_pts"][c]
            merged["group_rank"][c].update(p["group_rank"][c])
        merged["final_pairs"].update(p["final_pairs"])
        merged["title_match"].update(p["title_match"])
    return merged


def run_simulations(state: dict, sims: int, seed: int, workers: int) -> dict:
    by_code = state["by_code"]
    t0 = time.time()

    if workers <= 1 or sims < 50_000:
        agg = _run_chunk(state, sims, seed)
    else:
        n_chunks = workers * 8
        per = sims // n_chunks
        chunk_sims = [per] * n_chunks
        chunk_sims[-1] += sims - per * n_chunks
        tasks = [(n, seed * 1_000_003 + i) for i, n in enumerate(chunk_sims)]
        parts, done = [], 0
        ctx = mp.get_context("spawn")
        with ctx.Pool(workers) as pool:
            for part in pool.imap_unordered(_chunk_worker, tasks):
                parts.append(part)
                done += 1
                pct = done / n_chunks * 100
                eta = (time.time() - t0) / done * (n_chunks - done)
                print(f"\r  并行模拟 {workers} 进程: {pct:5.1f}%  "
                      f"剩余约 {eta / 60:.1f} 分钟 ...", end="", flush=True)
        agg = _merge(parts, by_code)
    print(f"\r  完成 {sims:,} 次条件模拟，耗时 {(time.time() - t0) / 60:.1f} 分钟"
          + " " * 24)

    market_winner = state.get("market_winner", {})
    teams_out = []
    for code, team in by_code.items():
        live = state["live_tables"][team["group"]][code]
        entry = {
            "p_champion_market": market_winner.get(code),
            "code": code, "name_zh": team["name_zh"], "name_en": team["name_en"],
            "group": team["group"], "host": team["host"],
            "elo_base": round(team["elo_base"], 1),
            "elo": round(team["elo"], 1),
            "exp_group_pts": round(agg["group_pts"][code] / sims, 2),
            "p_group_win": round(agg["group_rank"][code][1] / sims, 6),
            "live": live,
        }
        for stage in STAGES:
            entry["p_" + stage] = round(agg["counts"][code][stage] / sims, 6)
        teams_out.append(entry)
    teams_out.sort(key=lambda t: (-t["p_champion"], -t["p_final"], -t["elo"]))

    return {
        "teams": teams_out,
        "top_finals": [{"pair": list(p), "p": round(c / sims, 6)}
                       for p, c in agg["final_pairs"].most_common(10)],
        "top_title_matches": [
            {"champion": ch, "runner_up": ru, "p": round(c / sims, 6)}
            for (ch, ru), c in agg["title_match"].most_common(10)],
    }


# ----------------------------------------------------------------- schedule --

def build_schedule(state: dict, existing_schedule: list | None = None,
                   refresh_all: bool = False) -> list[dict]:
    """全部 104 场：已赛附事前预测（来自固定存档），未赛默认更新最近 10 场。

    参数:
        refresh_all: True 时强制重新计算所有未赛场，忽略 existing_schedule
    """
    by_code = state["by_code"]
    rec_by_match = {r["match"]: r for r in state["records"]}
    existing_by_match: dict[int, dict] = {}
    if existing_schedule and not refresh_all:
        for row in existing_schedule:
            if row.get("pred") and not row.get("score"):
                existing_by_match[row["match"]] = row["pred"]

    # 大小球盘口：bookmaker 对每场的评分分布偏差
    insights = bookmaker.compute_bookmaker_insights(state)

    # 找出最近 10 场未赛（按开球时间）
    from datetime import datetime, timezone
    now_utc = datetime.now(timezone.utc)
    unplayed_sorted = []
    for m in state["matches"]:
        if m["score"] or not m["home"] or not m["away"]:
            continue
        dt = datetime.fromisoformat(m["date_utc"].replace(" ", "T")).astimezone(timezone.utc)
        if dt > now_utc:
            unplayed_sorted.append((dt, m["match"]))
    unplayed_sorted.sort(key=lambda x: x[0])
    # refresh_all 时更新所有未赛，否则只更新最近 10 场
    if refresh_all:
        update_matches = {m_id for _, m_id in unplayed_sorted}
    else:
        update_matches = {m_id for _, m_id in unplayed_sorted[:10]}

    out = []
    for m in state["matches"]:
        row = {k: m[k] for k in ("match", "round", "stage", "group", "date_utc",
                                 "venue", "home", "away", "slot_home",
                                 "slot_away", "score", "winner")}
        rec = rec_by_match.get(m["match"])
        if rec:  # 已赛：用赛前预测（来自固定 played_preds 存档）
            row["pred"] = {"p_home": rec["p_home"], "p_draw": rec["p_draw"],
                           "p_away": rec["p_away"],
                           "pick": rec["pick"],
                           "pred_score": rec["pred_score"],
                           "top_scores": rec["top_scores"],
                           "grid": rec["grid"],
                           "p_actual_score": rec["p_actual_score"],
                           "market": rec["market"]}
            row["outcome_hit"] = rec["outcome_hit"]
            row["score_hit"] = rec["score_hit"]
        elif m["home"] and m["away"] and not m["score"]:  # 未赛但对阵已知
            if m["match"] in update_matches:
                ko = m["stage"] != "group"
                home, away = by_code[m["home"]], by_code[m["away"]]
                lk = state["locked"].get(str(m["match"]))
                we_o = lk["we"] if lk else None

                # 获取 bookmaker 大小球盘口偏差
                shift = None
                insp = insights.get((m["home"], m["away"]))
                if insp and isinstance(insp, dict):
                    shift = insp.get("score_shift")

                pred = match_probabilities(home, away, knockout=ko,
                                            we_override=we_o, score_shift=shift)
                row["pred"] = {
                    "p_home": round(pred["p_win"], 4),
                    "p_draw": round(pred["p_draw"], 4),
                    "p_away": round(pred["p_loss"], 4),
                    "pick": pred["outcome_pick"],
                    "pred_score": list(pred["outcome_score"][0]),
                    "top_scores": [{"score": list(s), "p": round(p, 4)}
                                   for s, p in pred["top_scores"][:5]],
                    "grid": score_grid(home, away, we_override=we_o, score_shift=shift),
                    "market": lk["market"] if lk else None,
                }
                if ko:
                    row["pred"]["p_adv_home"] = round(pred["p_advance_a"], 4)
                    row["pred"]["p_adv_away"] = round(pred["p_advance_b"], 4)
            else:
                # 保持 existing_schedule 中的预测（非 refresh_all 模式）
                existing = existing_by_match.get(m["match"])
                if existing:
                    row["pred"] = existing
                else:
                    # fallback：没有历史数据，正常生成
                    ko = m["stage"] != "group"
                    home, away = by_code[m["home"]], by_code[m["away"]]
                    lk = state["locked"].get(str(m["match"]))
                    we_o = lk["we"] if lk else None
                    pred = match_probabilities(home, away, knockout=ko, we_override=we_o)
                    row["pred"] = {
                        "p_home": round(pred["p_win"], 4),
                        "p_draw": round(pred["p_draw"], 4),
                        "p_away": round(pred["p_loss"], 4),
                        "pick": pred["outcome_pick"],
                        "pred_score": list(pred["outcome_score"][0]),
                        "top_scores": [{"score": list(s), "p": round(p, 4)}
                                       for s, p in pred["top_scores"][:5]],
                        "grid": score_grid(home, away, we_override=we_o),
                        "market": lk["market"] if lk else None,
                    }
        out.append(row)
    return out


# ------------------------------------------------------------------ history --

def update_history(sim_out: dict, played: int, sims: int) -> list[dict]:
    path = ROOT / "data" / "history.json"
    history = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    today = time.strftime("%Y-%m-%d")
    snapshot = {
        "date": today,
        "played": played,
        "sims": sims,
        "champion": {t["code"]: t["p_champion"] for t in sim_out["teams"][:12]},
    }
    history = [h for h in history if h["date"] != today] + [snapshot]
    history.sort(key=lambda h: h["date"])
    path.write_text(json.dumps(history, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    return history


# ------------------------------------------------------------------ outputs --

def write_outputs(payload: dict) -> None:
    out_dir = ROOT / "out"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "results.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    (ROOT / "web" / "data.js").write_text(
        "window.WC_DATA = " + json.dumps(payload, ensure_ascii=False) + ";\n",
        encoding="utf-8")
    # Also generate predictor-data.js for frontend compatibility
    (ROOT / "web" / "predictor-data.js").write_text(
        "window.WC_DATA = " + json.dumps(payload, ensure_ascii=False) + ";\n",
        encoding="utf-8")


def print_report(payload: dict) -> None:
    teams = payload["teams"]
    name = {t["code"]: t["name_zh"] for t in teams}
    stats = payload["record"]["stats"]

    print()
    print("=" * 78)
    print(f"  2026 世界杯 AI 预测  ·  已赛 {payload['meta']['played']}/104 场"
          f"  ·  更新于 {payload['meta']['updated_at']}")
    print("=" * 78)
    if stats["n"]:
        print(f"  预测战绩: 胜平负命中 {stats['outcome_acc'] * 100:.0f}%"
              f" | 精确比分命中 {stats['score_acc'] * 100:.0f}%"
              f" | Brier {stats['brier']:.3f}  (共 {stats['n']} 场)")
        print("-" * 78)
    print(f"  {'球队':　<8}{'组':>2}  {'Elo':>6}" + "".join(
        f"{STAGE_ZH[s]:>10}" for s in STAGES))
    print("-" * 78)
    for t in teams[:12]:
        row = f"  {t['name_zh']:　<8}{t['group']:>2}  {t['elo']:>6.0f}"
        for s in STAGES:
            row += f"{t['p_' + s] * 100:>9.2f}%"
        print(row)
    movers = sorted(teams, key=lambda t: abs(t["elo"] - t["elo_base"]),
                    reverse=True)[:5]
    if any(abs(t["elo"] - t["elo_base"]) > 0.5 for t in movers):
        print()
        print("  Elo 变化最大:")
        for t in movers:
            d = t["elo"] - t["elo_base"]
            if abs(d) > 0.5:
                print(f"    {t['name_zh']:　<8} {t['elo_base']:.0f} → "
                      f"{t['elo']:.0f}  ({d:+.0f})")
    print()
    print("  最可能的决赛对阵:")
    for fm in payload["top_finals"][:5]:
        a, b = fm["pair"]
        print(f"    {name[a]} vs {name[b]:　<8}  {fm['p'] * 100:5.2f}%")
    print()
    print("  数据已写入 web/data.js（网站）与 out/results.json")


# --------------------------------------------------------------------- main --

def run(sims: int, seed: int | None, do_fetch: bool,
        workers: int | None = None, refresh_all: bool = False) -> dict:
    import time
    log_file = ROOT / "update.log"
    
    def log_step(msg):
        try:
            safe = "".join(c if ord(c) < 128 else "?" for c in msg)
            ts = time.strftime("[%Y-%m-%d %H:%M:%S] ")
            line = ts + safe + "\n"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(line)
            print("[update] " + safe, flush=True)
        except Exception:
            pass
    
    log_step("run() 开始")
    if do_fetch:
        log_step("fetch.sync() 开始")
        fetch.sync()
        log_step("fetch.sync() 完成")
        log_step("odds.sync() 开始")
        odds.sync()
        log_step("odds.sync() 完成")
    log_step("build_state() 开始")
    state = build_state()
    log_step("build_state() 完成, teams=%d matches=%d" % (len(state["by_code"]), len(state["matches"])))
    played = len(state["records"])
    if seed is None:
        seed = int(time.strftime("%Y%m%d"))  # 每日不同但可复现
    if workers is None:
        workers = os.cpu_count() or 1

    # 加载现有 data.js（refresh_all 时跳过，强制重新计算所有预测）
    existing_payload = None
    if not refresh_all:
        data_js = ROOT / "web" / "data.js"
        if data_js.exists() and data_js.stat().st_size > 100:
            try:
                text = data_js.read_text(encoding="utf-8")
                if text.startswith("window.WC_DATA = "):
                    json_str = text[len("window.WC_DATA = "):].rstrip(";\n ")
                else:
                    json_str = text
                existing_payload = json.loads(json_str)
            except Exception:
                pass

    sim_out = run_simulations(state, sims, seed, workers)
    history = update_history(sim_out, played, sims)

    existing_schedule = existing_payload.get("schedule") if existing_payload else None

    payload = {
        "meta": {
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "sims": sims, "seed": seed,
            "played": played, "total": 104,
            "market": state.get("market_live", False),
            "refreshed": refresh_all,
        },
        "teams": sim_out["teams"],
        "schedule": build_schedule(state, existing_schedule=existing_schedule,
                                    refresh_all=refresh_all),
        "record": {"stats": state["record_stats"],
                   "list": list(reversed(state["records"]))},
        "top_finals": sim_out["top_finals"],
        "top_title_matches": sim_out["top_title_matches"],
        "history": history,
    }
    write_outputs(payload)
    report.update_all(payload)
    print_report(payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="AI 世界杯 2026 每日更新")
    parser.add_argument("--sims", type=int, default=1_000_000)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--no-fetch", action="store_true", help="跳过联网同步")
    parser.add_argument("--refresh-all", action="store_true",
                        help="强制重新计算所有未赛场预测（忽略缓存）")
    args = parser.parse_args()
    run(args.sims, args.seed, not args.no_fetch, args.workers, args.refresh_all)


if __name__ == "__main__":
    main()
