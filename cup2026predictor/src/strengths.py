"""攻防系数：用历史国际 A 级赛果拟合每队的进攻/防守强度。

数据：data/intl_results.csv（martj42/international_results，1872 年至今，
按需重新下载），取近 8 年、按时间衰减加权（半衰期约 2 年），友谊赛降权。

模型（乘法泊松，迭代比例拟合 IPF）：
    λ_主 = μ · att_主 · def_客 · home_adv（中立场地无主场项）
    λ_客 = μ · att_客 · def_主
att 越大进攻越强；def 越大防守越差（被进球乘数）。均值归一为 1。

用途：att·def 的乘积是球队"开放度"（强攻+漏防 → 比赛大开大合；
铁桶阵 → 低比分）。预测时只用开放度调节总进球，胜负仍由 Elo 决定，
避免与 Elo 重复计算实力。

用法：
    python3 -m src.strengths fit            # 重新拟合并写 data/strengths.json
    python3 -m src.strengths fit --refresh  # 先重新下载数据集
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import urllib.request
from datetime import date
from pathlib import Path

from ._paths import ROOT
CSV_PATH = ROOT / "data" / "intl_results.csv"
OUT_PATH = ROOT / "data" / "strengths.json"
DATA_URL = ("https://raw.githubusercontent.com/martj42/"
            "international_results/master/results.csv")

SINCE = "2018-01-01"
HALF_LIFE_DAYS = 730        # 时间衰减半衰期
FRIENDLY_WEIGHT = 0.5       # 友谊赛降权
MIN_EFF_MATCHES = 8.0       # 有效样本不足的队伍回退为 1.0
ITERATIONS = 60

# 数据集队名 → 我们的 name_en（仅差异项）
DATASET_ALIASES = {"Czech Republic": "Czechia", "Turkey": "Türkiye"}


def download() -> None:
    req = urllib.request.Request(DATA_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        CSV_PATH.write_bytes(resp.read())
    print(f"  已下载数据集 → {CSV_PATH.name}")


def load_matches() -> list[dict]:
    today = date.today()
    out = []
    with open(CSV_PATH, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["date"] < SINCE or row["date"] > today.isoformat():
                continue
            if not row["home_score"].isdigit():
                continue  # 未赛(NA)或异常行
            d = date.fromisoformat(row["date"])
            age = (today - d).days
            w = 0.5 ** (age / HALF_LIFE_DAYS)
            if row["tournament"] == "Friendly":
                w *= FRIENDLY_WEIGHT
            out.append({
                "home": DATASET_ALIASES.get(row["home_team"], row["home_team"]),
                "away": DATASET_ALIASES.get(row["away_team"], row["away_team"]),
                "gh": int(row["home_score"]),
                "ga": int(row["away_score"]),
                "neutral": row["neutral"] == "TRUE",
                "w": w,
            })
    return out


def fit(matches: list[dict]) -> tuple[dict, float, float]:
    teams = {m[k] for m in matches for k in ("home", "away")}
    att = {t: 1.0 for t in teams}
    deff = {t: 1.0 for t in teams}
    eff = {t: 0.0 for t in teams}
    for m in matches:
        eff[m["home"]] += m["w"]
        eff[m["away"]] += m["w"]

    total_w = sum(m["w"] for m in matches)
    mu = sum(m["w"] * (m["gh"] + m["ga"]) for m in matches) / (2 * total_w)
    home_adv = 1.25

    for _ in range(ITERATIONS):
        # 主场优势（仅非中立场）
        num = den = 0.0
        for m in matches:
            if not m["neutral"]:
                num += m["w"] * m["gh"]
                den += m["w"] * mu * att[m["home"]] * deff[m["away"]]
        home_adv = num / den if den else 1.25

        sg = {t: 0.0 for t in teams}   # 进球加权和 / 期望
        eg = {t: 1e-9 for t in teams}
        sc = {t: 0.0 for t in teams}   # 失球
        ec = {t: 1e-9 for t in teams}
        for m in matches:
            h, a, w = m["home"], m["away"], m["w"]
            hf = 1.0 if m["neutral"] else home_adv
            lam_h = mu * att[h] * deff[a] * hf
            lam_a = mu * att[a] * deff[h]
            sg[h] += w * m["gh"]; eg[h] += w * lam_h
            sg[a] += w * m["ga"]; eg[a] += w * lam_a
            sc[h] += w * m["ga"]; ec[h] += w * lam_a
            sc[a] += w * m["gh"]; ec[a] += w * lam_h
        for t in teams:
            att[t] *= (sg[t] / eg[t]) ** 0.5  # 半步更新，稳定收敛
            deff[t] *= (sc[t] / ec[t]) ** 0.5
        # 归一化
        ma = sum(att.values()) / len(teams)
        md = sum(deff.values()) / len(teams)
        for t in teams:
            att[t] /= ma
            deff[t] /= md

    strengths = {t: {"att": round(att[t], 3), "def": round(deff[t], 3),
                     "eff": round(eff[t], 1)} for t in teams}
    return strengths, mu, home_adv


def run_fit(refresh: bool = False) -> None:
    if refresh or not CSV_PATH.exists():
        download()
    matches = load_matches()
    print(f"  样本: {len(matches)} 场（{SINCE} 起，时间衰减半衰期 {HALF_LIFE_DAYS} 天）")
    strengths, mu, home_adv = fit(matches)
    print(f"  全局均值 μ={mu:.3f} 球/队/场，主场优势 ×{home_adv:.3f}")

    teams_db = json.load(open(ROOT / "data" / "teams.json", encoding="utf-8"))["teams"]
    out, missing = {}, []
    for t in teams_db:
        s = strengths.get(t["name_en"])
        if s and s["eff"] >= MIN_EFF_MATCHES:
            out[t["code"]] = s
        else:
            out[t["code"]] = {"att": 1.0, "def": 1.0, "eff": s["eff"] if s else 0}
            missing.append(t["name_en"])
    if missing:
        print(f"  样本不足回退为中性: {missing}")

    # 开放度 = att×def，相对 48 强几何均值归一（绝对尺度受全球弱队影响，
    # 只有相对值有意义），再按有效样本量向 1 收缩，避免小样本极端值。
    products = [s["att"] * s["def"] for s in out.values()]
    geo_mean = math.exp(sum(math.log(p) for p in products) / len(products))
    for code, s in out.items():
        rel = (s["att"] * s["def"]) / geo_mean
        shrink = s["eff"] / (s["eff"] + 15.0)
        s["open"] = round(min(max(rel ** shrink, 0.65), 1.5), 3)

    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    print(f"  已写入 {OUT_PATH.name}")

    name_zh = {t["code"]: t["name_zh"] for t in teams_db}
    rows = sorted(out.items(), key=lambda x: -x[1]["att"])
    print("\n  进攻最强:  " + "  ".join(
        f"{name_zh[c]}{s['att']:.2f}" for c, s in rows[:5]))
    print("  防守最稳:  " + "  ".join(
        f"{name_zh[c]}{s['def']:.2f}" for c, s in
        sorted(out.items(), key=lambda x: x[1]["def"])[:5]))
    print("  最开放(open):  " + "  ".join(
        f"{name_zh[c]}{s['open']:.2f}" for c, s in
        sorted(out.items(), key=lambda x: -x[1]["open"])[:5]))
    print("  最保守(open):  " + "  ".join(
        f"{name_zh[c]}{s['open']:.2f}" for c, s in
        sorted(out.items(), key=lambda x: x[1]["open"])[:5]))


def main() -> None:
    parser = argparse.ArgumentParser(description="拟合攻防系数")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("fit")
    p.add_argument("--refresh", action="store_true", help="重新下载数据集")
    args = parser.parse_args()
    run_fit(args.refresh)


if __name__ == "__main__":
    main()
