# -*- coding: utf-8 -*-
"""从题目 docx 提取图片并定位其上下文文字（用于 README 命名与引用）。"""
import zipfile, re, sys, os, html
sys.stdout.reconfigure(encoding='utf-8')

docx = r'第二十三届中国研究生数学建模竞赛 - 中文题目\中文题目\D题\山区洪涝灾害下无人机运输与通信协同优化.docx'
out_dir = r'第二十三届中国研究生数学建模竞赛 - 中文题目\中文题目\D题\问题描述图片'
os.makedirs(out_dir, exist_ok=True)

z = zipfile.ZipFile(docx)
rels = z.read('word/_rels/document.xml.rels').decode('utf-8')
rid_map = dict(re.findall(r'Id="(rId\d+)"[^>]*Target="media/([^"]+)"', rels))
print('rid -> media:', rid_map)

# 提取图片文件（重命名保存）
for n in z.namelist():
    if n.startswith('word/media/'):
        base = os.path.basename(n)
        ext = os.path.splitext(base)[1]
        with open(os.path.join(out_dir, '问题描述图' + ext), 'wb') as fh:
            fh.write(z.read(n))
        print('extracted ->', os.path.join(out_dir, '问题描述图' + ext))

# 定位图片在正文中的段落上下文
xml = z.read('word/document.xml').decode('utf-8')
paras = re.findall(r'<w:p[ >].*?</w:p>', xml, re.S)
for i, p in enumerate(paras):
    if 'blip' not in p:
        continue
    embs = re.findall(r'r:embed="(rId\d+)"', p)
    files = [rid_map.get(e, e) for e in embs]
    # 本段文字
    txt = html.unescape(''.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', p))).strip()
    # 前后各取 3 个非空段落
    def para_text(pi):
        if 0 <= pi < len(paras):
            t = html.unescape(''.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', paras[pi]))).strip()
            return t
        return ''
    ctx_before = ' | '.join(t for t in [para_text(i-3), para_text(i-2), para_text(i-1)] if t and t != txt)
    ctx_after = ' | '.join(t for t in [para_text(i+1), para_text(i+2), para_text(i+3)] if t)
    print('--- 段落 %d 图片 %s ---' % (i, files))
    print('  本段: %r' % txt[:150])
    print('  前文: %s' % ctx_before[-200:])
    print('  后文: %s' % ctx_after[:200])