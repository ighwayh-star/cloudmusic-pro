# cloudmusic-pro

网易云日语歌词提取器 — 一键提取日语歌词的**原文 + 罗马音 + 中文翻译**，逐句对照显示。

![Python](https://img.shields.io/badge/Python-3.8+-blue)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)

## 功能

- 按歌名搜索，选择后逐句显示原文 / 罗马音 / 中文翻译
- **当前播放** — 一键获取网易云客户端正在播放的歌曲（Windows）
- 自动过滤制作人/作词/作曲等非歌词信息（基于 LRC 时间戳对齐）
- 英文歌词单独显示，日文歌词自动生成罗马音
- 非日文歌曲自动跳过罗马音生成
- 导出 Markdown 文件

## 使用说明

> 视频演示：[cloudmusic-pro 使用教程](https://www.bilibili.com/video/BV1tpdAB8En2/)

### 搜索与提取

1. 启动后输入歌名搜索（如 `lemon`），双击结果即可提取歌词
2. 歌词按 **原文 / 罗马音 / 中文翻译** 逐句对照显示
3. 点击「当前播放」可直接获取网易云客户端正在播放的歌曲

### 罗马音说明

- 工具会自动检测歌词语言，仅对日语部分生成罗马音
- 使用 SudachiPy 进行形态分析，能准确识别汉字在语境中的读音（如 `今日` → `kyou`）
- 其他语言的歌词会单独显示，不生成罗马音

## 快速开始

### 方式一：下载 exe（推荐）

从 [Releases](../../releases) 下载 `cloudmusic.exe`，双击运行。

### 方式二：源码运行

```bash
pip install -r requirements.txt
python gui.py
```

Windows 用户可双击 `setup.bat` 安装依赖，然后双击 `run.bat` 启动。

## CLI 模式

```bash
# 搜索歌曲
python lyrics.py search lemon

# 按歌曲 ID 提取
python lyrics.py id 536622304

# 导出 Markdown
python lyrics.py search lemon -o lyrics.md
```

## 文件结构

```
├── lyrics.py          # 核心 API + CLI
├── gui.py             # tkinter GUI
├── requirements.txt   # 依赖
├── setup.bat          # Windows 一键安装依赖
├── run.bat            # Windows 一键启动
└── README.md
```

## 依赖

- Python 3.8+
- [requests](https://pypi.org/project/requests/) — HTTP 请求
- [SudachiPy](https://pypi.org/project/SudachiPy/) + SudachiDict-core — 日语形态分析（准确读音）
- [pykakasi](https://pypi.org/project/pykakasi/) — 假名 → 罗马音转换（回退方案）
- tkinter — Python 内置 GUI 框架

## 平台支持

仅支持 Windows。Linux / Mac 未测试。
