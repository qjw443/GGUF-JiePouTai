/* GGUF 解剖台 · 前端渲染（零依赖） */
(function () {
  'use strict';

  var D = window.MODEL_DATA;
  if (!D) {
    document.body.innerHTML = '<pre style="padding:24px;color:#ffb454">缺少 web/data/model.js\n先运行:  python build_web_data.py &lt;model.gguf&gt;</pre>';
    return;
  }

  /* 让前端错误直接可见，避免静默空白 */
  window.addEventListener('error', function (ev) {
    var bar = document.createElement('div');
    bar.style.cssText = 'position:fixed;left:0;right:0;bottom:0;z-index:999;background:#3a1418;color:#ffb454;' +
      'padding:8px 14px;font:12px/1.5 ui-monospace,monospace;white-space:pre-wrap';
    bar.textContent = 'JS ERROR: ' + ev.message + '  @ ' + String(ev.filename || '').split('/').pop() + ':' + ev.lineno;
    document.body.appendChild(bar);
  });

  /* ---------------------------- 工具 ---------------------------- */
  function $(s, r) { return (r || document).querySelector(s); }
  function nf(n) {
    if (n === null || n === undefined) return '-';
    var v = Number(n);
    return isNaN(v) ? String(n) : v.toLocaleString('en-US');
  }
  function fmtVal(v) {
    if (v === null || v === undefined) return '—';
    if (typeof v === 'number') {
      if (v !== 0 && Math.abs(v) < 1e-4) return v.toExponential(3);
      if (Number.isInteger(v)) return v.toLocaleString('en-US');
    }
    return String(v);
  }
  function bytes(b) {
    if (b === null || b === undefined) return '-';
    var u = ['B', 'KiB', 'MiB', 'GiB', 'TiB'], i = 0, x = b;
    while (x >= 1024 && i < u.length - 1) { x /= 1024; i++; }
    return (i === 0 ? x : x.toFixed(2)) + ' ' + u[i];
  }
  function params(n) {
    if (n >= 1e9) return (n / 1e9).toFixed(2) + ' B';
    if (n >= 1e6) return (n / 1e6).toFixed(1) + ' M';
    return nf(n);
  }
  function pct(a, b) { return b ? (100 * a / b).toFixed(1) + '%' : '-'; }
  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function visToken(t) {
    if (t === null || t === undefined) return '<span class="dim">∅</span>';
    var s = String(t).replace(/\n/g, '⏎').replace(/\r/g, '␍').replace(/\t/g, '⇥').replace(/ /g, '·');
    s = s.replace(/[\u0000-\u001f\u007f]/g, function (c) {
      return '\\x' + c.charCodeAt(0).toString(16).padStart(2, '0');
    });
    return esc(s);
  }
  function clip(s, n) { s = String(s); return s.length > n ? s.slice(0, n) + '…' : s; }

  var TYPE_CN = {
    'NORMAL': '普通词元', 'CONTROL': '控制符', 'USER_DEFINED': '用户自定义', 'UNUSED': '未使用',
    'UNKNOWN': '未知词', 'BYTE': '字节', 'UNDEFINED': '未定义'
  };

  var TT = { 0: '未定义' , 1: '普通词元', 2: '未知词', 3: '控制符', 4: '用户自定义', 5: '未使用', 6: '字节' };
  var TT_EN = { 0: 'UNDEFINED', 1: 'NORMAL', 2: 'UNKNOWN', 3: 'CONTROL', 4: 'USER_DEFINED', 5: 'UNUSED', 6: 'BYTE' };


  /* 高频英文词元的中文释义（语言知识库的中文映射层） */
  var GLOSS = {
    'the': '定冠词（这/那）', 'of': '的', 'and': '和', 'to': '到 / 向', 'in': '在…里', 'is': '是',
    'you': '你', 'that': '那个', 'it': '它', 'for': '为了', 'on': '在…上', 'with': '与…一起',
    'as': '作为', 'are': '是（复数）', 'be': '是 / 存在', 'at': '在', 'this': '这个', 'have': '有',
    'from': '从', 'or': '或者', 'by': '通过', 'not': '否定', 'but': '但是', 'they': '他们',
    'we': '我们', 'he': '他', 'she': '她', 'his': '他的', 'her': '她的', 'its': '它的',
    'all': '全部', 'an': '一个', 'one': '一', 'two': '二', 'three': '三', 'can': '能',
    'will': '将要', 'would': '将会', 'there': '那里', 'their': '他们的', 'what': '什么',
    'which': '哪个', 'when': '何时', 'where': '哪里', 'who': '谁', 'how': '如何', 'why': '为什么',
    'was': '是（过去）', 'were': '是（过去复数）', 'been': '是（完成）', 'has': '有（三单）',
    'had': '有（过去）', 'do': '做', 'does': '做（三单）', 'did': '做（过去）', 'more': '更多',
    'most': '最多', 'some': '一些', 'any': '任何', 'no': '没有', 'yes': '是', 'if': '如果',
    'then': '然后', 'than': '比', 'so': '所以', 'such': '如此', 'about': '关于', 'into': '进入',
    'over': '在…之上', 'after': '之后', 'before': '之前', 'up': '向上', 'down': '向下',
    'out': '向外', 'off': '关闭', 'only': '仅仅', 'also': '也', 'very': '非常', 'just': '只是',
    'now': '现在', 'new': '新的', 'old': '旧的', 'first': '第一', 'last': '最后', 'other': '其他',
    'time': '时间', 'year': '年', 'people': '人们', 'way': '方式', 'day': '天', 'man': '男人',
    'woman': '女人', 'child': '孩子', 'world': '世界', 'life': '生命', 'hand': '手', 'part': '部分',
    'place': '地方', 'work': '工作', 'week': '周', 'case': '情况', 'point': '点', 'company': '公司',
    'number': '数字', 'group': '组', 'problem': '问题', 'fact': '事实', 'model': '模型',
    'data': '数据', 'text': '文本', 'word': '单词', 'list': '列表', 'item': '项目', 'name': '名字',
    'value': '值', 'type': '类型', 'code': '代码', 'file': '文件', 'line': '行', 'page': '页',
    'user': '用户', 'system': '系统', 'network': '网络', 'server': '服务器', 'client': '客户端',
    'token': '词元 / 令牌', 'vector': '向量', 'matrix': '矩阵', 'layer': '层', 'head': '头',
    'attention': '注意力', 'embedding': '嵌入', 'weight': '权重', 'bias': '偏置', 'norm': '归一化',
    'query': '查询', 'key': '键', 'value2': '值', 'hello': '你好', 'world2': '世界',
    'good': '好的', 'bad': '坏的', 'yes2': '是', 'true': '真', 'false': '假', 'null': '空',
    'error': '错误', 'warning': '警告', 'info': '信息', 'debug': '调试', 'test': '测试',
    'start': '开始', 'end': '结束', 'open': '打开', 'close': '关闭', 'read': '读', 'write': '写',
    'get': '获取', 'set': '设置', 'add': '添加', 'delete': '删除', 'update': '更新', 'create': '创建',
    'list2': '列表', 'map': '映射', 'array': '数组', 'string': '字符串', 'int': '整数', 'float': '浮点',
    'function': '函数', 'return': '返回', 'class': '类', 'object': '对象', 'method': '方法',
    'print': '打印', 'import': '导入', 'input': '输入', 'output': '输出', 'process': '进程',
    'memory': '内存', 'storage': '存储', 'index': '索引', 'sort': '排序', 'search': '搜索'
  };

  var ROLE_GLOSS = {
    'control': '控制符（不参与正文）',
    'special': '对话模板标记',
    'byte': '字节回退（单字节）',
    'space': '空格',
    'lead': '词首（自带前导空格）',
    'cont': '子词续接',
    'digit': '数字',
    'punct': '标点 / 分隔符',
    'cjk': '中文词元',
    'ascii': '英文词元',
    'code': '代码片段',
    'mixed': '混合词元'
  };

  /* GPT-2 byte-level 词表解码：
     GGUF 里中文 token 存的是 UTF-8 字节的 Latin-1 映射（如「中」-> "ä¸"），
     先反查成字节再按 UTF-8 解一次，词表才可读。 */
  var CHAR2BYTE = (function () {
    var bs = [], cs = [], i;
    for (i = 33; i <= 126; i++) bs.push(i);
    for (i = 161; i <= 172; i++) bs.push(i);
    for (i = 174; i <= 255; i++) bs.push(i);
    cs = bs.slice();
    var n = 0;
    for (var b = 0; b < 256; b++) {
      if (bs.indexOf(b) < 0) { bs.push(b); cs.push(256 + n); n++; }
    }
    var m = {};
    for (i = 0; i < bs.length; i++) m[String.fromCharCode(cs[i])] = bs[i];
    return m;
  })();

  var decodedTokens = null;
  function ensureDecoded() {
    if (decodedTokens) return decodedTokens;
    var dec = new TextDecoder('utf-8');
    var out = new Array(tokens.length);
    for (var i = 0; i < tokens.length; i++) {
      var s = tokens[i];
      if (typeof s !== 'string') { out[i] = ''; continue; }
      var bytes = new Uint8Array(s.length), okb = true, j;
      for (j = 0; j < s.length; j++) {
        var b = CHAR2BYTE[s[j]];
        if (b === undefined) { okb = false; break; }
        bytes[j] = b;
      }
      if (!okb) { out[i] = s; continue; }
      var d = dec.decode(bytes);
      out[i] = d.indexOf('\uFFFD') >= 0 ? s : d;
    }
    decodedTokens = out;
    return decodedTokens;
  }

  var TCOL = {
    Q2_K: '#e05d72', Q3_K: '#c46bd8', Q4_K: '#4d8fe0', Q5_K: '#2fb4a8', Q6_K: '#7aa2ff',
    Q8_0: '#f0a04b', Q4_0: '#57b6ff', Q4_1: '#57b6ff', Q5_0: '#57b6ff', Q5_1: '#57b6ff',
    F32: '#8fd14f', F16: '#8fd14f', BF16: '#8fd14f', IQ4_NL: '#ffb454'
  };
  function tcol(t) { return TCOL[t] || '#8b98ad'; }

  var hp = D.hparams || {};
  var hpn = function (k, d) { return (hp[k] === undefined ? d : hp[k]); };
  var tokens = (D.vocab && D.vocab.tokens) || [];
  var ttypes = (D.vocab && D.vocab.types) || [];
  /* 视图状态：必须在任何渲染之前完成初始化（hash 直达时最先被调用） */
  var vq = '', vt = -1, vpage = 0, vper = 100, vnorms = null;
  var vecCache = null;
  var QP = new URLSearchParams(location.search);
  if (QP.get('q')) vq = QP.get('q');

  /* ---------------------------- 头部 + KPI ---------------------------- */
  $('#model-name').textContent = D.name || D.file;
  $('#model-meta').textContent = 'GGUF v' + D.ggufVersion + ' · ' + D.file + ' · ' + D.arch +
    ' · 解析于 ' + D.generated;

  var typeNames = D.typeStats.map(function (t) { return t.type; });
  var kpis = [
    { k: '参数量', v: params(D.totalParams), s: D.tensorCount + ' 个张量' },
    { k: '权重体积', v: bytes(D.totalBytes), s: '文件 ' + bytes(D.fileSize) },
    { k: 'Transformer 层数', v: String(D.layerCount), s: '注意力与前馈堆叠层' },
    { k: '隐藏维 / 前馈维', v: nf(hpn('embedding_length')) + ' / ' + nf(hpn('feed_forward_length')), s: '词元向量维度 / 前馈层宽度' },
    { k: '注意力头', v: nf(hpn('attention.head_count')) + ' / ' + nf(hpn('attention.head_count_kv', hpn('attention.head_count'))), s: '查询头 / 键值头' },
    { k: '上下文窗口', v: nf(hpn('context_length')), s: '最大词元数' },
    { k: '词表规模', v: nf(D.vocabStats.total), s: 'BPE 合并规则 ' + nf(D.vocabStats.mergeCount) + ' 条' },
    { k: '量化', v: typeNames[0] || '-', s: typeNames.join(' + ') }
  ];
  $('#kpis').innerHTML = kpis.map(function (x) {
    return '<div class="kpi"><div class="k">' + esc(x.k) + '</div><div class="v">' + esc(x.v) +
      '</div><div class="s">' + esc(x.s) + '</div></div>';
  }).join('');
  $('#gen-info').textContent = D.file + ' · ' + bytes(D.fileSize) + ' · ' + nf(D.totalParams) + ' 参数';

  /* ---------------------------- 视图切换 ---------------------------- */
  var rendered = {};
  var renderers = { overview: renderOverview, arch: renderArch, vocab: renderVocab, kb3d: renderKb3d, embed: renderEmbed, meta: renderMeta };
  document.querySelectorAll('#tabs button').forEach(function (b) {
    b.addEventListener('click', function () {
      document.querySelectorAll('#tabs button').forEach(function (x) { x.classList.remove('active'); });
      document.querySelectorAll('.view').forEach(function (v) { v.classList.remove('active'); });
      b.classList.add('active');
      var name = b.dataset.view;
      $('#view-' + name).classList.add('active');
      if (!rendered[name]) { rendered[name] = true; renderers[name](); }
    });
  });

  /* hash 路由：index.html#arch / #vocab / #embed / #meta */
  function activateView(name) {
    var btn = document.querySelector('#tabs button[data-view="' + name + '"]');
    if (btn) btn.click();
  }

  /* ---------------------------- 概览 ---------------------------- */
  function barRow(label, frac, right, color) {
    return '<div class="bar-row"><div class="dim">' + esc(label) + '</div>' +
      '<div class="track"><div class="fill" style="width:' + Math.max(0.5, frac * 100).toFixed(2) + '%;background:' + color + '"></div></div>' +
      '<div class="dim" style="text-align:right">' + esc(right) + '</div></div>';
  }

  var ROLE_CN = {
    'output': '输出层', 'token_embd': '词元嵌入', 'output_norm': '输出归一化',
    'attn_q': '查询投影', 'attn_k': '键投影', 'attn_v': '值投影',
    'attn_output': '注意力输出', 'attn_norm': '注意力归一化',
    'ffn_gate': '门控投影', 'ffn_up': '上投影', 'ffn_down': '下投影', 'ffn_norm': '前馈归一化'
  };
  function roleCn(k) {
    var isBias = k.indexOf('(bias)') >= 0;
    var base = k.replace('(bias)', '');
    if (ROLE_CN[base]) return ROLE_CN[base] + (isBias ? '（偏置）' : '');
    return k;
  }

  function renderOverview() {
    var rows = [
      ['模型架构', 'architecture', D.arch],
      ['模型名称', 'general.name', D.name],
      ['上下文长度', 'context_length', fmtVal(hpn('context_length'))],
      ['词元向量维度', 'embedding_length', fmtVal(hpn('embedding_length'))],
      ['前馈层宽度', 'feed_forward_length', fmtVal(hpn('feed_forward_length'))],
      ['注意力头数', 'attention.head_count', fmtVal(hpn('attention.head_count'))],
      ['键值头数（GQA）', 'attention.head_count_kv', fmtVal(hpn('attention.head_count_kv', null))],
      ['旋转位置维度', 'rope.dimension_count', fmtVal(hpn('rope.dimension_count', null))],
      ['旋转基频', 'rope.freq_base', fmtVal(hpn('rope.freq_base', null))],
      ['RMSNorm 容差', 'attention.layer_norm_rms_epsilon', fmtVal(hpn('attention.layer_norm_rms_epsilon', null))],
      ['输入输出嵌入共享', 'tie_word_embeddings', fmtVal(hpn('tie_word_embeddings', null))],
      ['词表大小', 'vocab_size', nf(D.vocabStats.total)],
      ['GGUF 文件头', 'general.alignment', 'v' + D.ggufVersion + ' · 对齐 ' + D.alignment + ' 字节 · 数据区 ' + nf(D.dataStart)],
      ['元数据 / 张量', '—', D.kvCount + ' 条 / ' + D.tensorCount + ' 个']
    ];
    var maxType = Math.max.apply(null, D.typeStats.map(function (t) { return t.elements; }));
    var typeBars = D.typeStats.map(function (t) {
      return barRow(t.type + '  (' + t.count + ' 张量)', t.elements / maxType, params(t.elements), tcol(t.type));
    }).join('');
    var byRole = {};
    D.tensors.forEach(function (t) {
      var role = t.name.indexOf('blk.') === 0
        ? t.name.split('.').slice(2).join('.').replace('.weight', '').replace('.bias', '(bias)')
        : t.name.replace('.weight', '');
      byRole[role] = (byRole[role] || 0) + t.elements;
    });
    var roleList = Object.keys(byRole).map(function (k) { return [k, byRole[k]]; })
      .sort(function (a, b) { return b[1] - a[1]; }).slice(0, 12);
    var maxRole = Math.max.apply(null, roleList.map(function (r) { return r[1]; }));
    var roleBars = roleList.map(function (r) {
      return barRow(roleCn(r[0]) + '（' + r[0] + '）', r[1] / maxRole, params(r[1]), '#3b6ea8');
    }).join('');

    $('#view-overview').innerHTML =
      '<div class="grid2">' +
        '<div class="panel"><h2>模型规格</h2><table>' +
          rows.map(function (r) {
            return '<tr><td style="white-space:nowrap">' + esc(r[0]) +
              ' <span class="dim" style="font-size:11px">' + esc(r[1]) + '</span></td>' +
              '<td class="num">' + esc(r[2]) + '</td></tr>';
          }).join('') +
        '</table>' +
        '<p class="note">词表共 ' + nf(D.vocabStats.total) + ' 个词元，其中字节词元 ' + nf(D.vocabStats.byteTokens) +
        ' 个，BPE 合并规则 ' + nf(D.vocabStats.mergeCount) + ' 条。</p></div>' +
        '<div class="panel"><h2>量化类型分布（按参数量）</h2><div class="bars">' + typeBars + '</div>' +
        '<p class="note">文件名写的是 q4_k_m，实际块类型是 ' + typeNames.join(' + ') +
        ' —— GGUF 按张量逐个分配量化块类型，同一套方案的各层精度可以相差几个 bit。</p>' +
        '<h3>张量角色参数量汇总</h3><div class="bars">' + roleBars + '</div></div>' +
      '</div>';
  }

  /* ---------------------------- 架构 ---------------------------- */
  function renderArch() {
    var emb = D.tensors.filter(function (t) { return t.name === 'token_embd.weight'; })[0];
    var head = D.tensors.filter(function (t) { return t.name === 'output.weight'; })[0];
    var norm = D.tensors.filter(function (t) { return t.name === 'output_norm.weight'; })[0];
    var maxLayer = Math.max.apply(null, D.layers.map(function (l) { return l.params; }));

    var layerHtml = D.layers.map(function (l) {
      var attn = l.tensors.filter(function (t) { return !t.is_bias && t.role.indexOf('attn') === 0 && t.role !== 'attn_norm'; }).length;
      var ffn = l.tensors.filter(function (t) { return t.role.indexOf('ffn') === 0 && t.role !== 'ffn_norm'; }).length;
      var bias = l.tensors.filter(function (t) { return t.is_bias; }).length;
      return '<div class="layer-row" data-i="' + l.index + '">' +
        '<div class="bar" style="width:' + (l.params / maxLayer * 100).toFixed(1) + '%"></div>' +
        '<span class="lidx">' + String(l.index).padStart(2, '0') + '</span>' +
        '<span><span class="tag attn">注意力 ' + attn + '</span><span class="tag ffn">前馈 ' + ffn + '</span>' +
        (bias ? '<span class="tag">偏置 ' + bias + '</span>' : '') + '</span>' +
        '<span class="lparam">' + params(l.params) + '</span></div>';
    }).join('');

    $('#view-arch').innerHTML =
      '<div class="grid2 wide">' +
        '<div class="panel"><h2>数据流（从上到下）</h2><div class="arch-chain">' +
          '<div class="node"><div class="t">token_embd.weight</div><div class="s">' +
            (emb ? (emb.shape.join(' × ') + ' · ' + emb.type + ' · ' + params(emb.elements)) : '—') + '</div></div>' +
          '<div class="arrow">▼</div>' +
          '<div class="layers" id="layer-list">' + layerHtml + '</div>' +
          '<div class="arrow">▼</div>' +
          '<div class="node small"><div class="t">output_norm.weight</div><div class="s">' +
            (norm ? (norm.shape.join(' × ') + ' · ' + norm.type) : '—') + '</div></div>' +
          '<div class="arrow">▼</div>' +
          '<div class="node small"><div class="t">output.weight (lm_head)</div><div class="s">' +
            (head ? (head.shape.join(' × ') + ' · ' + head.type + ' · ' + params(head.elements)) : '—') + '</div></div>' +
        '</div>' +
        '<p class="note">每层 = 1×RMSNorm → GQA 自注意力（q/k/v/o）→ 1×RMSNorm → SwiGLU FFN（gate/up/down）。点击任意层看该层张量。</p></div>' +
        '<div class="panel" id="layer-detail"></div>' +
      '</div>';

    document.querySelectorAll('.layer-row').forEach(function (row) {
      row.addEventListener('click', function () { renderLayer(+row.dataset.i); });
    });
    renderLayer(0);
  }

  var ROLE_ORDER = { attn_norm: 0, attn_q: 1, attn_k: 2, attn_v: 3, attn_output: 4,
    ffn_norm: 5, ffn_gate: 6, ffn_up: 7, ffn_down: 8 };

  function tensorTable(list) {
    list = list.slice().sort(function (a, b) {
      var ra = ROLE_ORDER[a.role] === undefined ? 99 : ROLE_ORDER[a.role];
      var rb = ROLE_ORDER[b.role] === undefined ? 99 : ROLE_ORDER[b.role];
      if (ra !== rb) return ra - rb;
      return a.is_bias - b.is_bias;
    });
    return '<table><thead><tr><th>张量</th><th>类型</th><th>形状</th><th class="num">元素</th><th class="num">体积</th></tr></thead><tbody>' +
      list.map(function (t) {
        var role = t.name.indexOf('blk.') === 0 ? t.name.split('.').slice(2).join('.') : t.name;
        var cn = roleCn(role.replace('.weight', '').replace('.bias', ''));
        return '<tr><td>' + esc(cn) + ' <span class="dim" style="font-size:11px">' + esc(t.name) + '</span></td>' +
          '<td><span class="chip ' + (TCOL[t.type] ? t.type : 'other') + '">' + esc(t.type) + '</span></td>' +
          '<td class="dim">' + esc(t.shape.join(' × ')) + '</td>' +
          '<td class="num">' + nf(t.elements) + '</td>' +
          '<td class="num">' + bytes(t.bytes) + '</td></tr>';
      }).join('') + '</tbody></table>';
  }

  function renderLayer(i) {
    document.querySelectorAll('.layer-row').forEach(function (r) {
      r.classList.toggle('sel', +r.dataset.i === i);
    });
    var L = D.layers[i];
    if (!L) { $('#layer-detail').innerHTML = '<p class="dim">无该层</p>'; return; }
    var kinds = {};
    L.tensors.forEach(function (t) { kinds[t.type] = (kinds[t.type] || 0) + 1; });
    $('#layer-detail').innerHTML =
      '<h2>blk.' + i + ' 层明细</h2>' +
      '<div class="stat-row">' +
        '<div class="stat"><div class="k">参数量</div><div class="v">' + nf(L.params) + '</div></div>' +
        '<div class="stat"><div class="k">张量数</div><div class="v">' + L.tensors.length + '</div></div>' +
        '<div class="stat"><div class="k">类型</div><div class="v">' + Object.keys(kinds).map(function (k) { return k; }).join('+') + '</div></div>' +
      '</div>' +
      '<div class="scroll" style="margin-top:12px">' + tensorTable(L.tensors) + '</div>' +
      '<p class="note">该层占全部参数 ' + pct(L.params, D.totalParams) + '；全模型 ' + D.layerCount + ' 层。</p>';
  }

  /* ---------------------------- 知识库（词表） ---------------------------- */

  function decodeNorms() {
    if (vnorms || !D.embed || !D.embed.normsQ) return vnorms;
    var q = D.embed.normsQ;
    var bin = atob(q.b64), n = q.n;
    var out = new Float32Array(n);
    for (var i = 0; i < n; i++) {
      var b0 = bin.charCodeAt(i * 2), b1 = bin.charCodeAt(i * 2 + 1);
      out[i] = q.min + (b0 | (b1 << 8)) * q.scale;
    }
    vnorms = out;
    return vnorms;
  }


  function isCJKStr(t) {
    if (!t) return false;
    for (var i = 0; i < t.length; i++) {
      var c = t.charCodeAt(i);
      if (c < 0x4e00 || c > 0x9fff) return false;
    }
    return true;
  }

  /* 把一个词元翻译成中文说明：角色 + 释义 */
  function explainToken(idx) {
    var dec = ensureDecoded();
    var s = dec[idx] || '';
    var ty = ttypes[idx] === undefined ? 1 : ttypes[idx];
    var tags = [];
    if (ty === 3) tags.push('控制符');
    else if (ty === 4) tags.push('用户自定义');
    else if (ty === 2) tags.push('未知词');
    else if (ty === 5) tags.push('未使用');
    if (s.indexOf('<|') === 0 && s.lastIndexOf('|>') > 0) tags.push('对话模板标记');
    if (s.indexOf('<0x') === 0 && s.slice(-1) === '>') tags.push('字节回退');
    if (s === ' ') tags.push('空格');
    else if (s.length > 1 && s[0] === ' ') tags.push('词首（带前导空格）');
    if (s.indexOf('\u2581') === 0) tags.push('句首标记');
    if (s.indexOf('##') === 0) tags.push('子词续接');
    var core = s.replace(/^[ \u2581]+/, '').replace(/^##/, '').trim();
    if (!tags.length && core) {
      var low = core.toLowerCase();
      if (GLOSS[low]) tags.push(GLOSS[low]);
      else if (isCJKStr(core)) tags.push(core.length === 1 ? '单字' : '中文词');
      else if (/^[0-9]+$/.test(core)) tags.push('数字 ' + core);
      else if (/^[A-Za-z]+$/.test(core)) tags.push('英文词');
      else if (/^[A-Za-z0-9]+$/.test(core)) tags.push('英文数字混合');
      else if (/[(){}\[\]<>=+*/\\|_$#@!~^&;:]/.test(core)) tags.push('代码片段');
      else tags.push('符号');
    }
    if (!tags.length) tags.push('普通词元');
    return tags.join(' · ');
  }

  function renderVocab() {
    ensureDecoded();
    var vs = D.vocabStats;
    var maxC = Math.max.apply(null, vs.typeCounts.map(function (x) { return x.count; }));
    var typeBars = vs.typeCounts.map(function (x) {
      return barRow(TYPE_CN[x.type] || x.type, x.count / maxC, nf(x.count), '#3b6ea8');
    }).join('');
    var maxL = Math.max.apply(null, vs.lenHist.map(function (x) { return x.count; }));
    var lenBars = vs.lenHist.map(function (x) {
      return barRow(x.len === 16 ? '16+' : String(x.len), x.count / maxL, nf(x.count), '#2f8f83');
    }).join('');
    var special = Object.keys(vs.special || {}).map(function (k) {
      return '<div class="stat"><div class="k">' + esc(k.replace('tokenizer.ggml.', '')) + '</div><div class="v">' + esc(vs.special[k]) + '</div></div>';
    }).join('');
    var mergeSample = (vs.merges || []).slice(0, 160).map(function (m) {
      return '<span class="pill" style="margin:2px">' + esc(m) + '</span>';
    }).join('');

    $('#view-vocab').innerHTML =
      '<div class="grid2">' +
        '<div class="panel"><h2>词表构成</h2>' +
          '<div class="stat-row">' +
            '<div class="stat"><div class="k">词元总数</div><div class="v">' + nf(vs.total) + '</div></div>' +
            '<div class="stat"><div class="k">BPE 合并规则</div><div class="v">' + nf(vs.mergeCount) + '</div></div>' +
            '<div class="stat"><div class="k">字节词元</div><div class="v">' + nf(vs.byteTokens) + '</div></div>' +
          '</div>' +
          '<h3>词元类型分布</h3><div class="bars">' + typeBars + '</div>' +
          '<h3>特殊词元配置</h3><div class="stat-row">' + special + '</div>' +
        '</div>' +
        '<div class="panel"><h2>词元字符长度分布</h2><div class="bars">' + lenBars + '</div>' +
          '<h3>BPE 合并规则（前 160 条 / 共 ' + nf(vs.mergeCount) + '）</h3>' +
          '<div class="scroll" style="max-height:150px;padding:6px">' + mergeSample + '</div>' +
          '<p class="note">合并规则是语言知识库的构词骨架：模型把生僻词拆成这些子词片段，再映射成向量。</p>' +
        '</div>' +
      '</div>' +
      '<div class="panel" style="margin-top:14px"><h2>词表检索</h2>' +
        '<div class="toolbar">' +
          '<input type="search" id="vsearch" placeholder="输入词元文本或编号（如 中国、hello、1234）">' +
          '<select id="vtype"><option value="-1">全部类型</option></select>' +
          '<select id="vper"><option value="100">100 / 页</option><option value="200">200 / 页</option><option value="500">500 / 页</option></select>' +
          '<span class="dim" id="vcount"></span>' +
        '</div>' +
        '<div class="pager" id="vpager"></div>' +
        '<div class="scroll tall"><table><thead><tr><th>编号</th><th>词元</th><th class="num">字符数</th><th>类型</th><th>中文说明</th>' +
          (D.embed && D.embed.normsQ ? '<th class="num">向量 L2 范数</th>' : '') + '</tr></thead>' +
          '<tbody id="vbody"></tbody></table></div>' +
      '</div>';

    var sel = $('#vtype');
    vs.typeCounts.forEach(function (x) {
      var o = document.createElement('option');
      o.value = String(vs.typeCounts.indexOf(x));
      o.textContent = (TYPE_CN[x.type] || x.type) + '（' + nf(x.count) + '）';
      sel.appendChild(o);
    });
    sel.addEventListener('change', function () {
      var idx = +sel.value;
      vt = idx < 0 ? -1 : Number(Object.keys(TT).filter(function (k) { return TT[k] === vs.typeCounts[idx].type; })[0]);
      vpage = 0; renderVocabTable();
    });
    $('#vsearch').addEventListener('input', function (e) { vq = e.target.value.trim(); vpage = 0; renderVocabTable(); });
    $('#vper').addEventListener('change', function (e) { vper = +e.target.value; vpage = 0; renderVocabTable(); });
    renderVocabTable();
  }

  function vocabMatches() {
    var out = [];
    var q = vq.toLowerCase();
    var dec = ensureDecoded();
    for (var i = 0; i < tokens.length; i++) {
      if (vt >= 0 && ttypes[i] !== vt) continue;
      if (q) {
        var tk = dec[i].toLowerCase();
        var raw = String(tokens[i]).toLowerCase();
        if (tk.indexOf(q) < 0 && raw.indexOf(q) < 0 && String(i).indexOf(q) !== 0) continue;
      }
      out.push(i);
      if (out.length > 200000) break;
    }
    return out;
  }

  function renderVocabTable() {
    var ids = vocabMatches();
    var pages = Math.max(1, Math.ceil(ids.length / vper));
    if (vpage >= pages) vpage = pages - 1;
    var slice = ids.slice(vpage * vper, vpage * vper + vper);
    var norms = decodeNorms();
    var hasNorm = !!(D.embed && D.embed.normsQ && norms);
    var dec = ensureDecoded();
    $('#vbody').innerHTML = slice.map(function (i) {
      var ty = ttypes[i] === undefined ? 1 : ttypes[i];
      var raw = tokens[i];
      var shown = dec[i];
      var alt = (shown !== raw) ? ' <span class="dim">' + visToken(raw) + '</span>' : '';
      return '<tr><td class="num dim">' + i + '</td><td class="tok">' + visToken(shown) + alt + '</td>' +
        '<td class="num">' + String(shown || '').length + '</td>' +
        '<td class="dim">' + esc(TT[ty] || ty) + '</td>' +
        '<td class="dim">' + esc(explainToken(i)) + '</td>' +
        (hasNorm ? '<td class="num">' + norms[i].toFixed(4) + '</td>' : '') + '</tr>';
    }).join('') || '<tr><td colspan="6" class="dim">没有匹配项</td></tr>';
    $('#vcount').textContent = '命中 ' + nf(ids.length) + ' / ' + nf(tokens.length);
    $('#vpager').innerHTML =
      '<button ' + (vpage === 0 ? 'disabled' : '') + ' data-p="0">⏮</button>' +
      '<button ' + (vpage === 0 ? 'disabled' : '') + ' data-p="' + (vpage - 1) + '">‹</button>' +
      '<span>第 ' + (vpage + 1) + ' / ' + pages + ' 页</span>' +
      '<button ' + (vpage >= pages - 1 ? 'disabled' : '') + ' data-p="' + (vpage + 1) + '">›</button>' +
      '<button ' + (vpage >= pages - 1 ? 'disabled' : '') + ' data-p="' + (pages - 1) + '">⏭</button>';
    document.querySelectorAll('#vpager button').forEach(function (b) {
      b.addEventListener('click', function () { vpage = +b.dataset.p; renderVocabTable(); });
    });
  }

  /* ---------------------------- 嵌入空间 ---------------------------- */

  /* 精确近邻索引：生成端用全 896 维算好的 top-k（PCA 降维会丢语义，实测 top10 重合 0/10） */
  var simMap = null;
  function buildSimMap() {
    if (simMap) return simMap;
    simMap = {};
    if (D.sim && D.sim.ids) {
      for (var i = 0; i < D.sim.ids.length; i++) simMap[D.sim.ids[i]] = i;
    }
    return simMap;
  }

  function renderSim(id) {
    var map = buildSimMap();
    var dec = ensureDecoded();
    var info = document.querySelector('#siminfo');
    var body = document.querySelector('#simbody');
    var pos = map[id];
    if (pos === undefined) {
      info.textContent = 'id=' + id + ' «' + clip(dec[id] || '', 16) + '» 不在精确索引内';
      body.innerHTML = '<tr><td colspan="4" class="dim">索引只覆盖 ' +
        (D.sim ? nf(D.sim.seeds) : 0) + ' 个 token（id&lt;16384 的高频 token + 1~2 字中文），换用 中国 / 中 / 人 / hello / the 试试</td></tr>';
      return;
    }
    var rows = D.sim.rows[pos];
    info.innerHTML = '锚点 id=' + id + ' «' + esc(clip(dec[id], 20)) + '» · 全 896 维余弦 · top' + D.sim.topk;
    body.innerHTML = rows.map(function (r, i) {
      return '<tr><td class="num dim">' + (i + 1) + '</td><td class="num dim">' + r[0] + '</td>' +
        '<td class="tok">' + visToken(dec[r[0]]) + '</td><td class="num">' + r[1].toFixed(3) + '</td></tr>';
    }).join('');
  }

  function findTokenId(q) {
    q = String(q).trim();
    if (!q) return -1;
    if (/^\d+$/.test(q) && +q < tokens.length) return +q;
    var dec = ensureDecoded();
    var i;
    for (i = 0; i < tokens.length; i++) if (dec[i] === q || tokens[i] === q) return i;
    for (i = 0; i < tokens.length; i++) {
      if (dec[i].indexOf(q) >= 0 || String(tokens[i]).indexOf(q) >= 0) return i;
    }
    return -1;
  }

  function renderEmbed() {
    var E = D.embed;
    if (!E || !E.available) {
      $('#view-embed').innerHTML = '<div class="panel dim">这个 GGUF 没有 token_embd 张量，跳过嵌入分析。</div>';
      return;
    }
    var h = E.normsHist, maxC = Math.max.apply(null, h.counts);
    var histHtml = h.counts.map(function (c, i) {
      return '<div class="b" style="height:' + (100 * c / maxC).toFixed(2) + '%" title="' +
        h.edges[i].toFixed(3) + ' – ' + h.edges[i + 1].toFixed(3) + ' : ' + nf(c) + ' tokens"></div>';
    }).join('');

    var pts = E.pca.points;
    var xs = pts.map(function (p) { return p[0]; }), ys = pts.map(function (p) { return p[1]; });
    var xmin = Math.min.apply(null, xs), xmax = Math.max.apply(null, xs);
    var ymin = Math.min.apply(null, ys), ymax = Math.max.apply(null, ys);
    var W = 640, H = 400, pad = 18;
    var sx = function (x) { return pad + (x - xmin) / (xmax - xmin || 1) * (W - 2 * pad); };
    var sy = function (y) { return H - pad - (y - ymin) / (ymax - ymin || 1) * (H - 2 * pad); };
    var dots = pts.map(function (p) {
      var ty = ttypes[p[2]] === undefined ? 1 : ttypes[p[2]];
      var col = ty === 6 ? '#5b6473' : ty === 3 ? '#e05d72' : ty === 4 ? '#ffb454' : '#4dd6c1';
      return '<circle class="dot" cx="' + sx(p[0]).toFixed(1) + '" cy="' + sy(p[1]).toFixed(1) +
        '" r="1.7" fill="' + col + '" fill-opacity="0.75"><title>id ' + p[2] + ' · ' + esc(clip(tokens[p[2]] || '', 24)) + '</title></circle>';
    }).join('');

    var topRows = E.topTokens.map(function (t) {
      return '<tr><td class="num dim">' + t[0] + '</td><td class="tok">' + visToken(t[1]) + '</td><td class="num">' + t[2].toFixed(4) + '</td></tr>';
    }).join('');

    $('#view-embed').innerHTML =
      '<div class="grid2">' +
        '<div class="panel"><h2>词元向量范数分布</h2>' +
          '<div class="stat-row">' +
            '<div class="stat"><div class="k">均值</div><div class="v">' + E.stats.mean.toFixed(4) + '</div></div>' +
            '<div class="stat"><div class="k">标准差</div><div class="v">' + E.stats.std.toFixed(4) + '</div></div>' +
            '<div class="stat"><div class="k">最小</div><div class="v">' + E.stats.min.toFixed(4) + '</div></div>' +
            '<div class="stat"><div class="k">最大</div><div class="v">' + E.stats.max.toFixed(4) + '</div></div>' +
          '</div>' +
          '<div class="hist" style="margin-top:12px">' + histHtml + '</div>' +
          '<p class="note">' + esc(E.tensor) + ' · ' + esc(E.shape.join(' × ')) + ' · ' + esc(E.quant) +
          ' 量化后反量化为 fp32 统计。范数越大的 token 在残差流里「声音」越大。</p>' +
          '<h3>范数最高的词元（前 120 / 共 ' + nf(E.shape[0]) + '）</h3>' +
          '<div class="scroll" style="max-height:220px"><table><thead><tr><th>编号</th><th>词元</th><th class="num">L2 范数</th></tr></thead>' +
          '<tbody>' + topRows + '</tbody></table></div>' +
        '</div>' +
        '<div class="panel"><h2>嵌入空间投影（PCA 前 2 主成分）</h2>' +
          '<svg class="scatter" viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="xMidYMid meet">' + dots + '</svg>' +
          '<p class="note">随机采样 ' + nf(pts.length) + ' 个 token；解释方差 PC1 ' +
          (E.pca.explained[0] * 100).toFixed(1) + '% / PC2 ' + (E.pca.explained[1] * 100).toFixed(1) +
          '%。青色 = 普通词元，灰 = 字节，黄 = 用户自定义，红 = 控制符。</p>' +
        '</div>' +
      '</div>' +
      '<div class="panel" style="margin-top:14px"><h2>语义最近邻（全 896 维精确余弦）</h2>' +
        '<div class="toolbar"><input type="search" id="simq" placeholder="输入词元文本或编号，如 中国 / hello / 42">' +
        '<button class="btn" id="simbtn">查最近邻</button><span class="dim" id="siminfo"></span></div>' +
        '<div class="scroll" style="max-height:340px"><table class="sim-list"><thead><tr><th>排名</th><th>编号</th><th>词元</th><th class="num">余弦相似度</th></tr></thead>' +
        '<tbody id="simbody"><tr><td colspan="4" class="dim">等待查询…</td></tr></tbody></table></div>' +
        '<p class="note">用 token_embd 原始 896 维向量算余弦，结果在生成端预计算，索引覆盖 ' +
        (D.sim ? nf(D.sim.seeds) : 0) + ' 个 token（id&lt;16384 的高频 token + 1~2 字中文），' +
        '每个种子取 top' + (D.sim ? D.sim.topk : 0) + '。降维到 8 维再用余弦会失真（实测与全维 top10 重合 0/10），所以这里不改维。</p>' +
      '</div>';

    function doSim() {
      var id = findTokenId($('#simq').value);
      if (id < 0) { $('#siminfo').textContent = '没找到 token: ' + $('#simq').value; return; }
      renderSim(id);
    }
    $('#simbtn').addEventListener('click', doSim);
    $('#simq').addEventListener('keydown', function (e) { if (e.key === 'Enter') doSim(); });
    if (QP.get('sim')) { $('#simq').value = QP.get('sim'); doSim(); }
  }


  /* ---------------------------- 三维知识体系 ---------------------------- */
  var KB3D_COLOR = ['#dc2626', '#2563eb', '#7c3aed', '#64748b', '#ea580c', '#059669'];

  function renderKb3d() {
    var K = D.kb3d;
    if (!K || !K.points || !K.points.length) {
      document.querySelector('#view-kb3d').innerHTML =
        '<div class="panel dim">这个模型没有 token_embd 张量，三维知识体系跳过。</div>';
      return;
    }
    var dec = ensureDecoded();
    var langCounts = K.langCounts || [];
    var legend = K.langs.map(function (name, i) {
      var c = (langCounts[i] ? langCounts[i].count : 0);
      return '<label><input type="checkbox" data-lang="' + i + '" checked>' +
        '<span class="sw" style="background:' + KB3D_COLOR[i] + '"></span>' + esc(name) +
        '<span class="cnt">' + nf(c) + ' 个</span></label>';
    }).join('');
    var maxB = Math.max.apply(null, (K.bucketCounts || [{ count: 1 }]).map(function (x) { return x.count; }));
    var bucketBars = (K.bucketCounts || []).map(function (b, i) {
      return barRow(b.name, b.count / maxB, nf(b.count), ['#f87171', '#60a5fa', '#a78bfa', '#fb923c'][i % 4]);
    }).join('');
    var axes = [
      ['维度一 · 语言体系', '中文 / 英文 / 数字 / 符号 / 代码片段 / 特殊标记，按解码后的字符判定'],
      ['维度二 · 结构层级', '单字 → 短词（2~3 字）→ 词（4~6 字）→ 短语（7 字以上）'],
      ['维度三 · 语义坐标', 'embedding 的 896 维 PCA 前三主成分，解释方差 ' +
        (K.explained ? K.explained.map(function (x) { return (x * 100).toFixed(1) + '%'; }).join(' + ') : '—')]
    ].map(function (a) {
      return '<div class="stat" style="margin-bottom:8px"><div class="k">' + esc(a[0]) + '</div>' +
        '<div class="s" style="color:#64748b;font-size:11px">' + esc(a[1]) + '</div></div>';
    }).join('');

    document.querySelector('#view-kb3d').innerHTML =
      '<div class="kb3d-wrap">' +
        '<div class="panel"><h2>三维知识体系 · 语义点云</h2>' +
          '<div class="toolbar">' +
            '<button class="btn" id="kb3d-auto">自动旋转</button>' +
            '<button class="btn" id="kb3d-reset">重置视角</button>' +
            '<span class="dim" id="kb3d-count"></span>' +
          '</div>' +
          '<canvas id="kb3d-canvas" width="1040" height="640"></canvas>' +
          '<div class="kb3d-hint">拖拽旋转 · 滚轮缩放 · 悬停查看词元 · 采样 ' + nf(K.n) +
          ' 个词元，每个点是一个词元在语义空间的坐标</div>' +
        '</div>' +
        '<div class="panel"><h2>三个维度</h2>' + axes +
          '<h3>维度一 · 语言体系（全量 ' + nf(D.vocabStats.total) + ' 个词元）</h3>' +
          '<div class="legend" id="kb3d-legend">' + legend + '</div>' +
          '<h3>维度二 · 结构层级</h3><div class="bars">' + bucketBars + '</div>' +
          '<h3>维度三 · 语义簇（8 簇 · 采样 ' + nf(K.n) + ' 点）</h3><div class="bars" id="kb3d-clusters"></div>' +
        '</div>' +
      '</div>' +
      '<div id="kb3d-tip"></div>';

    var cv = document.getElementById('kb3d-canvas');
    var ctx = cv.getContext('2d');
    var W = cv.width, H = cv.height;
    var pts = K.points;
    var enabled = [1, 1, 1, 1, 1, 1];
    var rotX = -0.32, rotY = 0.6, zoom = 1, auto = false, raf = null;
    var screen = new Float32Array(pts.length * 2);
    var nMin = 1e9, nMax = -1e9;
    pts.forEach(function (p) { if (p[6] < nMin) nMin = p[6]; if (p[6] > nMax) nMax = p[6]; });

    var shown = 0;
    var clustersEl = document.getElementById('kb3d-clusters');
    var clCounts = K.clusterCounts || [];
    var clMax = Math.max.apply(null, clCounts.map(function (x) { return x.count; }).concat([1]));

    function draw() {
      ctx.clearRect(0, 0, W, H);
      var cy = Math.cos(rotY), sy = Math.sin(rotY);
      var cx = Math.cos(rotX), sx = Math.sin(rotX);
      var arr = [];
      shown = 0;
      for (var i = 0; i < pts.length; i++) {
        var p = pts[i];
        if (!enabled[p[4]]) { screen[i * 2] = 1e9; continue; }
        var x1 = p[0] * cy + p[2] * sy;
        var z1 = -p[0] * sy + p[2] * cy;
        var y1 = p[1] * cx - z1 * sx;
        var z2 = p[1] * sx + z1 * cx;
        var sc = (2.6 / (3.3 + z2)) * zoom;
        var px = W / 2 + x1 * sc * W * 0.46;
        var py = H / 2 - y1 * sc * H * 0.46;
        screen[i * 2] = px;
        screen[i * 2 + 1] = py;
        arr.push([z2, i, px, py, sc]);
        shown++;
      }
      arr.sort(function (a, b) { return a[0] - b[0]; });
      for (var k = 0; k < arr.length; k++) {
        var o = arr[k], pp = pts[o[1]];
        var r = 1.0 + (pp[6] - nMin) / ((nMax - nMin) || 1) * 2.0;
        var rad = Math.max(1, r * Math.min(1.6, o[4] * 0.95));
        ctx.fillStyle = KB3D_COLOR[pp[4]] + 'cc';
        ctx.fillRect(o[2] - rad, o[3] - rad, rad * 2, rad * 2);
      }
      document.getElementById('kb3d-count').textContent = '当前显示 ' + nf(shown) + ' / ' + nf(pts.length) + ' 点';
    }

    clustersEl.innerHTML = clCounts.map(function (x, j) {
      return barRow('语义簇 #' + x.id, x.count / clMax, nf(x.count), KB3D_COLOR[j % 6]);
    }).join('');

    document.querySelectorAll('#kb3d-legend input').forEach(function (cb) {
      cb.addEventListener('change', function () {
        enabled[+cb.dataset.lang] = cb.checked ? 1 : 0;
        draw();
      });
    });

    var tip = document.getElementById('kb3d-tip');
    var dragging = false, lx = 0, ly = 0;
    cv.addEventListener('mousedown', function (e) {
      dragging = true; lx = e.clientX; ly = e.clientY; cv.classList.add('dragging');
    });
    window.addEventListener('mouseup', function () {
      dragging = false; if (cv) cv.classList.remove('dragging');
    });
    cv.addEventListener('mousemove', function (e) {
      if (dragging) {
        rotY += (e.clientX - lx) * 0.006;
        rotX += (e.clientY - ly) * 0.006;
        rotX = Math.max(-1.4, Math.min(1.4, rotX));
        lx = e.clientX; ly = e.clientY;
        draw();
        return;
      }
      var rect = cv.getBoundingClientRect();
      var mx = (e.clientX - rect.left) * (W / rect.width);
      var my = (e.clientY - rect.top) * (H / rect.height);
      var best = -1, bd = 169;
      for (var i = 0; i < pts.length; i++) {
        if (!enabled[pts[i][4]]) continue;
        var dx = screen[i * 2] - mx, dy = screen[i * 2 + 1] - my;
        if (dx > 13 || dx < -13 || dy > 13 || dy < -13) continue;
        var d = dx * dx + dy * dy;
        if (d < bd) { bd = d; best = i; }
      }
      if (best < 0) { tip.style.display = 'none'; return; }
      var p = pts[best];
      tip.innerHTML = '<b>' + esc(dec[p[3]] || '') + '</b> · 编号 ' + p[3] + '<br>' +
        '语言：' + esc(K.langs[p[4]]) + ' · 层级：' + esc(K.buckets[p[5]]) + '<br>' +
        '范数 ' + p[6].toFixed(4) + ' · 语义簇 #' + p[7] + '<br>' +
        '说明：' + esc(explainToken(p[3]));
      tip.style.display = 'block';
      tip.style.left = Math.min(e.clientX + 14, window.innerWidth - 330) + 'px';
      tip.style.top = (e.clientY + 14) + 'px';
    });
    cv.addEventListener('mouseleave', function () { tip.style.display = 'none'; });
    cv.addEventListener('wheel', function (e) {
      e.preventDefault();
      zoom *= (e.deltaY > 0 ? 0.92 : 1.08);
      zoom = Math.max(0.45, Math.min(2.6, zoom));
      draw();
    }, { passive: false });

    document.getElementById('kb3d-reset').addEventListener('click', function () {
      rotX = -0.32; rotY = 0.6; zoom = 1; draw();
    });
    document.getElementById('kb3d-auto').addEventListener('click', function () {
      auto = !auto;
      this.classList.toggle('primary', auto);
      this.textContent = auto ? '停止旋转' : '自动旋转';
      if (auto && !raf) raf = requestAnimationFrame(loop);
    });
    var lastT = 0;
    function loop(t) {
      raf = null;
      if (!auto) return;
      if (t - lastT > 40) { rotY += 0.0045; draw(); lastT = t; }
      raf = requestAnimationFrame(loop);
    }

    draw();
  }

  /* ---------------------------- 元数据 / 张量 ---------------------------- */
  var KV_TYPE_CN = { STRING: '字符串', ARRAY: '数组', UINT8: '8 位无符号整数', INT8: '8 位整数',
    UINT16: '16 位无符号整数', INT16: '16 位整数', UINT32: '32 位无符号整数', INT32: '32 位整数',
    UINT64: '64 位无符号整数', INT64: '64 位整数', FLOAT32: '32 位浮点数', FLOAT64: '64 位浮点数', BOOL: '布尔值' };
  function kvTypeCn(t) { return KV_TYPE_CN[t] || t; }

  function renderMeta() {
    var kvRows = D.kv.map(function (x) {
      var v = Array.isArray(x.value) ? x.value.map(function (y) { return clip(String(y), 40); }).join(', ') : String(x.value);
      return '<tr><td>' + esc(x.key) + '</td><td class="dim">' + esc(kvTypeCn(x.type)) + '</td><td>' + esc(clip(v, 160)) + '</td></tr>';
    }).join('');
    var typeRows = D.typeStats.map(function (t) {
      return '<tr><td><span class="chip ' + (TCOL[t.type] ? t.type : 'other') + '">' + esc(t.type) + '</span></td>' +
        '<td class="num">' + t.count + '</td><td class="num">' + nf(t.elements) + '</td>' +
        '<td class="num">' + bytes(t.bytes) + '</td><td class="num">' + pct(t.elements, D.totalParams) + '</td></tr>';
    }).join('');

    $('#view-meta').innerHTML =
      '<div class="grid2">' +
        '<div class="panel"><h2>元数据键值对（' + D.kvCount + ' 条）</h2>' +
          '<div class="scroll tall"><table class="kv"><thead><tr><th>键名</th><th>类型</th><th>值</th></tr></thead><tbody>' +
          kvRows + '</tbody></table></div></div>' +
        '<div class="panel"><h2>量化类型汇总</h2><table><thead><tr><th>类型</th><th class="num">张量</th>' +
          '<th class="num">参数</th><th class="num">体积</th><th class="num">占比</th></tr></thead><tbody>' +
          typeRows + '</tbody></table>' +
          '<p class="note">GGUF 的量化是分块的：每 32 或 256 个权重共享一个 fp16 缩放因子（外加 4~6 bit 的量化残差），所以文件只有 fp16 的 1/3 左右。</p>' +
        '</div>' +
      '</div>' +
      '<div class="panel" style="margin-top:14px"><h2>全部张量清单（' + D.tensorCount + ' 个）</h2>' +
        '<div class="toolbar"><input type="search" id="tsearch" placeholder="按张量名过滤：attn_q / ffn_down / blk.3"></div>' +
        '<div class="scroll tall"><table><thead><tr><th>张量名称</th><th>量化类型</th><th>形状</th>' +
        '<th class="num">元素数</th><th class="num">体积</th><th class="num">文件偏移</th></tr></thead>' +
        '<tbody id="tbody-tensors">' + tensorRows(D.tensors) + '</tbody></table></div>' +
      '</div>';

    $('#tsearch').addEventListener('input', function (e) {
      var q = e.target.value.trim();
      var list = q ? D.tensors.filter(function (t) { return t.name.indexOf(q) >= 0; }) : D.tensors;
      $('#tbody-tensors').innerHTML = tensorRows(list);
    });
  }

  function tensorRows(list) {
    return list.map(function (t) {
      return '<tr><td class="tok">' + esc(t.name) + '</td>' +
        '<td><span class="chip ' + (TCOL[t.type] ? t.type : 'other') + '">' + esc(t.type) + '</span></td>' +
        '<td class="dim">' + esc(t.shape.join(' × ')) + '</td>' +
        '<td class="num">' + nf(t.elements) + '</td>' +
        '<td class="num">' + bytes(t.bytes) + '</td>' +
        '<td class="num dim">' + nf(t.offset) + '</td></tr>';
    }).join('');
  }

  /* ---------------------------- 启动 ---------------------------- */
  rendered.overview = true;
  renderOverview();
  if (location.hash.length > 1) activateView(location.hash.slice(1));
  else if (QP.get('q')) activateView('vocab');
  else if (QP.get('sim')) activateView('embed');

  /* ---------------------------- 自检（?selftest=1） ---------------------------- */
  function runSelfTest() {
    var out = [];
    function ok(name, cond, extra) {
      out.push((cond ? '[通过] ' : '[失败] ') + name + (extra ? '   → ' + extra : ''));
    }
    try {
      activateView('vocab');
      var rows0 = document.querySelectorAll('#vbody tr').length;
      ok('词表默认分页 100 行', rows0 === 100, rows0 + ' 行');

      var inp = document.querySelector('#vsearch');
      inp.value = '中国';
      inp.dispatchEvent(new Event('input'));
      var cnt = document.querySelector('#vcount').textContent;
      ok('搜索「中国」命中', /命中/.test(cnt), cnt);

      var sel = document.querySelector('#vtype');
      sel.value = '3'; sel.dispatchEvent(new Event('change'));
      var cnt2 = document.querySelector('#vcount').textContent;
      ok('token_type 过滤可切换', cnt2.length > 0, cnt2);
      sel.value = '-1'; sel.dispatchEvent(new Event('change'));
      inp.value = ''; inp.dispatchEvent(new Event('input'));
      ok('清空搜索恢复全量', /151,936/.test(document.querySelector('#vcount').textContent),
        document.querySelector('#vcount').textContent);

      activateView('embed');
      var dots = document.querySelectorAll('svg.scatter circle').length;
      ok('PCA 散点渲染', dots === 2000, dots + ' 点');
      var bars = document.querySelectorAll('.hist .b').length;
      ok('范数直方图 64 bin', bars === 64, bars + ' bin');

      var t0 = performance.now();
      document.querySelector('#simq').value = '中国';
      document.querySelector('#simbtn').click();
      var ms = (performance.now() - t0).toFixed(0);
      var simRows = document.querySelectorAll('#simbody tr').length;
      var topk = D.sim ? D.sim.topk : 0;
      ok('语义最近邻 top' + topk, simRows > 0 && simRows <= topk, simRows + ' 条 / ' + ms + ' ms');
      var first = document.querySelector('#simbody tr td:nth-child(3)');
      ok('最近邻首条非空', !!first && first.textContent.trim().length > 0,
        first ? '«' + first.textContent + '»' : '空');

      activateView('meta');
      var tRows = document.querySelectorAll('#tbody-tensors tr').length;
      ok('张量表行数 = ' + D.tensorCount, tRows === D.tensorCount, tRows + ' 行');
      var tinp = document.querySelector('#tsearch');
      tinp.value = 'attn_q'; tinp.dispatchEvent(new Event('input'));
      var fRows = document.querySelectorAll('#tbody-tensors tr').length;
      ok('张量名过滤 attn_q', fRows > 0 && fRows < tRows, fRows + ' 行');

      activateView('arch');
      var lrows = document.querySelectorAll('.layer-row').length;
      ok('架构层数 = ' + D.layerCount, lrows === D.layerCount, lrows + ' 层');
      document.querySelectorAll('.layer-row')[5].click();
      ok('点击第 5 层切换详情', /blk\.5/.test(document.querySelector('#layer-detail').textContent),
        document.querySelector('#layer-detail').querySelector('h2').textContent);

      activateView('kb3d');
      ok('三维点云画布就绪', !!document.getElementById('kb3d-canvas'),
        (D.kb3d ? nf(D.kb3d.n) : 0) + ' 个采样点');
      var lg = document.querySelectorAll('#kb3d-legend label').length;
      ok('语言维度图例 6 类', lg === 6, lg + ' 类');
      var shownTxt = document.getElementById('kb3d-count').textContent;
      ok('点云已绘制', /4,000/.test(shownTxt), shownTxt);

      activateView('overview');
      ok('概览 KPI 8 张卡', document.querySelectorAll('.kpi').length === 8,
        document.querySelectorAll('.kpi').length + ' 张');
    } catch (e) {
      out.push('[异常] ' + e.message);
    }
    var pre = document.createElement('pre');
    pre.id = 'selftest';
    pre.style.cssText = 'margin:18px 22px 40px;padding:14px 16px;border:1px solid #e2e8f0;border-radius:10px;' +
      'background:#ffffff;color:#1e293b;white-space:pre-wrap;font:12px/1.8 ui-monospace,monospace;' +
      'box-shadow:0 1px 2px rgba(15,23,42,.04),0 2px 6px rgba(15,23,42,.05)';
    pre.textContent = '=== 界面自检结果 ===\n' + out.join('\n');
    document.body.appendChild(pre);
  }
  if (/selftest/.test(location.search)) {
    setTimeout(runSelfTest, 0);
  }
})();
