"""知识库加载器：解析球队状态与战术分析文档，结构化输出供预测模型使用。

核心设计：
1. TXT 文件 → 球队知识库（结构化数据：战绩、进球、战术等）
2. 其他文件（DOCX/EPUB）→ 庄家思维知识库（欧赔、亚盘、投注策略等 LLM 分析素材）

使用方式：
    from src.knowledge_loader import get_loader
    loader = get_loader()

    # 查询球队数据
    team_data = loader.get_team_data("ESP")

    # 查询庄家思维知识库（全文搜索）
    odds_info = loader.search_odds_knowledge("欧赔 亚盘", limit=5)

    # 获取所有已加载的球队
    teams = loader.get_all_team_names()

    # 获取庄家思维知识库摘要
    odds_summary = loader.get_odds_knowledge_summary()
"""

from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

# 修复 Windows GBK 编码问题
if hasattr(sys.stdout, "buffer"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


from ._paths import ROOT
KNOWLEDGE_DIR = ROOT / "knowledge"


class KnowledgeLoader:
    """双知识库加载器：球队知识库 + 庄家思维知识库。

    扩展（2026-06）：
    - EPUB/DOCX 不再只是 LLM 素材，也会提取结构化信号
    - _all_extracted_text.txt 会扫描球队名，做盘口/战术信号提取
    - get_prediction_boost 返回值新增若干字段参与数学预测
    """

    def __init__(self):
        self._team_cache: dict[str, dict] | None = None
        self._odds_full_text: str = ""
        self._odds_sources: list[dict[str, str]] = []
        self._bookmaker_signals: dict[str, dict] | None = None
        self._calibration: dict[str, float] | None = None

    # ------------------------------------------------------------------ #
    # 公共属性
    # ------------------------------------------------------------------ #
    @property
    def team_cache(self) -> dict[str, dict]:
        """懒加载球队知识库。"""
        if self._team_cache is None:
            self._load_team_knowledge()
        return self._team_cache  # type: ignore[return-value]

    @property
    def odds_full_text(self) -> str:
        """懒加载庄家思维全文知识库。"""
        if not self._odds_full_text:
            self._load_odds_knowledge()
        return self._odds_full_text

    @property
    def odds_sources(self) -> list[dict[str, str]]:
        """庄家思维知识库的来源文件信息。"""
        if not self._odds_full_text:
            self._load_odds_knowledge()
        return self._odds_sources

    # ------------------------------------------------------------------ #
    # 加载入口
    # ------------------------------------------------------------------ #
    def _load_team_knowledge(self) -> None:
        """从指定的球队状态分析 TXT 文件加载球队知识库。"""
        self._team_cache = {}
        # 只读取指定的球队分析文件，不扫描整个目录
        target_file = KNOWLEDGE_DIR / "2026_美加墨世界杯各球队状态与战术分析_完整版.txt"
        if not target_file.exists():
            self._log("warn", "[球队知识库] 未找到目标文件: %s" % target_file.name)
            return
        try:
            text = target_file.read_text(encoding="utf-8", errors="replace")
            if not text.strip():
                self._log("warn", "[球队知识库] 文件为空: %s" % target_file.name)
                return
            # 清理 Markdown 转义：反斜杠 + 标点 组合（如 2\.4 -> 2.4，1\-1 -> 1-1）
            text = re.sub(r'\\([0-9.+\-])', r'\1', text)
            parsed = self._parse_txt(text)
            self._team_cache = parsed
            self._log("info", "[球队知识库] OK: %s -> %d 队 (%d keys)" % (
                target_file.name, len(parsed), len(self._team_cache)))
        except Exception as exc:
            self._log("error", "[球队知识库] 解析失败: %s" % exc)


    def _load_odds_knowledge(self) -> None:
        """从 DOCX/EPUB + _all_extracted_text.txt 加载庄家思维全文与结构化信号。"""
        self._odds_full_text = ""
        self._odds_sources = []
        files = self._find_non_txt_files()

        for fp in files:
            try:
                ext = fp.suffix.lower()
                if ext == ".docx" and HAS_BS4:
                    text = self._extract_docx_text(fp)
                elif ext == ".epub" and HAS_BS4:
                    text = self._extract_epub_text(fp)
                else:
                    text = fp.read_text(encoding="utf-8", errors="replace")

                if text and len(text.strip()) > 100:
                    self._odds_sources.append({
                        "file": fp.name,
                        "size": len(text),
                    })
                    self._odds_full_text += "\n\n===== 来源: %s =====\n%s\n" % (fp.name, text)
                    self._log("info", "[庄家思维] OK: %s (%d chars)" % (fp.name[:50], len(text)))
                else:
                    self._log("info", "[庄家思维] SKIP: %s (too short: %d chars)" % (fp.name[:50], len(text)))
            except Exception as exc:
                self._log("error", "[庄家思维] FAIL: %s: %s" % (fp.name, exc))

        # 额外处理 _all_extracted_text.txt
        extra_txt = KNOWLEDGE_DIR / "_all_extracted_text.txt"
        if extra_txt.exists():
            try:
                text = extra_txt.read_text(encoding="utf-8", errors="replace")
                if text and len(text.strip()) > 100:
                    self._odds_sources.append({
                        "file": extra_txt.name,
                        "size": len(text),
                    })
                    self._odds_full_text += "\n\n===== 来源: %s =====\n%s\n" % (extra_txt.name, text)
                    self._log("info", "[庄家思维] OK: %s (%d chars)" % (extra_txt.name, len(text)))
            except Exception as exc:
                self._log("error", "[庄家思维] FAIL: %s: %s" % (extra_txt.name, exc))

        # 结构化信号提取
        self._extract_structured_signals()

    def _extract_structured_signals(self) -> None:
        """从全文中扫描结构化信号。

        注意：球队数据仅来自 `2026_美加墨世界杯各球队状态与战术分析_完整版.txt`（
        由 _parse_txt 处理），本方法不做球队名扫描。
        本方法仅从 EPUB/DOCX 提取全局盘口/战术原则，用作整体预测校准。
        """
        text = self._odds_full_text

        # ---- 全局盘口/战术原则：扫描全文做粗粒度统计 ----
        cal = {
            "book_home_bias": 0.0,          # 主场/东道主 被强调 → 主场加成
            "book_upset_emphasis": 0.0,     # 冷门/爆冷 被强调 → 爆冷概率上浮
            "book_draw_emphasis": 0.0,      # 平局/小球 被强调 → 平局概率上浮
            "book_strong_team_caution": 0.0,# 强队不稳/大热必死 → 强队 Elo 额外下调
            "book_total_goals_calibration": 1.0,  # 大球/小球倾向 → 总进球期望调整
        }

        home_kw = ["主场", "东道主", "主场优势", "主场作战", "球迷", "主场不败",
                   "主场龙", "客场虫", "主客场"]
        upset_kw = ["冷门", "爆冷", "弱队", "以弱胜强", "逆袭", "逆转", "意外",
                    "大热必死", "冷门温床", "反败为胜", "容易出冷", "打平就出线",
                    "战意", "默契球", "假球"]
        draw_kw = ["平局", "1-1", "0-0", "小球", "闷平", "战平", "平局多",
                   "打平出线", "双方各取1分", "谨慎", "保守"]
        strong_caution_kw = ["强队不稳", "强队未必", "强队不一定", "大热",
                             "未必赢", "热门不胜", "强队不一定强", "弱队不一定弱",
                             "豪门未必", "传统强队未必", "强队不一定",
                             "卫冕冠军魔咒", "小组赛慢热", "淘汰赛失常"]
        goals_kw_high = ["大球", "进球大战", "3-1", "2-2", "3-2", "高比分",
                         "进球多", "攻势足球", "对攻", "攻防转换快",
                         "开放比赛", "双方都进球", "至少2球"]
        goals_kw_low = ["小球", "0-0", "1-0", "低比分", "保守", "防守型",
                        "零封", "铁桶阵", "密集防守", "摆大巴",
                        "务实", "实用主义", "控制节奏", "死守"]

        for w in home_kw:
            count = text.count(w)
            if count > 0:
                cal["book_home_bias"] += min(count * 0.05, 0.40)
        for w in upset_kw:
            count = text.count(w)
            if count > 0:
                cal["book_upset_emphasis"] += min(count * 0.08, 0.50)
        for w in draw_kw:
            count = text.count(w)
            if count > 0:
                cal["book_draw_emphasis"] += min(count * 0.06, 0.40)
        for w in strong_caution_kw:
            count = text.count(w)
            if count > 0:
                cal["book_strong_team_caution"] += min(count * 0.10, 0.50)

        high_count = sum(text.count(w) for w in goals_kw_high)
        low_count = sum(text.count(w) for w in goals_kw_low)
        if high_count + low_count > 0:
            ratio = high_count / max(high_count + low_count, 1)
            cal["book_total_goals_calibration"] = round(0.70 + ratio * 0.6, 3)
        else:
            cal["book_total_goals_calibration"] = 1.0

        # 限制范围（增大到能产生明显影响）
        for k in cal:
            if k == "book_total_goals_calibration":
                cal[k] = round(max(0.75, min(1.35, cal[k])), 3)
            else:
                cal[k] = round(min(0.50, cal[k]), 3)

        self._bookmaker_signals = {}  # 不做球队级信号（球队数据仅来自 TXT）
        self._calibration = cal

        self._log("info", "[庄家思维] 全局校准: %s" % json.dumps(cal, ensure_ascii=False))
    # ------------------------------------------------------------------ #
    # 文件查找
    # ------------------------------------------------------------------ #
    def _find_non_txt_files(self) -> list[Path]:
        """查找知识库中非 TXT 的文件（DOCX、EPUB）。"""
        docx = sorted(list(KNOWLEDGE_DIR.glob("*.docx")), key=lambda p: p.name)
        epub = sorted(list(KNOWLEDGE_DIR.glob("*.epub")), key=lambda p: p.name)
        return docx + epub

    def _log(self, level, msg):
        """安全的日志输出：将所有非 ASCII 字符替换为 ?。"""
        try:
            safe = "".join(c if ord(c) < 128 else "?" for c in msg)
            print(safe, flush=True)
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # TXT 解析 → 球队知识库
    # ------------------------------------------------------------------ #
    def _parse_txt(self, text: str) -> dict[str, dict]:
        """解析球队状态分析文本，提取结构化数据。"""
        teams: dict[str, dict] = {}
        current_team = None
        current_data = {}

        lines = text.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i].strip()

            if not line:
                i += 1
                continue
            if re.match(r'^[一二三四五六七八九十]+、', line):
                i += 1
                continue

            # 检测球队标题
            team_match = re.match(r'^[\d]+[\.）][ ]*(.+)$', line)
            if team_match and not line.startswith('-'):
                if current_team:
                    teams[current_team] = current_data
                current_team = team_match.group(1).strip()
                current_data = {}
                i += 1
                continue

            # 检测属性行
            attr_match = re.match(r'^-[ ]*(.+?)[：:](.*)$', line)
            if attr_match and current_team:
                attr_name = attr_match.group(1).strip()
                attr_value = attr_match.group(2).strip()
                current_data[attr_name] = attr_value
                i += 1
                continue

            i += 1

        if current_team:
            teams[current_team] = current_data

        # 映射中文名到代码
        code_map = self._build_code_map()
        mapped = {}
        for cn_name, data in teams.items():
            code = code_map.get(cn_name)
            if code:
                mapped[code] = self._extract_stats(data)
                mapped[cn_name] = mapped[code]
            else:
                mapped[cn_name] = data

        return mapped

    def _build_code_map(self) -> dict[str, str]:
        """从 teams.json 构建中文名→代码的映射。"""
        teams_path = ROOT / "data" / "teams.json"
        if not teams_path.exists():
            return {}
        try:
            data = json.loads(teams_path.read_text(encoding="utf-8"))
            mapping = {}
            for t in data.get("teams", []):
                mapping[t.get("name_zh", "")] = t.get("code", "")
                mapping[t.get("name_en", "")] = t.get("code", "")
            return mapping
        except Exception:
            return {}

    def _extract_stats(self, data: dict[str, str]) -> dict[str, Any]:
        """从文本描述中提取数值化统计 + 战术风格 + 爆冷信号。"""
        result = {}
        status_text = data.get("近 10 场状态", "")

        wdl = re.search(r'([0-9]+)\s*胜\s*([0-9]*)\s*平\s*([0-9]*)\s*负', status_text)
        if wdl:
            wins = int(wdl.group(1))
            draws = int(wdl.group(2) or 0)
            losses = int(wdl.group(3) or 0)
            total = wins + draws + losses
            result["wins"] = wins
            result["draws"] = draws
            result["losses"] = losses
            result["total"] = total
            result["win_rate"] = wins / max(total, 1)

        m = re.search(r'场均进球\s*([0-9.]+)', status_text)
        if m:
            result["avg_scored"] = float(m.group(1))

        m = re.search(r'场均失球\s*([0-9.]+)', status_text)
        if m:
            result["avg_conceded"] = float(m.group(1))

        result["tactics"] = data.get("战术特点", "")
        result["strengths"] = data.get("优势", "")
        result["weaknesses"] = data.get("劣势", "")

        # ---- 战术风格 → open 因子：1.0 为中性，>1.0 偏对攻，<1.0 偏保守 ----
        tactics_text = (data.get("战术特点", "") + " " +
                        data.get("优势", "") + " " +
                        data.get("劣势", "") + " " +
                        status_text).lower()

        open_score = 1.0
        if any(k in tactics_text for k in ["攻势足球", "对攻", "边路爆破", "进攻手段丰富",
                                            "高位逼抢", "攻防转换速度快", "狂轰", "进攻端火力全开"]):
            open_score += 0.18
        if any(k in tactics_text for k in ["密集防守", "铁桶阵", "低位防守", "大巴防守",
                                            "防守反击", "收缩阵型", "低控球高转化"]):
            open_score -= 0.15
        if any(k in tactics_text for k in ["控球压迫", "传控", "短传渗透", "层层推进"]):
            open_score += 0.05  # 传控型球队未必大比分，但有持续进攻压制
        if any(k in tactics_text for k in ["阵地战攻坚不足", "破密集防守办法不多",
                                            "锋线终结效率低", "进攻手段单一"]):
            open_score -= 0.08  # 进攻偏弱的队对总进球有压制
        if any(k in tactics_text for k in ["防守硬度高", "防守纪律性强", "防守体系顶级",
                                            "零封能力强"]):
            open_score -= 0.05  # 强防守压低对手进球

        result["style_open"] = round(max(0.70, min(1.40, open_score)), 3)

        # ---- "遇强不弱"爆冷信号：从近 10 场状态描述中检测 ----
        giant_killer = 0.0
        if any(k in status_text for k in ["击败英格兰", "击败比利时", "击败巴西",
                                            "击败德国", "击败法国", "击败西班牙",
                                            "击败葡萄牙", "击败阿根廷", "击败荷兰",
                                            "击败意大利"]):
            giant_killer += 0.15
        if any(k in status_text for k in ["逼平西班牙", "逼平英格兰", "逼平法国",
                                            "逼平巴西", "逼平阿根廷", "逼平荷兰",
                                            "逼平德国", "逼平比利时", "逼平葡萄牙"]):
            giant_killer += 0.10
        if any(k in status_text for k in ["两度落后两度扳平", "逆转", "补时绝平"]):
            giant_killer += 0.08
        if "遇强不弱" in tactics_text:
            giant_killer += 0.12
        result["giant_killer"] = round(min(0.30, giant_killer), 3)

        # ---- "强队不稳"信号：顶级强队但近期有明显弱点/被爆冷 ----
        strong_but_weak = 0.0
        if any(k in status_text for k in ["负于阿尔及利亚", "被日本逼平", "被伊拉克逼平",
                                            "被沙特逼平", "被卡塔尔逼平", "负于科特迪瓦",
                                            "热身赛状态低迷", "负于巴西，比利时"]):
            strong_but_weak += 0.12
        if any(k in tactics_text for k in ["大赛关键战心理素质存疑", "阵容老化",
                                            "体能存隐患", "防守稳定性差", "容易被反击打穿"]):
            strong_but_weak += 0.08
        result["strong_but_weak"] = round(min(0.25, strong_but_weak), 3)

        # ---- 防守强度信号（从近 10 场状态中挖掘"防守特别强"的队）----
        defensive_strength = 1.0
        if "零失球" in status_text or "仅失 1 球" in status_text or "仅丢 1 球" in status_text:
            defensive_strength = 1.30
        elif "防守端创造纪录" in status_text or "仅丢 2 分" in status_text:
            defensive_strength = 1.25
        elif "防守体系顶级" in tactics_text:
            defensive_strength = 1.15
        result["defensive_strength"] = round(defensive_strength, 3)

        return result

    # ------------------------------------------------------------------ #
    # DOCX 文本提取
    # ------------------------------------------------------------------ #
    def _extract_docx_text(self, file_path: Path) -> str:
        """从 DOCX 文件中提取全部文本。"""
        try:
            with zipfile.ZipFile(file_path, 'r') as z:
                xml = z.read('word/document.xml').decode('utf-8', errors='replace')
                soup = BeautifulSoup(xml, 'xml')
                texts = soup.find_all('w:t')
                return ''.join(t.string for t in texts if t.string)
        except Exception as exc:
            self._log("error", "    DOCX 提取失败 %s: %s" % (file_path.name, exc))
            return ""

    # ------------------------------------------------------------------ #
    # EPUB 文本提取
    # ------------------------------------------------------------------ #
    def _extract_epub_text(self, file_path: Path) -> str:
        """从 EPUB 文件中提取全部文本（跳过图片路径和 JSON 元数据）。"""
        try:
            with zipfile.ZipFile(file_path, 'r') as z:
                names = z.namelist()
                text_parts = []

                for name in names:
                    if not (name.endswith('.xhtml') or name.endswith('.html')):
                        continue
                    if any(kw in name for kw in ('toc', 'cover', 'nav', 'titlepage')):
                        continue
                    try:
                        raw = z.read(name).decode('utf-8', errors='replace')
                        soup = BeautifulSoup(raw, 'html.parser')
                        for tag in soup(['script', 'style']):
                            tag.decompose()
                        t = soup.get_text(separator='\n', strip=True)
                        clean_lines = []
                        skip_json_block = False
                        for line in t.splitlines():
                            line = line.strip()
                            if not line:
                                continue
                            # 跳过 JSON 元数据块
                            if line.startswith('{') and ('"filename"' in line or '"pdg"' in line.lower()):
                                skip_json_block = True
                                continue
                            if skip_json_block:
                                if '}' in line:
                                    skip_json_block = False
                                continue
                            # 跳过图片路径
                            if re.match(r'^[\u4e00-\u9fff\w.()%\-/]+\.(pdg|jpg|png|jpeg)$', line):
                                continue
                            if '.jpg' in line or '.png' in line or '.jpeg' in line:
                                continue
                            clean_lines.append(line)
                        if clean_lines:
                            text_parts.append('\n'.join(clean_lines))
                    except Exception:
                        continue

                return '\n\n'.join(text_parts)
        except Exception as exc:
            self._log("error", "    EPUB 提取失败 %s: %s" % (file_path.name, exc))
            return ""

    # ------------------------------------------------------------------ #
    # 查询接口
    # ------------------------------------------------------------------ #
    def get_team_data(self, code_or_name: str) -> dict[str, Any] | None:
        """根据球队代码或中文名获取球队知识库数据。"""
        data = self.team_cache
        if code_or_name in data:
            return data[code_or_name]
        code_map = self._build_code_map()
        if code_or_name in code_map:
            code = code_map[code_or_name]
            if code in data:
                return data[code]
        return None

    def get_all_team_names(self) -> list[str]:
        """返回球队知识库中的所有球队名称。"""
        return list(self.team_cache.keys())

    def get_prediction_boost(self, code: str) -> dict[str, float] | None:
        """为预测模型提供状态修正因子。

        融合了两部分信号：
        (a) TXT 球队知识库：胜率/场均进球/场均失球/战术风格 等
        (b) EPUB/DOCX 庄家思维：文中对该队的正面/负面/爆冷/战术 描述

        只要能从任一知识库提取到信号就返回字典，即使缺少数值统计。
        """
        data = self.get_team_data(code)

        # 读取结构化的庄家思维信号（EPUB/DOCX 派生）
        book_sig = None
        if self._bookmaker_signals is not None:
            book_sig = self._bookmaker_signals.get(code)

        # 没有任何信号 → 返回 None
        if not data and not book_sig:
            return None

        # ---- (a) TXT 部分 ----
        avg_scored = data.get("avg_scored") if data else None
        avg_conceded = data.get("avg_conceded") if data else None

        if avg_scored is not None:
            attack_factor = min(max(avg_scored / 1.5, 0.85), 1.25)
        else:
            attack_factor = 1.0

        if avg_conceded is not None:
            defense_factor = min(max(1.0 / max(avg_conceded, 0.3), 0.75), 1.35)
        else:
            defense_factor = 1.0

        if data and data.get("win_rate"):
            form = data["win_rate"] / 0.5
            form = min(max(form, 0.8), 1.3)
        else:
            form = 1.0

        style_open = data.get("style_open", 1.0) if data else 1.0
        giant_killer = data.get("giant_killer", 0.0) if data else 0.0
        strong_but_weak = data.get("strong_but_weak", 0.0) if data else 0.0
        defensive_strength = data.get("defensive_strength", 1.0) if data else 1.0

        # ---- (b) EPUB/DOCX 部分：与 TXT 合并 ----
        # book 信号用于：修正 Elo（negative/positive/upset_risk）
        # 以及修正风格开放度（tactical_attack / tactical_defense）
        # 以及平局倾向（draw_bias）
        book_negative = book_sig.get("negative", 0.0) if book_sig else 0.0
        book_positive = book_sig.get("positive", 0.0) if book_sig else 0.0
        book_upset = book_sig.get("upset_risk", 0.0) if book_sig else 0.0
        book_attack = book_sig.get("tactical_attack", 0.0) if book_sig else 0.0
        book_defense = book_sig.get("tactical_defense", 0.0) if book_sig else 0.0
        book_draw = book_sig.get("draw_bias", 0.0) if book_sig else 0.0

        # 综合修正：TXT 为主（权重 0.7），book 为辅（权重 0.3）
        # strong_but_weak 综合：TXT strong_but_weak + book negative - book positive
        book_strong_weak = max(0.0, book_negative - book_positive * 0.5)
        # giant_killer 综合：TXT giant_killer + book upset
        book_giant_killer = book_upset

        # 防守强度修正：book_defense 暗示该队被多次描述为防守型/稳健
        book_defensive_strength = 1.0 + book_defense * 0.5
        # 进攻强度修正
        book_attack_open = 1.0 + book_attack * 0.5
        # 平局倾向
        book_draw_bias = book_draw

        # 合并
        merged_strong_but_weak = round(min(0.30, strong_but_weak * 0.6 + book_strong_weak * 0.4 + book_negative * 0.3), 3)
        merged_giant_killer = round(min(0.30, giant_killer * 0.6 + book_giant_killer * 0.4), 3)
        merged_defensive_strength = round(min(1.35, defensive_strength * 0.7 + book_defensive_strength * 0.3), 3)

        # style_open 与 book_attack_open/book_defense 融合
        book_style_open = round(1.0 + book_attack * 0.3 - book_defense * 0.25, 3)
        merged_style_open = round(min(1.45, max(0.70,
            style_open * 0.65 + book_style_open * 0.35)), 3)

        return {
            "form_factor": round(form, 3),
            "attack_factor": round(attack_factor, 3),
            "defense_factor": round(defense_factor, 3),
            "style_open": merged_style_open,
            "giant_killer": merged_giant_killer,
            "strong_but_weak": merged_strong_but_weak,
            "defensive_strength": merged_defensive_strength,
            # 来自 EPUB/DOCX 的新字段
            "book_draw_bias": round(book_draw_bias, 3),
            "book_upset": round(book_upset, 3),
            "book_mentions": book_sig.get("mentions", 0) if book_sig else 0,
        }

    def get_bookmaker_signals(self, code: str) -> dict[str, float] | None:
        """直接读取某队的 EPUB/DOCX 原始信号（不与 TXT 合并）。"""
        if self._bookmaker_signals is None:
            # 触发懒加载
            _ = self.odds_full_text
        if self._bookmaker_signals is None:
            return None
        return self._bookmaker_signals.get(code)

    def get_calibration(self) -> dict[str, float]:
        """读取全局盘口校准值。"""
        if self._calibration is None:
            _ = self.odds_full_text
        if self._calibration is None:
            return {
                "book_home_bias": 0.0,
                "book_upset_emphasis": 0.0,
                "book_draw_emphasis": 0.0,
                "book_strong_team_caution": 0.0,
                "book_total_goals_calibration": 1.0,
            }
        return self._calibration

    def search_odds_knowledge(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """在庄家思维知识库中搜索相关内容。

        Args:
            query: 搜索关键词
            limit: 返回最多匹配片段数

        Returns:
            匹配片段列表，每个包含 source, snippet
        """
        if not self.odds_full_text:
            return []

        results = []
        sections = self.odds_full_text.split('===== 来源:')

        for section in sections[1:]:
            parts = section.split('=====')
            if len(parts) < 2:
                continue
            source_name = parts[0].strip()
            content = parts[1].strip() if len(parts) > 1 else ""

            query_lower = query.lower()
            if query_lower in content.lower():
                idx = content.lower().index(query_lower)
                start = max(0, idx - 200)
                end = min(len(content), idx + 400)
                snippet = content[start:end].strip()
                results.append({
                    "source": source_name,
                    "snippet": snippet,
                })
                if len(results) >= limit:
                    break

        return results

    def get_odds_knowledge_summary(self) -> dict[str, Any]:
        """获取庄家思维知识库的摘要信息。"""
        return {
            "total_chars": len(self.odds_full_text),
            "sources": self.odds_sources,
            "source_count": len(self.odds_sources),
        }

    def reload(self) -> None:
        """强制重新加载所有知识库。"""
        self._team_cache = None
        self._odds_full_text = ""
        self._odds_sources = []


# 全局单例
_loader: KnowledgeLoader | None = None


def get_loader() -> KnowledgeLoader:
    """获取知识库加载器单例。"""
    global _loader
    if _loader is None:
        _loader = KnowledgeLoader()
    return _loader


def reload():
    """强制重新加载知识库（用于测试）。"""
    global _loader
    _loader = KnowledgeLoader()
