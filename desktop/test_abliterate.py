import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import ModelData
import abliterate as ab

MP = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'qwen2.5-0.5b-instruct-q4_k_m.gguf')
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'qwen2.5-0.5b-instruct-abliterated.gguf')

t0 = time.time()
m = ModelData(MP)
m.ensure_embedding()
print('loaded in %.1fs, emb %s' % (time.time() - t0, m.emb.shape))

r, info = ab.refusal_direction(m)
print('refusal terms:', info['refusal_terms'])
print('neutral terms:', info['neutral_terms'])
print('|r| =', round(info['norm'], 4))

t1 = time.time()
rows = ab.analyze(m, r)
print('analyze %.1fs, %d matrices' % (time.time() - t1, len(rows)))
for x in rows[:6]:
    print('  L%-2d %-12s energy=%.5f  %s' % (x['layer'], x['role'], x['energy'], x['name']))
print('mean energy = %.5f' % (sum(x['energy'] for x in rows) / len(rows)))

if '--export' in sys.argv:
    t2 = time.time()
    stats = ab.export_abliterated(m, r, OUT,
                                  progress=lambda d, t, txt: print('  %d/%d %s' % (d, t, txt)) if d % 24 == 0 else None)
    print('export %.1fs -> %s' % (time.time() - t2, stats))

    t3 = time.time()
    m2 = ModelData(OUT)
    m2.ensure_embedding()
    rows2 = ab.analyze(m2, r)
    print('re-analyze new file %.1fs' % (time.time() - t3))
    print('after : mean energy = %.5f, max = %.5f' % (
        sum(x['energy'] for x in rows2) / len(rows2), max(x['energy'] for x in rows2)))
    print('before: mean energy = %.5f, max = %.5f' % (
        sum(x['energy'] for x in rows) / len(rows), max(x['energy'] for x in rows)))
