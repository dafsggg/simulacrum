import os, shutil

src = r'D:\AI portect\世界杯预测（博主版）\cup2026predictor\src\knowledge_loader.py.bak'
dst = r'D:\AI portect\世界杯预测（博主版）\cup2026predictor\src\knowledge_loader.py'

with open(src, 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Add zipfile import
text = text.replace('import glob', 'import glob\nimport zipfile')

# 2. Add bs4 import
bs4_code = """
try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False
"""
text = text.replace('from typing import Any', 'from typing import Any' + bs4_code)

# 3. Replace _find_knowledge_files
old_find = """    def _find_knowledge_files(self) -> list[Path]:
        \"\"\"查找知识库目录下的所有 TXT 分析文件。\"\"\"
        return sorted(list(KNOWLEDGE_DIR.glob(\"*.txt\")), key=lambda p: p.name)"""
new_find = """    def _find_knowledge_files(self) -> list[Path]:
        \"\"\"查找知识库目录下的所有分析文件（TXT、DOCX、EPUB）。\"\"\"
        txt = sorted(list(KNOWLEDGE_DIR.glob(\"*.txt\")), key=lambda p: p.name)
        docx = sorted(list(KNOWLEDGE_DIR.glob(\"*.docx\")), key=lambda p: p.name)
        epub = sorted(list(KNOWLEDGE_DIR.glob(\"*.epub\")), key=lambda p: p.name)
        return txt + docx + epub"""
text = text.replace(old_find, new_find)

# 4. Replace _load_all
old_load = """    def _load_all(self) -> dict[str, dict]:
        \"\"\"加载所有知识库文件，返回按球队代码索引的数据。\"\"\"
        result: dict[str, dict] = {}
        files = self._find_knowledge_files()

        for file_path in files:
            try:
                content = file_path.read_text(encoding=\"utf-8\")
                parsed = self._parse_analysis(content)
                result.update(parsed)
            except Exception as exc:  # noqa: BLE001
                print(f\"  [knowledge] 解析失败 {file_path.name}: {exc}\")

        return result"""

new_load = """    def _load_all(self) -> dict[str, dict]:
        \"\"\"加载所有知识库文件，返回按球队代码索引的数据。\"\"\"
        result: dict[str, dict] = {}
        files = self._find_knowledge_files()

        for file_path in files:
            try:
                ext = file_path.suffix.lower()
                if ext == \".txt\":
                    content = file_path.read_text(encoding=\"utf-8\")
                    parsed = self._parse_txt(content)
                    result.update(parsed)
                    print(f\"  [knowledge] TXT OK: {file_path.name[:40]} -> {len(parsed)} teams\")
                elif ext == \".docx\":
                    self._parse_docx_to_teams(file_path, result)
                elif ext == \".epub\":
                    self._parse_epub_to_teams(file_path, result)
            except Exception as exc:  # noqa: BLE001
                print(f\"  [knowledge] 解析失败 {file_path.name}: {exc}\")

        return result"""
text = text.replace(old_load, new_load)

# 5. Rename _parse_analysis to _parse_txt
text = text.replace('def _parse_analysis(self, text: str)', 'def _parse_txt(self, text: str)')

# 6. Fix the split - use chr(10)
text = text.replace('lines = text.split("\\n")', 'NL = chr(10)\n        lines = text.split(NL)')

# 7. Rename _extract_numeric_stats to _extract_stats
text = text.replace('def _extract_numeric_stats(self, data: dict[str, str])', 'def _extract_stats(self, data: dict[str, str])')

# 8. Add docx/epub methods before _build_code_map
extra_methods = """
    def _parse_docx_to_teams(self, file_path, result):
        \"\"\"从 DOCX 书籍中提取球队相关数据。\"\"\"
        if not HAS_BS4:
            return
        try:
            with zipfile.ZipFile(file_path, 'r') as z:
                xml = z.read('word/document.xml').decode('utf-8', errors='replace')
                soup = BeautifulSoup(xml, 'xml')
                texts = soup.find_all('w:t')
                full = ''.join([t.string for t in texts if t.string])
            self._search_team_in_text(full, result)
        except Exception as exc:
            print(f'  [knowledge] DOCX ERROR {file_path.name}: {exc}')

    def _parse_epub_to_teams(self, file_path, result):
        \"\"\"从 EPUB 书籍中提取球队相关数据。\"\"\"
        if not HAS_BS4:
            return
        try:
            with zipfile.ZipFile(file_path, 'r') as z:
                htmls = [n for n in z.namelist() if n.endswith('.html') or n.endswith('.xhtml')]
                parts = []
                for h in htmls[:30]:
                    c = z.read(h).decode('utf-8', errors='replace')
                    s = BeautifulSoup(c, 'html.parser')
                    parts.append(s.get_text())
                full = chr(10).join(parts)
            self._search_team_in_text(full, result)
        except Exception as exc:
            print(f'  [knowledge] EPUB ERROR {file_path.name}: {exc}')

    def _search_team_in_text(self, text, result):
        \"\"\"在文本中搜索球队名，提取相关上下文。\"\"\"
        code_map = self._build_code_map()
        for cn, code in code_map.items():
            if code in result:
                continue
            idx = 0
            sections = []
            while True:
                pos = text.find(cn, idx)
                if pos == -1:
                    break
                s = max(0, pos - 800)
                e = min(len(text), pos + 800)
                sections.append(text[s:e])
                idx = pos + 1
            if sections:
                combined = chr(10).join(sections)
                extracted = self._extract_stats_from_text(combined)
                if extracted:
                    result[code] = extracted

    def _extract_stats_from_text(self, text):
        \"\"\"从文本中提取数值化统计。\"\"\"
        import re as _re
        r = {}
        m = _re.search(r'([0-9]+(?:[.][0-9]+)?)%[ ]*胜率', text)
        if m:
            r['win_rate'] = float(m.group(1)) / 100
        m = _re.search(r'场均?[进球进]?[ ]*([0-9.]+)', text)
        if m:
            r['avg_scored'] = float(m.group(1))
        m = _re.search(r'场均?[失球丢]?[ ]*([0-9.]+)', text)
        if m:
            r['avg_conceded'] = float(m.group(1))
        return r if r else None

"""
text = text.replace('    def _build_code_map(self)', extra_methods + '    def _build_code_map(self)')

# 9. Fix regex - replace \d with [0-9]
text = text.replace(r'\d+', '[0-9]+')
text = text.replace(r'\d*', '[0-9]*')
text = text.replace(r'\d.', '[0-9.]')
text = text.replace(r'\s*', '[ ]*')
text = text.replace(r'\s+', '[ ]+')

# 10. Also map Chinese team names as keys
old_map = """        mapped: dict[str, dict] = {}
        for cn_name, data in teams.items():
            code = code_map.get(cn_name)
            if code:
                mapped[code] = self._extract_numeric_stats(data)
            else:
                mapped[cn_name] = data

        return mapped"""
new_map = """        mapped: dict[str, dict] = {}
        for cn_name, data in teams.items():
            code = code_map.get(cn_name)
            if code:
                mapped[code] = self._extract_stats(data)
                # Also store under Chinese name
                mapped[cn_name] = mapped[code]
            else:
                mapped[cn_name] = data

        return mapped"""
text = text.replace(old_map, new_map)

# Write
shutil.copy2(src, dst + '.bak2')
with open(dst, 'w', encoding='utf-8') as f:
    f.write(text)

print(f'Done: {os.path.getsize(dst)} bytes')
