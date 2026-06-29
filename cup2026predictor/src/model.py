"""比赛模型：Elo 胜率 → 泊松进球分布 → 比分抽样。

核心思路：
1. 用 Elo 等级分差计算 A 队的"胜负期望" We = 1 / (1 + 10^(-d/400))。
2. 把 We 映射成两队的期望进球数（实力越悬殊，总进球越多、份额越偏）。
3. 双泊松分布生成比分，叠加 Dixon-Coles 低比分修正（纯独立泊松会系统性
   低估 0-0/1-1 平局），淘汰赛打平则模拟加时（强度 1/3），再进点球大战。

所有比分分布按 (elo_a, elo_b) 缓存成累计分布，抽样时一次 bisect 完成，
使数万次全程模拟可以在几秒内跑完（纯标准库，零依赖）。

知识库融合：
- effective_elo 中会读取 knowledge/ 目录下球队状态数据
- 根据近 10 场战绩（胜率、场均进球、场均失球）微调 Elo
- 修正量上限为 ±30 Elo 分，不影响整体量级
"""

from __future__ import annotations

import math
import random
from bisect import bisect_right
from functools import lru_cache

from .knowledge_loader import get_loader

MAX_GOALS = 12          # 泊松分布截断到单队 12 球
HOST_ELO_BONUS = 60     # 东道主（墨/美/加）全程主场加成
BASE_TOTAL_GOALS = 2.8  # 势均力敌时的预期总进球（世界杯历史均值约 2.7）
# 激进模式：提高实力悬殊时的总进球上限，让大比分概率增加
TOTAL_MISMATCH = 2.5    # 实力悬殊带来的总进球上浮（上调以增加大比分概率）
GD_LINEAR = 3.2         # 胜负期望 → 期望净胜球的线性项（上调以增加净胜球幅度）
GD_CUBIC = 12.0        # 极端悬殊时净胜球的非线性增长项（上调以增加极端比分概率）
MIN_LAMBDA = 0.70       # 单队期望进球下限（降低以允许弱队更少进球）
PENALTY_ELO_WEIGHT = 0.25  # 点球大战中 Elo 优势的衰减权重
DIXON_COLES_RHO = -0.02    # 低比分相关性修正
STYLE_MIN, STYLE_MAX = 0.70, 1.45  # 风格(开放度)对总进球的调节范围（保守：收紧极端开放度）
KBD_ELO_CAP = 30        # 知识库修正上限 Elo 分
KB_ENABLED = True       # 知识库修正开关

# 知识库数据缓存（延迟初始化）
_kbd_cache: dict[str, dict] | None = None
_cal_cache: dict[str, float] | None = None


def _get_kbd(code: str) -> dict | None:
    """获取球队知识库数据，带缓存。"""
    global _kbd_cache
    if _kbd_cache is None:
        _kbd_cache = {}
        loader = get_loader()
        for code in loader.get_all_team_names():
            _kbd_cache[code] = loader.get_prediction_boost(code)
    return _kbd_cache.get(code)


def _get_cal() -> dict[str, float]:
    """获取 EPUB/DOCX 中的全局盘口校准值，带缓存。"""
    global _cal_cache
    if _cal_cache is None:
        loader = get_loader()
        raw = loader.get_calibration() or {}
        # 设置默认值，确保所有关键键存在
        _cal_cache = {
            "book_home_bias": float(raw.get("book_home_bias", 0.0)),
            "book_upset_emphasis": float(raw.get("book_upset_emphasis", 0.0)),
            "book_draw_emphasis": float(raw.get("book_draw_emphasis", 0.0)),
            "book_strong_team_caution": float(raw.get("book_strong_team_caution", 0.0)),
            "book_total_goals_calibration": float(raw.get("book_total_goals_calibration", 1.0)),
        }
    return _cal_cache


def effective_elo(team: dict, opponent: dict | None = None) -> float:
    """东道主在本届比赛全程享受主场加成。

    知识库融合（分层，保守，不偏离 Elo 基准太远）：
    - 球队状态（TXT）：胜率/攻防因子 → 主修正方向（±30 Elo cap）
    - 强队不稳（TXT）：近期有弱点的强队 → 进一步下调
    - 防守强度（TXT）：防守特别强 → 额外加分
    - 遇强不弱（TXT）：当对手是顶级强队时，giant_killer boost
    - 全局盘口校准（EPUB/DOCX）：book_strong_team_caution 对顶级强队
      做整体下调（反映盘口知识中的"强队未必强"共识）
    """
    elo = team["elo"] + (HOST_ELO_BONUS if team.get("host") else 0)

    if not KB_ENABLED:
        return elo

    code = team.get("code", "")
    kbd = _get_kbd(code)

    # 全局校准（EPUB/DOCX 派生，即使没有球队 TXT 也起作用）
    cal = _get_cal()
    strong_caution = cal.get("book_strong_team_caution", 0.0)
    upset_cal = cal.get("book_upset_emphasis", 0.0)

    delta = 0.0

    # 全局：顶级强队整体下调（反映盘口知识中的"强队未必强"）
    # 调整系数：从 50 增大到 150，使 0.3 的校准值能产生 45 Elo 影响
    if elo >= 1900 and strong_caution > 0:
        delta -= strong_caution * 150.0
    elif elo >= 1800 and strong_caution > 0:
        delta -= strong_caution * 100.0  # 次强队也有小幅度下调

    # 全局：弱队整体上调（反映冷门/爆冷知识）
    # 调整系数：从 40 增大到 120，使 0.3 的校准值能产生 36 Elo 影响
    if elo < 1650 and upset_cal > 0:
        delta += upset_cal * 120.0
    elif elo < 1750 and upset_cal > 0:
        delta += upset_cal * 80.0  # 中下游球队也有爆冷倾向

    # 全局：主场加成（仅对东道主或中立场的主队）
    home_bias = cal.get("book_home_bias", 0.0)
    if team.get("host") and home_bias > 0:
        delta += home_bias * 80.0

    if kbd:
        # 基础修正：胜率/进攻/防守因子（等权重平均）
        form = (kbd["form_factor"] * 1.3 + kbd["attack_factor"] * 1.0 +
                kbd["defense_factor"] * 1.0) / 3.3
        delta += (form - 1.0) * 80.0

        # 防守强度：防守特别强
        if kbd.get("defensive_strength", 1.0) > 1.1:
            delta += (kbd["defensive_strength"] - 1.0) * 60.0

        # 强队不稳：传统强队但近期有弱点
        if kbd.get("strong_but_weak", 0.0) > 0:
            delta -= kbd["strong_but_weak"] * 80.0

        # 遇强不弱：当对手是强队时
        if opponent is not None and kbd.get("giant_killer", 0.0) > 0:
            opp_elo_base = opponent.get("elo", 0) + (HOST_ELO_BONUS if opponent.get("host") else 0)
            if opp_elo_base >= 1900:
                delta += kbd["giant_killer"] * 60.0

    # 总修正：应用上限
    delta = max(-KBD_ELO_CAP, min(KBD_ELO_CAP, delta))
    return elo + delta


def style_scale(team_a: dict, team_b: dict) -> float:
    """两队风格对总进球的乘数：开放度(open)的几何平均。

    融合两个信号源：
    1. 演化中的 open（由 strengths.json 初始化，随比赛结果更新）
    2. 知识库 style_open（从战术描述关键字推导，如"攻势足球"↑/
       "铁桶阵/密集防守"↓）
    两者取加权平均，知识信号权重 0.55（因为战术描述更稳定、
    反映真实战术意图而非偶然比分）。
    """
    open_a = team_a.get("open", 1.0)
    open_b = team_b.get("open", 1.0)

    # 知识库 style_open 补充
    kbd_a = _get_kbd(team_a.get("code", ""))
    kbd_b = _get_kbd(team_b.get("code", ""))
    if kbd_a and "style_open" in kbd_a:
        open_a = open_a * 0.45 + kbd_a["style_open"] * 0.55
    if kbd_b and "style_open" in kbd_b:
        open_b = open_b * 0.45 + kbd_b["style_open"] * 0.55

    s = (open_a * open_b) ** 0.5

    # 全局盘口校准：大球/小球倾向（来自 EPUB/DOCX）
    cal = _get_cal()
    goals_cal = cal.get("book_total_goals_calibration", 1.0)
    s = s * goals_cal

    return round(min(max(s, STYLE_MIN), STYLE_MAX), 3)


def win_expectancy(elo_a: float, elo_b: float) -> float:
    """A 队的 Elo 胜负期望（0~1）。"""
    return 1.0 / (1.0 + 10 ** ((elo_b - elo_a) / 400.0))


def expected_goals(we: float) -> tuple[float, float]:
    """由胜负期望推出双方期望进球 (λa, λb)。

    思路：实力差决定"期望净胜球"而非进球份额——总进球围绕世界杯均值，
    净胜球随 Elo 差非线性增长，两队各取 (总±净胜)/2。
    这样弱队始终保有合理的进攻基线（不会出现 0.1 球的荒谬期望），
    比分分布里 2-1 / 3-1 / 2-2 等"双方都进球"的结果占比贴近真实。
    """
    x = we - 0.5
    total = BASE_TOTAL_GOALS + TOTAL_MISMATCH * abs(x)
    diff = GD_LINEAR * x + GD_CUBIC * x ** 3
    lam_a = max((total + diff) / 2.0, MIN_LAMBDA)
    lam_b = max((total - diff) / 2.0, MIN_LAMBDA)
    return lam_a, lam_b



def apply_score_shift(cum: list[float], scores: list[tuple[int, int]],
                      shift: dict | None) -> tuple[list[float], list[tuple[int, int]]]:
    """根据 score_shift 微调比分分布的总进球倾向，保持胜负比例不变。

    大球偏差：提高高总进球比分的概率，降低低总进球比分
    小球偏差：提高低总进球比分的概率，降低高总进球比分
    """
    if not shift:
        return cum, scores

    magn = shift.get("magnitude", 0)
    mode = shift.get("shift_mode", "neutral")

    if mode == "neutral" or abs(magn) < 0.001:
        return cum, scores

    # 从累计分布还原为概率质量函数 (PMF)
    pmf = [cum[0]] + [cum[i] - cum[i - 1] for i in range(1, len(cum))]

    # 按总进球数分组
    low_idx = [i for i, (g1, g2) in enumerate(scores) if g1 + g2 <= 2]
    high_idx = [i for i, (g1, g2) in enumerate(scores) if g1 + g2 >= 3]

    if not low_idx or not high_idx:
        return cum, scores

    # 计算原始胜负比例（用于后续保持）
    p_win_orig = sum(pmf[i] for i, (g1, g2) in enumerate(scores) if g1 > g2)
    p_draw_orig = sum(pmf[i] for i, (g1, g2) in enumerate(scores) if g1 == g2)
    p_loss_orig = sum(pmf[i] for i, (g1, g2) in enumerate(scores) if g1 < g2)

    # 温和调整：将 magn 控制在合理范围内，避免过度扭曲
    # magn 最大影响约 15% 的概率转移
    transfer_rate = min(magn * 0.3, 0.15)

    if mode == "over":
        # 大球偏差：从低总进球向高总进球转移
        for idx in low_idx:
            delta = pmf[idx] * transfer_rate
            pmf[idx] -= delta
            # 按原始高总进球比分的比例分配
            high_total = sum(pmf[i] for i in high_idx)
            if high_total > 0:
                for hidx in high_idx:
                    pmf[hidx] += delta * (pmf[hidx] / high_total)
    elif mode == "under":
        # 小球偏差：从高总进球向低总进球转移
        for idx in high_idx:
            delta = pmf[idx] * transfer_rate
            pmf[idx] -= delta
            # 按原始低总进球比分的比例分配
            low_total = sum(pmf[i] for i in low_idx)
            if low_total > 0:
                for lidx in low_idx:
                    pmf[lidx] += delta * (pmf[lidx] / low_total)

    # 归一化
    total = sum(pmf)
    if total > 0:
        pmf = [p / total for p in pmf]

    # 保持胜负比例不变：按原始比例重新分配
    p_win_new = sum(pmf[i] for i, (g1, g2) in enumerate(scores) if g1 > g2)
    p_draw_new = sum(pmf[i] for i, (g1, g2) in enumerate(scores) if g1 == g2)
    p_loss_new = sum(pmf[i] for i, (g1, g2) in enumerate(scores) if g1 < g2)

    if p_win_new > 0 and p_win_orig > 0:
        win_scale = p_win_orig / p_win_new
        for i, (g1, g2) in enumerate(scores):
            if g1 > g2:
                pmf[i] *= win_scale
    if p_draw_new > 0 and p_draw_orig > 0:
        draw_scale = p_draw_orig / p_draw_new
        for i, (g1, g2) in enumerate(scores):
            if g1 == g2:
                pmf[i] *= draw_scale
    if p_loss_new > 0 and p_loss_orig > 0:
        loss_scale = p_loss_orig / p_loss_new
        for i, (g1, g2) in enumerate(scores):
            if g1 < g2:
                pmf[i] *= loss_scale

    # 再次归一化
    total = sum(pmf)
    if total > 0:
        pmf = [p / total for p in pmf]

    # PMF → 累计分布
    cum_new = [0.0] * len(pmf)
    cum_new[0] = pmf[0]
    for i in range(1, len(pmf)):
        cum_new[i] = cum_new[i - 1] + pmf[i]

    return cum_new, scores


@lru_cache(maxsize=512)
def _poisson_lgamma(n: int) -> float:
    """n! 的对数。"""
    if n <= 1:
        return 0.0
    return sum(math.log(i) for i in range(1, n + 1))


def _poisson_pmf(k: int, lam: float) -> float:
    """泊松分布 PMF：P(X = k) 当 E[X] = lam 时。"""
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam + k * math.log(lam) - _poisson_lgamma(k))


@lru_cache(maxsize=2048)
def score_distribution(elo_a: float, elo_b: float,
                       style: float = 1.0,
                       tempo: float = 1.0,
                       we_override: float | None = None,
                       ) -> tuple[list[float], list[tuple[int, int]]]:
    """预计算比分分布的累计函数（含 Dixon-Coles 修正），供抽样/查表用。

    返回：(累计分布, 比分列表)。
    比分列表长度 = 累计分布长度，一一对应。
    """
    if we_override is not None:
        lam_a, lam_b = expected_goals(we_override)
    else:
        lam_a, lam_b = expected_goals(win_expectancy(elo_a, elo_b))
    lam_a *= style * tempo
    lam_b *= style * tempo
    lam_a = max(lam_a, MIN_LAMBDA)
    lam_b = max(lam_b, MIN_LAMBDA)
    pmf = [[0.0] * (MAX_GOALS + 1) for _ in range(MAX_GOALS + 1)]
    for i in range(MAX_GOALS + 1):
        pi = _poisson_pmf(i, lam_a)
        for j in range(MAX_GOALS + 1):
            pj = _poisson_pmf(j, lam_b)
            p = pi * pj
            # Dixon-Coles 修正
            if i <= 1 and j <= 1:
                p *= math.exp(DIXON_COLES_RHO * i * j)
            pmf[i][j] = p
    # 展平 + 累计
    flat = []
    for i in range(MAX_GOALS + 1):
        for j in range(MAX_GOALS + 1):
            flat.append(pmf[i][j])
    total = sum(flat)
    if total == 0:
        flat[0] = 1.0
        total = 1.0
    flat = [x / total for x in flat]
    cum = [0.0] * len(flat)
    cum[0] = flat[0]
    for i in range(1, len(flat)):
        cum[i] = cum[i - 1] + flat[i]
    scores = []
    for i in range(MAX_GOALS + 1):
        for j in range(MAX_GOALS + 1):
            scores.append((i, j))
    return cum, scores


def sample_score(elo_a: float, elo_b: float, rng: random.Random,
                 style: float = 1.0, tempo: float = 1.0,
                 we_override: float | None = None) -> tuple[int, int]:
    """从双泊松分布（含 Dixon-Coles 修正）中抽样一个比分。"""
    cum, scores = score_distribution(elo_a, elo_b, style=style, tempo=tempo,
                                     we_override=we_override)
    r = rng.random()
    idx = bisect_right(cum, r)
    return scores[min(idx, len(scores) - 1)]


def simulate_group_match(team_a: dict, team_b: dict, rng: random.Random,
                         we_override: float | None = None) -> tuple[int, int]:
    """小组赛：90 分钟比分，允许平局。"""
    return sample_score(effective_elo(team_a, team_b), effective_elo(team_b, team_a), rng,
                        style=style_scale(team_a, team_b),
                        we_override=we_override)


def simulate_knockout_match(team_a: dict, team_b: dict, rng: random.Random,
                            we_override: float | None = None) -> tuple[int, int, bool]:
    """淘汰赛：90 分钟 + 加时 + 点球。

    返回：(比分 a, 比分 b, 是否通过加时/点球分出胜负)
    """
    # 90 分钟
    score_a, score_b = simulate_group_match(team_a, team_b, rng,
                                            we_override=we_override)
    if score_a != score_b:
        return score_a, score_b, False

    # 平局 → 加时赛（强度减半）
    et_style = style_scale(team_a, team_b) * 0.7
    et_a, et_b = sample_score(
        effective_elo(team_a, team_b), effective_elo(team_b, team_a),
        rng, style=et_style, tempo=0.6, we_override=we_override
    )
    score_a += et_a
    score_b += et_b
    if score_a != score_b:
        return score_a, score_b, True

    # 仍平局 → 点球大战（按 Elo 比例抽样）
    we = we_override if we_override is not None else win_expectancy(
        effective_elo(team_a, team_b), effective_elo(team_b, team_a))
    # 点球胜率近似：We^(PENALTY_ELO_WEIGHT)
    pen_win = we ** PENALTY_ELO_WEIGHT
    if rng.random() < pen_win:
        return score_a, score_b, True
    else:
        return score_b, score_a, True


def match_probabilities(team_a: dict, team_b: dict, knockout: bool = False,
                        we_override: float | None = None,
                        score_shift: dict | None = None) -> dict:
    """解析法计算单场胜平负概率与最可能比分（不做蒙特卡洛）。

    知识库融合：effective_elo 已自动考虑知识库中的球队状态数据，
    无需在此层额外处理。
    """
    ea, eb = effective_elo(team_a, team_b), effective_elo(team_b, team_a)
    st = style_scale(team_a, team_b)
    we = we_override if we_override is not None else win_expectancy(ea, eb)
    cum, scores = score_distribution(ea, eb, style=st, we_override=we)
    cum, scores = apply_score_shift(cum, scores, score_shift)
    probs = [cum[0]] + [cum[i] - cum[i - 1] for i in range(1, len(cum))]

    p_win = p_draw = p_loss = 0.0
    all_scores_sorted = sorted(zip(scores, probs), key=lambda x: -x[1])
    top_scores = all_scores_sorted[:5]
    top10_scores = all_scores_sorted[:10]
    for (ga, gb), p in zip(scores, probs):
        if ga > gb:
            p_win += p
        elif ga == gb:
            p_draw += p
        else:
            p_loss += p

    # 平局倾向校准（EPUB/DOCX 盘口知识：显著调整平局概率）
    cal = _get_cal()
    draw_cal = cal.get("book_draw_emphasis", 0.0)
    # 对势均力敌的比赛（胜负差距 < 0.40）应用平局校准
    if draw_cal > 0 and p_draw > 0 and abs(p_win - p_loss) < 0.40:
        draw_boost = min(draw_cal * 0.15, 0.08, p_win * 0.30, p_loss * 0.30)
        p_draw += draw_boost
        p_win -= draw_boost * 0.5
        p_loss -= draw_boost * 0.5
        p_win = max(p_win, 0.0)
        p_loss = max(p_loss, 0.0)
    # 对实力悬殊的比赛也给少量平局加成（至少有爆冷平局可能）
    elif draw_cal > 0 and p_draw > 0:
        draw_boost = min(draw_cal * 0.05, 0.03)
        p_draw += draw_boost
        p_win -= draw_boost * 0.5
        p_loss -= draw_boost * 0.5
        p_win = max(p_win, 0.0)
        p_loss = max(p_loss, 0.0)

    # 胜平负预测逻辑：选概率最高的结果，当平局足够接近最高概率时也选平局
    # （世界杯历史平局率约 25-30%，势均力敌比赛应倾向平局）
    max_non_draw = max(p_win, p_loss)
    if p_draw >= max_non_draw - 0.05:
        # 平局与最高胜负概率差距 < 5%，视为平局候选
        if p_draw >= 0.20:  # 平局概率也不能太低
            outcome = "D"
        elif p_win >= p_loss:
            outcome = "H"
        else:
            outcome = "A"
    elif p_win >= p_loss:
        outcome = "H"
    else:
        outcome = "A"

    # 筛选与胜负方向一致的所有比分，按概率降序排列
    aligned = []
    for (ga, gb), p in zip(scores, probs):
        ok = (ga > gb if outcome == "H"
              else ga == gb if outcome == "D" else ga < gb)
        if ok:
            aligned.append(((ga, gb), p))
    aligned.sort(key=lambda x: -x[1])

    lam_a, lam_b = expected_goals(we)
    lam_a_adj, lam_b_adj = lam_a * st, lam_b * st
    
    # 攻防特点调整：结合知识库的进攻/防守因子微调期望进球
    # 进攻强+对手防守弱 → 期望进球大幅上调；进攻弱+对手防守强 → 期望进球大幅下调
    # 激进模式：扩大调整范围，让攻防差距更明显
    kbd_a = _get_kbd(team_a.get("code", "")) or {}
    kbd_b = _get_kbd(team_b.get("code", "")) or {}
    att_a = kbd_a.get("attack_factor", 1.0)
    def_b = kbd_b.get("defense_factor", 1.0)
    att_b = kbd_b.get("attack_factor", 1.0)
    def_a = kbd_a.get("defense_factor", 1.0)
    
    # 激进调整：扩大范围到 0.70~1.40，让攻防差距更明显
    home_adj = min(max(att_a / max(def_b, 0.8), 0.70), 1.40)
    away_adj = min(max(att_b / max(def_a, 0.8), 0.70), 1.40)
    
    # 实力碾压加成：当Elo差距>150时，对强队额外增加进球期望
    elo_gap = abs(ea - eb)
    overkill_bonus = 0.0
    if elo_gap > 150:
        # 实力差距越大，强队额外加成越高（最高+20%）
        overkill_bonus = min((elo_gap - 150) / 1000, 0.20)
        if outcome == "H":
            home_adj = min(home_adj + overkill_bonus, 1.50)
        elif outcome == "A":
            away_adj = min(away_adj + overkill_bonus, 1.50)
    
    lam_a_final = lam_a_adj * home_adj
    lam_b_final = lam_b_adj * away_adj

    if not aligned:
        pick_score, pick_p = top_scores[0]
    else:
        best_p = aligned[0][1]
        # 激进模式：扩大候选范围，让更多比分有机会被选中
        top10_set = set(s for s, p in top10_scores)
        candidates = [item for item in aligned
                      if item[1] >= best_p - 0.06 and item[0] in top10_set]
        if not candidates:
            candidates = aligned[:5]  # fallback: 前5个同方向比分
        
        # 激进评分逻辑：更看重期望进球匹配度，强队大比分零封加分更高
        def score_candidate(item):
            (ga, gb), p = item
            # 基础分：概率（越高越好）
            prob_score = p
            # 期望进球距离分：用攻防调整后期望，距离越近加分越多（激进：权重加倍）
            dist = abs(ga - lam_a_final) + abs(gb - lam_b_final)
            dist_score = max(0, 0.040 - dist * 0.008)
            # 强队零封加分：实力碾压时，零封比分加分大幅提高
            shutout_bonus = 0.0
            elo_diff = abs(ea - eb)
            if outcome == "H" and p_win > 0.55 and gb == 0:
                # 激进加成：最低0.025 + 实力差距额外加分（最高0.015）
                shutout_bonus = 0.025 + min(0.015, max(0, (elo_diff - 150)) / 1000 * 0.015)
            elif outcome == "A" and p_loss > 0.55 and ga == 0:
                shutout_bonus = 0.025 + min(0.015, max(0, (elo_diff - 150)) / 1000 * 0.015)
            # 大比分加成：实力碾压时，3+球数的比分加分（进攻方多进球）
            overkill_bonus = 0.0
            if elo_diff > 150:
                if outcome == "H" and ga >= 3:
                    overkill_bonus = 0.012 * min(ga - 2, 2)  # 3-0/4-0加成
                elif outcome == "A" and gb >= 3:
                    overkill_bonus = 0.012 * min(gb - 2, 2)  # 0-3/0-4加成
            # 总得分
            total = prob_score + dist_score + shutout_bonus + overkill_bonus
            return total
        
        # 按综合得分排序
        candidates_scored = sorted(candidates, key=score_candidate, reverse=True)
        pick_score, pick_p = candidates_scored[0]

    result = {
        "win_expectancy": we,
        "lambdas": (lam_a_adj, lam_b_adj),
        "p_win": p_win, "p_draw": p_draw, "p_loss": p_loss,
        "top_scores": top_scores,
        "outcome_pick": outcome,
        "outcome_score": (pick_score, pick_p),
    }
    if knockout:
        # 平局部分按加时/点球的近似胜率劈给双方
        et_edge = 0.5 + (we - 0.5) * 0.6  # 加时+点球综合优势（经验近似）
        result["p_advance_a"] = p_win + p_draw * et_edge
        result["p_advance_b"] = p_loss + p_draw * (1 - et_edge)
    return result


GRID_SIZE = 6  # 0-5 goals


def score_grid(team_a: dict, team_b: dict,
               we_override: float | None = None,
               score_shift: dict | None = None) -> list[list[float]]:
    """返回 6×6 比分配对概率矩阵（主队进球×客队进球）。

    供前端比分热力图使用，与 match_probabilities 共用同一套模型参数。
    """
    ea = effective_elo(team_a, team_b)
    eb = effective_elo(team_b, team_a)
    st = style_scale(team_a, team_b)
    we = we_override if we_override is not None else win_expectancy(ea, eb)
    cum, scores = score_distribution(ea, eb, style=st, we_override=we)
    cum, scores = apply_score_shift(cum, scores, score_shift)

    # 从累计分布还原逐个概率
    probs = [cum[0]] + [cum[i] - cum[i - 1] for i in range(1, len(cum))]
    score_prob = dict(zip(scores, probs))

    # 构建 6×6 矩阵
    grid = [[0.0] * GRID_SIZE for _ in range(GRID_SIZE)]
    for ga in range(GRID_SIZE):
        for gb in range(GRID_SIZE):
            grid[ga][gb] = score_prob.get((ga, gb), 0.0)

    return grid


def exact_score_prob(team_a: dict, team_b: dict,
                     goals_a: int, goals_b: int,
                     we_override: float | None = None,
                     score_shift: dict | None = None) -> float:
    """返回指定比分的精确概率 P(goals_a : goals_b)。"""
    ea = effective_elo(team_a, team_b)
    eb = effective_elo(team_b, team_a)
    st = style_scale(team_a, team_b)
    we = we_override if we_override is not None else win_expectancy(ea, eb)
    cum, scores = score_distribution(ea, eb, style=st, we_override=we)
    cum, scores = apply_score_shift(cum, scores, score_shift)

    # 从累计分布还原逐个概率
    probs = [cum[0]] + [cum[i] - cum[i - 1] for i in range(1, len(cum))]
    score_prob = dict(zip(scores, probs))
    return score_prob.get((goals_a, goals_b), 0.0)