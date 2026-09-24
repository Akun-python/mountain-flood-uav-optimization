# -*- coding: utf-8 -*-
import openpyxl
p = r'第二十三届中国研究生数学建模竞赛 - 中文题目\中文题目\D题\结果提交模板.xlsx'
wb = openpyxl.load_workbook(p, data_only=True)
lines = []
for ws in wb.worksheets:
    lines.append('SHEET: %s  dims=%s' % (ws.title, ws.dimensions))
    for row in ws.iter_rows(values_only=True):
        lines.append('  | ' + ' | '.join('' if v is None else str(v) for v in row))
    lines.append('')
with open(r'solve_d\template_dump.txt', 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(lines))
print('ok')
