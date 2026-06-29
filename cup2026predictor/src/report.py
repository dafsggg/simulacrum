"""AI 复盘与单场看点：复盘已赛预测的胜败，前瞻接下来的比赛。

- 每期复盘 = 主笔正文（180~280 字复盘思路）+ Fable 跟评（40~90 字，冷静毒舌人设）。
  生成时机：当天首次更新，或自上期以来有新完赛。存档 data/reports.json，
  并写 web/reports.js（window.WC_REPORTS）供网站展示。
- 单场看点：开球前 36 小时内的比赛各生成一句"AI 怎么看"，按场次锁档
  data/blurbs.json → web/blurbs.js（window.WC_BLURBS）。

LLM 配置放 data/config.json（OpenAI 兼容接口）：
    "llm": {"base_url": "https://.../v1", "api_key": "...",
            "model": "...", "commenter_model": "..."(可选，默认同 model)}
没有配置或调用失败时静默跳过，已有存档照常发布到网站。
"""

from __future__ import annotations

import json
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ._paths import ROOT
REPORTS = ROOT / "data" / "reports.json"
BLURBS = ROOT / "data" / "blurbs.json"

WRITER_SYSTEM = (
    "你是世界杯预测网站的 AI 编辑。根据给定的数据摘要写一段 180~280 字的中文每日复盘。"
    "只使用摘要中的事实和数字，绝不编造；语气像懂球的老编辑，有梗但克制；"
    "重点放在复盘思路：先诚实分析预测翻的车（尤其是信心高却输的比赛），"
    "再客观评价命中的比赛，最后提未来 24 小时的比赛——所有分析都要回到数据证据。"
    "提到预测一律称'AI'，不要用'模型'这个词。"
    "直接输出正文纯文本，不要标题、不要列表。")
COMMENTER_SYSTEM = (
    "你是 Fable，一个冷静、略毒舌但友善的 AI，在复盘下面写一条 40~90 字的中文跟评。"
    "可以补充正文忽略的数据点、温和拆台、或提醒读者用概率思维看预测；"
    "别复述正文内容，不要客套，不要用'主笔''模型'这类词。直接输出跟评纯文本。")
BLURB_SYSTEM = (
    "你是世界杯预测网站的 AI 解说。为给定的每场比赛各写一句 40~70 字的中文'AI 怎么看'，"
    "依据各队 Elo、风格开放度、AI 与市场概率，说人话、有观点、不堆数字，"
    "提到预测一律称'AI'，不要用'模型'这个词。"
    "【重要规则】"
    "1. 绝对不能编造与'最可能比分'矛盾的说法——比如最可能比分是 2-1 就绝不能说'零封对手'，"
    "只有当最可能比分中客队为 0 球时才能提'零封'，主队为 0 球时才能提'被零封'。"
    "2. 所有判断必须基于提供的数据，不要自己脑补。"
    "3. 如果想提比分，只能用给出的最可能比分或前几名的比分，不要编其他比分。"
    '只输出 JSON 对象，键为场次编号字符串，值为该场的一句话，例如 {"5": "..."}')


# ------------------------------------------------------------------ LLM 调用 --

def _llm_config() -> dict | None:
    cfg_path = ROOT / "data" / "config.json"
    if not cfg_path.exists():
        return None
    cfg = json.loads(cfg_path.read_text(encoding="utf-8")).get("llm")
    if cfg and cfg.get("base_url") and cfg.get("api_key") and cfg.get("model"):
        return cfg
    return None


def _chat(cfg: dict, system: str, user: str, model: str | None = None) -> str:
    body = json.dumps({
        "model": model or cfg["model"],
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "temperature": 0.8,
        "max_tokens": 1000,
    }).encode("utf-8")
    req = urllib.request.Request(
        cfg["base_url"].rstrip("/") + "/chat/completions", data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {cfg['api_key']}"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        out = json.loads(resp.read().decode("utf-8"))
    return out["choices"][0]["message"]["content"].strip()


# ------------------------------------------------------------------ 数据摘要 --

def _build_digest(payload: dict) -> dict:
    name = {t["code"]: t["name_zh"] for t in payload["teams"]}
    now = datetime.now(timezone.utc)

    # ---- 已赛：区分命中/翻车，重点呈现翻车 ----
    recent_list = payload["record"]["list"][:10]  # 最近 10 场
    hits, misses = [], []
    for r in recent_list:
        home_name, away_name = name[r["home"]], name[r["away"]]
        actual_score = f"{r['score'][0]}-{r['score'][1]}"

        # 计算赛前预测
        ph, pd, pa = r["p_home"], r["p_draw"], r["p_away"]
        if ph >= max(pd, pa):
            predicted_winner = f"{home_name} 胜"
            confidence = f"{ph * 100:.0f}%"
        elif pa > ph:
            predicted_winner = f"{away_name} 胜"
            confidence = f"{pa * 100:.0f}%"
        else:
            predicted_winner = "平局"
            confidence = f"{pd * 100:.0f}%"

        pred_score = f"{r['pred_score'][0]}-{r['pred_score'][1]}"

        entry = {
            "对阵": f"{home_name} {actual_score} {away_name}",
            "赛前预测": f"{predicted_winner}（{confidence}）",
            "预测比分": pred_score,
            "实际结果": actual_score,
            "胜负命中": r["outcome_hit"],
            "比分命中": r["score_hit"],
            "实际比分的预测概率": f"{r.get('p_actual_score', 0) * 100:.1f}%" if r.get("p_actual_score") else "无",
        }
        if r["outcome_hit"] and r["score_hit"]:
            hits.append(entry)
        elif not r["outcome_hit"]:
            misses.append(entry)  # 胜负错了——核心翻车
        else:
            misses.append(entry)  # 胜负对但比分错——也算翻车（比分命中极严）

    # 找最大翻车（赛前信心最高却输了）
    biggest_miss = None
    if misses:
        def _conf(m):
            s = m["赛前预测"]
            # 从括号里提取百分比
            try:
                pct = int(s.rsplit("(", 1)[1].rstrip("%)"))
            except Exception:
                pct = 0
            return pct
        biggest_miss = max(misses, key=_conf)

    upcoming = []
    for m in payload["schedule"]:
        if m["score"] or not m.get("pred") or not (m["home"] and m["away"]):
            continue
        dt = datetime.fromisoformat(m["date_utc"].replace(" ", "T"))
        if timedelta(0) <= dt - now <= timedelta(hours=24):
            p = m["pred"]
            upcoming.append({
                "对阵": f"{name[m['home']]} vs {name[m['away']]}",
                "概率": f"主胜{p['p_home'] * 100:.0f}% 平{p['p_draw'] * 100:.0f}%"
                       f" 客胜{p['p_away'] * 100:.0f}%",
                "最可能比分": "-".join(map(str, p["pred_score"])),
            })

    history = payload.get("history", [])
    movers = []
    if len(history) >= 2:
        prev, cur = history[-2]["champion"], history[-1]["champion"]
        for code in cur:
            d = cur[code] - prev.get(code, 0)
            if abs(d) >= 0.005:
                movers.append(f"{name.get(code, code)} {d * 100:+.1f}pp")

    elo_moves = [f"{t['name_zh']} {t['elo'] - t['elo_base']:+.0f}"
                 for t in payload["teams"]
                 if abs(t["elo"] - t["elo_base"]) >= 3][:8]

    top5 = [{"队": t["name_zh"], "模型": f"{t['p_champion'] * 100:.1f}%",
             "市场": (f"{t['p_champion_market'] * 100:.1f}%"
                      if t.get("p_champion_market") else "无")}
            for t in payload["teams"][:5]]

    return {
        "日期": time.strftime("%Y-%m-%d"),
        "已赛场次": f"{payload['meta']['played']}/104",
        "AI 预测战绩": payload["record"]["stats"],
        "近期预测命中": hits[:5],
        "近期预测翻车": misses,
        "最大翻车（最高概率却错的那场）": biggest_miss,
        "未来24小时比赛": upcoming[:6],
        "夺冠概率异动": movers[:6],
        "Elo涨跌": elo_moves,
        "夺冠榜Top5_模型vs市场": top5,
    }


# ------------------------------------------------------------------ 每日复盘 --

def _load(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _publish() -> None:
    """把存档同步到网站（无论本次是否新生成）。"""
    reports = _load(REPORTS, [])
    (ROOT / "web" / "reports.js").write_text(
        "window.WC_REPORTS = " + json.dumps(reports[-60:], ensure_ascii=False)
        + ";\n", encoding="utf-8")
    blurbs = _load(BLURBS, {})
    (ROOT / "web" / "blurbs.js").write_text(
        "window.WC_BLURBS = " + json.dumps(
            {k: v["text"] for k, v in blurbs.items()}, ensure_ascii=False)
        + ";\n", encoding="utf-8")


def maybe_generate_report(payload: dict) -> None:
    reports = _load(REPORTS, [])
    today = time.strftime("%Y-%m-%d")
    played = payload["meta"]["played"]
    last = reports[-1] if reports else None
    if last and last["date"] == today and last["played"] >= played:
        return  # 当天已有且无新完赛
    cfg = _llm_config()
    if not cfg:
        return
    digest = json.dumps(_build_digest(payload), ensure_ascii=False)
    try:
        body = _chat(cfg, WRITER_SYSTEM, digest)
        comment_prompt = "数据摘要：" + digest + "\n\n" + "主笔复盘：" + body
        comment = _chat(cfg, COMMENTER_SYSTEM, comment_prompt,
                        model=cfg.get("commenter_model"))
        reports.append({
            "date": today, "time": time.strftime("%H:%M"),
            "played": played, "no": len(reports) + 1,
            "report": body, "comment": comment,
        })
        REPORTS.write_text(json.dumps(reports, ensure_ascii=False, indent=1),
                           encoding="utf-8")
        print(f"  [report] 已生成第 {len(reports)} 期复盘")
    except Exception as exc:  # noqa: BLE001
        print(f"  [report] 复盘生成失败（{exc}），跳过")


# ------------------------------------------------------------------ 单场看点 --

def maybe_generate_blurbs(payload: dict) -> None:
    cfg = _llm_config()
    if not cfg:
        return
    blurbs = _load(BLURBS, {})
    name = {t["code"]: t["name_zh"] for t in payload["teams"]}
    by_code = {t["code"]: t for t in payload["teams"]}
    now = datetime.now(timezone.utc)

    todo = {}
    for m in payload["schedule"]:
        if (m["score"] or not m.get("pred") or not (m["home"] and m["away"])
                or str(m["match"]) in blurbs):
            continue
        dt = datetime.fromisoformat(m["date_utc"].replace(" ", "T"))
        if timedelta(0) <= dt - now <= timedelta(hours=36):
            p, h, a = m["pred"], by_code[m["home"]], by_code[m["away"]]
            todo[str(m["match"])] = {
                "对阵": f"{name[m['home']]} vs {name[m['away']]}",
                "Elo": f"{h['elo']:.0f} vs {a['elo']:.0f}",
                "模型概率": f"主胜{p['p_home'] * 100:.0f}% 平{p['p_draw'] * 100:.0f}%"
                          f" 客胜{p['p_away'] * 100:.0f}%，最可能 "
                          + "-".join(map(str, p["pred_score"])),
                "市场": (f"主胜{p['market']['p_home'] * 100:.0f}%"
                        f" 客胜{p['market']['p_away'] * 100:.0f}%"
                        if p.get("market") else "无盘口"),
            }
    if not todo:
        return
    try:
        raw = _chat(cfg, BLURB_SYSTEM, json.dumps(todo, ensure_ascii=False))
        raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
        out = json.loads(raw)
        ts = time.strftime("%Y-%m-%d %H:%M")
        for k, text in out.items():
            if k in todo and isinstance(text, str) and text.strip():
                blurbs[k] = {"text": text.strip(), "ts": ts}
        BLURBS.write_text(json.dumps(blurbs, ensure_ascii=False, indent=1),
                          encoding="utf-8")
        print(f"  [report] 已生成 {len(out)} 条单场看点")
    except Exception as exc:  # noqa: BLE001
        print(f"  [report] 看点生成失败（{exc}），跳过")


def update_all(payload: dict) -> None:
    maybe_generate_report(payload)
    maybe_generate_blurbs(payload)
    _publish()
