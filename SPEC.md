# Spec: 网易云日语歌词提取器

## Objective
做一个命令行工具，输入网易云音乐的歌曲名或ID，一键提取日语歌词的**原文 + 发音（罗马音/假名）+ 中文翻译**，三列对照显示，解决网易云客户端只能看发音或翻译二选一的问题。

## Tech Stack
- **语言:** Python 3.11+
- **依赖:** `requests`（API 请求），`pykakasi`（日语→罗马音转换）
- **GUI:** `tkinter`（Python 内置，零额外依赖）
- **运行环境:** Windows 11

## Commands
| 操作 | 命令 |
|------|------|
| 安装依赖 | `pip install -r requirements.txt` |
| CLI 搜索 | `python lyrics.py search <歌名>` |
| CLI 按ID | `python lyrics.py id <歌曲ID>` |
| GUI 启动 | `python gui.py` |
| 导出文件 | `python lyrics.py search <歌名> -o output.md` |

## Project Structure
```
cloudmusic_pro/
├── lyrics.py           → 核心API + CLI入口
├── gui.py              → tkinter GUI窗口
├── SPEC.md             → 本文档
└── requirements.txt    → 依赖列表
```

## Data Flow
```
用户输入歌名/ID → 调用网易云API获取歌词
                ├── lrc     → 原文（日语汉字）
                ├── romalrc → 罗马音/假名发音
                └── tlyric  → 中文翻译
                ↓
            解析LRC时间标签 → 去掉时间戳
                ↓
            三列对照渲染输出（rich表格）
```

## Code Style
- 单一入口脚本，控制在 150 行以内
- 函数风格：`get_lyrics()`, `search_song()`, `display()`
- LRC 解析用正则去掉 `[mm:ss.xx]` 时间标签

## Testing Strategy
手动测试：
- 搜索 "lemon" → 能返回米津玄师的 Lemon 并提取三列歌词
- 按 ID 提取 → 能正确拿到歌词
- 歌曲无翻译/无发音时 → 对应列显示空，不崩溃

## Boundaries
- **Always:** 使用 pyncm 封装好的 API，不自己拼请求
- **Ask first:** 添加 GUI、修改文件输出格式
- **Never:** 硬编码 API key、下载受版权保护的音乐文件

## Success Criteria
- [ ] 输入歌名能搜索到候选歌曲列表
- [ ] 选择歌曲后能同时显示原文、发音、翻译三列
- [ ] 发音列为空时（非日语歌）不影响其他列显示
- [ ] 输出格式清晰，三列对齐

## Decisions Made
- 翻译来源：直接使用网易云 API 返回的 `tlyric` 字段（自带中文翻译）
- 导出支持：`-o` 参数导出为 Markdown 表格文件
