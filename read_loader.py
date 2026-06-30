import os, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

root = r"D:\AI portect\世界杯预测（博主版）\cup2026predictor\src"
path = os.path.join(root, "knowledge_loader.py")

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

print(f"当前文件大小: {len(content)} 字符")
print(f"行数: {content.count(chr(10))}")
print("--- 前100行 ---")
lines = content.split("\n")
for i, line in enumerate(lines[:100]):
    print(f"{i+1:3d}: {line}")