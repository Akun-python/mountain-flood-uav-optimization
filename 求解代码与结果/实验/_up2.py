# -*- coding: utf-8 -*-
import re, io
def edit(path, pairs):
    s = io.open(path, encoding='utf-8').read()
    for a, b in pairs:
        n = s.count(a)
        s = s.replace(a, b)
        print('%s: %d x %r -> %r' % (path.split(chr(92))[-1], n, a[:40], b[:40]))
    io.open(path, 'w', encoding='utf-8', newline='\n').write(s)
# 6_problem2.tex：冠军 25→24 架、69.77→69.13
edit('sections/6_problem2.tex', [
    ('本文选取完工冠军：25 架次、完工约 109.5\\,min、能耗 69.77\\,kWh', '本文选取完工冠军：24 架次、完工约 109.5\\,min、能耗 69.13\\,kWh'),
    ('能耗使总能耗降至 69.77\\,kWh。若以能耗为先', '能耗使总能耗降至 69.13\\,kWh。若以能耗为先'),
    ('\\textbf{完工冠军（RS+启发式精炼，本文选取）} & \\textbf{25} & \\textbf{6571.4} & \\textbf{69.77}', '\\textbf{完工冠军（RS+启发式精炼，本文选取）} & \\textbf{24} & \\textbf{6571.4} & \\textbf{69.13}'),
    ('精炼冠军方案共 25 架次，其中 A 型 12、B 型 7、C 型 6', '精炼冠军方案共 24 架次，其中 A 型 11、B 型 7、C 型 6'),
    ('总能耗 69.77\\,kWh。', '总能耗 69.13\\,kWh。'),
    ('\\caption{精炼冠军 25 架次调度明细', '\\caption{精炼冠军 24 架次调度明细'),
    ('\\caption{25 架次能耗构成（按机型着色，总量 69.77\\,kWh）}', '\\caption{24 架次能耗构成（按机型着色，总量 69.13\\,kWh）}'),
    ('14 组共享电池在 25 架次间轮换使用', '14 组共享电池在 24 架次间轮换使用'),
    ('均未发现更低完工的可行解，因此 6571.4\\,s 可视为该机队结构与调度规则下的', '均未发现更低完工的可行解，因此 6571.4\\,s 可视为该机队结构与调度规则下的'),
])
