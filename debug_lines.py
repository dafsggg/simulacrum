import sys, os
sys.path.insert(0, os.path.join(os.getcwd(), "cup2026predictor"))

from pathlib import Path

kb_dir = Path(os.path.join(os.getcwd(), "cup2026predictor", "knowledge"))
txt_files = list(kb_dir.glob("*.txt"))
content = txt_files[0].read_text(encoding="utf-8")

lines = content.split("\n")
for i, line in enumerate(lines[10:30], start=11):
    print(f"行{i}: [{repr(line[:80])}]")