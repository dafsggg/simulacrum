import sys
sys.path.insert(0, 'cup2026predictor')

with open('cup2026predictor/src/report.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

output = []
i = 0
while i < len(lines):
    line = lines[i]
    if 'comment = _chat(cfg, COMMENTER_SYSTEM,' in line and i + 1 < len(lines):
        next_line = lines[i + 1]
        if '数据摘要' in next_line:
            indent = '        '
            output.append(indent + 'comment_prompt = ' + chr(34) + '数据摘要：' + chr(34) + ' + digest + ' + chr(34) + chr(92) + 'n' + chr(92) + 'n' + chr(34) + ' + ' + chr(34) + '主笔战报：' + chr(34) + ' + body' + chr(10))
            output.append(indent + 'comment = _chat(cfg, COMMENTER_SYSTEM, comment_prompt,' + chr(10))
            i += 1
            if i < len(lines):
                output.append(lines[i])
            i += 1
            continue
    output.append(line)
    i += 1

with open('cup2026predictor/src/report.py', 'w', encoding='utf-8') as f:
    f.writelines(output)

print('Fix applied')
