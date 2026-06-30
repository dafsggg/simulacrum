import zipfile, os, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

root = r"D:\AI portect\世界杯预测（博主版）\cup2026predictor\knowledge"

print("=== 知识库文件列表 ===")
for f in os.listdir(root):
    ext = os.path.splitext(f)[1].lower()
    size = os.path.getsize(os.path.join(root, f))
    size_str = f"{size/1024/1024:.1f}MB" if size > 1024*1024 else f"{size/1024:.0f}KB"
    print(f"  [{ext}] {f[:50]}... ({size_str})")

print("\n=== EPUB 内部结构 ===")
for f in os.listdir(root):
    if f.lower().endswith('.epub'):
        try:
            with zipfile.ZipFile(os.path.join(root, f), 'r') as z:
                print(f"  文件: {os.path.splitext(f)[0][:30]}...")
                for name in z.namelist()[:15]:
                    print(f"    {name}")
                break
        except Exception as e:
            print(f"  打开失败: {e}")
            break

print("\n=== DOCX 内部结构 ===")
for f in os.listdir(root):
    if f.lower().endswith('.docx'):
        try:
            with zipfile.ZipFile(os.path.join(root, f), 'r') as z:
                print(f"  文件: {os.path.splitext(f)[0][:30]}...")
                for name in z.namelist()[:15]:
                    print(f"    {name}")
                break
        except Exception as e:
            print(f"  打开失败: {e}")
            break