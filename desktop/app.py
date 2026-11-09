# -*- coding: utf-8 -*-
"""
GGUF 解剖台 · Windows 桌面版
====================================================================
纯 Python + Tkinter，不依赖浏览器、不依赖 WebView、不需要本地服务器。
直接读 .gguf 文件，界面全中文，模型逻辑链路用 3D 复现。

运行：
    python app.py                       # 自动找同目录下的 *.gguf
    python app.py model.gguf            # 指定模型
    python app.py model.gguf --shot a.png   # 启动后截图退出（自检用）

打包：
    pyinstaller --noconfirm --onefile --windowed --name "GGUF解剖台" app.py
"""
import os
import sys
import math
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

BASE = os.path.dirname(os.path.abspath(sys.argv[0] if getattr(sys, 'frozen', False) else __file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np  # noqa: E402
import gguf_dump     # noqa: E402

# ----------------------------------------------------------------- 配色
BG = '#f4f6fb'
PANEL = '#ffffff'
PANEL2 = '#f8fafc'
LINE = '#e2e8f0'
FG = '#1e293b'
DIM = '#64748b'
ACC = '#0d9488'
ACC2 = '#2563eb'
WARN = '#d97706'

TYPE_CN = {'NORMAL': '普通词元', 'CONTROL': '控制符', 'USER_DEFINED': '用户自定义',
           'UNUSED': '未使用', 'UNKNOWN': '未知词', 'BYTE': '字节', 'UNDEFINED': '未定义'}
TT = {0: '未定义', 1: '普通词元', 2: '未知词', 3: '控制符', 4: '用户自定义', 5: '未使用', 6: '字节'}

ROLE_CN = {
    'attn_norm': '注意力归一化', 'attn_q': '查询投影', 'attn_k': '键投影',
    'attn_v': '值投影', 'attn_output': '注意力输出投影',
    'ffn_norm': '前馈归一化', 'ffn_gate': '门控投影', 'ffn_up': '上投影', 'ffn_down': '下投影',
}
GLOBAL_CN = {'token_embd': '词元嵌入表', 'output_norm': '输出归一化', 'output': '输出层（语言模型头）'}
ROLE_ORDER = ['attn_norm', 'attn_q', 'attn_k', 'attn_v', 'attn_output',
              'ffn_norm', 'ffn_gate', 'ffn_up', 'ffn_down']

GLOSS = {
    'the': '定冠词', 'of': '的', 'and': '和', 'to': '到', 'in': '在…里', 'is': '是', 'you': '你',
    'that': '那个', 'it': '它', 'for': '为了', 'on': '在…上', 'with': '与…一起', 'as': '作为',
    'are': '是（复数）', 'be': '是/存在', 'at': '在', 'this': '这个', 'have': '有', 'from': '从',
    'or': '或者', 'by': '通过', 'not': '否定', 'but': '但是', 'they': '他们', 'we': '我们',
    'he': '他', 'she': '她', 'his': '他的', 'her': '她的', 'its': '它的', 'all': '全部',
    'an': '一个', 'one': '一', 'two': '二', 'can': '能', 'will': '将要', 'would': '将会',
    'there': '那里', 'their': '他们的', 'what': '什么', 'which': '哪个', 'when': '何时',
    'where': '哪里', 'who': '谁', 'how': '如何', 'why': '为什么', 'was': '是（过去）',
    'were': '是（过去复数）', 'been': '是（完成）', 'has': '有（三单）', 'had': '有（过去）',
    'do': '做', 'does': '做（三单）', 'did': '做（过去）', 'more': '更多', 'most': '最多',
    'some': '一些', 'any': '任何', 'no': '没有', 'yes': '是', 'if': '如果', 'then': '然后',
    'than': '比', 'so': '所以', 'about': '关于', 'into': '进入', 'over': '在…之上',
    'after': '之后', 'before': '之前', 'up': '向上', 'down': '向下', 'out': '向外',
    'only': '仅仅', 'also': '也', 'very': '非常', 'just': '只是', 'now': '现在',
    'new': '新的', 'old': '旧的', 'first': '第一', 'last': '最后', 'other': '其他',
    'time': '时间', 'year': '年', 'people': '人们', 'way': '方式', 'day': '天', 'man': '男人',
    'woman': '女人', 'child': '孩子', 'world': '世界', 'life': '生命', 'hand': '手',
    'part': '部分', 'place': '地方', 'work': '工作', 'week': '周', 'case': '情况',
    'point': '点', 'company': '公司', 'number': '数字', 'group': '组', 'problem': '问题',
    'fact': '事实', 'model': '模型', 'data': '数据', 'text': '文本', 'word': '单词',
    'list': '列表', 'item': '项目', 'name': '名字', 'value': '值', 'type': '类型',
    'code': '代码', 'file': '文件', 'line': '行', 'page': '页', 'user': '用户',
    'system': '系统', 'network': '网络', 'server': '服务器', 'client': '客户端',
    'token': '词元/令牌', 'vector': '向量', 'matrix': '矩阵', 'layer': '层', 'head': '头',
    'attention': '注意力', 'embedding': '嵌入', 'weight': '权重', 'bias': '偏置',
    'norm': '归一化', 'query': '查询', 'key': '键', 'hello': '你好', 'good': '好的',
    'bad': '坏的', 'true': '真', 'false': '假', 'null': '空', 'error': '错误',
    'warning': '警告', 'info': '信息', 'debug': '调试', 'test': '测试', 'start': '开始',
    'end': '结束', 'open': '打开', 'close': '关闭', 'read': '读', 'write': '写',
    'get': '获取', 'set': '设置', 'add': '添加', 'delete': '删除', 'update': '更新',
    'create': '创建', 'map': '映射', 'array': '数组', 'string': '字符串', 'int': '整数',
    'float': '浮点', 'function': '函数', 'return': '返回', 'class': '类', 'object': '对象',
    'method': '方法', 'print': '打印', 'import': '导入', 'input': '输入', 'output': '输出',
    'process': '进程', 'memory': '内存', 'storage': '存储', 'index': '索引',
    'sort': '排序', 'search': '搜索',
}


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


def decode_token(tok):
    if not isinstance(tok, str):
        return ''
    try:
        return bytes(U2B[c] for c in tok).decode('utf-8')
    except Exception:
        return tok


def grab_window(hwnd, out_path):
    """用 PrintWindow 直接抓取窗口位图，不受其他窗口遮挡影响"""
    import ctypes
    from ctypes import wintypes
    from PIL import Image

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass
    rect = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return False
    w = rect.right - rect.left
    h = rect.bottom - rect.top
    if w <= 0 or h <= 0:
        return False
    hdc = user32.GetWindowDC(hwnd)
    mdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mdc, bmp)
    user32.PrintWindow(hwnd, mdc, 2)

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [('biSize', wintypes.DWORD), ('biWidth', wintypes.LONG), ('biHeight', wintypes.LONG),
                    ('biPlanes', wintypes.WORD), ('biBitCount', wintypes.WORD),
                    ('biCompression', wintypes.DWORD), ('biSizeImage', wintypes.DWORD),
                    ('biXPelsPerMeter', wintypes.LONG), ('biYPelsPerMeter', wintypes.LONG),
                    ('biClrUsed', wintypes.DWORD), ('biClrImportant', wintypes.DWORD)]

    bi = BITMAPINFOHEADER()
    bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.biWidth = w
    bi.biHeight = -h
    bi.biPlanes = 1
    bi.biBitCount = 32
    bi.biCompression = 0
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
    img = Image.frombuffer('RGBA', (w, h), buf, 'raw', 'BGRA', 0, 1).convert('RGB')
    img.save(out_path)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mdc)
    user32.ReleaseDC(hwnd, hdc)
    return True


def short_path(p, n=92):
    p = os.path.abspath(p)
    if len(p) <= n:
        return p
    keep = n - 3
    return p[:keep // 2] + '…' + p[-(keep - keep // 2):]


def fmt_num(v):
    try:
        if isinstance(v, bool):
            return '是' if v else '否'
        if isinstance(v, int):
            return '{:,}'.format(v)
        if isinstance(v, float):
            if v != 0 and abs(v) < 1e-4:
                return '%.3e' % v
            if abs(v) >= 1e6:
                return '{:,.3f}'.format(v).rstrip('0').rstrip('.')
            return ('%.6f' % v).rstrip('0').rstrip('.')
    except Exception:
        pass
    return str(v)


def human_bytes(n):
    for u in ('B', 'KiB', 'MiB', 'GiB', 'TiB'):
        if abs(n) < 1024 or u == 'TiB':
            return ('%d B' % n) if u == 'B' else ('%.2f %s' % (n, u))
        n /= 1024.0


def human_params(n):
    if n >= 1e9:
        return '%.2f B' % (n / 1e9)
    if n >= 1e6:
        return '%.1f M' % (n / 1e6)
    return '{:,}'.format(int(n))


# ----------------------------------------------------------------- 模型数据
class ModelData:
    def __init__(self, path):
        self.path = path
        self.reader = gguf_dump.GGUFReader(path)
        self.meta = {k: v for k, t, v in self.reader.meta}
        self.kv = [(k, t, v) for k, t, v in self.reader.meta]
        self.arch = self.meta.get('general.architecture', 'llama')
        self.tensors = self.reader.tensors
        self.tokens = self.meta.get('tokenizer.ggml.tokens') or []
        self.ttypes = self.meta.get('tokenizer.ggml.token_type') or []
        self.decoded = None
        self.emb = None
        self.norms = None
        self.pca3 = None
        self.pca2 = None
        self.pca_sample = None
        self.layers = {}
        self.base_tensors = []
        for t in self.tensors:
            if t['name'].startswith('blk.'):
                parts = t['name'].split('.', 2)
                if len(parts) == 3:
                    idx = int(parts[1])
                    role = parts[2].replace('.weight', '').replace('.bias', '')
                    self.layers.setdefault(idx, []).append(
                        {'role': role, 'is_bias': parts[2].endswith('.bias'),
                         'name': t['name'], 'type': gguf_dump.type_name(t['type']),
                         'shape': list(t['shape']), 'elements': t['n_elements'],
                         'bytes': t['n_bytes']})
            else:
                self.base_tensors.append(t)
        for i in self.layers:
            self.layers[i].sort(key=lambda x: (ROLE_ORDER.index(x['role']) if x['role'] in ROLE_ORDER else 99,
                                               x['is_bias']))
        self.layer_count = max(self.layers) + 1 if self.layers else 0
        self.total_params = sum(t['n_elements'] for t in self.tensors)

    def hp(self, key, default=None):
        return self.meta.get('%s.%s' % (self.arch, key), default)

    def ensure_decoded(self):
        if self.decoded is None:
            self.decoded = [decode_token(t) for t in self.tokens]
        return self.decoded

    MAX_EMB_ELEMS = 300_000_000      # 3 亿元素 × 4 字节 ≈ 1.2 GB，超过就降级

    def ensure_embedding(self):
        if self.emb is not None:
            return
        if getattr(self, '_emb_failed', None):
            raise RuntimeError(self._emb_failed)
        t = None
        for x in self.tensors:
            if x['name'] in ('token_embd.weight', 'token_embd'):
                t = x
                break
        if t is None:
            return
        if t['n_elements'] > self.MAX_EMB_ELEMS:
            self._emb_failed = ('嵌入矩阵 %s 个参数，反量化需要约 %.1f GB 内存，'
                                '已跳过向量空间分析（其余页面不受影响）'
                                % ('{:,}'.format(t['n_elements']),
                                   t['n_elements'] * 4 / 1024 ** 3))
            raise RuntimeError(self._emb_failed)
        arr = gguf_dump.dequant(self.reader.tensor_bytes(t), t['n_elements'], t['type'])
        self.emb = arr.reshape(t['shape']).astype(np.float32)
        self.norms = np.linalg.norm(self.emb, axis=1)
        rng = np.random.default_rng(7)
        n = self.emb.shape[0]
        valid = np.array([i for i in range(n) if (self.ttypes[i] if i < len(self.ttypes) else 1) not in (3, 5)])
        sample = rng.choice(valid, size=min(2400, len(valid)), replace=False)
        X = self.emb[sample]
        Xc = X - X.mean(0, keepdims=True)
        _U, S, Vt = np.linalg.svd(Xc, full_matrices=False)
        self.pca3 = (Xc @ Vt[:3].T).astype(np.float32)
        self.pca2 = (Xc @ Vt[:2].T).astype(np.float32)
        self.pca_sample = sample
        var = (S ** 2) / float((S ** 2).sum())
        self.pca_var = var

    def explain(self, idx):
        dec = self.ensure_decoded()
        s = dec[idx] if idx < len(dec) else ''
        ty = self.ttypes[idx] if idx < len(self.ttypes) else 1
        tags = []
        if ty == 3:
            tags.append('控制符')
        elif ty == 4:
            tags.append('用户自定义')
        elif ty == 2:
            tags.append('未知词')
        elif ty == 5:
            tags.append('未使用')
        if s.startswith('<|') and s.rfind('|>') > 0:
            tags.append('对话模板标记')
        if s.startswith('<0x') and s.endswith('>'):
            tags.append('字节回退')
        if s == ' ':
            tags.append('空格')
        elif s.startswith(' '):
            tags.append('词首（带前导空格）')
        core = s.strip()
        if not tags and core:
            low = core.lower()
            if low in GLOSS:
                tags.append(GLOSS[low])
            elif all('\u4e00' <= ch <= '\u9fff' for ch in core):
                tags.append('中文单字' if len(core) == 1 else '中文词')
            elif core.isdigit():
                tags.append('数字 ' + core)
            elif core.isalpha() and core.isascii():
                tags.append('英文词')
            elif any(ch in '(){}[]<>=+-*/\\|_$#@!~^&;:' for ch in core):
                tags.append('代码片段')
            else:
                tags.append('符号')
        return ' · '.join(tags) if tags else '普通词元'

    def nearest(self, idx, k=8):
        self.ensure_embedding()
        X = self.emb
        nrm = self.norms
        v = X[idx] / max(nrm[idx], 1e-9)
        sims = (X @ v) / np.maximum(nrm, 1e-9)
        sims[idx] = -2
        order = np.argpartition(-sims, k)[:k]
        order = order[np.argsort(-sims[order])]
        return [(int(i), float(sims[i])) for i in order]


# ----------------------------------------------------------------- 3D 引擎
class Scene3D:
    """极简 3D：旋转 + 透视投影，输出 2D 坐标供 Tkinter Canvas 绘制"""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.rot_x = -0.12
        self.rot_y = 0.62
        self.zoom = 42.0
        self.cx = w * 0.5
        self.cy = h * 0.5

    def project(self, x, y, z):
        cy, sy = math.cos(self.rot_y), math.sin(self.rot_y)
        x1 = x * cy + z * sy
        z1 = -x * sy + z * cy
        cx, sx = math.cos(self.rot_x), math.sin(self.rot_x)
        y1 = y * cx - z1 * sx
        z2 = y * sx + z1 * cx
        d = 26.0
        f = self.zoom * d / (d + z2)
        return self.cx + x1 * f, self.cy - y1 * f, z2


class Chain3DPage(tk.Frame):
    """模型逻辑链路 3D 复现"""

    def __init__(self, master, app):
        super().__init__(master, bg=BG)
        self.app = app
        self.model = None
        self.selected = 0
        self.auto = False
        self.billboards = []
        self.after_id = None
        self.scene = Scene3D(900, 620)

        bar = tk.Frame(self, bg=BG)
        bar.pack(fill='x', padx=16, pady=(14, 6))
        tk.Label(bar, text='模型逻辑链路 · 三维复现', bg=BG, fg=FG,
                 font=('Microsoft YaHei UI', 13, 'bold')).pack(side='left')
        self.btn_auto = tk.Button(bar, text='自动旋转', command=self.toggle_auto, bg=PANEL, fg=FG,
                                  relief='solid', bd=1, font=('Microsoft YaHei UI', 9),
                                  activebackground='#e6fffb', padx=12, pady=3)
        self.btn_auto.pack(side='right', padx=(6, 0))
        tk.Button(bar, text='重置视角', command=self.reset_view, bg=PANEL, fg=FG, relief='solid', bd=1,
                  font=('Microsoft YaHei UI', 9), activebackground='#e6fffb', padx=12, pady=3).pack(side='right')

        body = tk.Frame(self, bg=BG)
        body.pack(fill='both', expand=True, padx=16, pady=(0, 16))
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=0, minsize=380)
        body.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(body, bg='#fbfdff', highlightthickness=1,
                                highlightbackground=LINE, cursor='fleur')
        self.canvas.grid(row=0, column=0, sticky='nsew', padx=(0, 12))

        side = tk.Frame(body, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        side.grid(row=0, column=1, sticky='nsew')
        tk.Label(side, text='当前选中层', bg=PANEL, fg=DIM, font=('Microsoft YaHei UI', 9)).pack(
            anchor='w', padx=12, pady=(12, 0))
        self.lbl_layer = tk.Label(side, text='第 0 层', bg=PANEL, fg=FG,
                                  font=('Microsoft YaHei UI', 15, 'bold'))
        self.lbl_layer.pack(anchor='w', padx=12)
        self.lbl_params = tk.Label(side, text='', bg=PANEL, fg=DIM, font=('Consolas', 9))
        self.lbl_params.pack(anchor='w', padx=12, pady=(0, 8))

        cols = ('cn', 'type', 'shape', 'num')
        self.tree = ttk.Treeview(side, columns=cols, show='headings', height=13)
        for c, t, w, an in zip(cols, ('中文名称', '类型', '形状', '元素数'), (118, 62, 92, 96),
                               ('w', 'center', 'w', 'e')):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor=an)
        self.tree.pack(fill='both', expand=True, padx=12, pady=(0, 8))

        tk.Label(side, text='图例', bg=PANEL, fg=DIM, font=('Microsoft YaHei UI', 9)).pack(anchor='w', padx=12)
        leg = tk.Frame(side, bg=PANEL)
        leg.pack(anchor='w', padx=12, pady=(2, 12))
        for txt, col in (('注意力分支', '#dbeafe'), ('前馈分支', '#f3e8ff'), ('残差/输入输出', '#ccfbf1')):
            row = tk.Frame(leg, bg=PANEL)
            row.pack(anchor='w', pady=1)
            tk.Frame(row, bg=col, width=12, height=12, highlightthickness=1,
                     highlightbackground=LINE).pack(side='left')
            tk.Label(row, text=' ' + txt, bg=PANEL, fg=DIM, font=('Microsoft YaHei UI', 9)).pack(side='left')

        self.canvas.bind('<ButtonPress-1>', self.on_press)
        self.canvas.bind('<B1-Motion>', self.on_drag)
        self.canvas.bind('<ButtonRelease-1>', self.on_release)
        self.canvas.bind('<MouseWheel>', self.on_wheel)
        self.canvas.bind('<Configure>', lambda e: self.redraw())

    # ---------- 场景 ----------
    def set_model(self, model):
        self.model = model
        self.selected = 0
        self.after(60, self.fit)
        self.show_layer(0)

    def fit(self):
        """按画布尺寸与层数自动算缩放，保证 24 层完整落在可视区"""
        if self.model is None:
            return
        c = self.canvas
        c.update_idletasks()
        n = max(self.model.layer_count, 1)
        w = max(c.winfo_width(), 400)
        h = max(c.winfo_height(), 400)
        self.scene = Scene3D(w, h)
        self.scene.zoom = min(w * 0.46 / 4.4, h * 0.86 / (n + 4.2))
        self.redraw()

    def reset_view(self):
        self.fit()

    def toggle_auto(self):
        self.auto = not self.auto
        self.btn_auto.configure(text='停止旋转' if self.auto else '自动旋转',
                                bg='#0d9488' if self.auto else PANEL,
                                fg='white' if self.auto else FG)
        if self.auto:
            self.tick()

    def tick(self):
        if not self.auto:
            return
        self.scene.rot_y += 0.012
        self.redraw()
        self.after_id = self.after(50, self.tick)

    def on_press(self, e):
        self._drag = (e.x, e.y)

    def on_drag(self, e):
        if not hasattr(self, '_drag'):
            return
        dx = e.x - self._drag[0]
        dy = e.y - self._drag[1]
        self._drag = (e.x, e.y)
        self.scene.rot_y += dx * 0.012
        self.scene.rot_x = max(-0.9, min(0.9, self.scene.rot_x + dy * 0.008))
        self.redraw()

    def on_release(self, e):
        if not hasattr(self, '_drag'):
            return
        dx = abs(e.x - self._drag[0])
        dy = abs(e.y - self._drag[1])
        del self._drag
        if dx < 3 and dy < 3:
            best, bd = -1, 48 * 48
            for idx, (sx, sy) in self.billboards:
                d = (sx - e.x) ** 2 + (sy - e.y) ** 2
                if d < bd:
                    bd = d
                    best = idx
            if best >= 0:
                self.selected = best
                self.redraw()
                self.show_layer(best)

    def on_wheel(self, e):
        self.scene.zoom *= 1.1 if e.delta > 0 else 0.9
        self.scene.zoom = max(14, min(110, self.scene.zoom))
        self.redraw()

    # ---------- 绘制 ----------
    def _bg(self, w, h):
        """竖向渐变背景 + 极淡网格，给 3D 一个空间感"""
        steps = 24
        for i in range(steps):
            t = i / (steps - 1.0)
            col = '#%02x%02x%02x' % (
                int(255 - 12 * t), int(255 - 6 * t), int(255 - 2 * t))
            self.canvas.create_rectangle(0, h * i / steps, w, h * (i + 1) / steps + 1,
                                         fill=col, outline='')
        for k in range(1, 6):
            y = h * k / 6.0
            self.canvas.create_line(0, y, w, y, fill='#eaf2fb')

    def _box(self, cx, cy, cz, sx, sy, sz, fill, top, side, outline, shadow=True):
        v = []
        for dx in (-0.5, 0.5):
            for dy in (-0.5, 0.5):
                for dz in (-0.5, 0.5):
                    v.append(self.scene.project(cx + dx * sx, cy + dy * sy, cz + dz * sz))
        if shadow:
            bx, by, _ = self.scene.project(cx, cy - sy * 0.62, cz)
            sw = 34 + 10 * (sx / 3.6)
            self.canvas.create_oval(bx - sw, by - 5, bx + sw, by + 5,
                                    fill='#b9cde3', outline='', stipple='gray50')
        faces = [((0, 1, 3, 2), side), ((4, 5, 7, 6), side), ((2, 3, 7, 6), top),
                 ((0, 1, 5, 4), top), ((1, 3, 7, 5), fill), ((0, 2, 6, 4), side)]
        out = []
        for idx, col in faces:
            pts = [v[i] for i in idx]
            depth = sum(p[2] for p in pts) / 4.0
            out.append((depth, pts, col))
        out.sort(key=lambda x: -x[0])
        for depth, pts, col in out:
            flat = []
            for x, y, _ in pts:
                flat.extend((x, y))
            self.canvas.create_polygon(flat, fill=col, outline=outline, width=1)

    def _glow(self, x, y, w, h, color):
        """选中层的外发光：两层逐渐变淡的轮廓"""
        for k, c in ((3, '#e6fffb'), (2, '#99f6e4')):
            self.canvas.create_rectangle(x - w - k, y - h - k, x + w + k, y + h + k,
                                         outline=c, width=2)

    def redraw(self):
        c = self.canvas
        if self.model is None:
            return
        c.delete('all')
        cw, ch = max(c.winfo_width(), 400), max(c.winfo_height(), 400)
        if abs(self.scene.w - cw) > 2 or abs(self.scene.h - ch) > 2:
            z = getattr(self.scene, 'zoom', 26.0)
            self.scene = Scene3D(cw, ch)
            self.scene.zoom = z
        s = self.scene
        s.cx = cw * 0.5
        s.cy = ch * 0.52
        self._bg(cw, ch)
        self.billboards = []
        n = max(self.model.layer_count, 1)
        top_y = n / 2.0 + 1.6
        bottom_y = -n / 2.0 - 1.6

        # 主干：从底到顶的箭头 + 节点间的短连线
        x0, y0, _ = s.project(0, bottom_y, 0)
        x1, y1, _ = s.project(0, top_y, 0)
        c.create_line(x0, y0, x1, y1, fill='#b9cde3', width=4, arrow='last', arrowshape=(10, 12, 4))

        # 底部：词元嵌入（大节点）
        ex, ey, _ = s.project(0, bottom_y, 0)
        hot_emb = getattr(self, 'focus_target', None) == 'emb'
        self._box(0, bottom_y, 0, 4.0, 0.95, 2.1, '#ccfbf1' if not hot_emb else '#99f6e4',
                  '#e6fffb', '#5eead4', ACC, shadow=True)
        if hot_emb:
            self._glow(ex, ey, 70, 22, '#0d9488')
        c.create_text(ex, ey, text='词元嵌入表  151936×896', fill='#0f172a',
                      font=('Microsoft YaHei UI', 9, 'bold'))

        # 24 层
        for i in range(n):
            y = -n / 2.0 + i + 0.3
            sel = (i == self.selected)
            focus = (getattr(self, 'focus_target', None) == i)
            fill = '#dbeafe' if not sel else '#bae6fd'
            top = '#eff6ff' if not sel else '#e0f2fe'
            side = '#93c5fd' if not sel else '#7dd3fc'
            self._box(0, y, 0, 3.2, 0.76, 1.8, fill, top, side, ACC if sel else '#94a3b8')
            sx, sy, _ = s.project(0, y, 0)
            self.billboards.append((i, (sx, sy)))
            if focus:
                self._glow(sx, sy, 64, 14, ACC)
            c.create_text(sx, sy, text='第 %d 层' % i, fill='#0f172a',
                          font=('Microsoft YaHei UI', 9 if n > 12 else 10, 'bold'))


        # 顶部：输出归一化 + 输出层
        ny = n / 2.0 + 0.4
        nx, nyy, _ = s.project(0, ny, 0)
        self._box(0, ny, 0, 3.0, 0.56, 1.4, '#f1f5f9', '#f8fafc', '#e2e8f0', '#94a3b8')
        c.create_text(nx, nyy, text='输出归一化', fill='#0f172a', font=('Microsoft YaHei UI', 8))
        hy = n / 2.0 + 1.35
        hx, hyy, _ = s.project(0, hy, 0)
        hot_out = getattr(self, 'focus_target', None) == 'out'
        self._box(0, hy, 0, 4.0, 0.85, 2.1, '#ccfbf1' if not hot_out else '#99f6e4',
                  '#e6fffb', '#5eead4', ACC)
        if hot_out:
            self._glow(hx, hyy, 72, 20, ACC)
        c.create_text(hx, hyy, text='输出层（语言模型头）  151936×896', fill='#0f172a',
                      font=('Microsoft YaHei UI', 9, 'bold'))

        # 图例与提示
        c.create_text(14, 12, anchor='nw', text='拖拽旋转 · 滚轮缩放 · 点击层查看细节',
                      fill='#94a3b8', font=('Microsoft YaHei UI', 9))
        lx = cw - 16
        for txt, col in (('前馈分支', '#e9d5ff'), ('注意力分支', '#bfdbfe')):
            c.create_rectangle(lx - 58, 9, lx - 50, 19, fill=col, outline='#93c5fd')
            c.create_text(lx - 62, 14, anchor='e', text=txt, fill='#64748b',
                          font=('Microsoft YaHei UI', 8))
            lx -= 96

    def focus(self, target):
        """教学页联动：高亮层号 / 'emb' / 'out'"""
        self.focus_target = target
        if isinstance(target, int) and 0 <= target < (self.model.layer_count if self.model else 0):
            self.selected = target
            self.show_layer(target)
        self.redraw()

    def show_layer(self, i):
        m = self.model
        if m is None or i not in m.layers:
            return
        items = m.layers[i]
        params = sum(x['elements'] for x in items)
        self.lbl_layer.configure(text='第 %d 层' % i)
        self.lbl_params.configure(text='%s 个参数 · %d 个张量 · 占全模型 %.1f%%' % (
            '{:,}'.format(params), len(items), 100.0 * params / m.total_params))
        for r in self.tree.get_children():
            self.tree.delete(r)
        for t in items:
            cn = ROLE_CN.get(t['role'], t['role'])
            if t['is_bias']:
                cn += '（偏置）'
            self.tree.insert('', 'end', values=(cn, t['type'],
                                                '×'.join(str(x) for x in t['shape']),
                                                '{:,}'.format(t['elements'])))


# ----------------------------------------------------------------- 页面：概览
class OverviewPage(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, bg=BG)
        self.app = app

    def refusal_kpi(self):
        rep = getattr(self.app, 'refusal_report', None)
        if not rep:
            return '检测中…'
        return '%.2f%% · %s' % (rep['pct'], rep['level'])
        self.cards = tk.Frame(self, bg=BG)
        self.cards.pack(fill='x', padx=16, pady=(14, 8))
        self.body = tk.Frame(self, bg=BG)
        self.body.pack(fill='both', expand=True, padx=16, pady=(0, 16))

    def refresh(self):
        m = self.app.model
        if m is None:
            return
        for w in self.cards.winfo_children():
            w.destroy()
        for w in self.body.winfo_children():
            w.destroy()
        hp = m.hp
        items = [
            ('参数量', human_params(m.total_params), '%d 个张量' % len(m.tensors)),
            ('权重体积', human_bytes(sum(t['n_bytes'] for t in m.tensors)), '文件 ' + human_bytes(m.reader.size)),
            ('Transformer 层数', str(m.layer_count), '注意力与前馈堆叠层'),
            ('隐藏维 / 前馈维', '%s / %s' % ('{:,}'.format(hp('embedding_length') or 0),
                                          '{:,}'.format(hp('feed_forward_length') or 0)),
             '词元向量维度 / 前馈层宽度'),
            ('注意力头', '%s / %s' % (hp('attention.head_count'), hp('attention.head_count_kv', '—')),
             '查询头 / 键值头（GQA）'),
            ('上下文窗口', '{:,}'.format(hp('context_length') or 0), '最大词元数'),
            ('词表规模', '{:,}'.format(len(m.tokens)), 'BPE 合并规则 %s 条' % '{:,}'.format(
                len(m.meta.get('tokenizer.ggml.merges') or []))),
            ('拒答强度', self.refusal_kpi(), '自动检测 · 0~100 评分'),
        ]
        for i, (k, v, s) in enumerate(items):
            card = tk.Frame(self.cards, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
            card.grid(row=0, column=i, sticky='nsew', padx=(0 if i == 0 else 8, 0))
            self.cards.columnconfigure(i, weight=1)
            tk.Label(card, text=k, bg=PANEL, fg=DIM, font=('Microsoft YaHei UI', 8)).pack(
                anchor='w', padx=10, pady=(8, 0))
            tk.Label(card, text=v, bg=PANEL, fg='#0f172a',
                     font=('Microsoft YaHei UI', 12, 'bold')).pack(anchor='w', padx=10)
            tk.Label(card, text=s, bg=PANEL, fg=DIM, font=('Microsoft YaHei UI', 8)).pack(
                anchor='w', padx=10, pady=(0, 8))

        left = tk.Frame(self.body, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        left.pack(side='left', fill='both', expand=True, padx=(0, 8))
        tk.Label(left, text='模型规格', bg=PANEL, fg=FG,
                 font=('Microsoft YaHei UI', 11, 'bold')).pack(anchor='w', padx=12, pady=(10, 4))
        rows = [
            ('模型架构', 'architecture', m.arch),
            ('模型名称', 'general.name', m.meta.get('general.name', '')),
            ('上下文长度', 'context_length', hp('context_length')),
            ('词元向量维度', 'embedding_length', hp('embedding_length')),
            ('前馈层宽度', 'feed_forward_length', hp('feed_forward_length')),
            ('注意力头数', 'attention.head_count', hp('attention.head_count')),
            ('键值头数（GQA）', 'attention.head_count_kv', hp('attention.head_count_kv', '—')),
            ('旋转基频', 'rope.freq_base', hp('rope.freq_base', '—')),
            ('RMSNorm 容差', 'attention.layer_norm_rms_epsilon', hp('attention.layer_norm_rms_epsilon', '—')),
            ('词表大小', 'vocab_size', '{:,}'.format(len(m.tokens))),
            ('GGUF 文件头', 'general.alignment', 'v%d · 对齐 %d 字节' % (m.reader.version, m.reader.alignment)),
            ('元数据 / 张量', '—', '%d 条 / %d 个' % (m.reader.kv_count, len(m.tensors))),
        ]
        grid = tk.Frame(left, bg=PANEL)
        grid.pack(fill='both', expand=True, padx=12, pady=(0, 10))
        for r, (cn, key, val) in enumerate(rows):
            tk.Label(grid, text=cn, bg=PANEL, fg=FG, font=('Microsoft YaHei UI', 9)).grid(
                row=r, column=0, sticky='w', pady=2)
            tk.Label(grid, text=key, bg=PANEL, fg='#94a3b8', font=('Consolas', 8)).grid(
                row=r, column=1, sticky='w', padx=8)
            tk.Label(grid, text=fmt_num(val), bg=PANEL, fg='#0f172a', font=('Consolas', 9)).grid(
                row=r, column=2, sticky='e')
        grid.columnconfigure(2, weight=1)

        right = tk.Frame(self.body, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        right.pack(side='left', fill='both', expand=True)
        tk.Label(right, text='量化类型分布（按参数量）', bg=PANEL, fg=FG,
                 font=('Microsoft YaHei UI', 11, 'bold')).pack(anchor='w', padx=12, pady=(10, 6))
        agg = {}
        for t in m.tensors:
            tn = gguf_dump.type_name(t['type'])
            a = agg.setdefault(tn, [0, 0])
            a[0] += 1
            a[1] += t['n_elements']
        mx = max(v[1] for v in agg.values())
        for tn, (cnt, elems) in sorted(agg.items(), key=lambda x: -x[1][1]):
            row = tk.Frame(right, bg=PANEL)
            row.pack(fill='x', padx=12, pady=2)
            tk.Label(row, text='%s（%d 个）' % (tn, cnt), bg=PANEL, fg=DIM, width=16,
                     anchor='w', font=('Consolas', 8)).pack(side='left')
            bar = tk.Canvas(row, height=12, bg=PANEL2, highlightthickness=0)
            bar.pack(side='left', fill='x', expand=True, padx=6)
            bar.update_idletasks()
            w = max(4, int(bar.winfo_width() * elems / mx))
            color = {'Q5_0': '#60a5fa', 'Q8_0': '#fbbf24', 'Q6_K': '#818cf8', 'Q4_K': '#38bdf8',
                     'F32': '#a3e635'}.get(tn, '#94a3b8')
            bar.create_rectangle(0, 0, w, 12, fill=color, outline='')
            tk.Label(row, text=human_params(elems), bg=PANEL, fg=DIM, width=10, anchor='e',
                     font=('Consolas', 8)).pack(side='left')
        tk.Label(right, text='文件名写的是 q4_k_m，实际块类型按张量逐个分配，同名方案内部精度可以差几个 bit。',
                 bg=PANEL, fg=DIM, wraplength=460, justify='left',
                 font=('Microsoft YaHei UI', 8)).pack(anchor='w', padx=12, pady=(8, 4))

        tk.Label(right, text='张量角色参数量汇总', bg=PANEL, fg=FG,
                 font=('Microsoft YaHei UI', 11, 'bold')).pack(anchor='w', padx=12, pady=(10, 4))
        by_role = {}
        for t in m.tensors:
            if t['name'].startswith('blk.'):
                role = t['name'].split('.', 2)[2].replace('.weight', '').replace('.bias', '')
            else:
                role = t['name'].replace('.weight', '')
            by_role[role] = by_role.get(role, 0) + t['n_elements']
        mx2 = max(by_role.values()) if by_role else 1
        for role, elems in sorted(by_role.items(), key=lambda x: -x[1])[:10]:
            row = tk.Frame(right, bg=PANEL)
            row.pack(fill='x', padx=12, pady=1)
            cn = ROLE_CN.get(role, GLOBAL_CN.get(role, role))
            tk.Label(row, text='%s（%s）' % (cn, role), bg=PANEL, fg=DIM, width=26,
                     anchor='w', font=('Microsoft YaHei UI', 8)).pack(side='left')
            bar = tk.Canvas(row, height=10, bg=PANEL2, highlightthickness=0)
            bar.pack(side='left', fill='x', expand=True, padx=6)
            bar.update_idletasks()
            w = max(3, int(bar.winfo_width() * elems / mx2))
            bar.create_rectangle(0, 0, w, 10, fill='#3b82f6', outline='')
            tk.Label(row, text=human_params(elems), bg=PANEL, fg=DIM, width=8, anchor='e',
                     font=('Consolas', 8)).pack(side='left')


# ----------------------------------------------------------------- 页面：架构
class ArchPage(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, bg=BG)
        self.app = app
        self.selected = 0
        top = tk.Frame(self, bg=BG)
        top.pack(fill='x', padx=16, pady=(14, 6))
        tk.Label(top, text='模型架构 · 中文数据流', bg=BG, fg=FG,
                 font=('Microsoft YaHei UI', 13, 'bold')).pack(side='left')
        tk.Label(top, text='点击左侧任意层，查看该层的全部张量', bg=BG, fg=DIM,
                 font=('Microsoft YaHei UI', 9)).pack(side='left', padx=12)

        body = tk.Frame(self, bg=BG)
        body.pack(fill='both', expand=True, padx=16, pady=(0, 16))
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        self.list = tk.Listbox(body, width=34, font=('Microsoft YaHei UI', 10), bg=PANEL, fg=FG,
                               highlightthickness=1, highlightbackground=LINE, activestyle='none',
                               selectbackground='#ccfbf1', selectforeground='#0f172a')
        self.list.grid(row=0, column=0, sticky='ns', padx=(0, 10))
        self.list.bind('<<ListboxSelect>>', self.on_select)

        right = tk.Frame(body, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        right.grid(row=0, column=1, sticky='nsew')
        self.head = tk.Label(right, text='第 0 层', bg=PANEL, fg=FG,
                             font=('Microsoft YaHei UI', 13, 'bold'))
        self.head.pack(anchor='w', padx=12, pady=(10, 2))
        self.sub = tk.Label(right, text='', bg=PANEL, fg=DIM, font=('Consolas', 9))
        self.sub.pack(anchor='w', padx=12, pady=(0, 8))

        cols = ('cn', 'raw', 'type', 'shape', 'num', 'size')
        self.tree = ttk.Treeview(right, columns=cols, show='headings')
        for c, t, w, an in zip(cols, ('中文名称', '张量名', '类型', '形状', '元素数', '体积'),
                               (120, 210, 70, 150, 90, 90), ('w', 'w', 'center', 'w', 'e', 'e')):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor=an)
        self.tree.pack(fill='both', expand=True, padx=12, pady=(0, 10))

    def refresh(self):
        m = self.app.model
        if m is None:
            return
        self.list.delete(0, 'end')
        self.list.insert('end', '输入：词元嵌入表')
        for i in range(m.layer_count):
            self.list.insert('end', '第 %d 层   注意力 + 前馈' % i)
        self.list.insert('end', '输出：归一化 + 语言模型头')
        self.list.selection_set(1)
        self.show(1)

    def on_select(self, e):
        sel = self.list.curselection()
        if sel:
            self.show(sel[0])

    def show(self, pos):
        m = self.app.model
        if m is None:
            return
        for r in self.tree.get_children():
            self.tree.delete(r)
        if pos == 0:
            self.head.configure(text='输入 · 词元嵌入表')
            self.sub.configure(text='token_embd.weight')
            tensors = []
            for t in m.tensors:
                if t['name'].startswith('token_embd'):
                    tensors.append(t)
        elif pos == m.layer_count + 1:
            self.head.configure(text='输出 · 归一化 + 语言模型头')
            self.sub.configure(text='output_norm.weight → output.weight')
            tensors = [t for t in m.tensors if t['name'].startswith('output')]
        else:
            i = pos - 1
            items = m.layers.get(i, [])
            self.head.configure(text='第 %d 层' % i)
            self.sub.configure(text='RMSNorm → 自注意力（查询/键/值/输出）→ 残差 → RMSNorm → 前馈（门控/上/下）→ 残差')
            for t in items:
                cn = ROLE_CN.get(t['role'], t['role']) + ('（偏置）' if t['is_bias'] else '')
                self.tree.insert('', 'end', values=(cn, t['name'], t['type'],
                                                    '×'.join(str(x) for x in t['shape']),
                                                    '{:,}'.format(t['elements']), human_bytes(t['bytes'])))
            return
        for t in tensors:
            base = t['name'].split('.')[0]
            cn = GLOBAL_CN.get(base, t['name'])
            self.tree.insert('', 'end', values=(cn, t['name'], gguf_dump.type_name(t['type']),
                                                '×'.join(str(x) for x in t['shape']),
                                                '{:,}'.format(t['n_elements']), human_bytes(t['n_bytes'])))


# ----------------------------------------------------------------- 页面：知识库
class VocabPage(tk.Frame):
    PER = 100

    def __init__(self, master, app):
        super().__init__(master, bg=BG)
        self.app = app
        self.page = 0
        self.hits = []

        bar = tk.Frame(self, bg=BG)
        bar.pack(fill='x', padx=16, pady=(14, 6))
        tk.Label(bar, text='语言知识库', bg=BG, fg=FG,
                 font=('Microsoft YaHei UI', 13, 'bold')).pack(side='left')
        self.entry = tk.Entry(bar, width=34, font=('Microsoft YaHei UI', 10), relief='solid', bd=1)
        self.entry.pack(side='left', padx=12)
        self.entry.bind('<Return>', lambda e: self.search())
        tk.Button(bar, text='搜索', command=self.search, bg=ACC, fg='white', relief='flat',
                  font=('Microsoft YaHei UI', 9), padx=16, pady=2).pack(side='left')
        self.lbl = tk.Label(bar, text='', bg=BG, fg=DIM, font=('Microsoft YaHei UI', 9))
        self.lbl.pack(side='left', padx=12)
        tk.Button(bar, text='下一页 ›', command=lambda: self.flip(1), bg=PANEL, fg=FG, relief='solid',
                  bd=1, font=('Microsoft YaHei UI', 9), padx=12).pack(side='right')
        tk.Button(bar, text='‹ 上一页', command=lambda: self.flip(-1), bg=PANEL, fg=FG, relief='solid',
                  bd=1, font=('Microsoft YaHei UI', 9), padx=12).pack(side='right', padx=6)

        cols = ('id', 'tok', 'len', 'type', 'explain', 'norm')
        self.tree = ttk.Treeview(self, columns=cols, show='headings')
        for c, t, w, an in zip(cols, ('编号', '词元', '字符数', '类型', '中文说明', '向量范数'),
                               (80, 420, 70, 110, 320, 100), ('e', 'w', 'e', 'center', 'w', 'e')):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor=an)
        self.tree.pack(fill='both', expand=True, padx=16, pady=(0, 16))

    def refresh(self):
        self.search()

    def search(self):
        m = self.app.model
        if m is None:
            return
        q = self.entry.get().strip().lower()
        dec = m.ensure_decoded()
        if q:
            self.hits = [i for i in range(len(dec)) if q in dec[i].lower() or str(i).startswith(q)]
        else:
            self.hits = list(range(len(dec)))
        self.page = 0
        self.render()

    def flip(self, d):
        m = self.app.model
        if m is None:
            return
        pages = max(1, (len(self.hits) + self.PER - 1) // self.PER)
        self.page = max(0, min(pages - 1, self.page + d))
        self.render()

    def render(self):
        m = self.app.model
        dec = m.ensure_decoded()
        m.ensure_embedding()
        for r in self.tree.get_children():
            self.tree.delete(r)
        start = self.page * self.PER
        for i in self.hits[start:start + self.PER]:
            ty = m.ttypes[i] if i < len(m.ttypes) else 1
            norm = '%.4f' % m.norms[i] if m.norms is not None else '—'
            self.tree.insert('', 'end', values=(i, dec[i] if i < len(dec) else '', len(dec[i] or ''),
                                                TT.get(ty, ty), m.explain(i), norm))
        pages = max(1, (len(self.hits) + self.PER - 1) // self.PER)
        self.lbl.configure(text='命中 %s / %s · 第 %d / %d 页' % (
            '{:,}'.format(len(self.hits)), '{:,}'.format(len(dec)), self.page + 1, pages))


# ----------------------------------------------------------------- 页面：向量空间
class EmbedPage(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, bg=BG)
        self.app = app
        top = tk.Frame(self, bg=BG)
        top.pack(fill='x', padx=16, pady=(14, 6))
        tk.Label(top, text='向量空间', bg=BG, fg=FG,
                 font=('Microsoft YaHei UI', 13, 'bold')).pack(side='left')
        tk.Label(top, text='词元向量的范数分布、PCA 投影与语义最近邻（全 896 维精确余弦）',
                 bg=BG, fg=DIM, font=('Microsoft YaHei UI', 9)).pack(side='left', padx=12)

        self.cv = tk.Canvas(self, bg=PANEL, highlightthickness=1, highlightbackground=LINE, height=330)
        self.cv.pack(fill='x', padx=16)
        self.cv.bind('<Configure>', lambda e: self.draw())

        q = tk.Frame(self, bg=BG)
        q.pack(fill='x', padx=16, pady=10)
        tk.Label(q, text='查最近邻：', bg=BG, fg=FG, font=('Microsoft YaHei UI', 9)).pack(side='left')
        self.entry = tk.Entry(q, width=28, font=('Microsoft YaHei UI', 10), relief='solid', bd=1)
        self.entry.pack(side='left', padx=6)
        self.entry.bind('<Return>', lambda e: self.find())
        tk.Button(q, text='查询', command=self.find, bg=ACC, fg='white', relief='flat',
                  font=('Microsoft YaHei UI', 9), padx=16).pack(side='left')
        self.msg = tk.Label(q, text='', bg=BG, fg=DIM, font=('Microsoft YaHei UI', 9))
        self.msg.pack(side='left', padx=12)

        cols = ('rank', 'id', 'tok', 'cos')
        self.tree = ttk.Treeview(self, columns=cols, show='headings', height=10)
        for c, t, w, an in zip(cols, ('排名', '编号', '词元', '余弦相似度'), (70, 90, 480, 140),
                               ('center', 'e', 'w', 'e')):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor=an)
        self.tree.pack(fill='both', expand=True, padx=16, pady=(0, 16))

    def refresh(self):
        self.draw()

    def draw(self):
        m = self.app.model
        if m is None:
            return
        m.ensure_embedding()
        if m.norms is None:
            return
        c = self.cv
        c.delete('all')
        W = max(c.winfo_width(), 600)
        H = 330
        # 左：范数直方图
        hist, _edges = np.histogram(m.norms, bins=48)
        mx = hist.max()
        bw = (W * 0.44) / len(hist)
        for i, v in enumerate(hist):
            h = (H - 90) * v / mx
            c.create_rectangle(20 + i * bw, H - 44 - h, 20 + (i + 1) * bw - 1, H - 44,
                               fill='#2dd4bf', outline='')
        c.create_text(20, 16, anchor='nw', text='词元向量范数分布（48 档）', fill='#0f172a',
                      font=('Microsoft YaHei UI', 10, 'bold'))
        c.create_text(20, H - 22, anchor='nw',
                      text='均值 %.4f · 标准差 %.4f · 最大 %.4f' % (
                          float(m.norms.mean()), float(m.norms.std()), float(m.norms.max())),
                      fill='#64748b', font=('Microsoft YaHei UI', 8))
        # 右：PCA 散点
        if m.pca2 is not None:
            x0 = W * 0.5
            X = m.pca2[:, 0]
            Y = m.pca2[:, 1]
            xr = max(abs(X.min()), abs(X.max())) or 1
            yr = max(abs(Y.min()), abs(Y.max())) or 1
            c.create_text(x0, 16, anchor='nw', text='词元向量的 PCA 前两主成分投影', fill='#0f172a',
                          font=('Microsoft YaHei UI', 10, 'bold'))
            for i in range(len(X)):
                px = x0 + 30 + (X[i] / xr) * (W * 0.44) * 0.5
                py = H / 2 + (Y[i] / yr) * (H * 0.34)
                c.create_rectangle(px, py, px + 2, py + 2, fill='#0d9488', outline='')
            c.create_text(W - 20, H - 22, anchor='se',
                          text='采样 %d 点 · PC1 %.1f%% / PC2 %.1f%%' % (
                              len(X), m.pca_var[0] * 100, m.pca_var[1] * 100),
                          fill='#64748b', font=('Microsoft YaHei UI', 8))

    def find(self):
        m = self.app.model
        dec = m.ensure_decoded()
        q = self.entry.get().strip()
        target = -1
        if q.isdigit() and int(q) < len(dec):
            target = int(q)
        else:
            for i, t in enumerate(dec):
                if t == q:
                    target = i
                    break
            if target < 0:
                for i, t in enumerate(dec):
                    if q and q in t:
                        target = i
                        break
        if target < 0:
            self.msg.configure(text='没有找到这个词元')
            return
        self.msg.configure(text='锚点：%s（编号 %d）' % (dec[target], target))
        for r in self.tree.get_children():
            self.tree.delete(r)
        for rank, (idx, cos) in enumerate(m.nearest(target, 10), 1):
            self.tree.insert('', 'end', values=(rank, idx, dec[idx], '%.4f' % cos))


# ----------------------------------------------------------------- 页面：元数据
class MetaPage(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, bg=BG)
        self.app = app
        top = tk.Frame(self, bg=BG)
        top.pack(fill='x', padx=16, pady=(14, 6))
        tk.Label(top, text='元数据 / 张量清单', bg=BG, fg=FG,
                 font=('Microsoft YaHei UI', 13, 'bold')).pack(side='left')

        pane = tk.PanedWindow(self, orient='horizontal', bg=BG, sashwidth=6, bd=0)
        pane.pack(fill='both', expand=True, padx=16, pady=(0, 16))

        left = tk.Frame(pane, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        cols = ('k', 't', 'v')
        self.kvt = ttk.Treeview(left, columns=cols, show='headings')
        for c, t, w, an in zip(cols, ('键名', '类型', '值'), (250, 110, 300), ('w', 'center', 'w')):
            self.kvt.heading(c, text=t)
            self.kvt.column(c, width=w, anchor=an)
        self.kvt.pack(fill='both', expand=True)
        pane.add(left, minsize=420)

        right = tk.Frame(pane, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        cols2 = ('name', 'type', 'shape', 'num', 'size')
        self.t = ttk.Treeview(right, columns=cols2, show='headings')
        for c, t, w, an in zip(cols2, ('张量名', '量化类型', '形状', '元素数', '体积'),
                               (260, 80, 170, 100, 90), ('w', 'center', 'w', 'e', 'e')):
            self.t.heading(c, text=t)
            self.t.column(c, width=w, anchor=an)
        self.t.pack(fill='both', expand=True)
        pane.add(right, minsize=520)

    def refresh(self):
        m = self.app.model
        if m is None:
            return
        kv_cn = {'STRING': '字符串', 'ARRAY': '数组', 'UINT8': '8 位无符号整数', 'INT8': '8 位整数',
                 'UINT16': '16 位无符号整数', 'INT16': '16 位整数', 'UINT32': '32 位无符号整数',
                 'INT32': '32 位整数', 'UINT64': '64 位无符号整数', 'INT64': '64 位整数',
                 'FLOAT32': '32 位浮点数', 'FLOAT64': '64 位浮点数', 'BOOL': '布尔值'}
        tnames = {0: 'UINT8', 1: 'INT8', 2: 'UINT16', 3: 'INT16', 4: 'UINT32', 5: 'INT32',
                  6: 'FLOAT32', 7: 'BOOL', 8: 'STRING', 9: 'ARRAY', 10: 'UINT64',
                  11: 'INT64', 12: 'FLOAT64'}
        for r in self.kvt.get_children():
            self.kvt.delete(r)
        for k, t, v in m.kv:
            if isinstance(v, list):
                s = '[%s] %s' % (len(v), ', '.join(str(x)[:40] for x in v[:3]))
                if len(v) > 3:
                    s += ' …'
            else:
                s = str(v)
            self.kvt.insert('', 'end', values=(k, kv_cn.get(tnames.get(t, ''), tnames.get(t, t)), s[:120]))
        for r in self.t.get_children():
            self.t.delete(r)
        for x in m.tensors:
            self.t.insert('', 'end', values=(x['name'], gguf_dump.type_name(x['type']),
                                             '×'.join(str(i) for i in x['shape']),
                                             '{:,}'.format(x['n_elements']), human_bytes(x['n_bytes'])))




# ----------------------------------------------------------------- 术语词典
GLOSSARY = [
    ('GGUF', 'GGUF format',
     "llama.cpp 定义的模型容器格式：文件头 + 元数据键值对 + 张量索引 + 对齐后的量化块。"
     "一份文件同时装下权重、词表、超参数，可以只 mmap 不全部读进内存。",
     "本文件 v3 格式，26 条元数据、291 个张量、数据区从 5,947,744 字节开始，32 字节对齐。"),
    ('量化', 'quantization',
     "把 fp16/fp32 权重压成 4~8 bit 的块：每 32 或 256 个权重共享一个 fp16 缩放因子，"
     "块内只存整数索引。体积降到 1/3~1/4，精度损失很小。",
     "本模型 462.96 MiB 装着 630.2 M 参数，平均约 5.5 bit/参数。"),
    ('Q4_K / Q5_0 / Q6_K / Q8_0', 'quant types',
     "具体的块编码方案。数字是每权重平均位数，K 后缀表示 256 元素超块 + 二级缩放。",
     "本模型 Q5_0 133 个张量（61.6%）、Q8_0 13 个、Q6_K 12 个、Q4_K 12 个、F32 121 个。"),
    ('张量', 'tensor',
     "多维数组，模型的参数单位。名字形如 blk.3.attn_q.weight 表示「第 3 层的查询投影权重」。",
     "共 291 个：24 层 × 12 + 词元嵌入 + 输出层 + 输出归一化。"),
    ('词元', 'token',
     "模型处理文本的最小单位：一个汉字、一个英文词、或词的一部分。文本先切成词元编号序列再进模型。",
     "词表 151,936 条，「中国」是 1 个词元（编号 58695）。"),
    ('词表', 'vocabulary',
     "全部词元及其编号的列表，附带 BPE 合并规则。",
     "151,936 条词元，其中中文词元 25,511 个，BPE 合并规则 151,387 条。"),
    ('BPE', 'Byte Pair Encoding',
     "子词切分算法：从单个字符开始，反复把最高频的相邻对合并成新单元，直到达到目标词表大小。"
     "生僻词会被拆成几个常见片段。",
     "本模型 151,387 条合并规则，「中国特色」是一个词元，「饕餮」可能被拆成 2~3 个字节片段。"),
    ('嵌入', 'embedding',
     "把词元编号映射成稠密向量的矩阵。每个词元一行，行向量就是它的「语义坐标」。",
     "嵌入矩阵 151,936 × 896 = 136.1 M 参数，占全模型 21.6%。"),
    ('隐藏维', 'hidden size',
     "模型内部向量的宽度，所有层都在这个维度上累加（残差流）。",
     "本模型 896 维。"),
    ('注意力', 'attention',
     "每个词元根据与其他词元的相关性，加权收集信息。Q（查询）与 K（键）点积得到权重，乘 V（值）求和。",
     "每层 4 个投影矩阵：查询、键、值、输出，共约 1.8 M 参数。"),
    ('多头', 'multi-head',
     "把隐藏维切成若干份并行做注意力，每份关注不同的关系模式。",
     "14 个查询头，head_dim = 896 / 14 = 64。"),
    ('GQA', 'Grouped-Query Attention',
     "分组查询注意力：多个查询头共享一组 K/V，大幅减少 KV 缓存显存。",
     "14 个查询头共享 2 个键值头，KV 缓存省 7 倍。"),
    ('KV 缓存', 'KV cache',
     "推理时缓存历史词元的 K/V，避免重复计算。长上下文时它是显存大头。",
     "本模型 KV 头只有 2 个，32,768 上下文下缓存很小。"),
    ('RMSNorm', 'Root Mean Square Norm',
     "归一化层：只除以均方根、不减均值，比 LayerNorm 少一次计算。",
     "每层 2 个（注意力前、前馈前），ε = 9.9999997e-07。"),
    ('RoPE', 'Rotary Position Embedding',
     "旋转位置编码：按位置把 Q/K 向量旋转一个角度，让注意力能感知词序。",
     "基频 θ = 1,000,000，全部 896 维参与旋转。"),
    ('前馈网络', 'FFN / MLP',
     "注意力之后的逐位置两层网络，负责「记住知识」。",
     "896 → 4864 → 896，每层 13.07 M 参数，是注意力的 7 倍。"),
    ('SwiGLU', 'SwiGLU 门控',
     "门控前馈：xW1 ⊙ silu(xW3) 再乘 W2，比普通 ReLU 前馈效果更好。",
     "三个矩阵：门控、上投影、下投影，各 4,358,144 参数。"),
    ('残差', 'residual connection',
     "x = x + f(x)：把子层输出加回主通道，让梯度能直通到底层。",
     "残差流是贯穿 24 层的 896 维通道，拒答方向就藏在这里。"),
    ('logits', 'logits',
     "输出层给出的未归一化分数，每个词表项一个。",
     "151,936 个 logits。"),
    ('softmax', 'softmax',
     "把 logits 变成概率分布：p_i = exp(z_i) / Σ exp(z_j)。温度越低分布越尖锐。",
     "32,768 上下文、151,936 词表，一次前向产出这么多分数。"),
    ('上下文窗口', 'context length',
     "一次能处理的最大词元数，超过就被截断。",
     "32,768 个词元。"),
    ('F32 / F16 / BF16', 'float types',
     "未量化的浮点存储。F32 4 字节、F16/BF16 2 字节。",
     "本模型归一化层用 F32（121 个张量，共 71,552 参数）。"),
    ('拒答方向', 'refusal direction',
     "残差流里一个特定方向：沿它激活越大，模型越倾向拒绝回答。"
     "把该方向从权重里投影掉，拒答行为就消失。",
     "本模型用 11 个拒答词元减 8 个中性词元构造，平均能量 0.03351。"),
    ('正交化', 'orthogonalization',
     "W ← W − r(rᵀW)：把方向 r 从矩阵列空间里减掉，之后输出不再含 r 分量。",
     "49 个张量被处理，平均拒答能量 0.03351 → 0.00022。"),
    ('abliteration', 'abliteration',
     "ablate（切除）与 iteration 的合成词，指把拒答方向从模型权重中移除的整套做法。",
     "本程序「拒答移除」页做的就是这件事，导出 588 MiB 的新 GGUF。"),
    ('PCA', 'Principal Component Analysis',
     "主成分分析：找方差最大的几个正交方向，把 896 维压到 2~3 维画图。",
     "前两主成分解释 3.1% + 0.7% 方差，投影后能看到中心-边缘结构。"),
    ('余弦相似度', 'cosine similarity',
     "两个向量夹角余弦，1 同向、0 正交、-1 反向。检索语义近邻的常用度量。",
     "「中国」与「中國」余弦 0.663，与「中国人」0.517。"),
    ('范数', 'L2 norm',
     "向量的长度 √Σx²。词元向量的范数反映它在残差流里的「音量」。",
     "本模型词元范数均值 0.4528，最大 0.7804（编号 80874）。"),
]


class GlossaryPage(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, bg=BG)
        self.app = app
        top = tk.Frame(self, bg=BG)
        top.pack(fill='x', padx=16, pady=(14, 6))
        tk.Label(top, text='术语词典', bg=BG, fg=FG,
                 font=('Microsoft YaHei UI', 13, 'bold')).pack(side='left')
        tk.Label(top, text='界面上每个专有名词，点开看中文解释和本模型的具体数字',
                 bg=BG, fg=DIM, font=('Microsoft YaHei UI', 9)).pack(side='left', padx=12)
        self.entry = tk.Entry(top, width=24, font=('Microsoft YaHei UI', 10), relief='solid', bd=1)
        self.entry.pack(side='right')
        self.entry.bind('<Return>', lambda e: self.fill())
        tk.Button(top, text='搜索', command=self.fill, bg=ACC, fg='white', relief='flat',
                  font=('Microsoft YaHei UI', 9), padx=14).pack(side='right', padx=6)

        body = tk.Frame(self, bg=BG)
        body.pack(fill='both', expand=True, padx=16, pady=(0, 16))
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        self.lb = tk.Listbox(body, width=32, font=('Microsoft YaHei UI', 10), bg=PANEL, fg=FG,
                             highlightthickness=1, highlightbackground=LINE, activestyle='none',
                             selectbackground='#ccfbf1', selectforeground='#0f172a')
        self.lb.grid(row=0, column=0, sticky='ns', padx=(0, 10))
        self.lb.bind('<<ListboxSelect>>', self.on_select)

        right = tk.Frame(body, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        right.grid(row=0, column=1, sticky='nsew')
        self.h1 = tk.Label(right, text='', bg=PANEL, fg=FG, font=('Microsoft YaHei UI', 15, 'bold'))
        self.h1.pack(anchor='w', padx=18, pady=(16, 0))
        self.h2 = tk.Label(right, text='', bg=PANEL, fg='#0d9488', font=('Consolas', 10))
        self.h2.pack(anchor='w', padx=18, pady=(0, 10))
        self.text = tk.Text(right, bg=PANEL, fg=FG, relief='flat', wrap='word',
                            font=('Microsoft YaHei UI', 11), height=10, spacing1=6, spacing3=10)
        self.text.pack(fill='both', expand=True, padx=18, pady=(0, 16))
        self.text.tag_configure('dim', foreground='#475569')
        self.text.configure(state='disabled')

        self.items = []
        self.fill()

    def fill(self):
        q = self.entry.get().strip().lower()
        self.lb.delete(0, 'end')
        self.items = [x for x in GLOSSARY if not q or q in x[0].lower() or q in x[1].lower()]
        for name, en, _d, _m in self.items:
            self.lb.insert('end', '%s   %s' % (name, en))
        if self.items:
            self.lb.selection_set(0)
            self.show(0)

    def on_select(self, e):
        sel = self.lb.curselection()
        if sel:
            self.show(sel[0])

    def show(self, i):
        if i >= len(self.items):
            return
        name, en, desc, mine = self.items[i]
        self.h1.configure(text=name)
        self.h2.configure(text=en)
        self.text.configure(state='normal')
        self.text.delete('1.0', 'end')
        self.text.insert('1.0', desc + '\n\n')
        self.text.insert('end', '【本模型】' + mine, 'dim')
        self.text.configure(state='disabled')


# ----------------------------------------------------------------- 页面：教学演示
class TeachPage(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, bg=BG)
        self.app = app
        self.steps = []
        self.auto = False
        top = tk.Frame(self, bg=BG)
        top.pack(fill='x', padx=16, pady=(14, 6))
        tk.Label(top, text='教学演示 · 一层一层看懂 Transformer', bg=BG, fg=FG,
                 font=('Microsoft YaHei UI', 13, 'bold')).pack(side='left')
        tk.Label(top, text='每一步都代入当前模型的真实参数，切换时左侧三维链路同步高亮',
                 bg=BG, fg=DIM, font=('Microsoft YaHei UI', 9)).pack(side='left', padx=12)
        self.btn_auto = tk.Button(top, text='自动播放', command=self.toggle_auto, bg=PANEL, fg=FG,
                                  relief='solid', bd=1, font=('Microsoft YaHei UI', 9),
                                  padx=14, pady=2)
        self.btn_auto.pack(side='right')

        body = tk.Frame(self, bg=BG)
        body.pack(fill='both', expand=True, padx=16, pady=(0, 16))
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        self.list = tk.Listbox(body, width=30, font=('Microsoft YaHei UI', 10), bg=PANEL, fg=FG,
                               highlightthickness=1, highlightbackground=LINE, activestyle='none',
                               selectbackground='#ccfbf1', selectforeground='#0f172a')
        self.list.grid(row=0, column=0, sticky='ns', padx=(0, 10))
        self.list.bind('<<ListboxSelect>>', self.on_select)

        right = tk.Frame(body, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        right.grid(row=0, column=1, sticky='nsew')
        self.h1 = tk.Label(right, text='', bg=PANEL, fg=FG, font=('Microsoft YaHei UI', 14, 'bold'))
        self.h1.pack(anchor='w', padx=16, pady=(14, 2))
        self.formula = tk.Label(right, text='', bg='#f1f5f9', fg='#0f766e', font=('Consolas', 12),
                                anchor='w', justify='left', padx=10, pady=6)
        self.formula.pack(fill='x', padx=16, pady=(4, 10))
        self.body = tk.Text(right, bg=PANEL, fg=FG, relief='flat', wrap='word',
                            font=('Microsoft YaHei UI', 10), height=18, spacing1=4, spacing3=6)
        self.body.pack(fill='both', expand=True, padx=16, pady=(0, 14))
        self.body.configure(state='disabled')

    def refresh(self):
        m = self.app.model
        if m is None:
            return
        self.steps = self.build_steps(m)
        self.list.delete(0, 'end')
        for st in self.steps:
            self.list.insert('end', st[0])
        self.list.selection_set(0)
        self.show(0)

    def build_steps(self, m):
        hp = m.hp
        H = hp('embedding_length') or 0
        F = hp('feed_forward_length') or 0
        L = m.layer_count
        nh = hp('attention.head_count') or 0
        nkv = hp('attention.head_count_kv', nh) or nh
        V = len(m.tokens)
        merges = len(m.meta.get('tokenizer.ggml.merges') or [])
        eps = hp('attention.layer_norm_rms_epsilon') or 0
        theta = hp('rope.freq_base') or 0
        ctx = hp('context_length') or 0
        hd = (H // nh) if nh else 0
        steps = [
            ('① 文本 → 词元',
             'tokenizer.encode(text)  →  [id₀, id₁, …]',
             '模型不认识文字，只认识编号。当前词表有 %s 条词元、%s 条 BPE 合并规则。\n\n'
             '中文走 GPT-2 byte-level 规则：一个汉字先拆成 UTF-8 字节，再合并成子词。'
             '「中国」在词表里是 1 个词元（编号 58695），生僻字可能要 2~3 个。\n\n'
             '上下文窗口 %s 个词元，超过就会被截断。' % ('{:,}'.format(V), '{:,}'.format(merges),
                                              '{:,}'.format(ctx))),
            ('② 词元查表成向量',
             'X = E[id] ,   E ∈ ℝ^(%d × %d)' % (V, H),
             '嵌入矩阵 %s × %d = %s 个参数，占了全模型 %s。\n\n'
             '每个词元变成一个 %d 维浮点向量，后续所有计算都在这个维度上进行。'
             '这就是「词义」的数值表示——语义近似的词，向量方向也接近。'
             % ('{:,}'.format(V), H, human_params(V * H),
                '%.1f%%' % (100.0 * V * H / max(m.total_params, 1)), H)),
            ('③ 位置编码（RoPE）',
             'q ← RoPE(q, pos, θ) ,   θ = %s' % ('{:,}'.format(int(theta)) if theta else '—'),
             '注意力本身不知道词序，位置信息靠旋转编码注入：把 Q/K 向量按位置角速度旋转。\n\n'
             '基频 θ=%s 决定旋转快慢，这个模型没有单独的 rope.dimension_count，'
             '按全部 %d 维参与旋转。' % ('{:,}'.format(int(theta)) if theta else '未标注', H)),
            ('④ 每层第一步：RMSNorm',
             'x ← x / √(mean(x²) + ε) · γ ,   ε = %.3e' % eps,
             '归一化让每层输入的量级稳定，训练才不发散。\n\n'
             '与 LayerNorm 的区别：不减均值，只除以均方根，少一次计算。'
             '每层有 2 个 RMSNorm（注意力前、前馈前），各 %d 维。' % H),
            ('⑤ 多头注意力（GQA）',
             'Attn = softmax(QKᵀ / √d) V ,   d = %d' % hd,
             '查询头 %d 个、键值头 %d 个 —— 这是 GQA（分组查询注意力）：'
             '每 %d 个查询头共享一组 K/V，KV 缓存直接省 %d 倍显存。\n\n'
             'head_dim = %d / %d = %d。每层投影矩阵：查询 %d×%d、键 %d×%d、值 %d×%d、输出 %d×%d。'
             % (nh, nkv, max(nh // max(nkv, 1), 1), max(nh // max(nkv, 1), 1),
                H, nh, hd, H, H, hd, H, hd, H, H, H)),
            ('⑥ 每层第二步：SwiGLU 前馈',
             'FFN = (xW₁ ⊙ silu(xW₃)) W₂ ,   %d → %d → %d' % (H, F, H),
             '三个矩阵：门控（%d→%d）、上投影（%d→%d）、下投影（%d→%d）。\n\n'
             '每层前馈约 %s 参数，是注意力的 %d 倍左右 —— 模型的「知识」主要存在这里。'
             % (H, F, H, F, F, H, human_params(3 * H * F),
                int((3 * H * F) / max(4 * H * H, 1)))),
            ('⑦ 残差堆叠 × %d' % L,
             'x = x + Attn(Norm(x))\n x = x + FFN(Norm(x))',
             '每层 = 注意力子层 + 前馈子层，各带一条残差直连。\n\n'
             '本模型 %d 层，每层约 %s 参数，合计 %s。'
             '残差流是一条贯穿全模型的 %d 维向量通道，每层往里加东西——'
             '拒答行为就是加在这条通道上的一个方向（见「拒答移除」页）。'
             % (L, human_params(m.total_params // max(L, 1)), human_params(m.total_params), H)),
            ('⑧ 输出层',
             'logits = Norm(x) · Wᵀ ,   p = softmax(logits)',
             '最后一层输出再归一化一次，乘上 %s × %d 的输出矩阵，得到 %s 个候选词的分数，'
             'softmax 变成概率，按温度采样出下一个词元。\n\n'
             '本模型输出矩阵与嵌入表分开存储，各 %s 参数（不少模型会共享两者）。'
             % ('{:,}'.format(V), H, '{:,}'.format(V), human_params(V * H))),
        ]
        focus = ['emb', 'emb', 0, 0, 0, 0, max(L // 2, 0), 'out']
        return [steps[i] + (focus[i],) for i in range(len(steps))]

    def on_select(self, e):
        sel = self.list.curselection()
        if sel:
            self.show(sel[0])

    def toggle_auto(self):
        self.auto = not self.auto
        self.btn_auto.configure(text='停止播放' if self.auto else '自动播放',
                                bg=ACC if self.auto else PANEL,
                                fg='white' if self.auto else FG)
        if self.auto:
            self.play_next()

    def play_next(self):
        if not self.auto or not self.steps:
            return
        cur = self.list.curselection()
        i = (cur[0] + 1) % len(self.steps) if cur else 0
        self.list.selection_clear(0, 'end')
        self.list.selection_set(i)
        self.list.see(i)
        self.show(i)
        self.after(3200, self.play_next)

    def show(self, i):
        if i >= len(self.steps):
            return
        step = self.steps[i]
        title, formula, text = step[0], step[1], step[2]
        focus = step[3] if len(step) > 3 else None
        if hasattr(self.app, 'focus_chain'):
            self.app.focus_chain(focus)
        self.h1.configure(text=title)
        self.formula.configure(text=formula)
        self.body.configure(state='normal')
        self.body.delete('1.0', 'end')
        self.body.insert('1.0', text)
        self.body.configure(state='disabled')


# ----------------------------------------------------------------- 页面：中文知识体系
class ChinaKBPage(tk.Frame):
    PER = 120

    def __init__(self, master, app):
        super().__init__(master, bg=BG)
        self.app = app
        self.page = 0
        self.hits = []
        self.cache = None

        top = tk.Frame(self, bg=BG)
        top.pack(fill='x', padx=16, pady=(14, 6))
        tk.Label(top, text='中文知识体系', bg=BG, fg=FG,
                 font=('Microsoft YaHei UI', 13, 'bold')).pack(side='left')
        tk.Label(top, text='从 15 万词元里筛出全部中文词元，按字数分层浏览并查看语义近邻',
                 bg=BG, fg=DIM, font=('Microsoft YaHei UI', 9)).pack(side='left', padx=12)

        bar = tk.Frame(self, bg=BG)
        bar.pack(fill='x', padx=16, pady=(0, 6))
        self.entry = tk.Entry(bar, width=28, font=('Microsoft YaHei UI', 10), relief='solid', bd=1)
        self.entry.pack(side='left')
        self.entry.bind('<Return>', lambda e: self.search())
        tk.Button(bar, text='搜索', command=self.search, bg=ACC, fg='white', relief='flat',
                  font=('Microsoft YaHei UI', 9), padx=14).pack(side='left', padx=6)
        self.bucket = tk.StringVar(value='全部')
        cb = ttk.Combobox(bar, textvariable=self.bucket, width=14, state='readonly',
                          values=['全部', '单字', '双字', '三字', '四字及以上'])
        cb.pack(side='left', padx=6)
        cb.bind('<<ComboboxSelected>>', lambda e: self.search())
        tk.Button(bar, text='下一页 ›', command=lambda: self.flip(1), bg=PANEL, fg=FG, relief='solid',
                  bd=1, font=('Microsoft YaHei UI', 9), padx=12).pack(side='right')
        tk.Button(bar, text='‹ 上一页', command=lambda: self.flip(-1), bg=PANEL, fg=FG, relief='solid',
                  bd=1, font=('Microsoft YaHei UI', 9), padx=12).pack(side='right', padx=6)
        self.lbl = tk.Label(bar, text='', bg=BG, fg=DIM, font=('Microsoft YaHei UI', 9))
        self.lbl.pack(side='right', padx=10)

        pane = tk.PanedWindow(self, orient='horizontal', bg=BG, sashwidth=6, bd=0)
        pane.pack(fill='both', expand=True, padx=16, pady=(0, 16))

        left = tk.Frame(pane, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        cols = ('id', 'word', 'len', 'norm', 'explain')
        self.tree = ttk.Treeview(left, columns=cols, show='headings')
        for c, t, w, an in zip(cols, ('编号', '中文词元', '字数', '向量范数', '说明'),
                               (80, 240, 64, 100, 180), ('e', 'w', 'center', 'e', 'w')):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor=an)
        self.tree.pack(fill='both', expand=True)
        self.tree.bind('<<TreeviewSelect>>', self.on_pick)
        pane.add(left, minsize=560)

        right = tk.Frame(pane, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        tk.Label(right, text='语义近邻（全 896 维余弦）', bg=PANEL, fg=FG,
                 font=('Microsoft YaHei UI', 11, 'bold')).pack(anchor='w', padx=12, pady=(10, 4))
        self.anchor = tk.Label(right, text='点左侧任一词元查看', bg=PANEL, fg=DIM,
                               font=('Microsoft YaHei UI', 9))
        self.anchor.pack(anchor='w', padx=12, pady=(0, 6))
        cols2 = ('rank', 'word', 'cos')
        self.nb = ttk.Treeview(right, columns=cols2, show='headings')
        for c, t, w, an in zip(cols2, ('排名', '近邻词元', '余弦'), (70, 200, 100), ('center', 'w', 'e')):
            self.nb.heading(c, text=t)
            self.nb.column(c, width=w, anchor=an)
        self.nb.pack(fill='both', expand=True, padx=12, pady=(0, 10))
        pane.add(right, minsize=380)

    def ensure(self):
        if self.cache is not None:
            return self.cache
        m = self.app.model
        dec = m.ensure_decoded()
        out = []
        for i, t in enumerate(dec):
            if t and any('\u4e00' <= ch <= '\u9fff' for ch in t):
                out.append(i)
        self.cache = out
        return out

    def refresh(self):
        m = self.app.model
        if m is None:
            return
        self.cache = None
        self.ensure()
        self.page = 0
        self.search()

    def filtered(self):
        m = self.app.model
        dec = m.ensure_decoded()
        ids = self.ensure()
        q = self.entry.get().strip()
        b = self.bucket.get()
        out = []
        for i in ids:
            t = dec[i].strip()
            L = len(t)
            if b == '单字' and L != 1:
                continue
            if b == '双字' and L != 2:
                continue
            if b == '三字' and L != 3:
                continue
            if b == '四字及以上' and L < 4:
                continue
            if q and q not in t:
                continue
            out.append(i)
        return out

    def search(self):
        self.hits = self.filtered()
        self.page = 0
        self.render()

    def flip(self, d):
        pages = max(1, (len(self.hits) + self.PER - 1) // self.PER)
        self.page = max(0, min(pages - 1, self.page + d))
        self.render()

    def render(self):
        m = self.app.model
        dec = m.ensure_decoded()
        m.ensure_embedding()
        for r in self.tree.get_children():
            self.tree.delete(r)
        start = self.page * self.PER
        for i in self.hits[start:start + self.PER]:
            t = dec[i]
            norm = '%.4f' % m.norms[i] if m.norms is not None else '—'
            ty = m.ttypes[i] if i < len(m.ttypes) else 1
            self.tree.insert('', 'end', values=(i, t, len(t.strip()), norm, TT.get(ty, ty)))
        pages = max(1, (len(self.hits) + self.PER - 1) // self.PER)
        self.lbl.configure(text='中文词元 %s 个 · 当前 %d / %d 页' % (
            '{:,}'.format(len(self.hits)), self.page + 1, pages))

    def on_pick(self, e):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(self.tree.item(sel[0], 'values')[0])
        m = self.app.model
        dec = m.ensure_decoded()
        self.anchor.configure(text='锚点：%s（编号 %d）' % (dec[idx], idx))
        for r in self.nb.get_children():
            self.nb.delete(r)
        for rank, (i, cos) in enumerate(m.nearest(idx, 12), 1):
            self.nb.insert('', 'end', values=(rank, dec[i], '%.4f' % cos))


# ----------------------------------------------------------------- 页面：拒答移除
class AblitPage(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, bg=BG)
        self.app = app
        self.rows = []
        self.r = None

        top = tk.Frame(self, bg=BG)
        top.pack(fill='x', padx=16, pady=(14, 6))
        tk.Label(top, text='拒答移除 · 方向分析与权重正交化', bg=BG, fg=FG,
                 font=('Microsoft YaHei UI', 13, 'bold')).pack(side='left')
        self.btn_an = tk.Button(top, text='① 分析拒答方向', command=self.do_analyze, bg=ACC, fg='white',
                                relief='flat', font=('Microsoft YaHei UI', 9), padx=14, pady=3)
        self.btn_an.pack(side='right')
        self.btn_ex = tk.Button(top, text='② 移除并导出新模型', command=self.do_export, bg=PANEL, fg=FG,
                                relief='solid', bd=1, font=('Microsoft YaHei UI', 9), padx=14, pady=3)
        self.btn_ex.pack(side='right', padx=8)

        self.card = tk.Frame(self, bg='#f0fdfa', highlightthickness=1, highlightbackground='#99f6e4')
        self.card.pack(fill='x', padx=16, pady=(0, 8))
        self.lbl_score = tk.Label(self.card, text='检测中…', bg='#f0fdfa', fg='#0f766e',
                                  font=('Microsoft YaHei UI', 26, 'bold'))
        self.lbl_score.pack(side='left', padx=(16, 8), pady=(8, 10))
        right = tk.Frame(self.card, bg='#f0fdfa')
        right.pack(side='left', fill='x', expand=True, pady=8)
        self.lbl_level = tk.Label(right, text='', bg='#f0fdfa', fg='#0f766e',
                                  font=('Microsoft YaHei UI', 11, 'bold'), anchor='w')
        self.lbl_level.pack(fill='x')
        self.lbl_verdict = tk.Label(right, text='正在自动扫描各层权重…', bg='#f0fdfa', fg='#334155',
                                    font=('Microsoft YaHei UI', 9), anchor='w', justify='left',
                                    wraplength=980)
        self.lbl_verdict.pack(fill='x')

        self.info = tk.Label(self, text='点「分析拒答方向」：从词元嵌入里构造拒答方向 r，'
                                        '再扫描所有写回残差流的矩阵（注意力输出 / 前馈下投影）。',
                             bg=BG, fg=DIM, justify='left', anchor='w',
                             font=('Microsoft YaHei UI', 9), wraplength=1320)
        self.info.pack(fill='x', padx=16, pady=(0, 8))

        body = tk.Frame(self, bg=BG)
        body.pack(fill='both', expand=True, padx=16, pady=(0, 10))
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        cols = ('rank', 'layer', 'role', 'energy', 'bar', 'shape', 'name')
        self.tree = ttk.Treeview(body, columns=cols, show='headings')
        for c, t, w, an in zip(cols, ('排名', '层', '分支', '拒答能量', '占比', '形状', '张量'),
                               (60, 70, 130, 100, 220, 130, 300),
                               ('center', 'center', 'w', 'e', 'w', 'w', 'w')):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor=an)
        self.tree.grid(row=0, column=0, sticky='nsew')

        foot = tk.Frame(self, bg=BG)
        foot.pack(fill='x', padx=16, pady=(0, 16))
        self.pb = ttk.Progressbar(foot, orient='horizontal', length=420, mode='determinate')
        self.pb.pack(side='left')
        self.log = tk.Label(foot, text='', bg=BG, fg=DIM, font=('Consolas', 9))
        self.log.pack(side='left', padx=12)

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        self.rows = []
        self.r = None
        rep = getattr(self.app, 'refusal_report', None)
        if rep:
            self.set_report(rep)

    def set_report(self, rep):
        self.r = rep['r']
        self.rows = rep['rows']
        self.lbl_score.configure(text='%.2f%%' % rep['pct'])
        self.lbl_level.configure(text='拒答强度 · %s' % rep['level'])
        self.lbl_verdict.configure(text=rep['verdict'] + '  ' + rep['level_note'] +
                                   '  （扫描 %d 个矩阵，最高 %.4f）' % (rep['matrix_count'], rep['max']))
        self.info.configure(text='方向 r 由 %d 个拒答词元减 %d 个中性词元构造，|r|=%.4f。'
                                 '点「移除并导出」即可生成去拒答模型。'
                            % (len(rep['info']['refusal_terms']),
                               len(rep['info']['neutral_terms']), rep['info']['norm']))
        for r_ in self.tree.get_children():
            self.tree.delete(r_)
        top = self.rows[:40]
        bar_max = max((x['energy'] for x in top), default=1)
        for rank, x in enumerate(top, 1):
            bar = '█' * max(1, int(28 * x['energy'] / bar_max))
            role = ROLE_CN.get(x['role'], x['role'])
            self.tree.insert('', 'end', values=(rank, x['layer'], role, '%.5f' % x['energy'],
                                                bar, '×'.join(str(i) for i in x['shape']), x['name']))

    def do_analyze(self):
        if self.app.model is None:
            return
        self.info.configure(text='正在构造方向并扫描 48 个矩阵…')
        self.btn_an.configure(state='disabled')

        def work():
            import abliterate as ab
            try:
                r, info = ab.refusal_direction(self.app.model)
                rows = ab.analyze(self.app.model, r)
                self.app.root.after(0, lambda: self.show_rows(r, info, rows))
            except Exception as e:  # noqa
                self.app.root.after(0, lambda err=e: self.info.configure(text='分析失败：%s' % err))
                self.app.root.after(0, lambda: self.btn_an.configure(state='normal'))

        threading.Thread(target=work, daemon=True).start()

    def show_rows(self, r, info, rows):
        self.r = r
        self.rows = rows
        self.btn_an.configure(state='normal')
        mean = sum(x['energy'] for x in rows) / max(len(rows), 1)
        mx = max((x['energy'] for x in rows), default=0)
        self.info.configure(
            text='方向 r 由 %d 个拒答词元（%s）减去 %d 个中性词元（%s）构造，|r|=%.4f。\n'
                 '扫描 %d 个写残差流的矩阵：平均能量 %.5f，最高 %.5f（占比 %.1f%%）。'
                 % (len(info['refusal_terms']), ' / '.join(info['refusal_terms'][:6]),
                    len(info['neutral_terms']), ' / '.join(info['neutral_terms'][:6]),
                    info['norm'], len(rows), mean, mx, mx * 100))
        for r_ in self.tree.get_children():
            self.tree.delete(r_)
        top = rows[:40]
        bar_max = max((x['energy'] for x in top), default=1)
        for rank, x in enumerate(top, 1):
            bar = '█' * max(1, int(28 * x['energy'] / bar_max))
            role = ROLE_CN.get(x['role'], x['role'])
            self.tree.insert('', 'end', values=(rank, x['layer'], role, '%.5f' % x['energy'],
                                                bar, '×'.join(str(i) for i in x['shape']), x['name']))

    def do_export(self):
        if self.r is None:
            self.info.configure(text='先点「分析拒答方向」，再执行移除。')
            return
        out = os.path.splitext(self.app.model.path)[0] + '-abliterated.gguf'
        self.btn_ex.configure(state='disabled')
        self.pb['value'] = 0
        self.log.configure(text='导出中 → %s' % out)

        def work():
            import abliterate as ab
            try:
                stats = ab.export_abliterated(
                    self.app.model, self.r, out,
                    progress=lambda d, t, txt: self.app.root.after(0, self.on_progress, d, t, txt))
                m2 = ModelData(out)
                m2.ensure_embedding()
                rows2 = ab.analyze(m2, self.r)
                self.app.root.after(0, lambda: self.on_done(stats, rows2))
            except Exception as e:  # noqa
                self.app.root.after(0, lambda err=e: self.info.configure(text='导出失败：%s' % err))
                self.app.root.after(0, lambda: self.btn_ex.configure(state='normal'))

        threading.Thread(target=work, daemon=True).start()

    def on_progress(self, d, t, txt):
        self.pb['value'] = 100.0 * d / max(t, 1)
        self.log.configure(text='%d/%d  %s' % (d, t, txt))

    def on_done(self, stats, rows2):
        self.btn_ex.configure(state='normal')
        self.pb['value'] = 100
        before = sum(x['energy'] for x in self.rows) / max(len(self.rows), 1)
        after = sum(x['energy'] for x in rows2) / max(len(rows2), 1)
        drop = (1 - after / max(before, 1e-9)) * 100
        self.log.configure(text='完成：%s（%s，修改 %d 个张量）' % (
            stats['out'], human_bytes(stats['size']), stats['changed']))
        self.info.configure(
            text='导出完成：%s\n'
                 '平均拒答能量 %.5f → %.5f，下降 %.2f%%；文件 %s，%d 个张量被正交化（其余量化块原样复制）。\n'
                 '新文件可直接用 llama.cpp / 本程序打开验证。'
                 % (stats['out'], before, after, drop, human_bytes(stats['size']), stats['changed']))

# ----------------------------------------------------------------- 主窗口
class App:
    PAGES = [
        ('overview', '概览', OverviewPage),
        ('arch', '模型架构', ArchPage),
        ('chain', '三维链路', Chain3DPage),
        ('teach', '教学演示', TeachPage),
        ('gloss', '术语词典', GlossaryPage),
        ('vocab', '语言知识库', VocabPage),
        ('china', '中文知识', ChinaKBPage),
        ('embed', '向量空间', EmbedPage),
        ('ablate', '拒答移除', AblitPage),
        ('meta', '元数据 / 张量', MetaPage),
    ]

    def __init__(self, root, model_path):
        self.root = root
        self.model = None
        self.quiet = False
        self.model_path = model_path
        root.title('GGUF 解剖台 · 桌面版')
        root.geometry('1440x900')
        root.minsize(1180, 760)
        root.configure(bg=BG)

        style = ttk.Style()
        try:
            style.theme_use('clam')
        except Exception:
            pass
        style.configure('Treeview', background=PANEL, fieldbackground=PANEL, foreground=FG,
                        rowheight=23, font=('Consolas', 9))
        style.configure('Treeview.Heading', background=PANEL2, foreground='#475569',
                        font=('Microsoft YaHei UI', 9, 'bold'), relief='flat')
        style.map('Treeview', background=[('selected', '#ccfbf1')],
                  foreground=[('selected', '#0f172a')])

        head = tk.Frame(root, bg=PANEL, height=58)
        head.pack(fill='x')
        head.pack_propagate(False)
        tk.Label(head, text='GGUF 解剖台', bg=PANEL, fg=ACC,
                 font=('Microsoft YaHei UI', 15, 'bold')).pack(side='left', padx=(18, 8))
        self.lbl_name = tk.Label(head, text='加载中…', bg=PANEL, fg=FG,
                                 font=('Microsoft YaHei UI', 11))
        self.lbl_name.pack(side='left')
        self.lbl_info = tk.Label(head, text='', bg=PANEL, fg=DIM, font=('Consolas', 9))
        self.lbl_info.pack(side='left', padx=14)
        tk.Button(head, text='打开模型…', command=self.open_dialog, bg=PANEL, fg=FG, relief='solid',
                  bd=1, font=('Microsoft YaHei UI', 9), padx=12, pady=2).pack(side='right', padx=16)
        self.lbl_state = tk.Label(head, text='正在解析模型…', bg=PANEL, fg=WARN,
                                  font=('Microsoft YaHei UI', 9))
        self.lbl_state.pack(side='right', padx=8)

        self.recent = []
        self.last_dir = os.getcwd()

        pbar = tk.Frame(root, bg='#eef4fb')
        pbar.pack(fill='x')
        self.lbl_path = tk.Label(pbar, text='模型路径：—', bg='#eef4fb', fg='#334155',
                                 font=('Consolas', 9), anchor='w', width=96)
        self.lbl_path.pack(side='left', padx=(18, 10), pady=5)
        self.lbl_out = tk.Label(pbar, text='', bg='#eef4fb', fg='#7c899c',
                                font=('Consolas', 8), anchor='w', width=52)
        self.lbl_out.pack(side='left', padx=6)
        tk.Button(pbar, text='打开目录', command=self.open_folder, bg='#eef4fb', fg=ACC,
                  relief='flat', font=('Microsoft YaHei UI', 9), padx=8, cursor='hand2').pack(
            side='right', padx=(0, 16))
        tk.Button(pbar, text='复制路径', command=self.copy_path, bg='#eef4fb', fg=ACC,
                  relief='flat', font=('Microsoft YaHei UI', 9), padx=8, cursor='hand2').pack(
            side='right', padx=4)
        self.btn_recent = tk.Menubutton(pbar, text='最近打开 ▾', bg='#eef4fb', fg=ACC,
                                        relief='flat', font=('Microsoft YaHei UI', 9), padx=8)
        self.recent_menu = tk.Menu(self.btn_recent, tearoff=0)
        self.recent_menu.add_command(label='（空）', state='disabled')
        self.btn_recent.configure(menu=self.recent_menu)
        self.btn_recent.pack(side='right', padx=4)
        tk.Frame(pbar, bg='#dbe7f5', height=1).pack(fill='x', side='bottom')

        nav = tk.Frame(root, bg=PANEL)
        nav.pack(fill='x')
        tk.Frame(nav, bg=LINE, height=1).pack(fill='x', side='bottom')
        self.buttons = {}
        for key, title, _ in self.PAGES:
            b = tk.Button(nav, text=title, command=lambda k=key: self.show(k), bg=PANEL, fg=DIM,
                          relief='flat', font=('Microsoft YaHei UI', 10), padx=16, pady=8,
                          activebackground='#f1f5f9', bd=0)
            b.pack(side='left')
            self.buttons[key] = b

        self.container = tk.Frame(root, bg=BG)
        self.container.pack(fill='both', expand=True)
        self.container.rowconfigure(0, weight=1)
        self.container.columnconfigure(0, weight=1)
        self.pages = {}
        for key, _, cls in self.PAGES:
            p = cls(self.container, self)
            p.grid(row=0, column=0, sticky='nsew')
            self.pages[key] = p
        self.current = None
        self.show('overview')

        root.after(80, self.load_async)

    def detect_refusal(self):
        """模型加载后自动跑一遍拒答检测，不阻塞界面"""
        try:
            import abliterate as ab
            rep = ab.auto_detect(self.model)
            self.root.after(0, lambda r=rep: self.on_refusal(r))
        except Exception as e:  # noqa
            self.root.after(0, lambda err=e: print('拒答检测失败:', err))

    def on_refusal(self, rep):
        self.refusal_report = rep
        try:
            self.pages['ablate'].set_report(rep)
        except Exception:
            pass
        try:
            self.pages['overview'].refresh()
        except Exception:
            pass

    def focus_chain(self, target):
        p = self.pages.get('chain')
        if p is None or target is None:
            return
        try:
            p.focus(target)
        except Exception:
            pass

    def show(self, key):
        self.current = key
        self.pages[key].tkraise()
        for k, b in self.buttons.items():
            if k == key:
                b.configure(fg=ACC, font=('Microsoft YaHei UI', 10, 'bold'))
            else:
                b.configure(fg=DIM, font=('Microsoft YaHei UI', 10))
        if self.model is not None:
            p = self.pages[key]
            if hasattr(p, 'refresh'):
                try:
                    p.refresh()
                except Exception:
                    pass

    def copy_path(self):
        p = self.model.path if self.model is not None else self.model_path
        if not p:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(os.path.abspath(p))
        self.lbl_state.configure(text='路径已复制到剪贴板', fg=ACC)
        self.root.after(1800, lambda: self.lbl_state.configure(text='就绪', fg=ACC))

    def open_folder(self):
        p = self.model.path if self.model is not None else self.model_path
        if not p:
            return
        try:
            os.startfile(os.path.dirname(os.path.abspath(p)))
        except Exception:
            pass

    def add_recent(self, path):
        p = os.path.abspath(path)
        if p in self.recent:
            self.recent.remove(p)
        self.recent.insert(0, p)
        self.recent = self.recent[:8]
        self.recent_menu.delete(0, 'end')
        for r in self.recent:
            self.recent_menu.add_command(label=r, command=lambda x=r: self.load_path(x))
        if not self.recent:
            self.recent_menu.add_command(label='（空）', state='disabled')

    def load_path(self, path):
        self.model_path = path
        self.load_async()

    def open_dialog(self):
        path = filedialog.askopenfilename(title='选择 GGUF 模型', initialdir=self.last_dir,
                                          filetypes=[('GGUF 模型', '*.gguf'), ('全部文件', '*.*')])
        if path:
            self.last_dir = os.path.dirname(path)
            self.model_path = path
            self.load_async()

    def load_async(self):
        if not self.model_path:
            self.lbl_state.configure(text='没有模型文件，点右上角「打开模型…」')
            return
        self.lbl_state.configure(text='正在解析模型…')

        def work():
            try:
                m = ModelData(self.model_path)
                m.ensure_decoded()
                m.ensure_embedding()
                self.root.after(0, lambda: self.on_loaded(m, None))
            except Exception as e:  # noqa
                self.root.after(0, lambda err=e: self.on_loaded(None, err))

        threading.Thread(target=work, daemon=True).start()

    def on_loaded(self, m, err):
        if err is not None:
            self.lbl_state.configure(text='加载失败：%s' % err, fg='#dc2626')
            if not self.quiet:
                messagebox.showerror('加载失败', str(err))
            return
        self.model = m
        full = os.path.abspath(m.path)
        self.lbl_path.configure(text='模型路径：' + short_path(full))
        self.lbl_out.configure(text='输出目录：' + short_path(os.path.dirname(full), 46))
        self.add_recent(full)
        self.lbl_name.configure(text=m.meta.get('general.name', os.path.basename(m.path)))
        self.lbl_info.configure(text='GGUF v%d · %s · %s 层 · %s' % (
            m.reader.version, human_bytes(m.reader.size), m.layer_count, human_params(m.total_params)))
        self.lbl_state.configure(text='就绪', fg='#0d9488')
        self.pages['chain'].set_model(m)
        self.refusal_report = None
        threading.Thread(target=self.detect_refusal, daemon=True).start()
        if getattr(self, 'view', None):
            self.show(self.view)
        if getattr(self, 'demo', None) == 'ablate':
            self.show('ablate')
            self.root.after(600, self.pages['ablate'].do_analyze)
        for key, p in self.pages.items():
            if hasattr(p, 'refresh'):
                try:
                    p.refresh()
                except Exception:
                    pass


def find_default_model():
    here = os.path.dirname(os.path.abspath(sys.argv[0]))
    cands = []
    for d in (here, os.path.join(here, '..')):
        try:
            for f in os.listdir(d):
                if f.lower().endswith('.gguf'):
                    p = os.path.join(d, f)
                    cands.append((os.path.getsize(p), p))
        except Exception:
            pass
    pure = [c for c in cands if 'abliterated' not in os.path.basename(c[1]).lower()]
    cands = pure or cands
    cands.sort(reverse=True)   # 优先加载体积最大的原始模型
    return cands[0][1] if cands else ''


def main():
    model_path = ''
    view = None
    shot = None
    demo = None
    delay = 6000
    i = 1
    while i < len(sys.argv):
        a = sys.argv[i]
        if a == '--view' and i + 1 < len(sys.argv):
            view = sys.argv[i + 1]
            i += 2
            continue
        if a == '--shot' and i + 1 < len(sys.argv):
            shot = sys.argv[i + 1]
            i += 2
            continue
        if a == '--demo' and i + 1 < len(sys.argv):
            demo = sys.argv[i + 1]
            i += 2
            continue
        if a == '--shot-delay' and i + 1 < len(sys.argv):
            delay = int(sys.argv[i + 1])
            i += 2
            continue
        if a.startswith('--shot-delay='):
            delay = int(a.split('=', 1)[1])
            i += 1
            continue
        if not a.startswith('--'):
            model_path = a
        i += 1
    if not model_path:
        model_path = find_default_model()

    root = tk.Tk()
    app = App(root, model_path)
    app.quiet = shot is not None
    app.demo = demo
    app.view = view

    if shot:
        def cap():
            ok = False
            try:
                ok = grab_window(root.winfo_id(), shot)
            except Exception as e:
                print('PrintWindow 失败:', e)
            if not ok:
                try:
                    from PIL import ImageGrab
                    root.update_idletasks()
                    root.update()
                    x, y = root.winfo_rootx(), root.winfo_rooty()
                    w, h = root.winfo_width(), root.winfo_height()
                    ImageGrab.grab(bbox=(x, y, x + w, y + h)).save(shot)
                    ok = True
                except Exception as e:
                    print('截图失败:', e)
            print('截图已保存:' if ok else '截图失败:', shot)
            root.destroy()

        def begin():
            root.deiconify()
            root.attributes('-topmost', True)
            root.lift()
            root.update()
            root.after(900, cap)

        root.after(delay, begin)
    root.mainloop()


if __name__ == '__main__':
    main()
