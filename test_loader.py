import sys, os
sys.path.insert(0, os.path.join(os.getcwd(), "cup2026predictor"))
sys.path.insert(0, os.path.join(os.getcwd(), "cup2026predictor", "src"))

from knowledge_loader import get_loader

loader = get_loader()

print("=== 知识库来源 ===")
for src in loader.get_all_sources():
    fmt = src["format"]
    name = src["name"][:50]
    size = src["size_bytes"]
    print(f"  [{fmt}] {name}... ({size} bytes)")

print()
print("=== 已加载球队数量 ===")
teams = loader.get_all_team_names()
print(f"  共 {len(teams)} 支球队")
for t in teams[:15]:
    print(f"  - {t}")
if len(teams) > 15:
    print(f"  ... 还有 {len(teams)-15} 支")

print()
print("=== 示例：ARG ===")
arg = loader.get_team_data("ARG")
if arg:
    for k, v in arg.items():
        print(f"  {k}: {v}")
else:
    print("  未找到")

print()
print("=== 示例：BRA ===")
bra = loader.get_team_data("BRA")
if bra:
    for k, v in bra.items():
        print(f"  {k}: {v}")
else:
    print("  未找到")