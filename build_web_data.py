#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_web_data.py —— 把 GGUF 拆成前端可直接渲染的 window.MODEL_DATA

  python build_web_data.py qwen2.5-0.5b-instruct-q4_k_m.gguf
  # 产出 web/data/model.js（含 词表 / 架构 / 张量表 / 嵌入范数 / PCA / 8 维 token 向量）

浏览器无法直接读 400MB 的 GGUF，所以这一步在本地把「能呈现的部分」压成几 MB 的 JS 数据，
前端双击 index.html 即用（file:// 也能跑，免起服务器）。
"""
import base64
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gguf_dump import GGUFReader, dequant, type_name  # noqa: E402

TYPE_NAMES = {0: 'UNDEFINED', 1: 'NORMAL', 2: 'UNKNOWN', 3: 'CONTROL',
              4: 'USER_DEFINED', 5: 'UNUSED', 6: 'BYTE'}
SPECIAL_KEYS = ['tokenizer.ggml.bos_token_id', 'tokenizer.ggml.eos_token_id',
                'tokenizer.ggml.unknown_token_id', 'tokenizer.ggml.padding_token_id',
                'tokenizer.ggml.seperator_token_id', 'tokenizer.ggml.add_bos_token',
                'tokenizer.ggml.add_eos_token']


def hist(values, bins=64):
    h, edges = np.histogram(values, bins=bins)
    return {'edges': [float(x) for x in edges], 'counts': [int(x) for x in h]}


def _bytes_to_unicode():
    bs = list(range(33, 127)) + list(range(161, 173)) + list(range(174, 256))
    cs = bs[:]
    n = 0
    for b in range(256):
        if b not in bs:
            bs.append(b)
            cs.append(256 + n)
            n += 1
    return dict(zip(bs, [chr(c) for c in cs]))


U2B = {v: k for k, v in _bytes_to_unicode().items()}


def dec(tok):
    """把 GPT-2 byte-level 表示还原成可读文本（中文 token 在 GGUF 里是 UTF-8 字节的 Latin-1 映射）"""
    if not isinstance(tok, str):
        return ''
    try:
        return bytes(U2B[c] for c in tok).decode('utf-8')
    except Exception:
        return tok


def is_cjk(s):
    return bool(s) and all('\u4e00' <= ch <= '\u9fff' for ch in s)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else 'qwen2.5-0.5b-instruct-q4_k_m.gguf'
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web', 'data')
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()
    r = GGUFReader(path)
    meta = {k: v for k, t, v in r.meta}
    arch = meta.get('general.architecture', 'llama')
    print('读取 %s  (%.1f MiB, %d 张量, %d KV)' % (
        os.path.basename(path), r.size / 1048576, r.tensor_count, r.kv_count))

    # ---------- 超参 ----------
    hparams = {}
    for k in sorted(meta):
        if k.startswith(arch + '.') and not isinstance(meta[k], list):
            hparams[k[len(arch) + 1:]] = meta[k]

    # ---------- 张量表 / 类型统计 ----------
    tensors = []
    tstat = {}
    layers = {}
    for t in r.tensors:
        tn = type_name(t['type'])
        tensors.append({'name': t['name'], 'type': tn, 'shape': list(t['shape']),
                        'elements': t['n_elements'], 'bytes': t['n_bytes'],
                        'offset': t['offset']})
        s = tstat.setdefault(tn, {'type': tn, 'count': 0, 'elements': 0, 'bytes': 0})
        s['count'] += 1
        s['elements'] += t['n_elements']
        s['bytes'] += t['n_bytes']
        if t['name'].startswith('blk.'):
            parts = t['name'].split('.', 2)
            i = int(parts[1])
            layers.setdefault(i, []).append(
                {'role': parts[2].replace('.weight', '').replace('.bias', ''),
                 'is_bias': parts[2].endswith('.bias'),
                 'name': t['name'], 'type': tn, 'shape': list(t['shape']),
                 'elements': t['n_elements'], 'bytes': t['n_bytes']})
    type_stats = sorted(tstat.values(), key=lambda x: -x['elements'])

    # ---------- 词表 ----------
    tokens = meta.get('tokenizer.ggml.tokens') or []
    ttypes = meta.get('tokenizer.ggml.token_type') or []
    scores = meta.get('tokenizer.ggml.scores') or []
    merges = meta.get('tokenizer.ggml.merges') or []
    type_counts = {}
    len_hist = {}
    byte_tokens = 0
    for i, tok in enumerate(tokens):
        ty = ttypes[i] if i < len(ttypes) else 1
        type_counts[ty] = type_counts.get(ty, 0) + 1
        L = len(tok) if isinstance(tok, str) else 0
        b = min(L, 16)
        len_hist[b] = len_hist.get(b, 0) + 1
        if isinstance(tok, str) and tok.startswith('<0x') and tok.endswith('>'):
            byte_tokens += 1
    vocab_stats = {
        'total': len(tokens),
        'typeCounts': [{'type': TYPE_NAMES.get(k, str(k)), 'count': v}
                       for k, v in sorted(type_counts.items())],
        'lenHist': [{'len': k, 'count': len_hist[k]} for k in sorted(len_hist)],
        'byteTokens': byte_tokens,
        'mergeCount': len(merges),
        'merges': merges[:400],
        'special': {k: meta[k] for k in SPECIAL_KEYS if k in meta},
    }
    print('词表 %d 条, token_type 分布 %s, merges %d' % (
        len(tokens), type_counts, len(merges)))

    # ---------- 嵌入：行范数 / PCA / 8 维压缩向量 ----------
    emb_t = next((t for t in r.tensors if t['name'] in ('token_embd.weight', 'token_embd')), None)
    embed = {'available': False}
    data_sim = None
    data_kb3d = None
    if emb_t is not None:
        ti = time.time()
        arr = dequant(r.tensor_bytes(emb_t), emb_t['n_elements'], emb_t['type'])
        arr = arr.reshape(emb_t['shape']).astype(np.float32)
        print('反量化 %s %s (%s -> float32) %.1fs' % (
            emb_t['name'], list(arr.shape), type_name(emb_t['type']), time.time() - ti))
        norms = np.linalg.norm(arr, axis=1)
        valid = [i for i in range(arr.shape[0])
                 if (ttypes[i] if i < len(ttypes) else 1) not in (3, 5)]
        rng = np.random.default_rng(7)
        sample = rng.choice(np.array(valid), size=min(2000, len(valid)), replace=False)
        X = arr[sample]
        Xc = X - X.mean(0, keepdims=True)
        U, S, Vt = np.linalg.svd(Xc, full_matrices=False)
        pts = Xc @ Vt[:2].T
        var = (S ** 2) / float((S ** 2).sum())
        order = np.argsort(-norms)
        top = []
        for i in order:
            if (ttypes[i] if i < len(ttypes) else 1) in (3, 5):
                continue
            top.append([int(i), tokens[i] if i < len(tokens) else '', round(float(norms[i]), 4)])
            if len(top) >= 120:
                break
        embed = {
            'available': True,
            'tensor': emb_t['name'],
            'quant': type_name(emb_t['type']),
            'shape': list(arr.shape),
            'stats': {'min': float(norms.min()), 'max': float(norms.max()),
                      'mean': float(norms.mean()), 'std': float(norms.std())},
            'normsHist': hist(norms, 64),
            'topTokens': top,
            'pca': {
                'points': [[round(float(pts[k, 0]), 4), round(float(pts[k, 1]), 4), int(sample[k])]
                           for k in range(len(sample))],
                'explained': [round(float(x), 4) for x in var[:8]],
            },
            'normsQ': {
                'quant': 'uint16 linear',
                'n': int(norms.shape[0]),
                'min': 0.0,
                'scale': float(norms.max() / 65535.0) if norms.max() > 0 else 1.0,
                'b64': base64.b64encode(
                    np.clip(norms / max(float(norms.max()), 1e-9) * 65535.0, 0, 65535)
                    .astype('<u2').tobytes()).decode('ascii'),
            },
        }
        print('嵌入范数 mean=%.3f  std=%.3f  PCA 前2主成分解释 %.1f%%' % (
            float(norms.mean()), float(norms.std()), 100 * float(var[:2].sum())))

        # ---------------- 精确近邻索引（种子集上的全 896 维余弦） ----------------
        # PCA 降维会丢掉语义方向（实测 top10 与全维重合 0/10），所以近邻用全维算，
        # 但只覆盖高频 token（id<16384）与 1~2 字中文 token，把结果预计算成前端可查的表。
        Xn = (arr / np.maximum(norms[:, None], 1e-9)).astype(np.float32)
        seeds = []
        for i in range(arr.shape[0]):
            ty = ttypes[i] if i < len(ttypes) else 1
            if ty != 1:
                continue
            if i < 16384:
                seeds.append(i)
                continue
            d = dec(tokens[i] if i < len(tokens) else '')
            if 1 <= len(d) <= 2 and is_cjk(d):
                seeds.append(i)
        topk = 6
        S = np.ascontiguousarray(Xn[seeds])
        sim_ids, sim_rows = [], []
        ts = time.time()
        for s in range(0, len(seeds), 512):
            chunk = S[s:s + 512]
            sims = chunk @ Xn.T
            for ri in range(chunk.shape[0]):
                row = sims[ri]
                gid = seeds[s + ri]
                row[gid] = -2.0
                part = np.argpartition(-row, topk)[:topk]
                part = part[np.argsort(-row[part])]
                sim_ids.append(int(gid))
                sim_rows.append([[int(p), round(float(row[p]), 3)] for p in part])
        sim = {'topk': topk, 'seeds': len(seeds),
               'coverage': 'id<16384 的高频 token + 1~2 字中文 token，全 896 维精确余弦',
               'ids': sim_ids, 'rows': sim_rows}
        print('精确近邻索引: %d 个种子 × top%d，耗时 %.1fs（%.1f MiB）' % (
            len(seeds), topk, time.time() - ts,
            len(json.dumps(sim_rows, separators=(',', ':'))) / 1048576))
        del Xn, S
        data_sim = sim

        # ---------------- 三维知识体系（3D 点云 + 三个维度标签） ----------------
        # 维度 1 语言体系：中文 / 英文 / 数字 / 符号 / 代码片段 / 特殊标记
        # 维度 2 结构层级：单字 -> 短词 -> 词 -> 短语（按字符长度分档）
        # 维度 3 语义坐标：embedding 的前 3 主成分（真实 896 维 PCA 投影）
        def lang_of(idx):
            ty = ttypes[idx] if idx < len(ttypes) else 1
            s = dec(tokens[idx] if idx < len(tokens) else '')
            if ty in (2, 3, 4, 5) or (s.startswith('<') and s.endswith('>')):
                return 5
            core = s.strip()
            if not core:
                return 3
            if all('\u4e00' <= ch <= '\u9fff' for ch in core):
                return 0
            if all(ch.isdigit() or ch in '.,' for ch in core):
                return 2
            if all((ch.isascii() and ch.isalpha()) for ch in core):
                return 1
            if any(ch in '(){}[]<>=+-*/\\|_$#@!~^&;:' for ch in core) and any(ch.isalnum() for ch in core):
                return 4
            if any(ch.isalpha() for ch in core):
                return 1
            return 3

        def bucket_of(s):
            L = len(s)
            if L <= 1:
                return 0
            if L <= 3:
                return 1
            if L <= 6:
                return 2
            return 3

        LANGS = ['中文', '英文', '数字', '符号', '代码片段', '特殊标记']
        BUCKETS = ['单字 / 单字符', '短词（2~3）', '词（4~6）', '短语（7+）']
        mu_all = arr.mean(0, keepdims=True)
        rng3 = np.random.default_rng(11)
        pool = np.array([i for i in range(arr.shape[0])
                         if (ttypes[i] if i < len(ttypes) else 1) not in (5,)])
        pick = rng3.choice(pool, size=min(4000, len(pool)), replace=False)
        P3 = ((arr[pick] - mu_all) @ Vt[:3].T).astype(np.float32)
        P3 /= np.maximum(np.abs(P3).max(0, keepdims=True), 1e-6)

        def kmeans(X, k, iters=30, seed=5):
            rg = np.random.default_rng(seed)
            C = X[rg.choice(len(X), k, replace=False)].copy()
            lab = np.zeros(len(X), dtype=np.int32)
            for _ in range(iters):
                d = ((X[:, None, :] - C[None, :, :]) ** 2).sum(2)
                lab = d.argmin(1).astype(np.int32)
                for j in range(k):
                    m = lab == j
                    if m.any():
                        C[j] = X[m].mean(0)
            return lab

        clusters = kmeans(P3, 8)
        points = []
        lang_counts = {}
        bucket_counts = {}
        for i in range(arr.shape[0]):
            lg = lang_of(i)
            lang_counts[lg] = lang_counts.get(lg, 0) + 1
            bucket_counts[bucket_of(dec(tokens[i] if i < len(tokens) else ''))] = \
                bucket_counts.get(bucket_of(dec(tokens[i] if i < len(tokens) else '')), 0) + 1
        for k in range(len(pick)):
            idx = int(pick[k])
            s = dec(tokens[idx] if idx < len(tokens) else '')
            points.append([round(float(P3[k, 0]), 4), round(float(P3[k, 1]), 4), round(float(P3[k, 2]), 4),
                           idx, lang_of(idx), bucket_of(s), round(float(norms[idx]), 4), int(clusters[k])])
        kb3d = {
            'n': len(points),
            'langs': LANGS,
            'buckets': BUCKETS,
            'langCounts': [{'name': LANGS[k], 'count': lang_counts.get(k, 0)} for k in range(len(LANGS))],
            'bucketCounts': [{'name': BUCKETS[k], 'count': bucket_counts.get(k, 0)} for k in range(len(BUCKETS))],
            'clusterCounts': [{'id': c, 'count': int((clusters == c).sum())} for c in range(8)],
            'explained': [round(float(x), 4) for x in var[:3]],
            'points': points,
        }
        print('三维知识体系: %d 点，语言分布 %s' % (
            len(points), {LANGS[k]: v for k, v in sorted(lang_counts.items())}))
        data_kb3d = kb3d
        del arr

    # ---------- 元数据 KV（长数组折叠成摘要） ----------
    kv = []
    for k, t, v in r.meta:
        if isinstance(v, list):
            if len(v) <= 6:
                rep = v
            else:
                rep = (v[:3] + ['… 共 %d 项' % len(v)])
        else:
            rep = v
        kv.append({'key': k, 'type': {8: 'STRING', 9: 'ARRAY'}.get(t, str(t)),
                   'value': rep, 'size': len(v) if isinstance(v, list) else 1})

    data = {
        'generated': time.strftime('%Y-%m-%d %H:%M:%S'),
        'file': os.path.basename(path),
        'fileSize': r.size,
        'ggufVersion': r.version,
        'alignment': r.alignment,
        'dataStart': r.data_start,
        'arch': arch,
        'name': meta.get('general.name', ''),
        'quantVersion': meta.get('general.quantization_version'),
        'fileType': meta.get('general.file_type'),
        'hparams': hparams,
        'kv': kv,
        'kvCount': r.kv_count,
        'tensors': tensors,
        'tensorCount': len(tensors),
        'typeStats': type_stats,
        'totalParams': sum(t['elements'] for t in tensors),
        'totalBytes': sum(t['bytes'] for t in tensors),
        'layerCount': max(layers) + 1 if layers else 0,
        'layers': [{'index': i, 'tensors': sorted(layers[i], key=lambda x: x['name']),
                    'params': sum(x['elements'] for x in layers[i])} for i in sorted(layers)],
        'vocab': {'tokens': tokens, 'types': ttypes, 'scores': [round(float(s), 4) for s in scores[:2000]]},
        'vocabStats': vocab_stats,
        'embed': embed,
        'sim': data_sim,
        'kb3d': data_kb3d,
    }
    js = 'window.MODEL_DATA = ' + json.dumps(data, ensure_ascii=False, separators=(',', ':')) + ';\n'
    out = os.path.join(out_dir, 'model.js')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(js)
    print('写出 %s  (%.2f MiB)  总耗时 %.1fs' % (out, len(js.encode('utf-8')) / 1048576, time.time() - t0))


if __name__ == '__main__':
    main()
