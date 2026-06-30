import sys, os
sys.path.insert(0, os.path.join(os.getcwd(), "cup2026predictor"))
sys.path.insert(0, os.path.join(os.getcwd(), "cup2026predictor", "src"))

from knowledge_loader import get_loader

loader = get_loader()

# 检查 TXT 文件解析
print("=== TXT 解析测试 ===")
from pathlib import Path
kb_dir = Path(os.path.join(os.getcwd(), "cup2026predictor", "knowledge"))
txt_files = list(kb_dir.glob("*.txt"))
for tf in txt_files:
    content = tf.read_text(encoding="utf-8")
    print(f"TXT 文件: {tf.name[:40]}... ({len(content)} 字符)")
    # 提取球队名
    import re
    teams = re.findall(r'^[\d]+[\.）]\s*(.+)$', content, re.MULTILINE)
    print(f"  包含 {len(teams)} 支球队")
    for t in teams[:5]:
        print(f"    - {t}")

# 检查书籍提取的数据
print("\n=== 书籍提取测试 ===")
# 检查 EPUB
epub_files = list(kb_dir.glob("*.epub"))
import zipfile
from bs4 import BeautifulSoup

for ef in epub_files[:2]:
    print(f"\nEPUB: {ef.name[:40]}...")
    try:
        with zipfile.ZipFile(ef, 'r') as z:
            html_files = [n for n in z.namelist() if n.endswith('.html') or n.endswith('.xhtml')]
            text_parts = []
            for hf in html_files[:3]:
                c = z.read(hf).decode('utf-8', errors='replace')
                soup = BeautifulSoup(c, 'html.parser')
                text_parts.append(soup.get_text()[:200])
            full_text = "\n".join(text_parts)
            # 搜索"巴西"相关内容
            for team_name in ["巴西", "阿根廷", "法国", "德国"]:
                if team_name in full_text:
                    idx = full_text.find(team_name)
                    print(f"  找到 '{team_name}' 上下文: {full_text[max(0,idx-50):idx+100]}")
    except Exception as e:
        print(f"  解析失败: {e}")

# 检查 DOCX
docx_files = list(kb_dir.glob("*.docx"))
for df in docx_files[:1]:
    print(f"\nDOCX: {df.name[:40]}...")
    try:
        with zipfile.ZipFile(df, 'r') as z:
            xml = z.read('word/document.xml').decode('utf-8', errors='replace')
            soup = BeautifulSoup(xml, 'xml')
            texts = soup.find_all('w:t')
            full = "".join([t.string for t in texts[:100] if t.string])
            for team_name in ["巴西", "阿根廷", "法国"]:
                if team_name in full:
                    idx = full.find(team_name)
                    print(f"  找到 '{team_name}' 上下文: {full[max(0,idx-50):idx+100]}")
    except Exception as e:
        print(f"  解析失败: {e}")