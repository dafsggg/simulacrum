import sys, os, shutil, re

dest = os.path.join(os.getcwd(), "cup2026predictor", "src", "knowledge_loader.py")
backup = dest + ".bak2"

if os.path.exists(dest):
    shutil.copy2(dest, backup)
    print(f"已备份到: {backup}")

with open(dest, "w", encoding="utf-8") as f:
    f.write('"""知识库加载器：解析球队状态与战术分析文档，结构化输出供预测模型使用。

核心思路：
1. 读取 knowledge/ 目录下的所有分析文件（TXT、DOCX、EPUB）
2. TXT 文件解析球队近10场战绩、场均进球/失球、战术特点、优劣势
3. DOCX/EPUB 书籍提取博彩分析知识，辅助预测模型
4. 将结构化数据注入到预测模型的权重修正中

使用方式：
    from src.knowledge_loader import get_loader
    data = get_loader().get_team_data("ESP")  # 获取西班牙分析
"""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Any

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR = ROOT / "knowledge"


class KnowledgeLoader:
    """知识库加载与管理类。支持 TXT、DOCX、EPUB 三种格式。"""

    def __init__(self):
        self._cache: dict[str, dict] | None = None
        self._book_knowledge: list[dict] | None = None

    @property
    def cache(self) -> dict[str, dict]:
        """懒加载知识库数据。"""
        if self._cache is None:
            self._cache = self._load_all()
        return self._cache

    def _find_knowledge_files(self) -> list[Path]:
        """查找知识库目录下的所有分析文件（TXT、DOCX、EPUB）。"""
        txt_files = sorted(list(KNOWLEDGE_DIR.glob("*.txt")), key=lambda p: p.name)
        docx_files = sorted(list(KNOWLEDGE_DIR.glob("*.docx")), key=lambda p: p.name)
        epub_files = sorted(list(KNOWLEDGE_DIR.glob("*.epub")), key=lambda p: p.name)
        return txt_files + docx_files + epub_files

    def _load_all(self) -> dict[str, dict]:
        """加载所有知识库文件，返回按球队代码索引的数据。"""
        result: dict[str, dict] = {}
        files = self._find_knowledge_files()

        for file_path in files:
            try:
                ext = file_path.suffix.lower()
                content = file_path.read_text(encoding="utf-8") if ext == ".txt" else ""

                if ext == ".txt":
                    parsed = self._parse_txt_analysis(content)
                    result.update(parsed)
                    print(f"  [knowledge] TXT 解析完成: {file_path.name} -> {len(parsed)} 队")
                elif ext in (".docx", ".epub"):
                    parsed = self._parse_book_for_teams(file_path, ext)
                    if parsed:
                        result.update(parsed)
                        print(f"  [knowledge] 书籍提取完成: {file_path.name} -> {len(parsed)} 队")

            except Exception as exc:  # noqa: BLE001
                print(f"  [knowledge] 解析失败 {file_path.name}: {exc}")

        return result

    def _parse_txt_analysis(self, text: str) -> dict[str, dict]:
        """解析 TXT 球队状态分析文本，提取结构化数据。"""
        teams: dict[str, dict] = {}
        current_team: str | None = None
        current_data: dict[str, str] = {}

        lines = text.split("\\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 跳过分隔线
            if line.startswith("="):
                continue

            # 检测大区标题（跳过）
            if re.match(r'^[一二三四五六七八九十]+、', line):
                continue

            # 检测球队标题（如 "1. 阿根廷" 或 "1）巴西"）
            team_match = re.match(r'^[\\d]+[\\.）]\\s*(.+)$', line)
            if team_match and not line.startswith('-'):
                # 保存上一个球队的数据
                if current_team and current_data:
                    teams[current_team] = current_data
                team_name = team_match.group(1).strip()
                current_team = team_name
                current_data = {}
                continue

            # 检测属性行（如 "- 近 10 场状态：xxx"）
            attr_match = re.match(r'^-\\s*(.+?)[：:]\\s*(.+)$', line)
            if attr_match and current_team:
                attr_name = attr_match.group(1).strip()
                attr_value = attr_match.group(2).strip()
                current_data[attr_name] = attr_value
                continue

        # 保存最后一个球队的数据
        if current_team and current_data:
            teams[current_team] = current_data

        print(f"  [knowledge] TXT 解析出 {len(teams)} 个球队条目")
        for name in list(teams.keys())[:5]:
            print(f"    - {name}: {list(teams[name].keys())}")

        # 将中文队名映射到球队代码
        code_map = self._build_code_map()
        mapped: dict[str, dict] = {}
        for cn_name, data in teams.items():
            code = code_map.get(cn_name)
            if code:
                mapped[code] = self._extract_numeric_stats(data)
            else:
                mapped[cn_name] = data

        return mapped

    def _parse_book_for_teams(self, file_path: Path, ext: str) -> dict[str, dict] | None:
        """从 DOCX/EPUB 书籍中提取球队相关数据（备用）。"""
        if not HAS_BS4:
            return None

        text = self._extract_book_text(file_path, ext)
        if not text:
            return None

        code_map = self._build_code_map()
        result: dict[str, dict] = {}

        for cn_name, code in code_map.items():
            if code in result:
                continue
            team_sections = self._extract_team_sections(text, cn_name)
            if team_sections:
                extracted = self._extract_numeric_stats_from_text(team_sections)
                if extracted:
                    result[code] = extracted

        return result if result else None

    def _extract_book_text(self, file_path: Path, ext: str) -> str:
        """从 DOCX 或 EPUB 文件中提取纯文本。"""
        try:
            with zipfile.ZipFile(file_path, 'r') as z:
                if ext == ".docx":
                    return self._extract_docx_text(z)
                elif ext == ".epub":
                    return self._extract_epub_text(z)
        except Exception:
            pass
        return ""

    def _extract_docx_text(self, zip_ref: zipfile.ZipFile) -> str:
        """提取 DOCX 文件中的文本。"""
        try:
            xml_content = zip_ref.read('word/document.xml').decode('utf-8', errors='replace')
            soup = BeautifulSoup(xml_content, 'xml')
            texts = soup.find_all('w:t')
            return "".join([t.string for t in texts if t.string])
        except Exception:
            return ""

    def _extract_epub_text(self, zip_ref: zipfile.ZipFile) -> str:
        """提取 EPUB 文件中的文本。"""
        html_files = [n for n in zip_ref.namelist() if n.endswith('.html') or n.endswith('.xhtml')]
        full_text = []
        for hf in html_files[:20]:
            try:
                content = zip_ref.read(hf).decode('utf-8', errors='replace')
                soup = BeautifulSoup(content, 'html.parser')
                full_text.append(soup.get_text())
            except Exception:
                continue
        return "\\n".join(full_text)

    def _extract_team_sections(self, text: str, team_name: str, context_chars: int = 2000) -> str:
        """从文本中提取包含球队名的上下文段落。"""
        sections = []
        idx = 0
        while True:
            pos = text.find(team_name, idx)
            if pos == -1:
                break
            start = max(0, pos - context_chars // 2)
            end = min(len(text), pos + context_chars // 2)
            sections.append(text[start:end])
            idx = pos + 1
        return "\\n".join(sections) if sections else ""

    def _extract_numeric_stats_from_text(self, text: str) -> dict[str, Any]:
        """从书籍文本中提取数值化统计。"""
        result: dict[str, Any] = {}
        win_rate_match = re.search(r'(\\d+(?:\\.\\d+)?)%\\s*胜率', text)
        if win_rate_match:
            result["win_rate"] = float(win_rate_match.group(1)) / 100
        avg_scored = re.search(r'场均?[进球进]?\\s*([\\d.]+)', text)
        if avg_scored:
            result["avg_scored"] = float(avg_scored.group(1))
        avg_conceded = re.search(r'场均?[失球丢]?\\s*([\\d.]+)', text)
        if avg_conceded:
            result["avg_conceded"] = float(avg_conceded.group(1))
        result["source_text"] = text[:500] if text else ""
        return result

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

    def _extract_numeric_stats(self, data: dict[str, str]) -> dict[str, Any]:
        """从 TXT 解析的文本描述中提取数值化统计。"""
        result: dict[str, Any] = {}
        status_text = data.get("近 10 场状态", "")
        win_draw_loss = re.search(r'(\\d+)\\s*胜\\s*(\\d*)\\s*平\\s*(\\d*)\\s*负', status_text)
        if win_draw_loss:
            result["wins"] = int(win_draw_loss.group(1))
            result["draws"] = int(win_draw_loss.group(2) or 0)
            result["losses"] = int(win_draw_loss.group(3) or 0)
            result["total"] = result["wins"] + result["draws"] + result["losses"]
            result["win_rate"] = result["wins"] / max(result["total"], 1)
        avg_scored = re.search(r'场均进球\\s*([\\d.]+)', status_text)
        if avg_scored:
            result["avg_scored"] = float(avg_scored.group(1))
        avg_conceded = re.search(r'场均失球\\s*([\\d.]+)', status_text)
        if avg_conceded:
            result["avg_conceded"] = float(avg_conceded.group(1))
        result["tactics"] = data.get("战术特点", "")
        result["strengths"] = data.get("优势", "")
        result["weaknesses"] = data.get("劣势", "")
        return result

    def get_team_data(self, code_or_name: str) -> dict[str, Any] | None:
        """根据球队代码或中文名获取知识库数据。"""
        data = self.cache
        if code_or_name in data:
            return data[code_or_name]
        code_map = self._build_code_map()
        if code_or_name in code_map:
            code = code_map[code_or_name]
            if code in data:
                return data[code]
        return None

    def get_all_team_names(self) -> list[str]:
        """返回知识库中有数据的球队列表。"""
        return list(self.cache.keys())

    def get_prediction_boost(self, code: str) -> dict[str, float] | None:
        """为预测模型提供状态修正因子。"""
        data = self.get_team_data(code)
        if not data or "avg_scored" not in data:
            return None
        avg_scored = data.get("avg_scored", 1.0)
        avg_conceded = data.get("avg_conceded", 1.0)
        attack_factor = min(max(avg_scored / 1.5, 0.85), 1.25)
        defense_factor = min(max(1.0 / max(avg_conceded, 0.3), 0.75), 1.35)
        if data.get("win_rate"):
            form = data["win_rate"] / 0.5
            form = min(max(form, 0.8), 1.3)
        else:
            form = 1.0
        return {
            "form_factor": round(form, 3),
            "attack_factor": round(attack_factor, 3),
            "defense_factor": round(defense_factor, 3),
        }

    def get_all_sources(self) -> list[dict]:
        """获取所有知识库来源信息。"""
        sources = []
        for fp in self._find_knowledge_files():
            ext = fp.suffix.lower()
            size = fp.stat().st_size
            sources.append({
                "name": fp.name,
                "format": ext.lstrip("."),
                "size_bytes": size,
                "has_team_data": fp.name.endswith(".txt"),
            })
        return sources


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
''')

print(f"已更新: {dest}")
print(f"文件大小: {len(open(dest, encoding='utf-8').read())} 字符")