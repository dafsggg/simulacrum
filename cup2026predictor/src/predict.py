"""AI 世界杯预测 CLI（单场预测 + 全程模拟入口）。

用法（在项目根目录运行）：
    python3 -m src.predict match ESP ARG --knockout   # 单场预测（用当前动态 Elo）
    python3 -m src.predict match 西班牙 阿根廷
    python3 -m src.predict simulate --sims 20000      # 等价于 update --no-fetch

完整的每日更新（联网同步比分）请用 python3 -m src.update。
"""

from __future__ import annotations

import argparse
import sys

from .model import match_probabilities
from .state import build_state


def find_team(by_code: dict, query: str) -> dict:
    q = query.strip()
    for t in by_code.values():
        if q.upper() == t["code"] or q == t["name_zh"] \
                or q.lower() == t["name_en"].lower():
            return t
    sys.exit(f"找不到球队: {query}（可用三字码/中文名/英文名，如 ESP / 西班牙 / Spain）")


def predict_match(query_a: str, query_b: str, knockout: bool) -> None:
    state = build_state()
    by_code = state["by_code"]
    a, b = find_team(by_code, query_a), find_team(by_code, query_b)
    res = match_probabilities(a, b, knockout=knockout)

    def elo_label(t: dict) -> str:
        delta = t["elo"] - t["elo_base"]
        return (f"Elo {t['elo']:.0f}" +
                (f" ({delta:+.0f})" if abs(delta) > 0.5 else ""))

    print()
    print(f"  {a['name_zh']} ({elo_label(a)})  vs  {b['name_zh']} ({elo_label(b)})")
    if a["host"] or b["host"]:
        print("  * 东道主含 +60 Elo 主场加成")
    print("-" * 46)
    print(f"  {a['name_zh']}胜 {res['p_win'] * 100:5.1f}%   "
          f"平局 {res['p_draw'] * 100:5.1f}%   "
          f"{b['name_zh']}胜 {res['p_loss'] * 100:5.1f}%")
    la, lb = res["lambdas"]
    print(f"  期望进球: {la:.2f} - {lb:.2f}")
    if knockout:
        print(f"  晋级概率(含加时/点球): {a['name_zh']} {res['p_advance_a'] * 100:.1f}%"
              f" / {b['name_zh']} {res['p_advance_b'] * 100:.1f}%")
    print("  最可能比分:")
    for (ga, gb), p in res["top_scores"]:
        print(f"    {ga}-{gb}   {p * 100:4.1f}%")


def main() -> None:
    parser = argparse.ArgumentParser(description="AI 世界杯 2026 预测器")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sim = sub.add_parser("simulate", help="蒙特卡洛模拟（不联网，本地数据）")
    p_sim.add_argument("--sims", type=int, default=20000)
    p_sim.add_argument("--seed", type=int, default=None)

    p_match = sub.add_parser("match", help="预测单场比赛")
    p_match.add_argument("team_a")
    p_match.add_argument("team_b")
    p_match.add_argument("--knockout", action="store_true", help="淘汰赛模式(必分胜负)")

    args = parser.parse_args()
    if args.cmd == "simulate":
        from .update import run
        run(args.sims, args.seed, do_fetch=False)
    else:
        predict_match(args.team_a, args.team_b, args.knockout)


if __name__ == "__main__":
    main()
