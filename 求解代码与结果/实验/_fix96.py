p = '求解代码与结果/实验/v96_mk_push.py'
s = open(p, encoding='utf-8').read()
old = "def apply(fls=f, nf=nf):\n                return [nf if x.fid == f.fid else x for x in fls]"
new = "def apply(fi=f, nf=nf, flist=fls):\n                return [nf if x.fid == fi.fid else x for x in flist]"
assert old in s, 'not found'
open(p, 'w', encoding='utf-8').write(s.replace(old, new))
print('FIXED')
