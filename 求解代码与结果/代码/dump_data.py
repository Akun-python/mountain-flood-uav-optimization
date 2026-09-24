# -*- coding: utf-8 -*-
"""Dump all D题 Excel data + DEM info to a UTF-8 text report for inspection."""
import sys, io
import pandas as pd
import openpyxl
import numpy as np
from scipy.io import loadmat

BASE = r'第二十三届中国研究生数学建模竞赛 - 中文题目\中文题目\D题\数据'
OUT = r'solve_d\data_dump.txt'

lines = []
def out(*a):
    s = ' '.join(str(x) for x in a)
    lines.append(s)

files = ['调度中心与服务区.xlsx', '物资需求与配送时限.xlsx', '运输无人机数据.xlsx',
         '中继无人机数据.xlsx', '通信链路参数.xlsx']
for f in files:
    wb = openpyxl.load_workbook(BASE + r'\无人机应急物资运输基础数据\\' + f, data_only=True)
    out('=' * 100)
    out('FILE:', f)
    for ws in wb.worksheets:
        out('  SHEET:', ws.title)
        for row in ws.iter_rows(values_only=True):
            out('    |', ' | '.join('' if v is None else str(v) for v in row))
        out('')

# DEM .mat
dem = loadmat(BASE + r'\镇龙乡地理空间数据\镇龙乡及周边地理数据\数字高程模型数据（DEM）\镇龙乡及周边30米DEM.mat')
out('=' * 100)
out('DEM .mat keys:', list(dem.keys()))
for k, v in dem.items():
    if k.startswith('__'):
        continue
    a = np.asarray(v)
    out('  key:', k, 'shape:', a.shape, 'dtype:', a.dtype)
    if a.size < 40:
        out('  values:', a)
    else:
        out('  min:', np.nanmin(a), 'max:', np.nanmax(a), 'mean:', np.nanmean(a))

# 村镇点位 csv head
for f in ['村镇点位\镇龙乡及周边村镇点位.csv', '水系（线）\镇龙乡及周边水系.csv',
          '水体（面）\镇龙乡及周边水体.csv', '道路\镇龙乡及周边道路.csv']:
    out('=' * 100)
    out('CSV:', f)
    try:
        df = pd.read_csv(BASE + r'\镇龙乡地理空间数据\镇龙乡及周边地理数据\\' + f, encoding='utf-8-sig', nrows=8)
        out('  columns:', list(df.columns))
        out(df.head(8).to_string())
    except Exception as e:
        out('  ERROR:', e)

with open(OUT, 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(lines))
print('written', OUT)