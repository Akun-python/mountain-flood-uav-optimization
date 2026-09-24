# -*- coding: utf-8 -*-
"""论文统一绘图风格：无图内标题、300dpi、色盲友好、衬线中文字体。"""
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

# 中文字体：优先加载模板随附字体，避免依赖系统安装
_font_candidates = [
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', 'SimHei.ttf'),
    r'..\..\SimHei.ttf',
    r'C:\Windows\Fonts\msyh.ttc',
    r'C:\Windows\Fonts\simhei.ttf',
    r'C:\Windows\Fonts\simsun.ttc',
]
for f in _font_candidates:
    if os.path.exists(f):
        font_manager.fontManager.addfont(os.path.abspath(f))
plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Microsoft YaHei', 'SimHei', 'SimSun', 'sans-serif'],
    'axes.unicode_minus': False,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.06,
    'axes.labelsize': 11,
    'axes.titlesize': 0,          # 不画图内标题
    'text.color': 'black',
    'axes.labelcolor': 'black',
    'xtick.color': 'black',
    'ytick.color': 'black',
    'legend.labelcolor': 'black',
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 9,
    'axes.linewidth': 0.8,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'axes.grid': False,
    'grid.color': '#9CA3AF',
    'grid.alpha': 0.35,
    'grid.linewidth': 0.6,
})

# Okabe-Ito 色盲友好色板
C_BLUE = '#0072B2'      # 蓝
C_ORANGE = '#E69F00'    # 橙
C_SKY = '#56B4E9'       # 天蓝
C_GREEN = '#009E73'     # 绿
C_RED = '#D55E00'       # 红（朱红）
C_VIOLET = '#CC79A7'    # 紫
C_YELLOW = '#F0E442'    # 黄
C_BLACK = '#222222'     # 深灰

MODEL_COLORS = {'A': C_BLUE, 'B': C_ORANGE, 'C': C_RED}
AREA_COLORS = {'W': C_SKY, 'E': C_VIOLET, 'N': C_GREEN}