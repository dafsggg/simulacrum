"""手动录入比分（数据源不可用或滞后时的兜底）。

用法：
    python3 -m src.record 1 2-1              # 第 1 场，主队 2:1 获胜
    python3 -m src.record 89 1-1 --winner FRA  # 点球大战需指明晋级方
    python3 -m src.record --list              # 查看最近已录入

录入写到 data/manual_results.json，优先级高于自动抓取的数据；
录入后跑 `python3 -m src.update --no-fetch` 即可刷新预测。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ._paths import ROOT
MANUAL = ROOT / "data" / "manual_results.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="手动录入世界杯比分")
    parser.add_argument("match", nargs="?", type=int, help="场次编号 1~104")
    parser.add_argument("score", nargs="?", help="比分，如 2-1（含加时）")
    parser.add_argument("--winner", help="点球胜者三字码（平局时必填）")
    parser.add_argument("--list", action="store_true", help="查看已录入")
    args = parser.parse_args()

    data = json.loads(MANUAL.read_text(encoding="utf-8")) if MANUAL.exists() else {}

    if args.list or args.match is None:
        if not data:
            print("  尚无手动录入。")
        for k, v in sorted(data.items(), key=lambda x: int(x[0])):
            print(f"  第{k}场: {v['score'][0]}-{v['score'][1]}"
                  + (f"  点球胜者 {v['winner']}" if v.get("winner") else ""))
        return

    if not (1 <= args.match <= 104):
        sys.exit("场次编号需在 1~104")
    try:
        gh, ga = (int(x) for x in args.score.replace(":", "-").split("-"))
    except (AttributeError, ValueError):
        sys.exit("比分格式: 主队得分-客队得分，如 2-1")
    if gh == ga and args.match > 72 and not args.winner:
        sys.exit("淘汰赛平局需用 --winner 指明点球胜者（三字码）")

    data[str(args.match)] = {"score": [gh, ga]}
    if args.winner:
        data[str(args.match)]["winner"] = args.winner.upper()
    MANUAL.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                      encoding="utf-8")
    print(f"  已录入第 {args.match} 场 {gh}-{ga}"
          + (f"（点球胜者 {args.winner.upper()}）" if args.winner else ""))
    print("  运行 python3 -m src.update --no-fetch 刷新预测")


if __name__ == "__main__":
    main()
