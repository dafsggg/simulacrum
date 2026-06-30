import sys, os
sys.path.insert(0, os.path.join(os.getcwd(), "cup2026predictor"))
sys.path.insert(0, os.path.join(os.getcwd(), "cup2026predictor", "src"))

from knowledge_loader import get_loader

loader = get_loader()

# 检查哪些球队有完整的数值数据
teams = loader.get_all_team_names()
print(f"总共 {len(teams)} 支球队在知识库中")

with_numeric = []
without_numeric = []

for code in teams:
    data = loader.get_team_data(code)
    if data and "avg_scored" in data:
        with_numeric.append((code, data.get("wins", 0), data.get("avg_scored", 0)))
    else:
        without_numeric.append(code)

print(f"\n有完整数值数据的球队: {len(with_numeric)}")
for code, wins, scored in sorted(with_numeric, key=lambda x: -x[1])[:20]:
    print(f"  {code}: 胜{wins} 场均进球{scored}")

print(f"\n无数值数据的球队: {len(without_numeric)}")
for code in without_numeric[:15]:
    print(f"  {code}")
if len(without_numeric) > 15:
    print(f"  ... 还有 {len(without_numeric)-15} 支")