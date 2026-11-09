#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
safetensors_dump.py —— HuggingFace 原生权重（*.safetensors / 分片）解析 / 查看 / 导出
格式：8 字节小端 u64 = header 长度 N；紧跟 N 字节 UTF-8 JSON；之后是裸张量数据。

用法:
  python safetensors_dump.py model.safetensors
  python safetensors_dump.py model.safetensors --json out.json
  python safetensors_dump.py model.safetensors --tensor embed --stats
  python safetensors_dump.py model.safetensors --extract out
  python safetensors_dump.py model.safetensors.index.json      # 分片索引
"""
import argparse
import json
import os
import struct
import sys

ST_DTYPES = {  # dtype -> (numpy dtype, itemsize)
    'F64': ('<f8', 8), 'F32': ('<f4', 4), 'F16': ('<f2', 2), 'BF16': ('<u2', 2),
    'I64': ('<i8', 8), 'I32': ('<i4', 4), 'I16': ('<i2', 2), 'I8': ('i1', 1),
    'U64': ('<u8', 8), 'U32': ('<u4', 4), 'U16': ('<u2', 2), 'U8': ('u1', 1),
    'BOOL': ('?', 1), 'F8_E4M3': ('u1', 1), 'F8_E5M2': ('u1', 1),
}


def human(n):
    for unit in ('B', 'KiB', 'MiB', 'GiB', 'TiB'):
        if abs(n) < 1024 or unit == 'TiB':
            return ('%d B' % n) if unit == 'B' else ('%.2f %s' % (n, unit))
        n /= 1024.0


def np_():
    try:
        import numpy as np
        return np
    except ImportError:
        raise SystemExit('需要 numpy:  python -m pip install numpy')


def to_float(arr, dtype):
    np = np_()
    if dtype == 'BF16':
        return (arr.astype(np.uint32) << 16).view(np.float32)
    if dtype in ('F64', 'F32', 'F16'):
        return arr.astype(np.float32)
    return arr


def load_header(path):
    size = os.path.getsize(path)
    with open(path, 'rb') as f:
        raw = f.read(8)
        if len(raw) < 8:
            raise SystemExit('文件太小，不是 safetensors')
        n = struct.unpack('<Q', raw)[0]
        if n <= 0 or n > size - 8 or n > 100 * 1024 * 1024:
            raise SystemExit('header 长度异常: %d（不是 safetensors，或文件损坏）' % n)
        hdr = json.loads(f.read(n).decode('utf-8'))
    return hdr, n, size


def main():
    ap = argparse.ArgumentParser(description='safetensors 权重解析/导出')
    ap.add_argument('path')
    ap.add_argument('--json', metavar='FILE')
    ap.add_argument('--tensor', metavar='NAME', help='名字子串过滤')
    ap.add_argument('--stats', action='store_true')
    ap.add_argument('--extract', metavar='DIR')
    ap.add_argument('--limit', type=int, default=10)
    a = ap.parse_args()

    if a.path.endswith('.index.json'):
        with open(a.path, encoding='utf-8') as f:
            idx = json.load(f)
        wm = idx.get('weight_map', {})
        print('分片索引: %s' % os.path.abspath(a.path))
        print('metadata: %s' % json.dumps(idx.get('metadata', {}), ensure_ascii=False))
        files = {}
        for k, v in wm.items():
            files.setdefault(v, []).append(k)
        print('张量数: %d   分片数: %d' % (len(wm), len(files)))
        base = os.path.dirname(os.path.abspath(a.path))
        for fn, names in sorted(files.items()):
            p = os.path.join(base, fn)
            print('  %-46s %3d 张量  %s' % (fn, len(names), human(os.path.getsize(p)) if os.path.exists(p) else '缺失'))
        return

    hdr, hlen, size = load_header(a.path)
    meta = hdr.pop('__metadata__', None)
    print('文件   : %s  (%s)' % (os.path.abspath(a.path), human(size)))
    print('header : %d 字节   张量: %d   数据区: %s' % (hlen, len(hdr), human(size - 8 - hlen)))
    if meta:
        print('metadata:')
        for k, v in meta.items():
            s = str(v)
            print('  %-24s %s' % (k, s if len(s) <= 200 else s[:200] + '...'))

    items = sorted(hdr.items(), key=lambda kv: kv[1]['data_offsets'][0])
    if a.tensor:
        items = [kv for kv in items if a.tensor in kv[0]]
        if not items:
            raise SystemExit('没有匹配的张量: %s' % a.tensor)

    agg = {}
    total = 0
    print('\n%-52s %-6s %-24s %12s' % ('name', 'dtype', 'shape', 'bytes'))
    for name, info in items:
        dt = info['dtype']
        shape = info['shape']
        s, e = info['data_offsets']
        n = 1
        for d in shape:
            n *= d
        total += n
        agg[dt] = agg.get(dt, 0) + 1
        print('%-52s %-6s %-24s %12s' % (name, dt, str(shape), human(e - s)))
    print('\n元素合计: %s   类型分布: %s' % ('{:,}'.format(total),
          ', '.join('%s x%d' % (k, v) for k, v in sorted(agg.items(), key=lambda x: -x[1]))))

    if a.json:
        with open(a.json, 'w', encoding='utf-8') as f:
            json.dump({'file': os.path.abspath(a.path), 'header_bytes': hlen,
                       'file_bytes': size, '__metadata__': meta,
                       'tensors': [{'name': k, 'dtype': v['dtype'], 'shape': v['shape'],
                                    'data_offsets': v['data_offsets']} for k, v in items]},
                      f, ensure_ascii=False, indent=1)
        print('已写出 %s' % a.json)

    np = np_()
    f = open(a.path, 'rb')
    base = 8 + hlen
    if a.stats or a.extract:
        if a.extract:
            os.makedirs(a.extract, exist_ok=True)
        for name, info in items:
            dt, shape = info['dtype'], info['shape']
            nd, isize = ST_DTYPES.get(dt, (None, 1))
            s, e = info['data_offsets']
            f.seek(base + s)
            buf = f.read(e - s)
            if nd is None:
                print('%-50s 未知 dtype %s，跳过' % (name, dt))
                continue
            arr = np.frombuffer(buf, dtype=nd)
            if a.extract:
                out = os.path.join(a.extract, name.replace('/', '_') + '.npy')
                if dt == 'BF16':
                    np.save(out, (arr.astype(np.uint32) << 16).view(np.float32))
                else:
                    np.save(out, arr.reshape(shape) if arr.size == np.prod(shape or [1]) else arr)
                print('%-50s -> %s %s %s' % (name, out, dt, shape))
            if a.stats:
                v = to_float(arr, dt).astype(np.float64)
                print('%-50s %-6s min=%+.6g max=%+.6g mean=%+.6g std=%.6g' % (
                    name, dt, float(v.min()), float(v.max()), float(v.mean()), float(v.std())))
    f.close()


if __name__ == '__main__':
    main()
