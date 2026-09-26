# -*- coding: utf-8 -*-
"""v128：论文统一绘图样式（萱草橙色系 + Nature 级排版）。
- 配色：暖橙色系（萱草色板）——与论文原色一致（plot_style 同源）：
  A 金茶 #F39800 / B 柑子 #F6AD49 / C 鉛丹 #EC6D51 /
  W 萱草 #F8B862 / E 蜜柑 #F08300 / N 黄丹 #EE7948，图内文字一律黑色
- 排版：白底、无图内标题、去上右脊、细网格、字体 Microsoft YaHei 优先（不乱码）
- 字号阶梯 7/8/9/11；PDF+PNG 双格式 300dpi 导出
"""
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

# 中文字体：优先模板随附字体，避免依赖系统安装（Microsoft YaHei 优先 → 无乱码）
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
    # 字体：中文优先（微软雅黑/黑体），英文数字回退 Helvetica/Arial
    'font.family': 'sans-serif',
    'font.sans-serif': ['Microsoft YaHei', 'SimHei', 'SimSun',
                        'Helvetica', 'Arial', 'DejaVu Sans'],
    'axes.unicode_minus': False,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.06,
    'pdf.fonttype': 42,
    'ps.fonttype': 42,
    # 字号阶梯（Nature 默认 7pt 起步）
    'font.size': 9,
    'axes.labelsize': 11,
    'axes.titlesize': 0,          # 不画图内标题（图注在正文）
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 8.5,
    # 框架：去上右脊、细轴、白底
    'text.color': '#111111',
    'axes.labelcolor': '#111111',
    'xtick.color': '#111111',
    'ytick.color': '#111111',
    'legend.labelcolor': '#111111',
    'axes.edgecolor': '#444444',
    'axes.linewidth': 0.8,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'axes.grid': True,
    'grid.color': '#D6D8DC',
    'grid.alpha': 0.55,
    'grid.linewidth': 0.55,
    'legend.frameon': False,
    'legend.edgecolor': 'none',
    'legend.handlelength': 1.4,
    'legend.handletextpad': 0.6,
    'legend.columnspacing': 1.0,
    'figure.facecolor': 'white',
    'axes.facecolor': 'white',
    'savefig.facecolor': 'white',
})

# ============================================================
# 萱草橙色系色板（与论文原色一致）：
# 萱草 #F8B862 / 柑子 #F6AD49 / 金茶 #F39800 / 蜜柑 #F08300 /
# 鉛丹 #EC6D51 / 黄丹 #EE7948；图内文字一律黑色。
# ============================================================
C_A = '#F39800'       # A 型（金茶）
C_B = '#F6AD49'       # B 型（柑子色）
C_C = '#EC6D51'       # C 型（鉛丹色 / 强调）
C_W = '#F8B862'       # W 中继（萱草色）
C_E = '#F08300'       # E 中继（蜜柑色）
C_N = '#EE7948'       # N 中继（黄丹）
C_HERO = '#EC6D51'    # 冠军/强调（鉛丹色，与 C 型同族）
C_GRAY = '#6B7280'    # 中性灰（辅助线/网格）
C_LIGHT = '#E5E7EB'   # 浅灰（背景条/充电段）
C_TEXT = '#222222'    # 文字（深灰）

MODEL_COLORS = {'A': C_A, 'B': C_B, 'C': C_C}
AREA_COLORS = {'W': C_W, 'E': C_E, 'N': C_N}

# 色盲友好检验序列（预览用）
SWATCHES = {'A': C_A, 'B': C_B, 'C': C_C, 'W': C_W, 'E': C_E, 'N': C_N}


def save(fig, name, dpi=300, figdir='figures'):
    """PNG（论文用）+ PDF（矢量源）双格式导出。"""
    os.makedirs(figdir, exist_ok=True)
    fig.savefig(os.path.join(figdir, name + '.png'), dpi=dpi)
    fig.savefig(os.path.join(figdir, name + '.pdf'), dpi=dpi)
    plt.close(fig)
    print('saved %s.png/pdf' % name)