import os

# 目标文件路径
dest = r"D:\AI portect\世界杯预测（博主版）\cup2026predictor\src\knowledge_loader.py"

# 读取新文件内容
with open(r"D:\AI portect\世界杯预测（博主版）\cup2026predictor\src\knowledge_loader_new.py", "r", encoding="utf-8") as f:
    new_content = f.read()

# 备份原文件
import shutil
backup = dest + ".bak"
if os.path.exists(dest):
    shutil.copy2(dest, backup)
    print(f"已备份原文件到: {backup}")

# 写入新文件
with open(dest, "w", encoding="utf-8") as f:
    f.write(new_content)

print(f"已更新: {dest}")
print(f"文件大小: {len(new_content)} 字符")