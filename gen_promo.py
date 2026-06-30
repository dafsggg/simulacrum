from PIL import Image, ImageDraw, ImageFont, ImageFilter
import math
import os

W, H = 1200, 675
img = Image.new('RGB', (W, H), '#0a1628')
draw = ImageDraw.Draw(img)

for y in range(H):
    r = int(10 + (y / H) * 10)
    g = int(22 + (y / H) * 40)
    b = int(40 + (y / H) * 30)
    draw.line([(0, y), (W, y)], fill=(r, g, b))

for i in range(30):
    x = int((i * 137 + 50) % W)
    y = int((i * 89 + 30) % H)
    s = 2 + (i % 4)
    alpha = 30 + (i % 5) * 10
    overlay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.ellipse([x - s, y - s, x + s, y + s], fill=(0, 255, 150, alpha))
    img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')
    draw = ImageDraw.Draw(img)

try:
    font_big = ImageFont.truetype("msyhbd.ttc", 64)
    font_mid = ImageFont.truetype("msyh.ttc", 28)
    font_sm = ImageFont.truetype("msyh.ttc", 20)
    font_title = ImageFont.truetype("msyhbd.ttc", 36)
except:
    font_big = ImageFont.load_default()
    font_mid = ImageFont.load_default()
    font_sm = ImageFont.load_default()
    font_title = ImageFont.load_default()

draw.text((W // 2, 100), "世界杯 AI 分析系统", fill=(0, 255, 170), font=font_big, anchor="mt")
draw.text((W // 2, 175), "World Cup AI Analysis System", fill=(150, 200, 255), font=font_mid, anchor="mt")

cards = [
    ("Elo 评级", "百年历史数据\n客观实力量化"),
    ("知识库融合", "TXT + EPUB/DOCX\n理解球队状态"),
    ("赔率融合", "0.7模型 + 0.3市场\n兼顾客观与智慧"),
    ("激进模式", "实力碾压时\n自动放大比分差距"),
]

card_w, card_h = 240, 160
start_x = (W - len(cards) * card_w - (len(cards) - 1) * 20) // 2
start_y = 240

for i, (title, desc) in enumerate(cards):
    x = start_x + i * (card_w + 20)
    y = start_y
    
    overlay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle([x, y, x + card_w, y + card_h], radius=12, 
                         fill=(15, 35, 60, 200), outline=(0, 200, 150, 100), width=2)
    img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')
    draw = ImageDraw.Draw(img)
    
    draw.text((x + card_w // 2, y + 35), title, fill=(0, 255, 170), font=font_title, anchor="mt")
    
    lines = desc.split('\n')
    for j, line in enumerate(lines):
        draw.text((x + card_w // 2, y + 80 + j * 32), line, fill=(180, 210, 240), font=font_sm, anchor="mt")

bar_y = 500
draw.text((W // 2, bar_y), "30万次蒙特卡洛模拟 · 让分析更接近真相", fill=(255, 255, 255), font=font_mid, anchor="mt")

draw.text((W // 2, H - 60), "分析仅供娱乐 · 远离非法赌球 · 理性观赛", fill=(120, 150, 180), font=font_sm, anchor="mt")

out_path = r"d:\AI portect\世界杯预测（博主版）\产品宣传图.jpg"
img.save(out_path, quality=95)
print(f"宣传图已生成: {out_path}")
