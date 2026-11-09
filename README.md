# GGUF 解剖台 · GGUF Anatomy

把 HuggingFace 上的 `.gguf` 权重拆开看：**架构、词表、向量空间、量化块、拒答方向**，全部中文界面。
提供两种前端：

- **Windows 桌面版**：纯 Python + Tkinter 的独立 exe，不开浏览器、不起服务器，直接读 GGUF；
- **网页版**：零依赖静态页面 + 一个 Python 数据管线，把 GGUF 压成几 MB 的 `model.js` 后浏览器渲染。

![三维链路](desktop/shot-chain.png)

## 功能

| 页面 | 内容 |
|---|---|
| 概览 | 参数量、体积、层数、注意力头、上下文、词表、量化类型分布、张量角色参数量 |
| 模型架构 | 24 层 + 输入/输出，右侧该层张量表（中文名称 / 原名 / 类型 / 形状 / 元素数 / 体积） |
| 三维链路 | Canvas 手写 3D：词元嵌入 → 层堆叠 → 输出归一化 → 输出层，拖拽旋转、滚轮缩放、点击看层 |
| 教学演示 | 8 步讲透数据流，每步代入当前模型的真实参数，可自动播放并与 3D 联动 |
| 术语词典 | 28 条专有名词，中文定义 + 本模型具体数字 |
| 语言知识库 | 15 万词元检索，中文说明（角色 + 释义）、类型、向量范数、分页 |
| 中文知识 | 25,511 个中文词元，按字数分层，点词看全 896 维语义近邻 |
| 向量空间 | 范数直方图、PCA 投影、精确余弦最近邻 |
| 拒答移除 | 构造拒答方向 → 扫描 48 个写残差流的矩阵 → 正交化 → 导出新 GGUF |
| 元数据 / 张量 | 全部 KV 元数据（类型中文）与张量清单 |

## 快速开始

### 桌面版（推荐）

```powershell
# 从源码跑
pip install numpy
python desktop\app.py path\to\model.gguf

# 打包成单文件 exe（约 30 MB）
pip install pyinstaller
python -m PyInstaller --noconfirm --onefile --windowed --name "GGUF解剖台" ^
    --paths desktop --hidden-import numpy --hidden-import abliterate ^
    --exclude-module matplotlib --exclude-module scipy --exclude-module pandas desktop\app.py
```

exe 会优先加载同目录 / 上一级目录里体积最大的 `.gguf`；也可以拖路径进命令行，或在界面右上角「打开模型…」选文件。

### 网页版

```powershell
.\start.bat          # 自动装依赖 → 下载模型 → 生成数据 → 起服务 → 打开浏览器
```

或手动三步：

```powershell
pip install numpy
python build_web_data.py model.gguf        # 生成 web/data/model.js
python -m http.server 8899 --directory web # http://127.0.0.1:8899/index.html
```

网页版使用说明见 [`web`](web) 与 [`README_WEB.md`](README_WEB.md)（如有）。

## 模型不会进仓库

`.gitignore` 已排除 `*.gguf` 与 `*.exe`。首次使用自行下载，例如：

```powershell
hf download Qwen/Qwen2.5-0.5B-Instruct-GGUF --include "*q4_k_m.gguf" --local-dir .
```

已验证的模型：Qwen2.5-0.5B-Instruct q4_k_m（468.6 MiB，24 层 / 896 维 / 14 头 / 2 KV 头）。

## 拒答移除（abliteration）

1. 从词元嵌入里取拒答语义词（`sorry` / `apolog` / `cannot` / `抱歉` / `无法` / `拒绝` …）的平均向量，
   减去中性语义词（`Yes` / `sure` / `okay` / `当然` / `可以` / `好的` …）的平均向量，单位化得到 `r ∈ ℝ^896`；
2. 所有写回残差流的线性层（`attn_output`、`ffn_down`）输出维都是 hidden，`r` 在其中的占比
   `‖rᵀW‖ / ‖W‖` 就是「拒答能量」；
3. `W ← W − r(rᵀW)`，词元嵌入按行 `E ← E − (E r) rᵀ`；
4. 被改的 49 个张量重新编码成 Q8_0，其余张量原样复制量化块，导出新 GGUF。

本机实测（Qwen2.5-0.5B-Instruct q4_k_m）：

```
平均拒答能量  0.03351 → 0.00022   下降 99.3%
导出文件      588,490,592 字节，291 个张量，49 个被正交化
```

## 目录

```
desktop/
  app.py            Tkinter 主程序（10 个页面）
  abliterate.py     拒答方向分析 / 正交化 / GGUF 导出
  gguf_dump.py      GGUF 解析与反量化（15 种量化块，与官方 gguf-py 逐张量 0 差异）
web/
  index.html style.css app.js    零依赖前端
build_web_data.py   GGUF → web/data/model.js 数据管线
start.ps1 / start.bat  网页版一键启动
open-360.ps1       用 360 极速浏览器打开前端（找不到时回退 Edge）
push.ps1           一键创建 GitHub 公开仓库并推送
make_test_gguf.py  合成多量化类型 GGUF，用于交叉验证
verify.py          解码器与官方 gguf-py 的交叉验证
```

## 技术要点

- **反量化**：Q4_0 / Q4_1 / Q5_0 / Q5_1 / Q8_0 / Q2_K~Q6_K / Q8_K / BF16 / F16 / F32 / IQ4_NL，
  纯 numpy 向量化实现，与 `gguf.quants.dequantize` 逐张量比对 `max|diff| = 0`。
- **中文词表**：GGUF 里中文 token 是 UTF-8 字节的 Latin-1 映射，前端按 GPT-2 byte-level 规则反查还原。
- **3D**：`Scene3D` 只做绕 Y/X 旋转 + 透视投影，Tkinter Canvas 六面按深度排序绘制。
- **内存保护**：嵌入矩阵超过 3 亿元素（≈1.2 GB）时降级，不拖垮整机。

## 推送到 GitHub

仓库已在本地初始化好（`main` 分支，`git log` 可见提交），`.gitignore` 已排除模型权重、exe、构建产物。

```powershell
# 1) 建 token：https://github.com/settings/tokens（勾 repo）
$env:GITHUB_TOKEN = 'YOUR_GITHUB_TOKEN'

# 2) 一键创建公开仓库并推送
.\push.ps1 -Repo gguf-anatomy

# 已有远程仓库时直接指定
.\push.ps1 -Remote https://github.com/<you>/gguf-anatomy.git
```

没有 token 时可以先分发仓库快照：

```powershell
git clone gguf-anatomy.bundle gguf-anatomy   # 完整提交历史
# 或解压 gguf-anatomy.zip 后手动上传
```

## 用 360 极速浏览器打开

```powershell
.\open-360.ps1            # 自动起服务并用 360 打开；没装 360 时回退 Edge
.\open-360.ps1 -File      # file:// 模式直接开 web\index.html
.\open-360.ps1 -List      # 只看检测结果
```

360 极速浏览器是 Chromium 内核，网页版全部功能（3D 点云、中文词表、向量空间）都能跑。
下载地址：<https://browser.360.cn/ee/>

## 许可

[MIT](LICENSE)
