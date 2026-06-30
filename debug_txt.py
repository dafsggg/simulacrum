import sys, os, re
sys.path.insert(0, os.path.join(os.getcwd(), "cup2026predictor"))
sys.path.insert(0, os.path.join(os.getcwd(), "cup2026predictor", "src"))

from pathlib import Path

# 手动测试 TXT 解析
kb_dir = Path(os.path.join(os.getcwd(), "cup2026predictor", "knowledge"))
txt_files = list(kb_dir.glob("*.txt"))
print(f"TXT 文件数: {len(txt_files)}")

for tf in txt_files:
    print(f"\n=== 解析 {tf.name[:50]} ===")
    content = tf.read_text(encoding="utf-8")
    
    # 测试正则
    lines = content.split("\n")
    team_count = 0
    for line in lines[:50]:
        line_s = line.strip()
        # 测试球队匹配
        m1 = re.match(r'^[\d]+[\.）]\s*(.+)$', line_s)
        if m1 and not line_s.startswith('-'):
            team_count += 1
            print(f"  匹配球队: {m1.group(1)}")
            # 检查下一行是否匹配属性
            idx = lines.index(line)
            if idx + 1 < len(lines):
                attr_line = lines[idx + 1].strip()
                m2 = re.match(r'^-\s*(.+?)[：:]\s*(.+)$', attr_line)
                if m2:
                    print(f"    属性: {m2.group(1)}: {m2.group(2)[:40]}")
                else:
                    print(f"    下一行不匹配属性: {repr(attr_line[:50])}")
    
    print(f"  总共匹配 {team_count} 支球队")