# GGUF 解剖台 — 模型知识库与架构可视化前端

把 HuggingFace 上下的 `.gguf` 权重拆开，用纯前端页面呈现：**模型架构**、**词表（知识库）**、**嵌入空间**、**原始元数据**。
没有框架、没有构建步骤、没有 npm；数据由本地一个 Python 脚本一次性生成，页面双击就能开。

## 目录

```
gguf-lab/
├─ qwen2.5-0.5b-instruct-q4_k_m.gguf     下载的模型（468 MiB，Qwen2.5-0.5B-Instruct 官方 GGUF）
├─ build_web_data.py                      GGUF -> web/data/model.js（数据管线）
├─ gguf_dump.py                           GGUF 解析/反量化库（被上面复用，也可单独 CLI）
├─ gguf_to_hf.py                          GGUF -> HF 目录（safetensors + config.json）
├─ safetensors_dump.py                    safetensors 解析/导出
├─ verify.py                              解码器 vs 官方 gguf-py 交叉验证
├─ make_test_gguf.py                      合成多量化类型 GGUF（测试用）
└─ web/
   ├─ index.html                          页面骨架（零依赖）
   ├─ style.css                           深色主题
   ├─ app.js                              全部渲染逻辑（含 ?selftest=1 自检）
   └─ data/model.js                       window.MODEL_DATA —— 由 build_web_data.py 生成
```

## Windows 桌面版（独立 exe，不用浏览器）

```
GGUF解剖台.exe          30.3 MB 单文件，双击即开
desktop\app.py          源码（Tkinter，约 1250 行）
desktop\README.md       桌面版说明与打包命令
```

- 纯 Python + Tkinter，**不依赖浏览器 / WebView / 本地服务器**，直接读 `.gguf`；
- 六个中文页面：概览、模型架构（中文数据流）、**三维链路（3D 复现）**、语言知识库、向量空间、元数据；
- 3D 链路用 `Scene3D` 手写旋转 + 透视投影：词元嵌入 → 24 层立方体堆叠 → 输出归一化 → 输出层，拖拽旋转、滚轮缩放、点击层看细节；
- 放在 `.gguf` 同目录或上一级目录时自动加载体积最大的模型，也可 `--` 传路径或在界面里选文件。

```powershell
.\GGUF解剖台.exe                                  # 双击或命令行
python desktop\app.py ..\qwen2.5-0.5b-instruct-q4_k_m.gguf   # 从源码跑
```

详细说明见 [desktop/README.md](desktop/README.md)。

## 跑起来

### 一键启动（推荐）

```powershell
.\start.bat
```

`start.bat` 只是包了一层 `powershell -ExecutionPolicy Bypass -File start.ps1`，双击即可。它会自动：

1. 找 Python（PATH → `%LOCALAPPDATA%\Programs\Python` → `.venv`），要求 3.8+；
2. 缺 `numpy` 就 `pip install`，可选依赖 `gguf` / `safetensors` 缺了也顺手装（装不上只告警，主流程继续）；
3. 校验模型文件，没有就用 `curl` 从 HuggingFace 下载 468 MiB 的 Qwen2.5-0.5B-Instruct q4_k_m；
4. 比对时间戳，`web/data/model.js` 缺失或落后于模型/脚本时自动重跑 `build_web_data.py`（约 33 秒）；
5. 起 `http.server`（端口被占会自动顺延，若已是本应用则直接复用），最后用默认浏览器打开。

参数：

```powershell
.\start.ps1 -NoBrowser                 只起服务
.\start.ps1 -Port 9000                 换端口
.\start.ps1 -Model other.gguf          换模型（相对本目录或绝对路径）
.\start.ps1 -Rebuild                   强制重算 model.js
.\start.ps1 -ForceDownload             强制重下默认模型
.\start.ps1 -PythonExe .venv\Scripts\python.exe   指定解释器
.\start.ps1 -Stop                      停掉后台服务
```

### 手动三步

```powershell
cd gguf-lab
pip install numpy gguf safetensors          # 只用于生成数据；页面本身零依赖

# 换模型就换第一行参数
python build_web_data.py qwen2.5-0.5b-instruct-q4_k_m.gguf

# 打开方式 A：直接双击（数据内联，file:// 可用）
start web\index.html

# 打开方式 B：本地静态服务
python -m http.server 8899 --bind 127.0.0.1 --directory web
# http://127.0.0.1:8899/index.html
```

## 页面里有什么

| 视图 | 内容 |
|---|---|
| 概览 | 参数量/体积/层数/隐藏维/注意力头/上下文/词表/量化，超参表，量化类型分布，张量角色参数量汇总 |
| 架构 | token_embd → 24 × (RMSNorm + GQA + RMSNorm + SwiGLU) → output_norm → lm_head 的数据流；点层看该层每个张量的类型/形状/元素/体积 |
| 语言知识库 | 151,936 条词元检索（中文可搜，已按 GPT-2 byte-level 还原）、词元类型分布、字符长度分布、BPE 合并规则、每个词元的向量 L2 范数、中文说明列（角色 + 释义） |
| 三维知识体系 | Canvas 手写 3D 点云：拖拽旋转 / 滚轮缩放 / 悬停查看；三个维度分别是语言体系、结构层级、语义坐标（embedding 前 3 主成分），8 个语义簇 |
| 嵌入空间 | embedding 行范数分布直方图、范数 Top-120、2000 点 PCA 投影散点、语义最近邻（全 896 维精确余弦，预计算） |
| 元数据 / 张量 | 26 条 KV 元数据、类型汇总、291 个张量全表（可过滤） |

URL 参数：

```
index.html#arch           直接打开架构视图（#vocab / #embed / #meta 同理）
index.html?q=中国          打开词表并搜索
index.html?sim=中国        打开嵌入空间并对该 token 查最近邻
index.html?selftest=1     跑 16 项界面自检，结果打印在页面底部
```

## 数据管线做了什么

`build_web_data.py` 读 GGUF → 生成 `web/data/model.js`（约 7 MiB）：

1. 解析 header / KV / 张量表，按 `blk.N.*` 重建 24 层结构；
2. 取 `token_embd.weight`（Q5_0，151,936 × 896）**反量化成 fp32**（`gguf_dump.dequant`，与官方 `gguf.quants.dequantize` 逐张量 0 差异）；
3. 算每行 L2 范数 → uint16 量化后 base64；
4. 2000 个 token 做 PCA → 2D 散点；
5. 36406 个种子 token（id<16384 的高频 token + 1~2 字中文）用**全 896 维**算 top-6 最近邻，预计算成表；
6. 词表按 GPT-2 byte-level 规则在浏览器端还原中文，避免显示成 `ä¸­å›½`。

## 已验证的结论（页面上能看到）

- 文件名是 `q4_k_m`，实际块类型是 **Q5_0 (61.6%) + Q8_0 (21.8%) + Q6_K (8.3%) + Q4_K (8.3%) + F32 (0.02%)** —— GGUF 按张量分配量化块类型，同名方案内部精度可以差好几个 bit。
- 参数量 630,167,424（Qwen2.5-0.5B 报 0.49B 是把 `lm_head` 与 embedding 共享口径算的；本文件两者都独立存储，各 136.1 M）。
- token_embd 行范数 mean 0.4528 / std 0.0591 / max 0.7804。
- 「中国」的语义最近邻（全维余弦）：中國 0.663、中国的 0.639、` China` 0.618、` Chinese` 0.578、China 0.540、中国人 0.517 —— PCA 降到 8 维后这套关系会完全丢失（与全维 top10 重合 0/10），所以近邻索引不做降维。
- 词表 151,936 条：普通词元 151,643 / 控制符 20 / 用户自定义 2 / 未使用 271；BPE 合并规则 151,387 条。
- 三维知识体系的语言分布：中文 24,953、英文 105,854、数字 117、符号 8,656、代码片段 12,056、特殊标记 300。

## 换别的模型

```powershell
hf download Qwen/Qwen2.5-1.5B-Instruct-GGUF --include "*q4_k_m.gguf" --local-dir .
python build_web_data.py qwen2.5-1.5b-instruct-q4_k_m.gguf
```

前端完全数据驱动：层数、张量数、词表大小、量化类型都从 `MODEL_DATA` 读，代码不用改。
只对 llama 家族（Llama / Qwen2 / Qwen3 / Mistral 等同构命名 `blk.N.attn_q` …）做了角色识别；
其它架构（Mamba、MoE 的 `ffn_gate_inp`）也能显示，只是角色标签按名字推断。

## 附：命令行工具（不开浏览器也能看）

```powershell
python gguf_dump.py model.gguf --limit 3                    # 元数据 + 张量表
python gguf_dump.py model.gguf --meta tokenizer.ggml.tokens --limit 5
python gguf_dump.py model.gguf --tensor blk.0.attn_q --stats
python gguf_dump.py model.gguf --extract out                # 每张量 -> .npy（fp32）
python gguf_to_hf.py model.gguf hf_out --dtype f16          # 还原成 HF 目录
python verify.py model.gguf                                 # 解码器交叉验证
```
