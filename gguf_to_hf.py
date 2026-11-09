#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gguf_to_hf.py —— 把 GGUF 解开成 HuggingFace 目录（model.safetensors + config.json）

  python gguf_to_hf.py model.gguf  ./hf_out
  python gguf_to_hf.py model.gguf  ./hf_out --dtype f16 --keep-names
  python gguf_to_hf.py model.gguf  ./hf_out --dtype f32

张量名按 llama.cpp 命名映射回 transformers 命名（llama/qwen2/qwen3 等同构模型通用）。
"""
import argparse
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gguf_dump import GGUFReader, dequant, type_name, human  # noqa: E402


def np_():
    try:
        import numpy as np
        return np
    except ImportError:
        raise SystemExit('需要 numpy:  python -m pip install numpy')


MAP_BLOCK = {
    'attn_norm.weight': 'input_layernorm.weight',
    'attn_q.weight': 'self_attn.q_proj.weight',
    'attn_k.weight': 'self_attn.k_proj.weight',
    'attn_v.weight': 'self_attn.v_proj.weight',
    'attn_output.weight': 'self_attn.o_proj.weight',
    'attn_q.bias': 'self_attn.q_proj.bias',
    'attn_k.bias': 'self_attn.k_proj.bias',
    'attn_v.bias': 'self_attn.v_proj.bias',
    'attn_output.bias': 'self_attn.o_proj.bias',
    'ffn_norm.weight': 'post_attention_layernorm.weight',
    'ffn_gate.weight': 'mlp.gate_proj.weight',
    'ffn_up.weight': 'mlp.up_proj.weight',
    'ffn_down.weight': 'mlp.down_proj.weight',
    'ffn_gate_inp.weight': 'mlp.gate.weight',
    'attn_q_norm.weight': 'self_attn.q_norm.weight',
    'attn_k_norm.weight': 'self_attn.k_norm.weight',
}
MAP_GLOBAL = {
    'token_embd.weight': 'model.embed_tokens.weight',
    'output_norm.weight': 'model.norm.weight',
    'output.weight': 'lm_head.weight',
}


def hf_name(name):
    if name in MAP_GLOBAL:
        return MAP_GLOBAL[name]
    if name.startswith('blk.'):
        rest = name.split('.', 2)
        if len(rest) == 3:
            idx, tail = rest[1], rest[2]
            if tail in MAP_BLOCK:
                return 'model.layers.%s.%s' % (idx, MAP_BLOCK[tail])
    return name


def cast(arr, dt):
    np = np_()
    if dt == 'f32':
        return arr.astype(np.float32), 'F32'
    if dt == 'f16':
        return arr.astype(np.float16), 'F16'
    if dt == 'bf16':
        u = arr.astype(np.float32).view(np.uint32) >> 16
        return u.astype(np.uint16), 'BF16'
    raise SystemExit('未知 dtype %s' % dt)


def write_safetensors(path, entries):
    """entries: list of (name, dtype_str, shape_list, ndarray)；分块写入避免占内存"""
    hdr = {}
    off = 0
    for name, dt, shape, _ in entries:
        n = 1
        for d in shape:
            n *= d
        nbytes = n * {'F32': 4, 'F16': 2, 'BF16': 2}[dt]
        hdr[name] = {'dtype': dt, 'shape': shape, 'data_offsets': [off, off + nbytes]}
        off += nbytes
    blob = json.dumps(hdr, separators=(',', ':')).encode('utf-8')
    blob += b' ' * ((8 - len(blob) % 8) % 8)
    with open(path, 'wb') as f:
        f.write(struct.pack('<Q', len(blob)))
        f.write(blob)
        for name, dt, shape, arr in entries:
            f.write(arr.tobytes(order='C'))
    return off


def build_config(meta):
    g = lambda k, d=None: meta.get(k, d)
    arch = g('general.architecture', 'llama')
    p = lambda k: g('%s.%s' % (arch, k))
    cfg = {
        'architectures': ['LlamaForCausalLM'],
        'model_type': 'llama',
        'hidden_size': p('embedding_length'),
        'intermediate_size': p('feed_forward_length'),
        'num_hidden_layers': p('block_count'),
        'num_attention_heads': p('attention.head_count'),
        'num_key_value_heads': p('attention.head_count_kv') or p('attention.head_count'),
        'max_position_embeddings': p('context_length'),
        'rms_norm_eps': p('attention.layer_norm_rms_epsilon'),
        'vocab_size': meta.get('tokenizer.ggml.tokens') and len(meta['tokenizer.ggml.tokens']),
        'hidden_act': 'silu',
        'tie_word_embeddings': False,
        'torch_dtype': 'float16',
    }
    rb = p('rope.freq_base')
    if rb:
        cfg['rope_theta'] = float(rb)
    return {k: v for k, v in cfg.items() if v is not None}


def main():
    ap = argparse.ArgumentParser(description='GGUF -> HF safetensors 目录')
    ap.add_argument('gguf')
    ap.add_argument('outdir')
    ap.add_argument('--dtype', choices=['f16', 'f32', 'bf16'], default='f16')
    ap.add_argument('--keep-names', action='store_true')
    ap.add_argument('--max-shard', type=int, default=0, help='单文件最大字节，超过则分片 (默认 0=不分片)')
    a = ap.parse_args()
    np = np_()
    r = GGUFReader(a.gguf)
    meta = {k: v for k, t, v in r.meta}
    os.makedirs(a.outdir, exist_ok=True)

    entries = []
    total = 0
    for t in r.tensors:
        buf = r.tensor_bytes(t)
        arr = dequant(buf, t['n_elements'], t['type']).reshape(t['shape'])
        name = t['name'] if a.keep_names else hf_name(t['name'])
        out, dt = cast(arr, a.dtype)
        entries.append((name, dt, list(t['shape']), out))
        total += out.size
        print('%-34s -> %-46s %-6s %s' % (t['name'], name, dt, list(t['shape'])))

    if a.max_shard and sum(e[3].nbytes for e in entries) > a.max_shard:
        shards, cur, cur_bytes, i = [], [], 0, 1
        for e in entries:
            if cur and cur_bytes + e[3].nbytes > a.max_shard:
                shards.append(('model-%05d-of-%05d.safetensors' % (i, 0), cur))
                cur, cur_bytes, i = [], 0
            cur.append(e)
            cur_bytes += e[3].nbytes
        if cur:
            shards.append(('model-%05d-of-%05d.safetensors' % (i, 0), cur))
        total_shards = len(shards)
        weight_map = {}
        for j, (fn, ents) in enumerate(shards, 1):
            real = 'model-%05d-of-%05d.safetensors' % (j, total_shards)
            write_safetensors(os.path.join(a.outdir, real), ents)
            for e in ents:
                weight_map[e[0]] = real
        with open(os.path.join(a.outdir, 'model.safetensors.index.json'), 'w', encoding='utf-8') as f:
            json.dump({'metadata': {'total_size': sum(e[3].nbytes for e in entries)},
                       'weight_map': weight_map}, f, indent=1)
        print('\n写出 %d 个分片 + index.json' % total_shards)
    else:
        path = os.path.join(a.outdir, 'model.safetensors')
        nbytes = write_safetensors(path, entries)
        print('\n写出 %s (%s)' % (path, human(nbytes)))

    cfg = build_config(meta)
    with open(os.path.join(a.outdir, 'config.json'), 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2)
    print('写出 config.json: %s' % json.dumps(cfg, ensure_ascii=False))
    print('参数合计: %s' % '{:,}'.format(total))


if __name__ == '__main__':
    main()
