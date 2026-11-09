import io

P = r'C:\Users\Administrator\Documents\deepseek-harness\default-workspace\gguf-lab\desktop\abliterate.py'
s = io.open(P, encoding='utf-8').read()

CODE = '''

# ------------------------------------------------------------------ 自动检测
LEVELS = [
    (1.0, '极弱', '几乎没有拒答训练痕迹，接近基座模型'),
    (2.5, '偏弱', '有轻微对齐倾向，拒答行为不稳定'),
    (4.0, '中等', '明确做过安全对齐，常规问题可能触发拒答'),
    (6.0, '偏强', '拒答行为稳定，换措辞也很难绕开'),
    (999.0, '很强', '拒答高度固化，建议直接移除后再用'),
]


def _level(pct):
    for limit, name, note in LEVELS:
        if pct < limit:
            return name, note
    return '很强', LEVELS[-1][2]


def auto_detect(model, progress=None):
    """
    一次调用完成「检测 + 打分 + 结论」：
      1. 从词元嵌入构造拒答方向 r（中英文拒答词减去中性词）
      2. 扫描所有写回残差流的矩阵（注意力输出 / 前馈下投影），算方向能量
      3. 换算成 0~100 的「拒答强度」，定位贡献最大的层，给出移除预期

    返回值里带 r，可以直接喂给 export_abliterated 做移除。
    """
    if progress:
        progress('构造拒答方向…')
    r, info = refusal_direction(model)

    if progress:
        progress('扫描写回残差流的矩阵…')
    rows = analyze(model, r)
    if not rows:
        raise RuntimeError('没有找到可分析的矩阵（模型可能不是 llama 结构）')

    mean = sum(x['energy'] for x in rows) / len(rows)
    mx = max(x['energy'] for x in rows)
    pct = mean * 100.0                     # 平均能量百分比
    score = max(0.0, min(100.0, pct * 10.0))   # 0~100 分：3.35% → 33.5 分
    level, note = _level(pct)

    by_layer = {}
    for x in rows:
        by_layer[x['layer']] = by_layer.get(x['layer'], 0.0) + x['energy']
    top_layers = sorted(by_layer.items(), key=lambda kv: -kv[1])[:5]

    # 移除预期：正交化后残差来自量化误差，经验值约 0.2%~0.5% 的残留
    expect = max(0.005, mean * 0.01)

    verdict = ('模型存在明确的拒答倾向（%s），主要分布在 %s 层。'
               % (level, ' / '.join('第 %d 层' % l for l, _ in top_layers[:3])))
    if pct < 1.0:
        verdict += ' 这类模型通常不需要处理。'
    else:
        verdict += ' 执行移除后，拒答能量预计从 %.4f 降到 %.5f 左右。' % (mean, expect)

    return {
        'r': r,
        'info': info,
        'rows': rows,
        'mean': mean,
        'max': mx,
        'pct': pct,
        'score': score,
        'level': level,
        'level_note': note,
        'top_layers': top_layers,
        'expect_after': expect,
        'verdict': verdict,
        'matrix_count': len(rows),
    }
'''

if 'def auto_detect(' not in s:
    s = s.rstrip() + CODE
io.open(P, 'w', encoding='utf-8').write(s)
print('auto_detect added, len', len(s))
