import io

P = r'C:\Users\Administrator\Documents\deepseek-harness\default-workspace\gguf-lab\desktop\abliterate.py'
s = io.open(P, encoding='utf-8').read()
s = s.replace("""    verdict = ('模型存在明确的拒答倾向（%s），主要分布在 %s 层。'
               % (level, ' / '.join('第 %d 层' % l for l, _ in top_layers[:3])))""",
"""    verdict = ('模型存在明确的拒答倾向（%s），主要分布在 %s。'
               % (level, ' / '.join('第 %d 层' % l for l, _ in top_layers[:3])))""")
io.open(P, 'w', encoding='utf-8').write(s)

A = r'C:\Users\Administrator\Documents\deepseek-harness\default-workspace\gguf-lab\desktop\app.py'
a = io.open(A, encoding='utf-8').read()

# ---------- 1) 拒答页顶部评分卡 ----------
a = a.replace("""        self.info = tk.Label(self, text='点「分析拒答方向」：从词元嵌入里构造拒答方向 r，'""",
"""        self.card = tk.Frame(self, bg='#f0fdfa', highlightthickness=1, highlightbackground='#99f6e4')
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

        self.info = tk.Label(self, text='点「分析拒答方向」：从词元嵌入里构造拒答方向 r，'""")

# ---------- 2) set_report：把检测结果灌进界面 ----------
a = a.replace("""    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        self.rows = []
        self.r = None""",
"""    def refresh(self):
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
                                                bar, '×'.join(str(i) for i in x['shape']), x['name']))""")

# ---------- 3) 概览 KPI 加拒答强度 ----------
a = a.replace("""            ('词表规模', '{:,}'.format(len(m.tokens)), 'BPE 合并规则 %s 条' % '{:,}'.format(
                len(m.meta.get('tokenizer.ggml.merges') or []))),""",
"""            ('词表规模', '{:,}'.format(len(m.tokens)), 'BPE 合并规则 %s 条' % '{:,}'.format(
                len(m.meta.get('tokenizer.ggml.merges') or []))),
            ('拒答强度', self.refusal_kpi(), '自动检测 · 0~100 评分'),""")

a = a.replace("""class OverviewPage(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, bg=BG)
        self.app = app""",
"""class OverviewPage(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, bg=BG)
        self.app = app

    def refusal_kpi(self):
        rep = getattr(self.app, 'refusal_report', None)
        if not rep:
            return '检测中…'
        return '%.2f%% · %s' % (rep['pct'], rep['level'])""")

# ---------- 4) App：加载后自动检测 ----------
a = a.replace("""        self.pages['chain'].set_model(m)
        if getattr(self, 'view', None):""",
"""        self.pages['chain'].set_model(m)
        self.refusal_report = None
        threading.Thread(target=self.detect_refusal, daemon=True).start()
        if getattr(self, 'view', None):""")

a = a.replace("""    def focus_chain(self, target):""",
"""    def detect_refusal(self):
        \"\"\"模型加载后自动跑一遍拒答检测，不阻塞界面\"\"\"
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

    def focus_chain(self, target):""")

io.open(A, 'w', encoding='utf-8').write(a)
print('ui patched, len', len(a))
