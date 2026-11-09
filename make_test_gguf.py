#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成一个含多种量化类型的合成 GGUF，用来验证 gguf_dump.py 的反量化正确性。
python make_test_gguf.py out.gguf
"""
import struct
import sys
import numpy as np

# (name, ggml_type_id, block_elems, block_bytes, n_blocks)
SPEC = [
    ('t.f32', 0, 1, 4, 10),
    ('t.f16', 1, 1, 2, 10),
    ('t.bf16', 30, 1, 2, 10),
    ('t.q4_0', 2, 32, 18, 4),
    ('t.q4_1', 3, 32, 20, 4),
    ('t.q5_0', 6, 32, 22, 4),
    ('t.q5_1', 7, 32, 24, 4),
    ('t.q8_0', 8, 32, 34, 4),
    ('t.iq4_nl', 20, 32, 18, 4),
    ('t.q2_k', 10, 256, 84, 2),
    ('t.q3_k', 11, 256, 110, 2),
    ('t.q4_k', 12, 256, 144, 2),
    ('t.q5_k', 13, 256, 176, 2),
    ('t.q6_k', 14, 256, 210, 2),
    ('t.q8_k', 15, 256, 292, 2),
]


def s(x):
    b = x.encode('utf-8')
    return struct.pack('<Q', len(b)) + b


def fix_fp16(data, positions):
    """把 fp16 字段写成 1.0 / 0.5，避免随机字节产生 inf/nan"""
    for off, val in positions:
        data[off:off + 2] = struct.pack('<H', val)


def build():
    rng = np.random.default_rng(1234)
    kvs = []
    kvs.append(('general.architecture', 8, s('llama')))
    kvs.append(('general.name', 8, s('synthetic-test')))
    kvs.append(('llama.block_count', 4, struct.pack('<I', 2)))
    kvs.append(('general.alignment', 4, struct.pack('<I', 32)))
    # 字符串数组
    toks = ['<unk>', '<s>', '</s>']
    arr = struct.pack('<I', 8) + struct.pack('<Q', len(toks))
    for t in toks:
        arr += s(t)
    kvs.append(('tokenizer.ggml.tokens', 9, arr))

    tensors = []
    data_parts = []
    offset = 0
    for name, tid, be, bb, nblk in SPEC:
        n = be * nblk
        buf = bytearray(rng.integers(0, 256, size=nblk * bb, dtype=np.uint8).tobytes())
        if tid in (2, 6, 8, 20):
            for i in range(nblk):
                fix_fp16(buf, [(i * bb, 0x3C00)])
        elif tid in (3, 7):
            for i in range(nblk):
                fix_fp16(buf, [(i * bb, 0x3C00), (i * bb + 2, 0x0000)])
        elif tid == 8:
            for i in range(nblk):
                fix_fp16(buf, [(i * bb, 0x3C00)])
        elif tid == 10:
            for i in range(nblk):
                fix_fp16(buf, [(i * bb + 80, 0x3C00), (i * bb + 82, 0x3800)])
        elif tid == 11:
            for i in range(nblk):
                fix_fp16(buf, [(i * bb + 108, 0x3C00)])
        elif tid in (12, 13):
            for i in range(nblk):
                fix_fp16(buf, [(i * bb, 0x3C00), (i * bb + 2, 0x3800)])
        elif tid == 14:
            for i in range(nblk):
                fix_fp16(buf, [(i * bb + 208, 0x3C00)])
        elif tid == 15:
            for i in range(nblk):
                buf[i * bb:i * bb + 4] = struct.pack('<f', 1.0)
        tensors.append((name, tid, n, offset))
        data_parts.append(bytes(buf))
        offset += len(buf)
        if offset % 32:
            pad = 32 - offset % 32
            data_parts.append(b'\x00' * pad)
            offset += pad

    out = bytearray()
    out += b'GGUF' + struct.pack('<I', 3)
    out += struct.pack('<Q', len(tensors)) + struct.pack('<Q', len(kvs))
    for key, vtype, payload in kvs:
        out += s(key) + struct.pack('<I', vtype) + payload
    for name, tid, n, off in tensors:
        out += s(name) + struct.pack('<I', 1) + struct.pack('<Q', n)
        out += struct.pack('<I', tid) + struct.pack('<Q', off)
    # 对齐到 32
    while len(out) % 32:
        out += b'\x00'
    for p in data_parts:
        out += p
    return bytes(out), tensors


if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else 'synthetic.gguf'
    blob, tensors = build()
    with open(path, 'wb') as f:
        f.write(blob)
    print('写出 %s (%d bytes), %d 个张量' % (path, len(blob), len(tensors)))
