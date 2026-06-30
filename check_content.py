import zipfile, os, sys, io
from bs4 import BeautifulSoup

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

root = r"D:\AI portect\世界杯预测（博主版）\cup2026predictor\knowledge"

# 1. 读取 TXT 文件中的球队列表
print("=== TXT 文件中的球队 ===")
txt_files = [f for f in os.listdir(root) if f.endswith(".txt")]
for tf in txt_files:
    with open(os.path.join(root, tf), "r", encoding="utf-8") as f:
        content = f.read()
    import re
    teams = re.findall(r"^[\d]+[\.）]\s*(.+)", content, re.MULTILINE)
    for t in teams[:30]:
        print(f"  {t}")
    print(f"  ... 共 {len(teams)} 支球队")

# 2. 读取 epub 的第一章内容样本
print("\n=== EPUB 内容样本（数字游戏）===")
epub_files = [f for f in os.listdir(root) if f.endswith(".epub") and "数字游戏" in f]
if epub_files:
    with zipfile.ZipFile(os.path.join(root, epub_files[0]), 'r') as z:
        html_files = [n for n in z.namelist() if n.endswith('.html') or n.endswith('.xhtml')]
        print(f"  HTML 文件: {len(html_files)} 个")
        if html_files:
            sample = z.read(html_files[0]).decode('utf-8', errors='replace')
            soup = BeautifulSoup(sample, 'html.parser')
            text = soup.get_text()[:500]
            print(f"  第一章前500字:\n{text}")

# 3. 读取 docx 的第一章内容样本
print("\n=== DOCX 内容样本（足球彩票指南）===")
docx_files = [f for f in os.listdir(root) if f.endswith(".docx")]
if docx_files:
    zf = zipfile.ZipFile(os.path.join(root, docx_files[0]), 'r')
    xml_content = zf.read('word/document.xml').decode('utf-8', errors='replace')
    soup = BeautifulSoup(xml_content, 'xml')
    texts = soup.find_all('w:t')
    full_text = "".join([t.string for t in texts[:50]])
    print(f"  前50段文本:\n{full_text[:800]}")
    zf.close()