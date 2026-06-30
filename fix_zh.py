import re

with open(r"cup2026predictor\web\index.html", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace("<html lang=\"en\">", "<html lang=\"zh-CN\">", 1)
text = re.sub(r"<title>.*?</title>", "<title>AI 世界杯预测 2026 ｜ 实时夺冠概率 · 比分预测 · 每日 AI 战报</title>", text, count=1)
text = re.sub(r'<meta name="description" content=".*?">', '<meta name="description" content="AI 世界杯预测 2026：实时夺冠概率、逐场比分预测、小组出线形势、每日 AI 战报与预测战绩追踪。">', text, count=1)
text = re.sub(r'<meta property="og:title" content=".*?">', '<meta property="og:title" content="AI 世界杯预测 2026 ｜ 实时夺冠概率 · 比分预测 · 每日 AI 战报">', text, count=1)
text = re.sub(r'<meta property="og:description" content=".*?">', '<meta property="og:description" content="AI 世界杯预测 2026：实时夺冠概率、逐场比分预测、小组出线形势、每日 AI 战报与预测战绩追踪。">', text, count=1)
text = text.replace("og:locale\" content=\"en_US\"", "og:locale\" content=\"zh_CN\"")
text = re.sub(r'<meta name="twitter:title" content=".*?">', '<meta name="twitter:title" content="AI 世界杯预测 2026 ｜ 实时夺冠概率 · 比分预测 · 每日 AI 战报">', text, count=1)
text = re.sub(r'<meta name="twitter:description" content=".*?">', '<meta name="twitter:description" content="AI 世界杯预测 2026：实时夺冠概率、逐场比分预测、小组出线形势、每日 AI 战报与预测战绩追踪。">', text, count=1)
text = text.replace("href=\"/\"", "href=\"/zh/\"", 1)
text = text.replace(">English</button", ">中文</button")

with open(r"cup2026predictor\web\zh\index.html", "w", encoding="utf-8") as f:
    f.write(text)

print("Fixed successfully!")
print("Size:", len(text))
