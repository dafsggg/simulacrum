"""赛后 Elo 动态更新，公式与 eloratings.net 一致。

- 世界杯正赛 K = 60；
- 净胜球乘数 G：1 球 ×1.0，2 球 ×1.5，3 球及以上 ×(1.75 + (N-3)/8)；
- 点球分出胜负的比赛按常规时间+加时的比分记分（双方各记 0.5 场分），
  与 eloratings 的处理一致；
- 期望胜率沿用 model.win_expectancy，东道主含主场加成。
"""

from __future__ import annotations

from .model import HOST_ELO_BONUS, win_expectancy

K_WORLD_CUP = 60


def goal_multiplier(goal_diff: int) -> float:
    n = abs(goal_diff)
    if n <= 1:
        return 1.0
    if n == 2:
        return 1.5
    return 1.75 + (n - 3) / 8.0


def update_elo(elo_home: float, elo_away: float, score: tuple[int, int],
               home_is_host: bool = False, away_is_host: bool = False
               ) -> tuple[float, float]:
    """返回赛后 (新主队 Elo, 新客队 Elo)。score 为含加时的最终比分。"""
    gh, ga = score
    eff_home = elo_home + (HOST_ELO_BONUS if home_is_host else 0)
    eff_away = elo_away + (HOST_ELO_BONUS if away_is_host else 0)
    we = win_expectancy(eff_home, eff_away)

    if gh > ga:
        w = 1.0
    elif gh < ga:
        w = 0.0
    else:
        w = 0.5  # 点球大战在 Elo 体系中按平局计

    delta = K_WORLD_CUP * goal_multiplier(gh - ga) * (w - we)
    return elo_home + delta, elo_away - delta
