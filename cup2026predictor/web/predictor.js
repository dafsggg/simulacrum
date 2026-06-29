/**
 * 纯前端预测引擎
 *
 * 功能：
 * 1. 加载 web/teams.json 和 web/calibration.json
 * 2. 对 WC_DATA.schedule 中的未赛场次进行胜平负概率 + 最可能比分预测
 * 3. 只刷新最近 limit 场未赛（默认 10 场），其他保持不变
 * 4. 更新后基于已赛场次生成 AI 复盘简报
 *
 * 与 Python 后端 model.py 的核心参数保持一致。
 */

const Predictor = (function () {
  // 常量（与 model.py 一致）
  const MAX_GOALS = 12;
  const HOST_ELO_BONUS = 60;
  const BASE_TOTAL_GOALS = 2.8;
  const TOTAL_MISMATCH = 2.0;
  const GD_LINEAR = 3.0;
  const GD_CUBIC = 10.0;
  const MIN_LAMBDA = 0.75;
  const DIXON_COLES_RHO = -0.02;
  const STYLE_MIN = 0.70;
  const STYLE_MAX = 1.45;
  const KBD_ELO_CAP = 30;

  let teamsMap = {};
  let calibration = {};

  // 比分分布缓存 key: "ea,eb,st"
  const distCache = new Map();

  function winExpectancy(eloA, eloB) {
    return 1.0 / (1.0 + Math.pow(10, (eloB - eloA) / 400.0));
  }

  function expectedGoals(we) {
    const x = we - 0.5;
    const total = BASE_TOTAL_GOALS + TOTAL_MISMATCH * Math.abs(x);
    const diff = GD_LINEAR * x + GD_CUBIC * x * x * x;
    const lamA = Math.max((total + diff) / 2.0, MIN_LAMBDA);
    const lamB = Math.max((total - diff) / 2.0, MIN_LAMBDA);
    return [lamA, lamB];
  }

  function logFactorial(n, cache) {
    if (n <= 1) return 0.0;
    if (cache[n] !== undefined) return cache[n];
    let s = 0;
    for (let i = 2; i <= n; i++) s += Math.log(i);
    cache[n] = s;
    return s;
  }

  function poissonPmf(k, lam, logCache) {
    if (lam <= 0) return k === 0 ? 1.0 : 0.0;
    return Math.exp(-lam + k * Math.log(lam) - logFactorial(k, logCache));
  }

  function scoreDistribution(ea, eb, style) {
    const key = `${ea.toFixed(2)},${eb.toFixed(2)},${style.toFixed(3)}`;
    if (distCache.has(key)) return distCache.get(key);

    const we = winExpectancy(ea, eb);
    let [lamA, lamB] = expectedGoals(we);
    lamA *= style;
    lamB *= style;
    lamA = Math.max(lamA, MIN_LAMBDA);
    lamB = Math.max(lamB, MIN_LAMBDA);

    const logCache = {};
    const pmf = [];
    const scores = [];
    for (let i = 0; i <= MAX_GOALS; i++) {
      const pi = poissonPmf(i, lamA, logCache);
      for (let j = 0; j <= MAX_GOALS; j++) {
        const pj = poissonPmf(j, lamB, logCache);
        let p = pi * pj;
        if (i <= 1 && j <= 1) {
          p *= Math.exp(DIXON_COLES_RHO * i * j);
        }
        pmf.push(p);
        scores.push([i, j]);
      }
    }

    const total = pmf.reduce((a, b) => a + b, 0);
    const norm = total === 0 ? 1.0 : total;
    const flat = pmf.map(p => p / norm);
    const cum = [];
    cum[0] = flat[0];
    for (let i = 1; i < flat.length; i++) {
      cum[i] = cum[i - 1] + flat[i];
    }

    const result = { cum, scores, flat, lamA, lamB, we };
    distCache.set(key, result);
    return result;
  }

  function effectiveElo(team, opponent) {
    let elo = team.elo + (team.host ? HOST_ELO_BONUS : 0);
    if (!team.boost) return elo;

    const cal = calibration || {};
    const strongCaution = cal.book_strong_team_caution || 0;
    const upsetCal = cal.book_upset_emphasis || 0;

    let delta = 0.0;

    if (elo >= 1900 && strongCaution > 0) delta -= strongCaution * 150.0;
    else if (elo >= 1800 && strongCaution > 0) delta -= strongCaution * 100.0;

    if (elo < 1650 && upsetCal > 0) delta += upsetCal * 120.0;
    else if (elo < 1750 && upsetCal > 0) delta += upsetCal * 80.0;

    const homeBias = cal.book_home_bias || 0;
    if (team.host && homeBias > 0) delta += homeBias * 80.0;

    const b = team.boost;
    const form = (b.form_factor * 1.3 + b.attack_factor * 1.0 + b.defense_factor * 1.0) / 3.3;
    delta += (form - 1.0) * 80.0;

    if (b.defensive_strength > 1.1) delta += (b.defensive_strength - 1.0) * 60.0;
    if (b.strong_but_weak > 0) delta -= b.strong_but_weak * 80.0;

    if (opponent && b.giant_killer > 0) {
      const oppEloBase = opponent.elo + (opponent.host ? HOST_ELO_BONUS : 0);
      if (oppEloBase >= 1900) delta += b.giant_killer * 60.0;
    }

    delta = Math.max(-KBD_ELO_CAP, Math.min(KBD_ELO_CAP, delta));
    return elo + delta;
  }

  function styleScale(a, b) {
    let openA = a.open || 1.0;
    let openB = b.open || 1.0;
    if (a.boost && a.boost.style_open !== undefined) {
      openA = openA * 0.45 + a.boost.style_open * 0.55;
    }
    if (b.boost && b.boost.style_open !== undefined) {
      openB = openB * 0.45 + b.boost.style_open * 0.55;
    }
    let s = Math.sqrt(openA * openB);
    const goalsCal = calibration.book_total_goals_calibration || 1.0;
    s *= goalsCal;
    return Math.min(Math.max(s, STYLE_MIN), STYLE_MAX);
  }

  function buildGrid(flat, scores) {
    // 6x6 概率网格
    const grid = Array.from({ length: 6 }, () => Array(6).fill(0));
    for (let i = 0; i < scores.length; i++) {
      const [ga, gb] = scores[i];
      if (ga < 6 && gb < 6) grid[ga][gb] += flat[i];
    }
    return grid;
  }

  function matchProbabilities(homeCode, awayCode) {
    const teamA = getTeam(homeCode);
    const teamB = getTeam(awayCode);
    const ea = effectiveElo(teamA, teamB);
    const eb = effectiveElo(teamB, teamA);
    const st = styleScale(teamA, teamB);
    const dist = scoreDistribution(ea, eb, st);
    const { flat, scores, lamA, lamB, we } = dist;

    let pWin = 0, pDraw = 0, pLoss = 0;
    const topScoresAll = [];
    for (let i = 0; i < scores.length; i++) {
      const [ga, gb] = scores[i];
      const p = flat[i];
      if (ga > gb) pWin += p;
      else if (ga === gb) pDraw += p;
      else pLoss += p;
      topScoresAll.push({ score: [ga, gb], p });
    }
    topScoresAll.sort((x, y) => y.p - x.p);
    const topScores = topScoresAll.slice(0, 5);
    const top10Scores = topScoresAll.slice(0, 10);

    // 平局校准
    const drawCal = calibration.book_draw_emphasis || 0;
    if (drawCal > 0 && pDraw > 0) {
      const close = Math.abs(pWin - pLoss) < 0.40;
      const drawBoost = close
        ? Math.min(drawCal * 0.15, 0.08, pWin * 0.30, pLoss * 0.30)
        : Math.min(drawCal * 0.05, 0.03);
      pDraw += drawBoost;
      pWin -= drawBoost * 0.5;
      pLoss -= drawBoost * 0.5;
      pWin = Math.max(pWin, 0);
      pLoss = Math.max(pLoss, 0);
    }

    const maxNonDraw = Math.max(pWin, pLoss);
    let outcome;
    if (pDraw >= maxNonDraw - 0.05 && pDraw >= 0.20) outcome = "D";
    else if (pWin >= pLoss) outcome = "H";
    else outcome = "A";

    const aligned = [];
    for (let i = 0; i < scores.length; i++) {
      const [ga, gb] = scores[i];
      const p = flat[i];
      const ok = outcome === "H" ? ga > gb : outcome === "D" ? ga === gb : ga < gb;
      if (ok) aligned.push({ score: [ga, gb], p });
    }
    aligned.sort((x, y) => y.p - x.p);

    let pickScore, pickP;
    if (!aligned.length) {
      const top = topScores[0];
      pickScore = top.score;
      pickP = top.p;
    } else {
      const bestP = aligned[0].p;
      const top10Set = new Set(top10Scores.map(s => s.score.join(',')));
      // 取概率 >= bestP - 0.04 且在 TOP10 内的候选（概率差距4%以内都有机会）
      let candidates = aligned.filter(item =>
        item.p >= bestP - 0.04 && top10Set.has(item.score.join(','))
      );
      if (!candidates.length) {
        candidates = aligned.slice(0, 5);
      }
      
      const lamAAdj = lamA * st;
      const lamBAdj = lamB * st;
      
      // 攻防特点调整：结合知识库的进攻/防守因子微调期望进球
      const boostA = teamA.boost || {};
      const boostB = teamB.boost || {};
      const attA = boostA.attack_factor || 1.0;
      const defB = boostB.defense_factor || 1.0;
      const attB = boostB.attack_factor || 1.0;
      const defA = boostA.defense_factor || 1.0;
      
      // 主队进球调整 = 主队进攻因子 / 客队防守因子（范围限制在 0.85~1.18）
      let homeAdj = Math.min(Math.max(attA / Math.max(defB, 0.8), 0.85), 1.18);
      let awayAdj = Math.min(Math.max(attB / Math.max(defA, 0.8), 0.85), 1.18);
      
      // 只有当两队 Elo 差距较大时，攻防调整才明显（防止接近的比赛过度调整）
      const eloGap = Math.abs(ea - eb);
      if (eloGap < 200) {
        const blend = eloGap / 200;
        homeAdj = 1.0 + (homeAdj - 1.0) * blend;
        awayAdj = 1.0 + (awayAdj - 1.0) * blend;
      }
      
      const lamAFinal = lamAAdj * homeAdj;
      const lamBFinal = lamBAdj * awayAdj;
      
      // 评分选择逻辑：结合概率、期望进球距离（含攻防调整）、强队零封偏好
      function scoreCandidate(item) {
        const [ga, gb] = item.score;
        const p = item.p;
        // 基础分：概率
        let total = p;
        // 期望进球距离分：用攻防调整后期望，距离越近加分越多
        const dist = Math.abs(ga - lamAFinal) + Math.abs(gb - lamBFinal);
        total += Math.max(0, 0.022 - dist * 0.006);
        // 强队零封加分：主胜/客胜概率 >58% 时，零封比分加额外分，Elo差距越大加分越多
        const eloDiff = Math.abs(ea - eb);
        if (outcome === "H" && pWin > 0.58 && gb === 0) {
          total += 0.020 + Math.min(0.008, Math.max(0, (eloDiff - 200)) / 200 * 0.008);
        } else if (outcome === "A" && pLoss > 0.58 && ga === 0) {
          total += 0.020 + Math.min(0.008, Math.max(0, (eloDiff - 200)) / 200 * 0.008);
        }
        return total;
      }
      
      candidates.sort((a, b) => scoreCandidate(b) - scoreCandidate(a));
      pickScore = candidates[0].score;
      pickP = candidates[0].p;
    }

    return {
      p_home: parseFloat(pWin.toFixed(4)),
      p_draw: parseFloat(pDraw.toFixed(4)),
      p_away: parseFloat(pLoss.toFixed(4)),
      pick: outcome,
      pred_score: pickScore,
      top_scores: topScores.slice(0, 5).map(s => ({ score: s.score, p: parseFloat(s.p.toFixed(4)) })),
      grid: buildGrid(flat, scores).map(row => row.map(v => parseFloat(v.toFixed(4)))),
      lambdas: [parseFloat((lamA * st).toFixed(4)), parseFloat((lamB * st).toFixed(4))],
      win_expectancy: parseFloat(we.toFixed(4))
    };
  }

  async function loadData() {
    let teamsJson, calJson;

    // 优先使用页面内联数据（predictor-data.js），避免 file:// 或移动端 fetch 失败
    if (window.WC_TEAMS && window.WC_CALIBRATION) {
      teamsJson = window.WC_TEAMS;
      calJson = window.WC_CALIBRATION;
    } else {
      // 如果从语言子目录访问，数据文件在上一级目录
      const inLangFolder = /^\/(de|es|pt|ru|zh)\b/.test(location.pathname);
      const base = inLangFolder ? '../' : './';
      let teamsErr, calErr;
      try {
        const teamsRes = await fetch(base + 'teams.json');
        if (!teamsRes.ok) throw new Error('status ' + teamsRes.status);
        teamsJson = await teamsRes.json();
      } catch (e) {
        teamsErr = e;
      }
      try {
        const calRes = await fetch(base + 'calibration.json');
        if (!calRes.ok) throw new Error('status ' + calRes.status);
        calJson = await calRes.json();
      } catch (e) {
        calErr = e;
      }
      if (!teamsJson) throw new Error('无法加载 teams.json: ' + (teamsErr && teamsErr.message));
      if (!calJson) throw new Error('无法加载 calibration.json: ' + (calErr && calErr.message));
    }

    calibration = calJson;
    teamsMap = {};
    for (const t of teamsJson.teams) {
      teamsMap[t.code] = t;
    }
  }

  function getTeam(code) {
    return teamsMap[code] || { code, elo: 1500, host: false, open: 1.0 };
  }

  // 根据已赛场次生成复盘简报
  function generateReview(schedule) {
    const played = (schedule || []).filter(m => m.score !== null && m.score !== undefined);
    const missed = played.filter(m => !m.outcome_hit);
    const wrongScores = played.filter(m => !m.score_hit);
    const upsets = played.filter(m => {
      if (!m.pred || !m.winner) return false;
      return m.pred.pick !== "D" && m.winner !== m.home && m.winner !== m.away && m.winner;
    });

    const lines = [];
    lines.push(`已赛 ${played.length} 场，胜负方向命中 ${played.length - missed.length} 场，命中率 ${played.length ? (((played.length - missed.length) / played.length) * 100).toFixed(1) : 0}%。`);
    if (missed.length) {
      const examples = missed.slice(-3).map(m => {
        const predPick = m.pred.pick === "H" ? m.home : m.pred.pick === "A" ? m.away : "平局";
        return `${m.home} ${m.score[0]}-${m.score[1]} ${m.away}（AI 原判 ${predPick}）`;
      });
      lines.push(`近期失误：${examples.join("；")}。`);
      lines.push("复盘思路：强队 Elo 下调系数与盘口冷门信号已纳入模型；若强队仍被高估，可能是状态因子（form_factor）对近期热身赛权重不足，或东道主主场加成被中立场削弱。后续可收紧强队下调阈值、提高中下游球队爆冷加成。");
    }
    if (wrongScores.length) {
      lines.push(`比分命中 ${played.length - wrongScores.length} 场。比分预测偏向期望进球附近的保守选择，单边大比分需要球队 open 因子显著上调才会触发。`);
    }
    if (upsets.length) {
      lines.push(`爆冷场次 ${upsets.length} 场，模型已通过全局爆冷校准上调弱队得分基线，但极端冷门仍属低概率事件。`);
    }
    if (!missed.length && !wrongScores.length) {
      lines.push("目前预测与实际赛果高度一致，模型参数保持当前水准。");
    }
    return lines.join("\n");
  }

  /**
   * 运行预测并直接修改内存中的 WC_DATA。
   * @param {Object} options
   * @param {Array} options.schedule WC_DATA.schedule
   * @param {number} options.limit 最多刷新几场未赛（默认 10）
   * @param {Function} options.onProgress (done, total, message)
   * @param {Function} options.onDone (updatedMatches, reviewText)
   * @param {Function} options.onError (message)
   */
  function runPredictions({ schedule, limit = 10, onProgress, onDone, onError } = {}) {
    if (!schedule || !schedule.length) {
      if (onError) onError("没有赛程数据");
      return;
    }

    // 未赛场次：score 为 null/undefined
    const unplayed = schedule.filter(m => m.score === null || m.score === undefined);
    if (!unplayed.length) {
      if (onDone) onDone([], generateReview(schedule));
      return;
    }

    const toUpdate = unplayed.slice(0, limit);
    const results = [];
    let idx = 0;

    function processBatch() {
      const batchSize = 5;
      const end = Math.min(idx + batchSize, toUpdate.length);
      for (let i = idx; i < end; i++) {
        const m = toUpdate[i];
        try {
          const pred = matchProbabilities(m.home, m.away);
          // 保留原 market 数据
          if (m.pred && m.pred.market) pred.market = m.pred.market;
          m.pred = pred;
          results.push({ match: m.match, home: m.home, away: m.away, pred });
        } catch (e) {
          console.error("预测失败", m, e);
        }
      }
      idx = end;
      if (onProgress) onProgress(idx, toUpdate.length, `正在预测第 ${idx}/${toUpdate.length} 场`);
      if (idx < toUpdate.length) {
        setTimeout(processBatch, 0);
      } else {
        const review = generateReview(schedule);
        if (onDone) onDone(results, review);
      }
    }

    processBatch();
  }

  return {
    loadData,
    runPredictions,
    matchProbabilities,
    getTeam,
    generateReview
  };
})();

window.Predictor = Predictor;

/**
 * 全局更新预测入口，供各语言版本 index.html 的按钮调用。
 * 优先调用后端 API 联网拉取最新赛果/赔率并重新计算，
 * API 不可用时降级为纯前端本地计算。
 */
window.updatePredictions = async function () {
  const btn = document.getElementById("update-btn");
  if (!btn) return;

  // 防止重复点击
  if (btn.disabled || btn.classList.contains("busy")) return;

  const D = window.WC_DATA;
  if (!D || !D.schedule) {
    alert("赛程数据未加载");
    return;
  }

  btn.disabled = true;
  btn.classList.add("busy");

  const progressEl = document.getElementById("update-progress");
  const btnLabel = btn.querySelector("span");
  const setProgress = (msg) => {
    if (progressEl) progressEl.textContent = msg;
    if (btnLabel) btnLabel.textContent = msg || "更新预测";
  };

  // ── 尝试调用后端 API 联网刷新（带重试）───────────────────────
  try {
    setProgress("正在连接后端服务...");
    const apiUrl = "/api/refresh";

    // 重试 2 次，每次间隔 1 秒
    let resp = null;
    let lastErr = null;
    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 8000);
        resp = await fetch(apiUrl, {
          method: "POST",
          signal: controller.signal,
          headers: { "Content-Type": "application/json" }
        });
        clearTimeout(timeoutId);
        break;
      } catch (e) {
        lastErr = e;
        if (attempt < 2) {
          setProgress(`连接后端失败，重试中（${attempt + 1}/3）...`);
          await new Promise(r => setTimeout(r, 1500));
        }
      }
    }

    if (!resp) throw lastErr || new Error("无法连接后端");

    if (resp.ok || resp.status === 409) {
      if (resp.status === 409) {
        setProgress("后端正在刷新中，请稍候...");
      } else {
        setProgress("后端联网刷新中（约3~5分钟）...");
      }
      await _pollApiRefresh(() => {
        setProgress("后端正在计算，请稍候...");
      });

      // 拉取最新数据
      const latestResp = await fetch("/api/latest", {
        signal: AbortSignal.timeout(8000)
      });
      if (latestResp.ok) {
        const newData = await latestResp.json();
        // 替换内存中的数据
        Object.assign(window.WC_DATA, newData);

        // 触发页面重渲染
        if (typeof window.renderSchedule === "function") window.renderSchedule();
        if (typeof window.renderReports === "function") window.renderReports();

        setProgress("联网刷新完成（30万次模拟）");
        btn.disabled = false;
        btn.classList.remove("busy");
        return;
      }
    }
    // API 返回非 200 且非 409
    throw new Error("API 返回错误: " + resp.status);
  } catch (e) {
    // API 不可用时，提示用户而不是默默降级
    const useLocal = confirm(
      "后端服务连接失败！\n\n" +
      "请确认程序已启动后再试。\n\n" +
      "点击【确定】使用本地快速计算（仅重新计算比分预测，不更新赛程/赔率，不跑锦标赛模拟）\n" +
      "点击【取消】放弃更新"
    );
    if (!useLocal) {
      btn.disabled = false;
      btn.classList.remove("busy");
      setProgress("已取消");
      return;
    }
    setProgress("本地计算中...");
  }

  // ── 降级：纯前端本地计算 ───────────────────────────────────
  try {
    await Predictor.loadData();
  } catch (e) {
    alert("加载预测数据失败: " + (e && e.message || e));
    btn.disabled = false;
    btn.classList.remove("busy");
    return;
  }

  Predictor.runPredictions({
    schedule: D.schedule,
    limit: 10,
    onProgress: (done, total, msg) => setProgress(msg),
    onDone: (results, review) => {
      setProgress("更新完成，正在重渲染...");
      // 更新元信息
      D.meta.updated_at = new Date().toISOString().replace("T", " ").slice(0, 19);

      // 触发挥程表重新渲染（如果页面提供 renderSchedule）
      if (typeof window.renderSchedule === "function") {
        window.renderSchedule();
      }
      // 触发战报/复盘重新渲染（如果页面提供 renderReports）
      if (typeof window.renderReports === "function") {
        window.renderReports(review);
      }

      setProgress(`已刷新 ${results.length} 场预测`);
      btn.disabled = false;
      btn.classList.remove("busy");

      // 如果页面没有 renderReports，把复盘内容放到控制台
      if (typeof window.renderReports !== "function") {
        console.log("AI 复盘:\n" + review);
      }
    },
    onError: (msg) => {
      alert("更新预测失败: " + msg);
      btn.disabled = false;
      btn.classList.remove("busy");
    }
  });
};

/**
 * 轮询 /api/status，等待后端刷新完成（返回非 refreshing），
 * 最多等待 600 秒（10 分钟）。
 */
async function _pollApiRefresh(onPoll) {
  const start = Date.now();
  while (Date.now() - start < 600_000) {
    await new Promise(r => setTimeout(r, 3000)); // 每 3 秒轮询一次
    try {
      const resp = await fetch("/api/status", {
        signal: AbortSignal.timeout(5000)
      });
      if (resp.ok) {
        const data = await resp.json();
        if (!data.refreshing) return; // 刷新完成
      }
    } catch (_) {}
    if (onPoll) onPoll();
  }
  throw new Error("后端刷新超时");
}
