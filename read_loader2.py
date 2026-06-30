import os, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

path = r"D:\AI portect\世界杯预测（博主版）\cup2026predictor\src\knowledge_loader.py"

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

lines = content.split("\n")
for i, line in enumerate(lines[100:]):
    print(f"{101+i:3d}: {line}")