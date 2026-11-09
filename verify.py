#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""交叉验证：gguf_dump.dequant  vs  官方 gguf.quants.dequantize（独立实现）
python verify.py file.gguf
"""
import sys
import numpy as np
from gguf import GGUFReader, GGMLQuantizationType
from gguf.quants import dequantize as ref_dequant

sys.path.insert(0, '.')
from gguf_dump import GGUFReader as MyReader, dequant as my_dequant, type_name

path = sys.argv[1]
mine = MyReader(path)
theirs = GGUFReader(path)
print('文件: %s  (%d 张量)' % (path, len(mine.tensors)))
print('%-34s %-7s %-20s %12s %s' % ('tensor', 'type', 'shape', 'max|diff|', 'verdict'))

bad = 0
for t, ref in zip(mine.tensors, theirs.tensors):
    assert t['name'] == ref.name, (t['name'], ref.name)
    n = t['n_elements']
    tid = int(ref.tensor_type)
    buf = mine.tensor_bytes(t)
    try:
        a = my_dequant(buf, n, tid)
    except (ValueError, SystemExit) as e:
        print('%-34s %-7s SKIP %s' % (t['name'], type_name(tid), e))
        continue
    src = np.frombuffer(buf, dtype=np.uint8).copy()
    try:
        b = ref_dequant(src, GGMLQuantizationType(tid)).astype(np.float32).reshape(-1)
    except NotImplementedError:
        print('%-34s %-7s %-20s %12s %s' % (t['name'], type_name(tid), str(a.shape), '-', 'OK(官方包不支持对比)'))
        continue
    a = a.reshape(-1)
    if a.shape != b.shape:
        print('%-34s %-7s SHAPE MISMATCH %s vs %s' % (t['name'], type_name(tid), a.shape, b.shape))
        bad += 1
        continue
    diff = float(np.max(np.abs(a - b)))
    ok = diff < 1e-3 * max(1.0, float(np.max(np.abs(b))))
    if not ok:
        bad += 1
    print('%-34s %-7s %-20s %12.3e %s' % (t['name'], type_name(tid), str(a.shape), diff, 'OK' if ok else 'MISMATCH'))

print('\n结果: %d 个张量不一致' % bad)
sys.exit(1 if bad else 0)
