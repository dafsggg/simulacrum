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
 * 全局更新预测入口
 * 
 * 由于部署在 Cloudflare Pages 上无后端，点击更新后会：
 * 1. 打开 GitHub Actions 手动触发页面
 * 2. 用户点击 Run workflow 触发更新（约10-15分钟）
 * 3. 页面会轮询检查更新状态
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
  const btnLabel = btn.querySelector("span");
  const progressEl = document.getElementById("update-progress");
  const setProgress = (msg) => {
    if (progressEl) progressEl.textContent = msg;
    if (btnLabel) btnLabel.textContent = msg || "更新预测";
  };

  setProgress("正在触发更新...");

  // 尝试通过 Cloudflare Pages Function 触发 GitHub Actions
  try {
    const response = await fetch('/api/refresh', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });

    if (response.ok) {
      const data = await response.json();
      if (data.status === 'success') {
        setProgress("更新已触发！请等待 10-15 分钟...");
        // 开始轮询检查更新状态
        await pollForCompletion(setProgress);
        return;
      }
    }
  } catch (e) {
    console.log('API trigger failed, falling back to manual trigger:', e.message);
  }

  // 降级方案：引导用户手动触发
  setProgress("准备打开更新页面...");
  await new Promise(r => setTimeout(r, 1000));
  
  const githubUrl = 'https://github.com/dafsggg/simulacrum/actions/workflows/auto-update.yml';
  window.open(githubUrl, '_blank');
  
  setProgress("请在 GitHub 页面点击 'Run workflow'，然后返回此处");
  
  // 开始轮询检查是否有新数据
  await pollForManualCompletion(setProgress);
};

/**
 * 轮询检查更新是否完成（自动触发模式）
 */
async function pollForCompletion(setProgress) {
  const maxAttempts = 60; // 最多轮询 10 分钟（每次 10 秒）
  let attempts = 0;
  
  while (attempts < maxAttempts) {
    attempts++;
    setProgress(`正在检查更新进度... (${attempts}/${maxAttempts})`);
    
    try {
      // 检查最新的 workflow run
      const response = await fetch(
        'https://api.github.com/repos/dafsggg/simulacrum/actions/runs?per_page=1',
        {
          headers: { 'Accept': 'application/vnd.github.v3+json' }
        }
      );
      
      if (response.ok) {
        const data = await response.json();
        if (data.workflow_runs && data.workflow_runs.length > 0) {
          const latestRun = data.workflow_runs[0];
          
          if (latestRun.conclusion === 'success') {
            setProgress("更新完成！正在刷新页面...");
            // 延迟 2 秒让用户看到完成消息
            await new Promise(r => setTimeout(r, 2000));
            // 强制刷新页面获取最新数据
            window.location.reload();
            return;
          } else if (latestRun.conclusion === 'failure') {
            setProgress("更新失败，请稍后重试");
            setTimeout(() => {
              location.reload();
            }, 3000);
            return;
          } else if (latestRun.status === 'in_progress' || latestRun.status === 'queued') {
            setProgress(`更新进行中... (${Math.round(attempts/maxAttempts*100)}%)`);
          }
        }
      }
    } catch (e) {
      console.log('Polling error:', e);
    }
    
    await new Promise(r => setTimeout(r, 10000)); // 每 10 秒检查一次
  }
  
  setProgress("更新可能需要更长时间，请手动检查 GitHub Actions");
}

/**
 * 轮询检查更新是否完成（手动触发模式）
 */
async function pollForManualCompletion(setProgress) {
  const maxAttempts = 120; // 最多轮询 20 分钟
  let attempts = 0;
  
  while (attempts < maxAttempts) {
    attempts++;
    setProgress(`等待更新完成... (${Math.round(attempts/maxAttempts*100)}%)`);
    
    try {
      // 获取最新的 workflow run
      const response = await fetch(
        'https://api.github.com/repos/dafsggg/simulacrum/actions/runs?per_page=1',
        {
          headers: { 'Accept': 'application/vnd.github.v3+json' }
        }
      );
      
      if (response.ok) {
        const data = await response.json();
        if (data.workflow_runs && data.workflow_runs.length > 0) {
          const latestRun = data.workflow_runs[0];
          
          if (latestRun.conclusion === 'success') {
            setProgress("更新完成！正在刷新页面...");
            await new Promise(r => setTimeout(r, 2000));
            window.location.reload();
            return;
          } else if (latestRun.conclusion === 'failure') {
            setProgress("更新失败，请查看 GitHub Actions");
            return;
          }
        }
      }
    } catch (e) {
      console.log('Polling error:', e);
    }
    
    await new Promise(r => setTimeout(r, 10000));
  }
  
  setProgress("更新超时，请手动刷新页面或检查 GitHub Actions");
}

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
