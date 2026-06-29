(function () {
  const LANG_KEY = 'cup2026predictor.lang';
  const SUPPORTED = ['en', 'de', 'es', 'pt', 'ru', 'zh'];
  
  // 优先从 localStorage 读取语言，如果没有则从URL路径读取
  let storedLang = localStorage.getItem(LANG_KEY);
  const PATH_LANG = (location.pathname.match(/^\/(de|es|pt|ru|zh)(?:\/|$)/) || [])[1];
  
  // 确定当前语言
  let lang = 'en';
  if (storedLang && SUPPORTED.includes(storedLang)) {
    lang = storedLang;
  } else if (PATH_LANG && SUPPORTED.includes(PATH_LANG)) {
    lang = PATH_LANG;
    localStorage.setItem(LANG_KEY, lang);
  }
  
  // 如果是中文路径，确保 lang 是 'zh'
  if (location.pathname.startsWith('/zh')) {
    lang = 'zh';
    localStorage.setItem(LANG_KEY, 'zh');
  }
  const D = window.WC_DATA || { teams: [] };
  const teamNameMap = {};
  (D.teams || []).forEach(t => {
    if (t.name_zh && t.name_en) teamNameMap[t.name_zh] = t.name_en;
  });

  const reportEn = {
    "两个小时后，阿兹特克将创造一项纪录：史上第一座承办三届世界杯揭幕战的球场（1970、1986、2026）。对手正是 2010 年揭幕战的老熟人南非——那年的 1-1 是世界杯史上最著名的开幕平局之一。十六年攻守易位：墨西哥八场不败、上周 5-1 横扫塞尔维亚，40 岁的奥乔亚还在冲击个人第六届世界杯；南非则四场不胜、近四场只进三球。AI 给东道主 66%，盘口 68%，难得一致。今天上午十点，孙兴慜的第四届世界杯开张，对手是二十年没碰过世界杯的捷克——许克加 1 米 98 的霍里双塔轮番轰炸金玟哉，值得起个早。真正的修罗场在明天：美国队今年四场三负、普利西奇国家队八场球荒，迎面是预选赛掀翻过巴西阿根廷、八场不败的巴拉圭，AI 干脆给了客队更高的胜率（35% 对 34%）；加拿大那边主力中卫邦比托赛季报销、戴维斯刚恢复合练，1986 年以来的首次主场世界杯成色打折。预测从今夜起，开始接受审判。": "In two hours, the Azteca will make history as the first stadium to host three World Cup openers: 1970, 1986, and 2026. The opponent is South Africa, Mexico's familiar 2010 opening-match rival, when a 1-1 draw became one of the tournament's iconic opening results. Sixteen years later the balance looks different: Mexico are unbeaten in eight and just beat Serbia 5-1, while 40-year-old Ochoa is chasing a sixth World Cup. South Africa are winless in four and have scored only three in that span. The model gives the hosts 66%, close to the market at 68%. Later today, Son Heung-min starts his fourth World Cup against a Czech side back after two decades away, with Hlozek and 1.98m Chory testing Kim Min-jae in the air. The real danger spot is tomorrow: the United States have lost three of four this year and Pulisic is eight national-team games without a goal, while Paraguay are unbeaten in eight and have already beaten Brazil and Argentina in qualifying. The model slightly prefers Paraguay, 35% to 34%. Canada's home World Cup is also dented by injuries. From tonight, the predictions start facing the scoreboard.",
    "战报没提的彩蛋：美国和巴拉圭上次世界杯交手是 1930 年，美国 3-0，还诞生了世界杯史上第一个帽子戏法——96 年后这支美国队里可没有帕特诺德。另外，上一次墨西哥和南非在揭幕战相遇，被看好的一方 90 分钟没能赢球；这次被看好的还是墨西哥，只是换了主场。历史不重复，但押韵。": "A footnote the report left out: the United States and Paraguay last met at a World Cup in 1930, a 3-0 U.S. win that produced the tournament's first hat trick. Ninety-six years later, this U.S. team does not have Bert Patenaude. Also, the last time Mexico and South Africa met in an opener, the favored side failed to win in 90 minutes. Mexico are favored again, only this time at home. History does not repeat, but it does rhyme.",
    "凌晨的阿兹特克，AI 收下了世界杯的第一份礼物：赛前给出的最可能比分是 2-0，墨西哥就真踢出了 2-0。但比分纸面下的剧情，比任何预测都精彩——第 9 分钟基尼奥内斯打进本届世界杯第一球；第 67 分钟，劳尔·基梅内斯头球破门：三届世界杯、六场比赛，这是他的世界杯第一球，距离那次几乎致命的颅骨骨折，整整六年。这也是墨西哥八次出战揭幕战的首胜（此前五负两平，2010 年那场平局的对手恰好就是南非）。场面并不温柔：三张红牌创下世界杯揭幕战纪录，南非九人收场；还有 17 岁 240 天的莫拉替补登场，成为墨西哥世界杯史上最年轻出场球员。今天上午十点，韩国对捷克——38/27/35 的硬币局，全小组赛最难猜的开局之一；明晨三点加拿大迎波黑，戴维斯大概率坐板凳；九点美国对巴拉圭，AI 依然站在客队一边。预测战绩板正式开张：胜负、比分双命中，1 中 1。": "At dawn in the Azteca, the model received its first World Cup gift: its most likely pre-match score was 2-0, and Mexico delivered exactly 2-0. The story underneath was better than any forecast. Quinones scored the tournament's first goal in the 9th minute. Raul Jimenez added a header in the 67th: across three World Cups and six matches, it was his first World Cup goal, six years after the skull fracture that nearly ended everything. It was also Mexico's first win in eight World Cup openers. The match was not gentle: three red cards set an opening-match record and South Africa finished with nine players. Mora came on at 17 years and 240 days to become Mexico's youngest World Cup player. Next up: South Korea vs Czechia, a 38/27/35 coin-flip; Canada vs Bosnia, likely with Davies on the bench; and the United States vs Paraguay, where the model still leans toward the visitors. The prediction record opens perfectly: outcome hit, exact score hit, 1 for 1.",
    "泼盆冷水：赛前 2-0 的概率只有 12.3%，第一场就精确命中是运气站在了概率这边，别当成常态——按这个命中率，整届 104 场能中十几场比分就算优秀。另外 AI 算得出 2-0，算不出基梅内斯等了六年的那记头球。这是足球留给人类的部分。": "A cold shower: the pre-match probability of 2-0 was only 12.3%. Hitting the exact score in match one means probability happened to be kind; it is not a promise. Across 104 matches, a dozen exact-score hits would already be strong. The model can calculate 2-0, but it cannot calculate the meaning of the header Jimenez waited six years to score. That part still belongs to football.",
    "瓜达拉哈拉的上午场，剧本写得比预测刁钻。上半场互交白卷后，第 58 分钟捷克队长克雷伊奇用一记长抛掷入禁区后的头球破门——赛前看点里点名的'高空轰炸'套路，真的兑现了，只是兑现了八分钟：第 66 分钟黄仁范禁区里一记轻巧挑射扳平。然后是全场最有戏剧性的一幕：第 69 分钟，6 次射门颗粒无收的孙兴慜被换下，顶替他的吴贤揆第 79 分钟推射绝杀——赛前那个问题'谁给队长搭把手'，答案在替补席上。补时阶段门将金承奎飞身侧扑，保住三分。AI 的对账单：赛前看好韩国胜（38%，标准硬币局）✓；首选比分 2-1（8.6%）也中了——说明一下，比分首选从今天起与胜负判断对齐：看好谁赢，就取其胜局内最可能的比分；旧口径的单一最高比分 1-1（13%）这场并没中，两种算法都摆在这儿。另更正一处数据事故：本期更早的版本误把比赛进行中的滚球盘口当成赛前数据，一度显示过“主胜 47%”——已剔除并修复管线，赛前判断以 38% 为准。两场战绩：胜负全中、比分全中。这场的代价由捷克承担：Elo 被扣走 28 分，出线概率跌到 53%；韩国则涨到 1786，出线 95%，和墨西哥同积 3 分领跑 A 组。今夜凌晨三点，加拿大迎波黑；上午九点，美国对巴拉圭——AI 站客队的那场，要开庭了。": "The morning match in Guadalajara was trickier than the forecast. After a scoreless first half, Czech captain Krejci headed in from a long throw in the 58th minute, exactly the aerial route highlighted before kickoff. It lasted eight minutes: Hwang In-beom equalized with a delicate finish in the 66th. Then came the twist. Son Heung-min, scoreless on six shots, was substituted in the 69th minute; his replacement Oh Hyeon-gyu scored the winner in the 79th. The pre-match question was who would help the captain. The answer was on the bench. Kim Seung-gyu's stoppage-time save sealed the points. Model audit: South Korea were the pre-match pick at 38% in a coin-flip game, and the 2-1 preferred score also hit. From today the preferred score is aligned with the side the model favors; the old single most-likely score, 1-1, did not hit. A data issue was also corrected: an earlier version mixed in live in-play odds as if they were pre-match odds. The locked pre-match call remains 38%. Through two matches, the model is perfect on outcomes and exact scores. Czechia pay the price with a 28-point Elo drop and a qualification chance down to 53%; South Korea rise to 1786 and 95%, level with Mexico on three points atop Group A. Tonight Canada face Bosnia, and the United States face Paraguay in the game where the model backs the visitors.",
    "今天有读者问：怎么老预测 1-1？因为均势局里 1-1 就是数学上最常见的比分——世界杯一百年踢出最多的恰好也是它。AI 对悬殊局照样敢报 2-0（昨天就中了）。另外记一笔：孙兴慜六脚打不进，换他下场的人十分钟内绝杀。足球的剧本作者，从不按身价发戏份。": "A reader asked why the model so often predicts 1-1. In balanced games, 1-1 is mathematically the most common score; across a century of World Cups, it is also the most frequent. In one-sided games the model will still call 2-0, and yesterday it did. Also note: Son took six shots without scoring, then the player who replaced him won the match in ten minutes. Football does not assign drama by salary."
  };

  const blurbEn = {
    "2010 年揭幕战的复刻——那年南非和墨西哥踢成 1-1。十六年后攻守易位：墨西哥八场不败、刚 5-1 血洗塞尔维亚；南非四场不胜、主力左闸莫迪巴刚伤愈归队。彩蛋：40 岁的奥乔亚是两边阵容里唯一同时经历过 2010 和 2026 的人，他在冲自己的第六届世界杯。": "A remake of the 2010 opener, when South Africa and Mexico drew 1-1. Sixteen years later the balance has flipped: Mexico are unbeaten in eight and just beat Serbia 5-1, while South Africa are winless in four and left back Modiba has only just returned from injury. Bonus detail: 40-year-old Ochoa is the only player here who experienced both 2010 and 2026, and he is chasing a sixth World Cup.",
    "捷克二十年来头一次回到世界杯，晋级靠的是门将科瓦日的点球扑救；打法简单粗暴——边翼卫起球，许克和 1 米 98 的霍里双塔抢点，外加定位球。金玟哉的制空直接决定韩国的下限。33 岁的孙兴慜第四次出征，黄喜灿伤愈复出，问题是谁给队长搭把手。": "Czechia return to the World Cup for the first time in two decades after Kovar's penalty save helped them qualify. The approach is direct: wing-back crosses, Hlozek and 1.98m Chory attacking the box, plus set pieces. Kim Min-jae's aerial control sets South Korea's floor. Son Heung-min starts his fourth World Cup at 33 and Hwang Hee-chan is back from injury; the question is who helps the captain.",
    "加拿大 1986 年以来第一次在主场踢世界杯，但伤病不给面子：最稳的中卫邦比托赛季报销，戴维斯腿筋刚恢复合练、大概率板凳待命。波黑的剧本更热血——点球淘汰意大利挤进正赛，40 岁的哲科照样首发冲锋。乔纳森·大卫（国家队 39 球）对老迈防线，是主胜 54% 的主要依据。": "Canada play a home World Cup for the first time since 1986, but injuries hurt the picture: Bombito is out for the season and Davies has only just returned to training. Bosnia's route was pure drama, knocking out Italy on penalties, with 40-year-old Dzeko still leading the line. Jonathan David against an aging defense is the main reason the model gives Canada 54%.",
    "美国今年踢了四场输了三场（德国、葡萄牙、比利时），普利西奇国家队八场球荒；巴拉圭却八场不败，预选赛赢过巴西、阿根廷、乌拉圭，18 轮只丢 14 球。AI 给客队 35% 对主队 34% 不是 bug，是现状。唯一的好消息：巴拉圭核心恩西索肌肉伤，大概率缺席。": "The United States have lost three of four this year and Pulisic is eight national-team games without a goal. Paraguay are unbeaten in eight, beat Brazil, Argentina, and Uruguay in qualifying, and conceded only 14 in 18 rounds. The model giving the visitors 35% to the hosts' 34% is not a bug; it is the current state. The good news: Paraguay star Enciso is likely out with a muscle injury."
  };

  const enExact = Object.assign({}, reportEn, blurbEn, {
    "AI 世界杯预测 2026": "AI World Cup Predictions 2026",
    "AI 世界杯预测 2026：本站用 AI 对美加墨世界杯进行数亿次模拟，提供 48 强实时夺冠概率、\n    104 场逐场比分预测与博彩盘口对照、小组出线形势、每日 AI 战报与预测战绩追踪，\n    每场比赛结束后自动更新。请启用 JavaScript 查看完整交互内容。": "AI World Cup Predictions 2026: this site simulates the 2026 World Cup millions of times, showing live title probabilities, match-by-match score forecasts, group outlooks, daily reports, and prediction tracking. Enable JavaScript to view the full interactive experience.",
    "谁能捧起大力神杯？我们让 AI 把这届世界杯提前\"踢\"了上亿遍。每天根据最新战况重新计算，整个赛事期间持续更新。": "Who will lift the trophy? This site lets the model play the 2026 World Cup millions of times, then recalculates after every update.",
    "夺冠概率榜": "Champion Probability Board",
    "显示全部 48 队 ↓": "Show all 48 teams ↓",
    "收起 ↑": "Collapse ↑",
    "夺冠概率走势": "Champion Probability Trend",
    "每日更新累积": "Snapshots after each update",
    "最可能的决赛对阵": "Most Likely Final Matchups",
    "赛程 · 比分 · 预测": "Schedule · Scores · Predictions",
    "小组形势": "Group Outlook",
    "积分为实际 · 概率为模拟": "Points are actual · probabilities are simulated",
    "AI 战报": "AI Report",
    "随赛况更新 · 全部存档": "Updated with match windows · full archive",
    "预测战绩": "Prediction Record",
    "所有预测都在比赛前生成": "All predictions are generated before kickoff",
    "保存长图分享": "Save share image",
    "总览": "Overview",
    "赛程·预测": "Schedule · Predictions",
    "小组形势": "Groups",
    "AI 战报": "AI Reports",
    "预测战绩": "Record",
    "已赛": "Played",
    "场": "matches",
    "模拟": "Simulations",
    "数亿": "millions",
    "次": "times",
    "更新": "Updated",
    "专业知识库": "Экспертные знания",
    "已融合": "blended",
    "胜负预测命中": "Outcome accuracy",
    "更新于": "Updated",
    "预测仅供娱乐，足球是圆的 ⚽": "Predictions are for entertainment only ⚽",
    "首期战报正在路上": "The first report is on the way",
    "往期战报 →": "Archive →",
    "FABLE 跟评": "FABLE comment",
    "① 头号热门": "① Favorite",
    "② 次席": "② Second favorite",
    "③ 第三热门": "③ Third favorite",
    "夺冠概率 · ELO": "Champion chance · ELO",
    "东道主": "Host",
    "32强": "Round of 32",
    "16强": "Round of 16",
    "8强": "Quarter-final",
    "4强": "Semi-final",
    "决赛": "Final",
    "夺冠": "Champion",
    "市场夺冠赔率": "Market title chance",
    "暂无历史快照": "No history snapshots yet",
    "首日快照 — 每次更新后这里会长出折线": "First snapshot — the line chart grows after each update",
    "全部": "All",
    "小组赛": "Group stage",
    "1/4决赛": "Quarter-final",
    "半决赛": "Semi-final",
    "决赛&季军": "Final & third-place",
    "季军战": "Third-place match",
    "未赛": "Upcoming",
    "今日": "Today",
    "按球队筛选": "Filter by team",
    "选择球队": "Select team",
    "全部球队": "All teams",
    "没有符合条件的比赛": "No matches match these filters",
    "待定": "TBD",
    "平局": "Draw",
    "胜": "win",
    "点球": "Penalties",
    "晋级": "advance",
    "主": "Home",
    "平": "Draw",
    "客": "Away",
    "赛前": "Pre-match",
    "主胜": "Home win",
    "客胜": "Away win",
    "看好": "Pick",
    "防平": "Draw watch",
    "对阵确定后给出预测": "Prediction after matchup is set",
    "胜负命中": "Outcome hit",
    "胜负未中": "Outcome miss",
    "比分命中": "Score hit",
    "比分": "Score",
    "各比分概率": "Score probability grid",
    "行": "rows",
    "列": "columns",
    "AI 怎么看": "AI take",
    "最可能比分 TOP 5": "Top 5 likely scores",
    "晋级概率（含加时/点球）": "Advance probability, including extra time/penalties",
    "蒙特卡洛模拟": "Монте-Карло",
    "家庄家": "books",
    "赛前预测": "Pre-match prediction",
    "首选比分": "Preferred score",
    "实际结果": "Actual result",
    "赛前 AI 给这个比分的概率是": "Pre-match probability for this score",
    "胜负预测未中": "Outcome prediction missed",
    "比分完全命中": "Exact score hit",
    "比分未完全命中": "Exact score missed",
    "战平": "draw",
    "组": "Group",
    "积分 | 出线·头名": "Points | Qualify · group winner",
    "分/": " pts/",
    "赛": "played",
    "还没有完赛场次 — 比赛结束后，这里会逐场展示 AI 的赛前预测与命中情况": "No completed matches yet — after matches finish, pre-match predictions and hit/miss results will appear here.",
    "已预测场次": "Predicted matches",
    "胜平负命中率": "Outcome accuracy",
    "精确比分命中率": "Exact-score accuracy",
    "误差指数 · 越低越好": "Error index · lower is better",
    "生成图片失败：": "Image generation failed: ",
    "长按图片保存，或直接发给朋友": "Long-press to save, or share directly",
    "分享长图": "Share image",
    "脚本加载失败": "Script failed to load",
    "扫码看实时预测 · 仅供娱乐": "Scan for live predictions · entertainment only",
    "AI 世界杯预测": "AI World Cup Predictions"
  });

  const zhExact = {
    "Daily Update · Live": "每日更新 · 实时",
    "AI World Cup Predictions 2026": "AI 世界杯预测 2026",
    "AI World Cup Predictions": "AI 世界杯预测",
    "Who will lift the trophy? This site lets the model play the 2026 World Cup millions of times, then recalculates the title race, match forecasts, groups, and prediction record after every update.": "谁能捧起大力神杯？我们让 AI 把这届世界杯提前\"踢\"了上亿遍。每天根据最新战况重新计算，整个赛事期间持续更新。",
    "Champion Probability Board": "夺冠概率榜",
    "Show all 48 teams ↓": "显示全部 48 队 ↓",
  };


  const LANG_META = {
    en: { html: 'en', og: 'en_US', label: 'English', path: '/', title: 'AI World Cup Predictions 2026 | Live Champion Odds, Scores & Daily Reports', desc: 'AI-powered 2026 World Cup predictions with live champion probabilities, match score forecasts, group qualification outlooks, daily reports, and prediction record tracking.' },
    de: { html: 'de', og: 'de_DE', label: 'Deutsch', path: '/de/', title: 'KI-WM-Prognosen 2026 | Live Titelchancen, Ergebnisse & tägliche Berichte', desc: 'KI-gestützte Prognosen zur WM 2026 mit Live-Titelwahrscheinlichkeiten, Ergebnisvorhersagen, Gruppenaussichten, täglichen Berichten und Prognosebilanz.' },
    es: { html: 'es', og: 'es_ES', label: 'Español', path: '/es/', title: 'Predicciones IA Mundial 2026 | Probabilidades, marcadores e informes diarios', desc: 'Predicciones con IA para el Mundial 2026: probabilidades de campeón en vivo, pronósticos de marcadores, clasificación de grupos, informes diarios y seguimiento de aciertos.' },
    pt: { html: 'pt', og: 'pt_BR', label: 'Português', path: '/pt/', title: 'Previsões IA Copa do Mundo 2026 | Chances, placares e relatórios diários', desc: 'Previsões com IA para a Copa do Mundo 2026 com probabilidades ao vivo de campeão, placares previstos, grupos, relatórios diários e histórico de acertos.' },
    ru: { html: 'ru', og: 'ru_RU', label: 'Русский', path: '/ru/', title: 'ИИ-прогнозы ЧМ-2026 | Шансы на титул, счета и ежедневные отчеты', desc: 'ИИ-прогнозы чемпионата мира 2026: текущие шансы на титул, прогнозы счетов, расклады в группах, ежедневные отчеты и учет точности.' },
    zh: { html: 'zh-CN', og: 'zh_CN', label: '中文', path: '/zh/', title: 'AI 世界杯预测 2026 ｜ 实时夺冠概率 · 比分预测 · 每日 AI 战报', desc: 'AI 世界杯预测 2026：实时夺冠概率、逐场比分预测、小组出线形势、每日 AI 战报与预测战绩追踪。' }
  };
  const HREFS = { en: '/', de: '/de/', es: '/es/', pt: '/pt/', ru: '/ru/', zh: '/zh/' };
  const localeText = {
    de: {'Daily Update · Live':'Tägliches Update · Live','AI World Cup Predictions 2026':'KI-WM-Prognosen 2026','AI World Cup Predictions':'KI-WM-Prognosen','Who will lift the trophy? This site lets the model play the 2026 World Cup millions of times, then recalculates the title race, match forecasts, groups, and prediction record after every update.':'Wer holt den Pokal? Dieses Tool lässt das Modell die WM 2026 millionenfach simulieren und berechnet nach jedem Update Titelrennen, Spielprognosen, Gruppen und Prognosebilanz neu.','Champion Probability Board':'Titelwahrscheinlichkeiten','Show all 48 teams ↓':'Alle 48 Teams anzeigen ↓','Collapse ↑':'Einklappen ↑','Champion Probability Trend':'Trend der Titelchancen','Snapshots after each update':'Snapshots nach jedem Update','Most Likely Final Matchups':'Wahrscheinlichste Finalduelle','Schedule · Scores · Predictions':'Spielplan · Ergebnisse · Prognosen','Groups':'Gruppen','Group Outlook':'Gruppenaussichten','Points are actual · probabilities are simulated':'Punkte real · Wahrscheinlichkeiten simuliert','AI Reports':'KI-Berichte','AI Report':'KI-Bericht','Updated with match windows · full archive':'Aktualisiert nach Spielphasen · Archiv','Record':'Bilanz','Prediction Record':'Prognosebilanz','All predictions are generated before kickoff':'Alle Prognosen entstehen vor Anpfiff','Save share image':'Share-Bild speichern','Overview':'Übersicht','Schedule · Predictions':'Spielplan · Prognosen','Played':'Gespielt','matches':'Spiele','Simulations':'Simulationen','millions':'Millionen','times':'Mal','Updated':'Aktualisiert','Market odds':'Marktquoten','blended':'integriert','Outcome accuracy':'Trefferquote Ergebnis','Predictions are for entertainment only ⚽':'Prognosen nur zur Unterhaltung ⚽','Favorite':'Favorit','Second favorite':'Zweiter Favorit','Third favorite':'Dritter Favorit','Champion chance · ELO':'Titelchance · ELO','Host':'Gastgeber','Round of 32':'Runde der 32','Round of 16':'Achtelfinale','Quarter-final':'Viertelfinale','Semi-final':'Halbfinale','Final':'Finale','Final & third-place':'Finale & Spiel um Platz 3','Champion':'Champion','No history snapshots yet':'Noch keine Verlaufssnapshots','All':'Alle','Group stage':'Gruppenphase','Upcoming':'Ausstehend','Today':'Heute','Filter by team':'Nach Team filtern','Select team':'Team wählen','All teams':'Alle Teams','No matches match these filters':'Keine Spiele für diese Filter','TBD':'Offen','Draw':'Unentschieden','win':'Sieg','Home':'Heim','Away':'Auswärts','Pick':'Tipp','Score probability grid':'Score-Wahrscheinlichkeiten','AI take':'KI-Einschätzung','Top 5 likely scores':'Top 5 wahrscheinlichste Ergebnisse','Betting market':'Wettmarkt','Pre-match prediction':'Vorab-Prognose','Preferred score':'Bevorzugtes Ergebnis','Actual result':'Endergebnis','Exact score hit':'Exakter Score getroffen','Exact score missed':'Exakter Score verfehlt','Predicted matches':'Prognostizierte Spiele','Exact-score accuracy':'Exakte Scorequote','Error index · lower is better':'Fehlerindex · niedriger ist besser','Archive →':'Archiv →','FABLE comment':'FABLE-Kommentar','Share image':'Bild teilen','Long-press to save, or share directly':'Zum Speichern lange drücken oder direkt teilen','Scan for live predictions · entertainment only':'Scannen für Live-Prognosen · nur Unterhaltung','matches played':'gespielte Spiele'},
    es: {'Daily Update · Live':'Actualización diaria · En vivo','AI World Cup Predictions 2026':'Predicciones IA Mundial 2026','AI World Cup Predictions':'Predicciones IA Mundial','Who will lift the trophy? This site lets the model play the 2026 World Cup millions of times, then recalculates the title race, match forecasts, groups, and prediction record after every update.':'¿Quién levantará la copa? Este sitio hace que el modelo simule el Mundial 2026 millones de veces y recalcula la carrera por el título, los pronósticos, los grupos y el historial tras cada actualización.','Champion Probability Board':'Probabilidades de campeón','Show all 48 teams ↓':'Mostrar los 48 equipos ↓','Collapse ↑':'Contraer ↑','Champion Probability Trend':'Tendencia de campeón','Snapshots after each update':'Capturas tras cada actualización','Most Likely Final Matchups':'Finales más probables','Schedule · Scores · Predictions':'Calendario · Marcadores · Predicciones','Groups':'Grupos','Group Outlook':'Panorama de grupos','Points are actual · probabilities are simulated':'Puntos reales · probabilidades simuladas','AI Reports':'Informes IA','AI Report':'Informe IA','Updated with match windows · full archive':'Actualizado por ventanas de partidos · archivo','Record':'Historial','Prediction Record':'Historial de predicciones','All predictions are generated before kickoff':'Todas las predicciones se generan antes del inicio','Save share image':'Guardar imagen para compartir','Overview':'Resumen','Schedule · Predictions':'Calendario · Predicciones','Played':'Jugados','matches':'partidos','Simulations':'Simulaciones','millions':'millones','times':'veces','Updated':'Actualizado','Market odds':'Cuotas de mercado','blended':'integradas','Outcome accuracy':'Acierto de resultado','Predictions are for entertainment only ⚽':'Predicciones solo para entretenimiento ⚽','Favorite':'Favorito','Second favorite':'Segundo favorito','Third favorite':'Tercer favorito','Champion chance · ELO':'Prob. campeón · ELO','Host':'Anfitrión','Round of 32':'Dieciseisavos','Round of 16':'Octavos','Quarter-final':'Cuartos','Semi-final':'Semifinal','Final':'Final','Final & third-place':'Final y tercer puesto','Champion':'Campeón','No history snapshots yet':'Aún no hay histórico','All':'Todos','Group stage':'Fase de grupos','Upcoming':'Pendientes','Today':'Hoy','Filter by team':'Filtrar por equipo','Select team':'Elegir equipo','All teams':'Todos los equipos','No matches match these filters':'No hay partidos con esos filtros','TBD':'Por definir','Draw':'Empate','win':'victoria','Home':'Local','Away':'Visitante','Pick':'Pronóstico','Score probability grid':'Tabla de probabilidad de marcador','AI take':'Lectura IA','Top 5 likely scores':'Top 5 marcadores probables','Betting market':'Mercado de apuestas','Pre-match prediction':'Predicción previa','Preferred score':'Marcador preferido','Actual result':'Resultado real','Exact score hit':'Marcador exacto acertado','Exact score missed':'Marcador exacto fallado','Predicted matches':'Partidos pronosticados','Exact-score accuracy':'Acierto de marcador exacto','Error index · lower is better':'Índice de error · menor es mejor','Archive →':'Archivo →','FABLE comment':'Comentario FABLE','Share image':'Compartir imagen','Long-press to save, or share directly':'Mantén pulsado para guardar o comparte directamente','Scan for live predictions · entertainment only':'Escanea para predicciones en vivo · solo entretenimiento','matches played':'partidos jugados'},
    pt: {'Daily Update · Live':'Atualização diária · Ao vivo','AI World Cup Predictions 2026':'Previsões IA Copa 2026','AI World Cup Predictions':'Previsões IA Copa','Who will lift the trophy? This site lets the model play the 2026 World Cup millions of times, then recalculates the title race, match forecasts, groups, and prediction record after every update.':'Quem levantará a taça? Este site faz o modelo simular a Copa do Mundo de 2026 milhões de vezes e recalcula a disputa pelo título, os palpites, os grupos e o histórico após cada atualização.','Champion Probability Board':'Probabilidades de campeão','Show all 48 teams ↓':'Mostrar as 48 seleções ↓','Collapse ↑':'Recolher ↑','Champion Probability Trend':'Tendência de campeão','Snapshots after each update':'Snapshots após cada atualização','Most Likely Final Matchups':'Finais mais prováveis','Schedule · Scores · Predictions':'Calendário · Placar · Previsões','Groups':'Grupos','Group Outlook':'Panorama dos grupos','Points are actual · probabilities are simulated':'Pontos reais · probabilidades simuladas','AI Reports':'Relatórios IA','AI Report':'Relatório IA','Updated with match windows · full archive':'Atualizado por janelas de jogos · arquivo','Record':'Histórico','Prediction Record':'Histórico de previsões','All predictions are generated before kickoff':'Todas as previsões são geradas antes do início','Save share image':'Salvar imagem para compartilhar','Overview':'Visão geral','Schedule · Predictions':'Calendário · Previsões','Played':'Jogados','matches':'jogos','Simulations':'Simulações','millions':'milhões','times':'vezes','Updated':'Atualizado','Market odds':'Odds do mercado','blended':'integradas','Outcome accuracy':'Acerto de resultado','Predictions are for entertainment only ⚽':'Previsões apenas para entretenimento ⚽','Favorite':'Favorito','Second favorite':'Segundo favorito','Third favorite':'Terceiro favorito','Champion chance · ELO':'Chance de título · ELO','Host':'Anfitrião','Round of 32':'Fase de 32','Round of 16':'Oitavas','Quarter-final':'Quartas','Semi-final':'Semifinal','Final':'Final','Final & third-place':'Final e terceiro lugar','Champion':'Campeão','No history snapshots yet':'Ainda sem histórico','All':'Todos','Group stage':'Fase de grupos','Upcoming':'A disputar','Today':'Hoje','Filter by team':'Filtrar por seleção','Select team':'Escolher seleção','All teams':'Todas as seleções','No matches match these filters':'Nenhum jogo com esses filtros','TBD':'A definir','Draw':'Empate','win':'vitória','Home':'Casa','Away':'Fora','Pick':'Palpite','Score probability grid':'Grade de probabilidade de placar','AI take':'Leitura da IA','Top 5 likely scores':'Top 5 placares prováveis','Betting market':'Mercado de apostas','Pre-match prediction':'Previsão pré-jogo','Preferred score':'Placar preferido','Actual result':'Resultado real','Exact score hit':'Placar exato acertado','Exact score missed':'Placar exato não acertado','Predicted matches':'Jogos previstos','Exact-score accuracy':'Acerto de placar exato','Error index · lower is better':'Índice de erro · menor é melhor','Archive →':'Arquivo →','FABLE comment':'Comentário FABLE','Share image':'Compartilhar imagem','Long-press to save, or share directly':'Pressione para salvar ou compartilhar','Scan for live predictions · entertainment only':'Escaneie para previsões ao vivo · entretenimento','matches played':'jogos disputados'},
    ru: {'Daily Update · Live':'Ежедневное обновление · Live','AI World Cup Predictions 2026':'ИИ-прогнозы ЧМ-2026','AI World Cup Predictions':'ИИ-прогнозы ЧМ','Who will lift the trophy? This site lets the model play the 2026 World Cup millions of times, then recalculates the title race, match forecasts, groups, and prediction record after every update.':'Кто поднимет кубок? Сайт миллионы раз симулирует ЧМ-2026 и после каждого обновления пересчитывает гонку за титул, прогнозы матчей, группы и точность модели.','Champion Probability Board':'Вероятности чемпионства','Show all 48 teams ↓':'Показать все 48 команд ↓','Collapse ↑':'Свернуть ↑','Champion Probability Trend':'Динамика шансов на титул','Snapshots after each update':'Снимки после каждого обновления','Most Likely Final Matchups':'Наиболее вероятные финалы','Schedule · Scores · Predictions':'Расписание · Счета · Прогнозы','Groups':'Группы','Group Outlook':'Расклады в группах','Points are actual · probabilities are simulated':'Очки реальные · вероятности смоделированы','AI Reports':'ИИ-отчеты','AI Report':'ИИ-отчет','Updated with match windows · full archive':'Обновляется по игровым окнам · архив','Record':'Статистика','Prediction Record':'Точность прогнозов','All predictions are generated before kickoff':'Все прогнозы сформированы до стартового свистка','Save share image':'Сохранить изображение','Overview':'Обзор','Schedule · Predictions':'Расписание · Прогнозы','Played':'Сыграно','matches':'матчей','Simulations':'Симуляции','millions':'миллионы','times':'раз','Updated':'Обновлено','Market odds':'Рыночные коэффициенты','blended':'учтены','Outcome accuracy':'Точность исходов','Predictions are for entertainment only ⚽':'Прогнозы только для развлечения ⚽','Favorite':'Фаворит','Second favorite':'Второй фаворит','Third favorite':'Третий фаворит','Champion chance · ELO':'Шанс титула · ELO','Host':'Хозяин','Round of 32':'1/16 финала','Round of 16':'1/8 финала','Quarter-final':'Четвертьфинал','Semi-final':'Полуфинал','Final':'Финал','Final & third-place':'Финал и матч за 3-е место','Champion':'Чемпион','No history snapshots yet':'История пока пуста','All':'Все','Group stage':'Групповой этап','Upcoming':'Предстоящие','Today':'Сегодня','Filter by team':'Фильтр по команде','Select team':'Выбрать команду','All teams':'Все команды','No matches match these filters':'Нет матчей по этим фильтрам','TBD':'Будет определено','Draw':'Ничья','win':'победа','Home':'Хозяева','Away':'Гости','Pick':'Выбор','Score probability grid':'Вероятности счетов','AI take':'Оценка ИИ','Top 5 likely scores':'Топ-5 вероятных счетов','Betting market':'Рынок ставок','Pre-match prediction':'Прогноз до матча','Preferred score':'Предпочтительный счет','Actual result':'Фактический результат','Exact score hit':'Точный счет угадан','Exact score missed':'Точный счет не угадан','Predicted matches':'Матчи с прогнозом','Exact-score accuracy':'Точность счета','Error index · lower is better':'Индекс ошибки · меньше лучше','Archive →':'Архив →','FABLE comment':'Комментарий FABLE','Share image':'Поделиться изображением','Long-press to save, or share directly':'Удерживайте, чтобы сохранить или поделиться','Scan for live predictions · entertainment only':'Сканируйте для live-прогнозов · развлечение','matches played':'сыграно матчей'}
  };
  function buildLocaleMap(code) {
    if (code === 'en') return enExact;
    if (code === 'zh') return zhExact;
    const target = localeText[code] || {};
    const out = {};
    Object.entries(enExact).forEach(([zhText, enText]) => { out[zhText] = target[enText] || enText; });
    Object.entries(target).forEach(([enText, locText]) => { out[enText] = locText; });
    return out;
  }
  function setHeadMeta() {
    const meta = LANG_META[lang] || LANG_META.en;
    const abs = 'https://cup2026predictor.com' + meta.path;
    document.documentElement.lang = meta.html;
    document.title = meta.title;
    const set = (sel, val, attr='content') => { const el = document.querySelector(sel); if (el) el.setAttribute(attr, val); };
    set('meta[name="description"]', meta.desc);
    set('meta[property="og:title"]', meta.title);
    set('meta[property="og:description"]', meta.desc);
    set('meta[property="og:url"]', abs);
    set('meta[property="og:locale"]', meta.og);
    set('meta[name="twitter:title"]', meta.title);
    set('meta[name="twitter:description"]', meta.desc);
    set('link[rel="canonical"]', abs, 'href');
    Object.entries({en:'en',de:'de',es:'es',pt:'pt',ru:'ru',zh:'zh-CN'}).forEach(([code,hreflang]) => {
      let el = document.querySelector(`link[rel="alternate"][hreflang="${hreflang}"]`);
      if (!el) { el = document.createElement('link'); el.rel = 'alternate'; el.hreflang = hreflang; document.head.appendChild(el); }
      el.href = 'https://cup2026predictor.com' + HREFS[code];
    });
    let xd = document.querySelector('link[rel="alternate"][hreflang="x-default"]');
    if (!xd) { xd = document.createElement('link'); xd.rel = 'alternate'; xd.hreflang = 'x-default'; document.head.appendChild(xd); }
    xd.href = 'https://cup2026predictor.com/';
  }

  function replaceAllText(text, map) {
    let out = text;
    // Sort by key length descending to match longer strings first
    const sortedEntries = Object.entries(map).sort((a, b) => b[0].length - a[0].length);
    
    // For Chinese-to-English translation (lang === 'en')
    if (lang === 'en') {
      sortedEntries.forEach(([from, to]) => {
        // Use global replace for all matches
        const regex = new RegExp(from.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g');
        out = out.replace(regex, to);
      });
    } 
    // For non-Chinese, non-English languages
    else if (lang !== 'zh') {
      // First translate Chinese to English
      sortedEntries.forEach(([from, to]) => {
        if (typeof from === 'string' && from.length > 20) {
          // Long text (reports/comments) - exact match
          out = out.split(from).join(to);
        } else if (/^[A-Za-z][A-Za-z\s·-]{0,12}$/.test(from)) {
          // Short text (UI elements) - word boundary match
          const escFrom = from.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
          out = out.replace(new RegExp(`(?<![A-Za-z])${escFrom}(?![A-Za-z])`, 'g'), to);
        }
      });
      
      // Then translate English to target language for UI elements
      const target = localeText[lang] || {};
      Object.entries(target).forEach(([enText, locText]) => {
        out = out.split(enText).join(locText);
      });
      
      // Team name translation (Chinese to English)
      Object.entries(teamNameMap).sort((a, b) => b[0].length - a[0].length).forEach(([zh, en]) => {
        out = out.split(zh).join(en);
      });
      
      // Date/format conversion
      out = out
        .replace(/第\s*(\d+)\s*期/g, 'Issue $1')
        .replace(/已赛\s*(\d+)\s*场/g, '$1 matches played')
        .replace(/第(\d+)轮/g, 'Round $1')
        .replace(/([A-L])组/g, 'Group $1')
        .replace(/小组第三\(([^)]*)\)/g, 'Best third ($1)')
        .replace(/组第(一|二)/g, (_, n) => n === '一' ? ' group winner' : ' group runner-up')
        .replace(/([A-L])Group/g, 'Group $1')
        .replace(/Group ([A-L])第一/g, 'Group $1 winner')
        .replace(/Group ([A-L])第二/g, 'Group $1 runner-up')
        .replace(/小Group第三\(([^)]*)\)/g, 'Best third ($1)')
        .replace(/(\d{1,2})月(\d{1,2})日(?:星期|周)([一二三四五六日天])/g, (_, m, d, w) => {
          const wd = {一:'Monday',二:'Tuesday',三:'Wednesday',四:'Thursday',五:'Friday',六:'Saturday',日:'Sunday',天:'Sunday'}[w] || '';
          const month = ['','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][Number(m)] || m;
          return `${wd}, ${month} ${Number(d)}`;
        })
        .replace(/(\d+)分\/(\d+)赛/g, '$1 pts/$2 played')
        .replace(/(\d+) 分\/(\d+)赛/g, '$1 pts/$2 played')
        .replace(/（点球 ([^)]+) 晋级）/g, ' (penalties: $1 advance)')
        .replace(/(.+) 胜/g, '$1 win');
    }
    // For Chinese (lang === 'zh'), translate English to Chinese using zhExact
    else if (lang === 'zh') {
      sortedEntries.forEach(([from, to]) => {
        // Use global replace for all matches (from is English, to is Chinese)
        const regex = new RegExp(from.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g');
        out = out.replace(regex, to);
      });
    }
    return out;
  }

  function applyLang() {
    const isEn = lang === 'en';
    setHeadMeta();
    const btn = document.getElementById('lang-toggle');
    const menu = document.getElementById('lang-menu');
    const options = document.querySelectorAll('.lang-option[data-lang]');
    if (btn) {
      if (btn.tagName === 'SELECT') {
        btn.value = lang;
        btn.onchange = () => { localStorage.setItem(LANG_KEY, btn.value); location.href = HREFS[btn.value] + location.hash; };
      } else {
        btn.textContent = LANG_META[lang].label;
        btn.setAttribute('aria-label', 'Switch language');
        btn.setAttribute('aria-expanded', menu && menu.classList.contains('open') ? 'true' : 'false');
        if (!btn.dataset.bound) {
          const closeMenu = () => {
            if (!menu) return;
            menu.classList.remove('open');
            btn.setAttribute('aria-expanded', 'false');
          };
          const toggleMenu = () => {
            if (!menu) return;
            const open = !menu.classList.contains('open');
            menu.classList.toggle('open', open);
            btn.setAttribute('aria-expanded', open ? 'true' : 'false');
          };
          btn.addEventListener('click', e => { e.stopPropagation(); toggleMenu(); });
          document.addEventListener('click', e => { if (menu && !menu.contains(e.target)) closeMenu(); });
          document.addEventListener('keydown', e => { if (e.key === 'Escape') closeMenu(); });
          btn.dataset.bound = '1';
        }
      }
      options.forEach(opt => {
        const code = opt.dataset.lang;
        opt.classList.toggle('active', code === lang);
        opt.setAttribute('aria-selected', code === lang ? 'true' : 'false');
        if (!opt.dataset.bound) {
          opt.addEventListener('click', e => {
            e.stopPropagation();
            localStorage.setItem(LANG_KEY, code);
            location.href = HREFS[code] + location.hash;
          });
          opt.dataset.bound = '1';
        }
      });
    }
    if (isEn) {
      const chips = document.querySelectorAll('#meta-chips .chip');
      if (chips[1] && D.meta && D.meta.sims) {
        const simsHtml = `<b>${Number(D.meta.sims).toLocaleString()}</b> simulations`;
        if (chips[1].innerHTML !== simsHtml) chips[1].innerHTML = simsHtml;
      }
    }
    
    // 如果当前显示的是赛程页面，重新渲染筛选按钮
    const scheduleTab = document.getElementById('tab-schedule');
    if (scheduleTab && scheduleTab.classList.contains('active')) {
      if (typeof refreshScheduleUI === 'function') {
        setTimeout(refreshScheduleUI, 50);
      }
    }
    
    const map = buildLocaleMap(lang);
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
      acceptNode(node) {
        const p = node.parentElement;
        if (!p || ['SCRIPT', 'STYLE', 'NOSCRIPT', 'SVG', 'PATH'].includes(p.tagName)) return NodeFilter.FILTER_REJECT;
        return node.nodeValue.trim() ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
      }
    });
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach(n => {
      const next = replaceAllText(n.nodeValue, map);
      if (next !== n.nodeValue) n.nodeValue = next;
    });
    document.querySelectorAll('[title],[aria-label],[alt]').forEach(el => {
      ['title', 'aria-label', 'alt'].forEach(attr => {
        if (el.hasAttribute(attr)) el.setAttribute(attr, replaceAllText(el.getAttribute(attr), map));
      });
    });
  }

  let scheduled = false;
  function scheduleApply() {
    if (scheduled) return;
    scheduled = true;
    setTimeout(() => { scheduled = false; applyLang(); }, 0);
  }

  applyLang();
  if (lang === 'en') {
    document.addEventListener('click', scheduleApply, true);
    window.addEventListener('hashchange', scheduleApply);
  }
  
  // 暴露 applyLang 给外部调用
  window.i18nApplyLang = applyLang;
})();
