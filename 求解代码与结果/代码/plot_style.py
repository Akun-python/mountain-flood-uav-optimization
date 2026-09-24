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

# 暖橙色系（萱草色系）色板：萱草 #F8B862 / 柑子 #F6AD49 / 金茶 #F39800 /
# 蜜柑 #F08300 / 鉛丹 #EC6D51 / 黄丹 #EE7948；图内文字一律黑色。
C_BLUE = '#F39800'      # 金茶（A 型）
C_ORANGE = '#F6AD49'    # 柑子色（B 型）
C_RED = '#EC6D51'       # 鉛丹色（C 型 / 强调）
C_SKY = '#F8B862'       # 萱草色（W 中继）
C_VIOLET = '#F08300'    # 蜜柑色（E 中继）
C_GREEN = '#EE7948'     # 黄丹（N 中继 / 冠军）
C_YELLOW = '#F8B862'    # 萱草
C_BLACK = '#222222'     # 深灰（文字/元素）

MODEL_COLORS = {'A': C_BLUE, 'B': C_ORANGE, 'C': C_RED}
AREA_COLORS = {'W': C_SKY, 'E': C_VIOLET, 'N': C_GREEN}