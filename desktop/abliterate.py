# -*- coding: utf-8 -*-
"""
abliterate.py —— 拒答方向（refusal direction）分析、移除与 GGUF 导出

原理
----
1. 在词元嵌入空间构造「拒答方向」r：拒答类语义词（sorry / apolog / cannot / 抱歉 / 无法 / 拒绝 …）
   的平均向量，减去中性语义词（yes / sure / 当然 / 可以 …）的平均向量，单位化。
2. 模型里所有「写回残差流」的线性层（attn_output、ffn_down）的输出维都是 hidden，
   方向 r 在其中的分量就是拒答行为的载体。能量 = ||rᵀW|| / ||W||。
3. 移除即把 r 方向从这些矩阵里正交投影掉：W ← W − r·(rᵀW)，同时可从词元嵌入里去掉该方向。
4. 导出新的 GGUF：被修改的张量写 F16，其余张量原样复制量化块，保证体积与精度可控。

对外接口
--------
    kvs, infos = read_header(path)          # 保留数组元素类型，用于原样重写
    r, info = refusal_direction(model)      # 拒绝方向 + 构造信息
    rows = analyze(model, r)                # 每层每分支的拒答能量
    stats = export_abliterated(model, r, out_path, progress=cb)
"""
import os
import struct

import numpy as np

import gguf_dump

MAGIC = b'GGUF'
FMT = {0: '<B', 1: '<b', 2: '<H', 3: '<h', 4: '<I', 5: '<i', 6: '<f', 7: '<?',
       10: '<Q', 11: '<q', 12: '<d'}
T_STRING = 8
T_ARRAY = 9

REFUSAL_WORDS = ['sorry', 'apolog', 'cannot', 'unable', 'refuse', 'decline', "can't",
                 '抱歉', '无法', '不能', '拒绝', '恕难', '没办法']
NEUTRAL_WORDS = ['yes', 'sure', 'okay', '当然', '可以', '好的', '没问题', '行']

# 写回残差流的层（输出维 = hidden）
TARGET_ROLES = ('attn_output', 'ffn_down')


# ------------------------------------------------------------------ header
def _rs(f):
    n = struct.unpack('<Q', f.read(8))[0]
    return f.read(n).decode('utf-8', 'replace')


def _rv(f, t):
    if t == T_STRING:
        return _rs(f)
    code = FMT.get(t)
    if code is None:
        raise ValueError('未知值类型 %d' % t)
    return struct.unpack(code, f.read(struct.calcsize(code)))[0]


def read_header(path):
    """返回 (kvs, infos)。kvs: (key, vtype, elem_type, value)；infos: (name, dims, ttype, offset)"""
    with open(path, 'rb') as f:
        if f.read(4) != MAGIC:
            raise ValueError('不是 GGUF 文件')
        struct.unpack('<I', f.read(4))[0]
        n_tensors = struct.unpack('<Q', f.read(8))[0]
        n_kv = struct.unpack('<Q', f.read(8))[0]
        kvs = []
        for _ in range(n_kv):
            key = _rs(f)
            t = struct.unpack('<I', f.read(4))[0]
            if t == T_ARRAY:
                et = struct.unpack('<I', f.read(4))[0]
                n = struct.unpack('<Q', f.read(8))[0]
                vals = [_rv(f, et) for _ in range(n)]
                kvs.append((key, t, et, vals))
            else:
                kvs.append((key, t, None, _rv(f, t)))
        infos = []
        for _ in range(n_tensors):
            name = _rs(f)
            nd = struct.unpack('<I', f.read(4))[0]
            dims = [struct.unpack('<Q', f.read(8))[0] for _ in range(nd)]
            ttype = struct.unpack('<I', f.read(4))[0]
            off = struct.unpack('<Q', f.read(8))[0]
            infos.append((name, dims, ttype, off))
    return kvs, infos


# ------------------------------------------------------------------ 方向
def _word_vecs(model, words):
    if model.emb is None:
        model.ensure_embedding()
    dec = model.ensure_decoded()
    emb = model.emb
    low = [w.lower() for w in words]
    exact = {}
    fuzzy = {}
    for i, t in enumerate(dec):
        if not t:
            continue
        tl = t.lower()
        core = tl.strip()
        for k, w in enumerate(low):
            if k in exact:
                continue
            if core == w or tl == w:
                exact[k] = i
            elif k not in fuzzy and core.startswith(w) and len(core) <= len(w) + 2:
                fuzzy[k] = i
            elif k not in fuzzy and core.endswith(w) and len(core) <= len(w) + 3:
                fuzzy[k] = i
        if len(exact) == len(low):
            break
    idxs = [exact.get(k, fuzzy.get(k)) for k in range(len(low))]
    idxs = [i for i in idxs if i is not None]
    if not idxs:
        return None, []
    return emb[idxs].mean(0), idxs


def refusal_direction(model):
    """在 hidden 空间构造拒答方向 r（单位向量）"""
    if model.emb is None:
        model.ensure_embedding()
    vr, ir = _word_vecs(model, REFUSAL_WORDS)
    vn, inn = _word_vecs(model, NEUTRAL_WORDS)
    if vr is None or vn is None:
        raise RuntimeError('词表里没有找到足够的中/英文拒答或中性词，无法构造方向')
    r = vr - vn
    n = float(np.linalg.norm(r))
    if n < 1e-9:
        raise RuntimeError('构造出的方向向量长度为 0')
    r = (r / n).astype(np.float32)
    dec = model.ensure_decoded()
    return r, {
        'refusal_terms': [dec[i] for i in ir if i < len(dec)],
        'neutral_terms': [dec[i] for i in inn if i < len(dec)],
        'norm': n,
    }


# ------------------------------------------------------------------ 分析
def _decoded_weight(model, t):
    arr = gguf_dump.dequant(model.reader.tensor_bytes(t), t['n_elements'], t['type'])
    return arr.reshape(t['shape']).astype(np.float32)


def analyze(model, r, roles=TARGET_ROLES):
    """每层每个写残差流的矩阵里，方向 r 的能量占比"""
    src_map = {t['name']: t for t in model.reader.tensors}
    rows = []
    for i in sorted(model.layers):
        for t in model.layers[i]:
            if t['role'] not in roles or t['is_bias']:
                continue
            W = _decoded_weight(model, src_map[t['name']])
            proj = r @ W
            e = float(np.linalg.norm(proj) / max(np.linalg.norm(W), 1e-9))
            rows.append({'layer': i, 'role': t['role'], 'name': t['name'],
                         'energy': e, 'elements': t['elements'],
                         'type': t['type'], 'shape': list(t['shape'])})
    rows.sort(key=lambda x: -x['energy'])
    return rows


# ------------------------------------------------------------------ 导出
def _quant_q8_0(arr):
    """把 float32 数组编码成 Q8_0 块（32 元素 / 34 字节），精度损失极小、体积只有 F16 的一半"""
    W = np.ascontiguousarray(arr.reshape(-1)).astype(np.float32)
    n = W.size
    nb = n // 32
    if nb * 32 != n:
        raise ValueError('元素数不是 32 的倍数，无法编码成 Q8_0')
    blocks = W.reshape(nb, 32)
    amax = np.abs(blocks).max(1)
    d = np.where(amax > 0, amax / 127.0, 0.0).astype(np.float32)
    inv = np.where(d > 0, 1.0 / np.maximum(d, 1e-9), 0.0)
    q = np.rint(blocks * inv[:, None]).clip(-127, 127).astype(np.int8)
    out = np.empty((nb, 34), dtype=np.uint8)
    out[:, 0:2] = d.astype(np.float16).view(np.uint8).reshape(nb, 2)
    out[:, 2:34] = q.view(np.uint8)
    return out.tobytes()


def _w_str(f, s):
    b = s.encode('utf-8')
    f.write(struct.pack('<Q', len(b)))
    f.write(b)


def _w_val(f, t, v):
    if t == T_STRING:
        _w_str(f, v)
    else:
        f.write(struct.pack(FMT[t], v))


def export_abliterated(model, r, out_path, roles=TARGET_ROLES,
                       embed_too=True, progress=None):
    """
    生成一个新的 GGUF：目标矩阵做 W ← W − r(rᵀW)，写 F16；其余张量原样复制。
    progress(done, total, text) 回调。
    """
    src_map = {t['name']: t for t in model.reader.tensors}
    kvs, infos = read_header(model.path)
    align_kv = None
    for k, vtype, et, v in kvs:
        if k == 'general.alignment':
            align_kv = int(v)
    align = align_kv or model.reader.alignment or 32

    plan = []           # (name, dims, out_type, kind)
    total = len(infos)
    for idx, (name, dims, ttype, off) in enumerate(infos):
        role = ''
        if name.startswith('blk.'):
            parts = name.split('.', 2)
            role = parts[2].replace('.weight', '').replace('.bias', '') if len(parts) == 3 else ''
        do_mod = (role in roles and not name.endswith('.bias'))
        if embed_too and name in ('token_embd.weight', 'token_embd'):
            do_mod = True
        plan.append((name, dims, ttype, off, role, do_mod))

    # 数据区起点
    hdr_size = 4 + 4 + 8 + 8
    for key, vtype, et, v in kvs:
        hdr_size += 8 + len(key.encode('utf-8')) + 4
        if vtype == T_ARRAY:
            hdr_size += 4 + 8
            for x in v:
                hdr_size += (8 + len(x.encode('utf-8'))) if et == T_STRING else struct.calcsize(FMT[et])
        elif vtype == T_STRING:
            hdr_size += 8 + len(v.encode('utf-8'))
        else:
            hdr_size += struct.calcsize(FMT[vtype])
    for name, dims, ttype, off, role, do_mod in plan:
        hdr_size += 8 + len(name.encode('utf-8')) + 4 + 8 * len(dims) + 4 + 8
    data_start = (hdr_size + align - 1) // align * align

    # 计算每个张量的 offset 与字节
    offsets = []
    off = 0
    sizes = []
    for name, dims, ttype, src_off, role, do_mod in plan:
        n = 1
        for d in dims:
            n *= d
        if do_mod:
            nbytes = n // 32 * 34                    # Q8_0
        else:
            be, bb = gguf_dump.type_info(ttype)[1:]
            nbytes = n // be * bb
        offsets.append(off)
        sizes.append(nbytes)
        off += nbytes
        off += (-off) % align

    f = open(out_path, 'wb')
    try:
        f.write(MAGIC)
        f.write(struct.pack('<I', 3))
        f.write(struct.pack('<Q', len(plan)))
        f.write(struct.pack('<Q', len(kvs)))
        for key, vtype, et, v in kvs:
            _w_str(f, key)
            f.write(struct.pack('<I', vtype))
            if vtype == T_ARRAY:
                f.write(struct.pack('<I', et))
                f.write(struct.pack('<Q', len(v)))
                for x in v:
                    _w_val(f, et, x)
            else:
                _w_val(f, vtype, v)
        for (name, dims, ttype, src_off, role, do_mod), o, nb in zip(plan, offsets, sizes):
            _w_str(f, name)
            f.write(struct.pack('<I', len(dims)))
            for d in dims:
                f.write(struct.pack('<Q', d))
            f.write(struct.pack('<I', 8 if do_mod else ttype))
            f.write(struct.pack('<Q', o))
        pad = data_start - f.tell()
        if pad > 0:
            f.write(b'\x00' * pad)

        done = 0
        changed = 0
        for k, (name, dims, ttype, src_off, role, do_mod) in enumerate(plan):
            pos = f.tell()
            if do_mod:
                arr = _decoded_weight(model, src_map[name])
                if name in ('token_embd.weight', 'token_embd'):
                    # 词元嵌入：每一行是一个词向量，去掉行内 r 分量（分块省内存）
                    step = 32768
                    for s0 in range(0, arr.shape[0], step):
                        blk = arr[s0:s0 + step]
                        blk -= np.outer(blk @ r, r)
                else:
                    # 写残差流的矩阵：输出维是第 0 维，去掉列空间的 r 分量
                    arr -= np.outer(r, r @ arr)
                f.write(_quant_q8_0(arr))
                changed += 1
            else:
                nbytes = sizes[k]
                model.reader.f.seek(model.reader.data_start + src_off)
                f.write(model.reader.raw(nbytes))
            written = f.tell() - pos
            pad = (-written) % align
            if pad:
                f.write(b'\x00' * pad)
            done += 1
            if progress and (done % 8 == 0 or done == len(plan)):
                progress(done, len(plan), '写入 %s' % name)
    finally:
        f.close()
    return {'out': out_path, 'size': os.path.getsize(out_path), 'changed': changed,
            'tensors': len(plan)}
