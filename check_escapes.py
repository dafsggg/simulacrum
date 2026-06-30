import os, shutil

dest = r"D:\AI portect\世界杯预测（博主版）\cup2026predictor\src\knowledge_loader.py"
src = r"D:\AI portect\世界杯预测（博主版）\cup2026predictor\src\knowledge_loader_new.py"
shutil.copy2(src, dest)
print(f"Copied: {dest}")
print(f"Size: {os.path.getsize(dest)} bytes")

# Now fix the escaped newlines issue
with open(dest, "r", encoding="utf-8") as f:
    content = f.read()
# Check if there are literal \\n that should be actual newlines
count = content.count("\\\\n")
print(f"Literal \\\\n count: {count}")