"""导出前端预测所需数据为 JSON。

运行后会生成：
- web/teams.json     球队基础数据 + 知识库修正因子
- web/calibration.json 全局盘口校准值
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.knowledge_loader import get_loader


def main():
    loader = get_loader()

    # 1. 导出球队数据
    teams_path = ROOT / "data" / "teams.json"
    teams_data = json.loads(teams_path.read_text(encoding="utf-8"))

    out_teams = []
    for t in teams_data.get("teams", []):
        code = t.get("code", "")
        boost = loader.get_prediction_boost(code)
        entry = {
            "code": code,
            "name_en": t.get("name_en", ""),
            "name_zh": t.get("name_zh", ""),
            "elo": t.get("elo", 1500),
            "host": t.get("host", False),
            "open": t.get("open", 1.0),
            "group": t.get("group", ""),
        }
        if boost:
            entry["boost"] = boost
        out_teams.append(entry)

    # 2. 导出校准数据
    cal = loader.get_calibration()

    teams_payload = {"teams": out_teams}
    (ROOT / "web" / "teams.json").write_text(
        json.dumps(teams_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (ROOT / "web" / "calibration.json").write_text(
        json.dumps(cal, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    # 额外生成 predictor-data.js：把数据直接内联到 JS，避免 file:// 或移动端 fetch 失败
    (ROOT / "web" / "predictor-data.js").write_text(
        "window.WC_TEAMS = " + json.dumps(teams_payload, ensure_ascii=False, indent=2) + ";\n"
        "window.WC_CALIBRATION = " + json.dumps(cal, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )

    print(f"[OK] web/teams.json: {len(out_teams)} teams")
    print(f"[OK] web/calibration.json: {cal}")
    print(f"[OK] web/predictor-data.js generated")


if __name__ == "__main__":
    main()
