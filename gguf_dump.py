#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gguf_dump.py —— GGUF（HuggingFace 上 .gguf 量化权重）解析 / 查看 / 导出
零第三方依赖；只有 --extract / --stats 需要 numpy。

用法:
  python gguf_dump.py model.gguf                          # 元数据 + 张量表
  python gguf_dump.py model.gguf --json out.json           # 结构化导出
  python gguf_dump.py model.gguf --meta tokenizer.ggml.tokens
  python gguf_dump.py model.gguf --tensor blk.0.attn_q.weight --stats
  python gguf_dump.py model.gguf --extract out             # 每个张量 -> out/<name>.npy (反量化 fp32)
  python gguf_dump.py model.gguf --extract out --raw       # 保留原始量化块字节
"""
import argparse
import json
import os
import struct
import sys

GGUF_MAGIC = b"GGUF"

# ---- metadata value types ----
T_UINT8, T_INT8, T_UINT16, T_INT16, T_UINT32, T_INT32, T_FLOAT32, T_BOOL, \
    T_STRING, T_ARRAY, T_UINT64, T_INT64, T_FLOAT64 = range(13)

VAL_FMT = {0: '<B', 1: '<b', 2: '<H', 3: '<h', 4: '<I', 5: '<i',
           6: '<f', 7: '<?', 10: '<Q', 11: '<q', 12: '<d'}
TYPE_NAME = {0: 'UINT8', 1: 'INT8', 2: 'UINT16', 3: 'INT16', 4: 'UINT32',
             5: 'INT32', 6: 'FLOAT32', 7: 'BOOL', 8: 'STRING', 9: 'ARRAY',
             10: 'UINT64', 11: 'INT64', 12: 'FLOAT64'}

# ---- ggml tensor types: id -> (name, block_elems, block_bytes) ----
GGML_TYPES = {
    0: ('F32', 1, 4), 1: ('F16', 1, 2), 2: ('Q4_0', 32, 18), 3: ('Q4_1', 32, 20),
    6: ('Q5_0', 32, 22), 7: ('Q5_1', 32, 24), 8: ('Q8_0', 32, 34), 9: ('Q8_1', 32, 36),
    10: ('Q2_K', 256, 84), 11: ('Q3_K', 256, 110), 12: ('Q4_K', 256, 144),
    13: ('Q5_K', 256, 176), 14: ('Q6_K', 256, 210), 15: ('Q8_K', 256, 292),
    16: ('IQ2_XXS', 256, 66), 17: ('IQ2_XS', 256, 74), 18: ('IQ3_XXS', 256, 98),
    19: ('IQ1_S', 256, 50), 20: ('IQ4_NL', 32, 18), 21: ('IQ3_S', 256, 110),
    22: ('IQ2_S', 256, 82), 23: ('IQ4_XS', 256, 136), 24: ('I8', 1, 1),
    25: ('I16', 1, 2), 26: ('I32', 1, 4), 27: ('I64', 1, 8), 28: ('F64', 1, 8),
    29: ('IQ1_M', 256, 56), 30: ('BF16', 1, 2), 34: ('TQ1_0', 256, 54),
    35: ('TQ2_0', 256, 66), 39: ('MXFP4', 32, 17),
}


def type_info(tid):
    return GGML_TYPES.get(tid, ('UNKNOWN_%d' % tid, 1, 1))


def type_name(tid):
    return type_info(tid)[0]


class GGUFReader:
    def __init__(self, path):
        self.path = path
        self.f = open(path, 'rb')
        magic = self.f.read(4)
        if magic != GGUF_MAGIC:
            raise SystemExit('不是 GGUF 文件: magic=%r' % magic)
        self.version = self.u32()
        if self.version not in (1, 2, 3):
            raise SystemExit('未知 GGUF 版本: %d' % self.version)
        self.tensor_count = self.u64()
        self.kv_count = self.u64()
        self.meta = []
        for _ in range(self.kv_count):
            key = self.string()
            vtype = self.u32()
            self.meta.append((key, vtype, self.value(vtype)))
        self.tensors = []
        for _ in range(self.tensor_count):
            name = self.string()
            n_dims = self.u32()
            dims = [self.u64() for _ in range(n_dims)]
            ttype = self.u32()
            offset = self.u64()
            self.tensors.append({'name': name, 'dims': dims, 'dims_gguf': list(dims),
                                 'shape': tuple(reversed(dims)), 'type': ttype,
                                 'offset': offset})
        self.alignment = self.meta_get('general.alignment', 32) or 32
        hdr_end = self.f.tell()
        self.data_start = (hdr_end + self.alignment - 1) // self.alignment * self.alignment
        self.size = os.path.getsize(path)
        for t in self.tensors:
            n = 1
            for d in t['dims']:
                n *= d
            _, be, bb = type_info(t['type'])
            t['n_elements'] = n
            t['n_bytes'] = n // be * bb if be else 0
            t['params'] = n

    # --- primitives ---
    def raw(self, n):
        b = self.f.read(n)
        if len(b) != n:
            raise SystemExit('文件被截断（需要 %d 字节，只读到 %d）' % (n, len(b)))
        return b

    def u32(self):
        return struct.unpack('<I', self.raw(4))[0]

    def u64(self):
        return struct.unpack('<Q', self.raw(8))[0]

    def string(self):
        n = self.u64()
        return self.raw(n).decode('utf-8', 'replace')

    def value(self, vtype):
        if vtype == T_STRING:
            return self.string()
        if vtype == T_ARRAY:
            atype = self.u32()
            n = self.u64()
            return [self.value(atype) for _ in range(n)]
        fmt = VAL_FMT.get(vtype)
        if fmt is None:
            raise SystemExit('未知 metadata 类型 %d' % vtype)
        return struct.unpack(fmt, self.raw(struct.calcsize(fmt)))[0]

    def meta_get(self, key, default=None):
        for k, _, v in self.meta:
            if k == key:
                return v
        return default

    def tensor_bytes(self, t):
        self.f.seek(self.data_start + t['offset'])
        return self.raw(t['n_bytes'])


# ======================= 反量化 (numpy) =======================
def _np():
    try:
        import numpy as np
        return np
    except ImportError:
        raise SystemExit('需要 numpy:  python -m pip install numpy')


def _f16(cols):
    np = _np()
    return np.ascontiguousarray(cols).view(np.float16).astype(np.float32)


def _f16_u8(a):
    """把 uint8 数组的最后一维 2 字节当 fp16 -> float32（shape 少一维）"""
    np = _np()
    return a.copy().view(np.float16).astype(np.float32)


def dequant(buf, n, ttype):
    """把某种 ggml 量化块的原始字节解成 float32 向量（n 个元素）。"""
    np = _np()
    name, be, bb = type_info(ttype)

    if ttype == 0:      # F32
        return np.frombuffer(buf, dtype='<f4').astype(np.float32)
    if ttype == 1:      # F16
        return np.frombuffer(buf, dtype='<f2').astype(np.float32)
    if ttype == 30:     # BF16
        u = np.frombuffer(buf, dtype='<u2').astype(np.uint32) << 16
        return u.view(np.float32)
    if ttype == 24:     # I8
        return np.frombuffer(buf, dtype=np.int8).astype(np.float32)
    if ttype == 25:     # I16
        return np.frombuffer(buf, dtype='<i2').astype(np.float32)
    if ttype == 26:     # I32
        return np.frombuffer(buf, dtype='<i4').astype(np.float32)
    if ttype == 27:     # I64
        return np.frombuffer(buf, dtype='<i8').astype(np.float32)
    if ttype == 28:     # F64
        return np.frombuffer(buf, dtype='<f8').astype(np.float32)

    if be == 0 or bb == 0:
        raise ValueError('未知类型 %d' % ttype)
    nb = n // be
    a = np.frombuffer(buf, dtype=np.uint8)[: nb * bb].reshape(nb, bb)

    if ttype == 2:      # Q4_0
        d = _f16_u8(a[:, 0:2]).reshape(nb, 1)
        qs = a[:, 2:18]
        out = np.empty((nb, 32), dtype=np.float32)
        out[:, :16] = (qs & 0x0F).astype(np.float32) * d - 8.0 * d
        out[:, 16:] = (qs >> 4).astype(np.float32) * d - 8.0 * d
        return out.reshape(-1)
    if ttype == 3:      # Q4_1
        d = _f16_u8(a[:, 0:2]).reshape(nb, 1)
        m = _f16_u8(a[:, 2:4]).reshape(nb, 1)
        qs = a[:, 4:20]
        out = np.empty((nb, 32), dtype=np.float32)
        out[:, :16] = (qs & 0x0F).astype(np.float32) * d + m
        out[:, 16:] = (qs >> 4).astype(np.float32) * d + m
        return out.reshape(-1)
    if ttype in (6, 7):  # Q5_0 / Q5_1
        d = _f16_u8(a[:, 0:2]).reshape(nb, 1)
        if ttype == 7:
            m = _f16_u8(a[:, 2:4]).reshape(nb, 1)
            qh = a[:, 4:8]
            qs = a[:, 8:24]
        else:
            m = None
            qh = a[:, 2:6]
            qs = a[:, 6:22]
        bits = np.unpackbits(qh, axis=1, bitorder='little').astype(np.int32)
        lo = (qs & 0x0F).astype(np.int32) | (bits[:, :16] << 4)
        hi = (qs >> 4).astype(np.int32) | (bits[:, 16:] << 4)
        out = np.empty((nb, 32), dtype=np.float32)
        if ttype == 6:
            out[:, :16] = lo.astype(np.float32) * d - 16.0 * d
            out[:, 16:] = hi.astype(np.float32) * d - 16.0 * d
        else:
            out[:, :16] = lo.astype(np.float32) * d + m
            out[:, 16:] = hi.astype(np.float32) * d + m
        return out.reshape(-1)

    if ttype == 8:      # Q8_0
        d = _f16_u8(a[:, 0:2]).reshape(nb, 1)
        q = a[:, 2:34].view(np.int8).astype(np.float32)
        return (q * d).reshape(-1)
    if ttype == 20:     # IQ4_NL (e2m1 表)
        np_ = np
        kvalues = np_.array([-127, -104, -83, -65, -49, -35, -22, -10,
                             1, 13, 25, 38, 53, 69, 89, 113], dtype=np.float32)
        d = _f16_u8(a[:, 0:2]).reshape(nb, 1)
        qs = a[:, 2:18]
        out = np_.empty((nb, 32), dtype=np_.float32)
        out[:, :16] = kvalues[qs & 0x0F] * d
        out[:, 16:] = kvalues[qs >> 4] * d
        return out.reshape(-1)

    if ttype == 10:     # Q2_K
        sc = a[:, 0:16]
        qs = a[:, 16:80]
        d = _f16_u8(a[:, 80:82]).reshape(nb)
        dmin = _f16_u8(a[:, 82:84]).reshape(nb)
        out = np.empty((nb, 256), dtype=np.float32)
        for blk in range(2):
            qb = qs[:, blk * 32:(blk + 1) * 32]
            scb = sc[:, blk * 8:(blk + 1) * 8]
            for j in range(4):
                for half in range(2):
                    s = scb[:, j * 2 + half].astype(np.int32)
                    dl = (d * (s & 0xF)).astype(np.float32).reshape(nb, 1)
                    ml = (dmin * (s >> 4)).astype(np.float32).reshape(nb, 1)
                    src = qb[:, half * 16:(half + 1) * 16]
                    v = ((src >> (2 * j)) & 3).astype(np.float32)
                    out[:, blk * 128 + j * 32 + half * 16:
                          blk * 128 + j * 32 + half * 16 + 16] = dl * v - ml
        return out.reshape(-1)

    if ttype == 11:     # Q3_K
        hm = a[:, 0:32]
        qs = a[:, 32:96]
        raw = a[:, 96:108]
        d = _f16_u8(a[:, 108:110]).reshape(nb, 1)
        b = np.zeros((nb, 16), dtype=np.uint8)
        b[:, 0:12] = raw
        u = b.view(np.uint32)
        tmp = u[:, 2].copy()
        u2 = u.copy()
        k1 = np.uint32(0x03030303)
        k2 = np.uint32(0x0f0f0f0f)
        u2[:, 2] = ((u[:, 0] >> np.uint32(4)) & k2) | (((tmp >> np.uint32(4)) & k1) << np.uint32(4))
        u2[:, 3] = ((u[:, 1] >> np.uint32(4)) & k2) | (((tmp >> np.uint32(6)) & k1) << np.uint32(4))
        u2[:, 0] = (u[:, 0] & k2) | (((tmp >> np.uint32(0)) & k1) << np.uint32(4))
        u2[:, 1] = (u[:, 1] & k2) | (((tmp >> np.uint32(2)) & k1) << np.uint32(4))
        sc = u2.view(np.int8).astype(np.int32) - 32
        out = np.empty((nb, 256), dtype=np.float32)
        for blk in range(2):
            qb = qs[:, blk * 32:(blk + 1) * 32]
            hb = hm          # hmask 32 字节被整个 256 块的 8 个 bit 层共用
            for j in range(4):
                m = np.uint8(1 << (blk * 4 + j))
                s0 = sc[:, blk * 8 + j * 2 + 0].astype(np.float32)
                s1 = sc[:, blk * 8 + j * 2 + 1].astype(np.float32)
                for half in range(2):
                    src = qb[:, half * 16:(half + 1) * 16]
                    hv = hb[:, half * 16:(half + 1) * 16]
                    v = ((src >> (2 * j)) & 3).astype(np.int32)
                    v = v - np.where((hv & m) != 0, 0, 4)
                    sv = (s0 if half == 0 else s1).reshape(nb, 1)
                    out[:, blk * 128 + j * 32 + half * 16:
                          blk * 128 + j * 32 + half * 16 + 16] = (d * sv) * v.astype(np.float32)
        return out.reshape(-1)

    if ttype == 12:     # Q4_K
        d = _f16_u8(a[:, 0:2]).reshape(nb, 1)
        dmin = _f16_u8(a[:, 2:4]).reshape(nb, 1)
        scales = a[:, 4:16]
        qs = a[:, 16:144]
        sc = np.zeros((nb, 8), dtype=np.int32)
        mn = np.zeros((nb, 8), dtype=np.int32)
        for j in range(4):
            sc[:, j] = scales[:, j] & 63
            mn[:, j] = scales[:, j + 4] & 63
        for j in range(4, 8):
            sc[:, j] = (scales[:, j + 4] & 0x0F) | ((scales[:, j - 4] >> 6) << 4)
            mn[:, j] = (scales[:, j + 4] >> 4) | ((scales[:, j] >> 6) << 4)
        lo = (qs & 0x0F).astype(np.float32)
        hi = (qs >> 4).astype(np.float32)
        out = np.empty((nb, 256), dtype=np.float32)
        for g in range(4):
            sl = slice(g * 32, (g + 1) * 32)
            d0 = (d * sc[:, 2 * g].reshape(nb, 1)).astype(np.float32)
            m0 = (dmin * mn[:, 2 * g].reshape(nb, 1)).astype(np.float32)
            d1 = (d * sc[:, 2 * g + 1].reshape(nb, 1)).astype(np.float32)
            m1 = (dmin * mn[:, 2 * g + 1].reshape(nb, 1)).astype(np.float32)
            out[:, g * 64:g * 64 + 32] = lo[:, sl] * d0 - m0
            out[:, g * 64 + 32:g * 64 + 64] = hi[:, sl] * d1 - m1
        return out.reshape(-1)

    if ttype == 13:     # Q5_K
        d = _f16_u8(a[:, 0:2]).reshape(nb, 1)
        dmin = _f16_u8(a[:, 2:4]).reshape(nb, 1)
        scales = a[:, 4:16]
        qh = a[:, 16:48]
        qs = a[:, 48:176]
        sc = np.zeros((nb, 8), dtype=np.int32)
        mn = np.zeros((nb, 8), dtype=np.int32)
        for j in range(4):
            sc[:, j] = scales[:, j] & 63
            mn[:, j] = scales[:, j + 4] & 63
        for j in range(4, 8):
            sc[:, j] = (scales[:, j + 4] & 0x0F) | ((scales[:, j - 4] >> 6) << 4)
            mn[:, j] = (scales[:, j + 4] >> 4) | ((scales[:, j] >> 6) << 4)
        lo = (qs & 0x0F).astype(np.int32)
        hi = (qs >> 4).astype(np.int32)
        out = np.empty((nb, 256), dtype=np.float32)
        for g in range(4):
            sl = slice(g * 32, (g + 1) * 32)
            u1, u2 = 1 << (2 * g), 2 << (2 * g)
            lo_g = lo[:, sl] + np.where((qh & u1) != 0, 16, 0)
            hi_g = hi[:, sl] + np.where((qh & u2) != 0, 16, 0)
            d0 = (d * sc[:, 2 * g].reshape(nb, 1)).astype(np.float32)
            m0 = (dmin * mn[:, 2 * g].reshape(nb, 1)).astype(np.float32)
            d1 = (d * sc[:, 2 * g + 1].reshape(nb, 1)).astype(np.float32)
            m1 = (dmin * mn[:, 2 * g + 1].reshape(nb, 1)).astype(np.float32)
            out[:, g * 64:g * 64 + 32] = lo_g.astype(np.float32) * d0 - m0
            out[:, g * 64 + 32:g * 64 + 64] = hi_g.astype(np.float32) * d1 - m1
        return out.reshape(-1)

    if ttype == 14:     # Q6_K
        ql = a[:, 0:128]
        qh = a[:, 128:192]
        sct = a[:, 192:208].view(np.int8).astype(np.float32)
        d = _f16_u8(a[:, 208:210]).reshape(nb, 1)
        out = np.empty((nb, 256), dtype=np.float32)
        for blk in range(2):
            qlb = ql[:, blk * 64:(blk + 1) * 64].astype(np.int32)
            qhb = qh[:, blk * 32:(blk + 1) * 32].astype(np.int32)
            scb = sct[:, blk * 8:(blk + 1) * 8]
            for l in range(32):
                s = l // 16
                q1 = ((qlb[:, l] & 0xF) | (((qhb[:, l] >> 0) & 3) << 4)) - 32
                q2 = ((qlb[:, l + 32] & 0xF) | (((qhb[:, l] >> 2) & 3) << 4)) - 32
                q3 = ((qlb[:, l] >> 4) | (((qhb[:, l] >> 4) & 3) << 4)) - 32
                q4 = ((qlb[:, l + 32] >> 4) | (((qhb[:, l] >> 6) & 3) << 4)) - 32
                base = blk * 128 + l
                out[:, base + 0] = d[:, 0] * scb[:, s + 0] * q1.astype(np.float32)
                out[:, base + 32] = d[:, 0] * scb[:, s + 2] * q2.astype(np.float32)
                out[:, base + 64] = d[:, 0] * scb[:, s + 4] * q3.astype(np.float32)
                out[:, base + 96] = d[:, 0] * scb[:, s + 6] * q4.astype(np.float32)
        return out.reshape(-1)

    if ttype == 15:     # Q8_K
        d = a[:, 0:4].copy().view('<f4').astype(np.float32)
        q = a[:, 4:260].view(np.int8).astype(np.float32)
        return (q * d).reshape(-1)

    raise ValueError('未实现的反量化类型 %s(id=%d)；用 --raw 导出原始块，'
                     '或 pip install gguf 后用 gguf.quants.dequantize()' % (name, ttype))


# ======================= 输出 =======================
def human(n):
    for unit in ('B', 'KiB', 'MiB', 'GiB', 'TiB'):
        if abs(n) < 1024 or unit == 'TiB':
            return '%.2f %s' % (n, unit) if unit != 'B' else '%d B' % n
        n /= 1024.0


def fmt_val(v, maxlen=120):
    if isinstance(v, list):
        s = str(v)
        return s if len(s) <= maxlen else s[:maxlen] + ' ... (len=%d)' % len(v)
    if isinstance(v, str):
        return v if len(v) <= maxlen else v[:maxlen] + ' ... (len=%d)' % len(v)
    return v


def main():
    ap = argparse.ArgumentParser(description='GGUF 权重文件解析/导出')
    ap.add_argument('path')
    ap.add_argument('--json', metavar='FILE', help='把元数据与张量清单写成 JSON')
    ap.add_argument('--meta', metavar='KEY', help='只打印某个 metadata 键（支持前缀匹配）')
    ap.add_argument('--tensor', metavar='NAME', help='只处理某个张量（支持子串匹配）')
    ap.add_argument('--stats', action='store_true', help='打印张量数值统计')
    ap.add_argument('--extract', metavar='DIR', help='导出张量为 .npy')
    ap.add_argument('--raw', action='store_true', help='导出原始量化块字节（不反量化）')
    ap.add_argument('--limit', type=int, default=8, help='--meta 数组最多打印几项')
    a = ap.parse_args()

    r = GGUFReader(a.path)

    if a.meta:
        hits = [m for m in r.meta if m[0] == a.meta] or \
               [m for m in r.meta if m[0].startswith(a.meta)]
        if not hits:
            print('没有匹配的键: %s' % a.meta)
            print('可用键:')
            for k, _, _ in r.meta:
                print('  ' + k)
            return
        for k, t, v in hits:
            if isinstance(v, list):
                print('%s (%s[%d]):' % (k, TYPE_NAME.get(t, t), len(v)))
                for x in v[:a.limit]:
                    print('  %r' % x)
                if len(v) > a.limit:
                    print('  ... 共 %d 项' % len(v))
            else:
                print('%s (%s) = %r' % (k, TYPE_NAME.get(t, t), v))
        return

    if a.json:
        doc = {
            'file': os.path.abspath(a.path),
            'file_size': r.size,
            'gguf_version': r.version,
            'tensor_count': r.tensor_count,
            'kv_count': r.kv_count,
            'alignment': r.alignment,
            'data_start': r.data_start,
            'metadata': [{'key': k, 'type': TYPE_NAME.get(t, t), 'value': v}
                         for k, t, v in r.meta],
            'tensors': [{'name': t['name'], 'type': type_name(t['type']),
                         'shape': list(t['shape']), 'elements': t['n_elements'],
                         'bytes': t['n_bytes'], 'offset': t['offset']}
                        for t in r.tensors],
        }
        with open(a.json, 'w', encoding='utf-8') as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
        print('已写出 %s (%s)' % (a.json, human(os.path.getsize(a.json))))

    targets = r.tensors
    if a.tensor:
        targets = [t for t in r.tensors if a.tensor == t['name'] or a.tensor in t['name']]
        if not targets:
            raise SystemExit('没有匹配的张量: %s' % a.tensor)

    # 头部信息 + 元数据
    if not a.tensor and not a.extract:
        print('文件      : %s  (%s)' % (os.path.abspath(a.path), human(r.size)))
        print('GGUF 版本 : %d' % r.version)
        print('张量数量  : %d' % r.tensor_count)
        print('KV 数量   : %d   对齐: %d 字节   数据区起点: %d' % (r.kv_count, r.alignment, r.data_start))
        print('架构      : %s' % (r.meta_get('general.architecture'),))
        print('模型名    : %s' % (r.meta_get('general.name'),))
        print('量化版本  : %s' % (r.meta_get('general.quantization_version'),))
        print('\n== 元数据 (%d) ==' % len(r.meta))
        for k, t, v in r.meta:
            if t == T_ARRAY and isinstance(v, list) and len(v) > 8:
                print('  %-42s ARRAY[%d]' % (k, len(v)))
            else:
                print('  %-42s %s' % (k, fmt_val(v)))

        # 张量按类型汇总
        agg = {}
        for t in r.tensors:
            nm = type_name(t['type'])
            s = agg.setdefault(nm, [0, 0])
            s[0] += 1
            s[1] += t['n_elements']
        print('\n== 张量类型分布 ==')
        for nm, (cnt, par) in sorted(agg.items(), key=lambda x: -x[1][1]):
            print('  %-10s %4d 张量  %14s 参数' % (nm, cnt, '{:,}'.format(par)))
        print('  合计                 %14s 参数' % '{:,}'.format(sum(t['n_elements'] for t in r.tensors)))

        print('\n== 张量表 (%d) ==' % len(r.tensors))
        print('%-46s %-8s %-26s %10s %10s' % ('name', 'type', 'shape', 'elements', 'bytes'))
        for t in r.tensors:
            print('%-46s %-8s %-26s %10d %10s' % (
                t['name'], type_name(t['type']), str(list(t['shape'])),
                t['n_elements'], human(t['n_bytes'])))

    # 导出
    if a.extract:
        os.makedirs(a.extract, exist_ok=True)
        np = _np()
        total = 0
        for t in targets:
            buf = r.tensor_bytes(t)
            fn = os.path.join(a.extract, t['name'].replace('/', '_') + '.npy')
            if a.raw or t['type'] in (0, 1, 30, 24, 25, 26, 27, 28):
                if a.raw:
                    fn = fn[:-4] + '.bin'
                    with open(fn, 'wb') as f:
                        f.write(buf)
                    print('%-50s -> %s (%s, raw)' % (t['name'], fn, human(len(buf))))
                    continue
            try:
                arr = dequant(buf, t['n_elements'], t['type'])
            except (ValueError, SystemExit) as e:
                fn2 = os.path.join(a.extract, t['name'].replace('/', '_') + '.bin')
                with open(fn2, 'wb') as f:
                    f.write(buf)
                print('%-50s !! %s' % (t['name'], e))
                print('%-50s -> %s (原始块)' % ('', fn2))
                continue
            arr = arr.reshape(t['shape'])
            np.save(fn, arr)
            total += arr.size
            print('%-50s -> %s %s %s' % (t['name'], fn, arr.dtype, list(arr.shape)))
        print('\n共导出 %s 个参数到 %s' % ('{:,}'.format(total), os.path.abspath(a.extract)))

    # 统计
    if a.stats:
        np = _np()
        for t in targets:
            buf = r.tensor_bytes(t)
            try:
                arr = dequant(buf, t['n_elements'], t['type'])
            except (ValueError, SystemExit) as e:
                print('%s: %s' % (t['name'], e))
                continue
            print('%-46s %-6s shape=%-22s min=%+.6g max=%+.6g mean=%+.6g std=%.6g' % (
                t['name'], type_name(t['type']), str(list(t['shape'])),
                float(arr.min()), float(arr.max()),
                float(arr.astype(np.float64).mean()), float(arr.astype(np.float64).std())))


if __name__ == '__main__':
    main()
