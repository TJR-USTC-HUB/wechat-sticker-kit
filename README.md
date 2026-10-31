# wechat-sticker-kit

```把图片和视频变成微信能「添加为表情」的 GIF。```

保持原比例、不补边、不裁切，自动压进微信的体积限制。图片输出**单帧静止 GIF**，视频输出循环 GIF。

![python](https://img.shields.io/badge/python-3.9%2B-blue)
![platform](https://img.shields.io/badge/platform-windows%20%7C%20macos%20%7C%20linux-lightgrey)
![license](https://img.shields.io/badge/license-MIT-green)
![tests](https://img.shields.io/badge/tests-24%20passing-brightgreen)

---

## 为什么是 GIF

微信「添加的单个表情」在文档上支持 PNG / JPG / GIF，但实测（以及大量用户反馈）**只有 GIF 最稳**：PNG/JPG 即使只有几十 KB，在部分客户端也会被判为“图片太大”或直接不入库；同样内容的 GIF，哪怕只有一帧，都能正常添加和发送。

| 格式 | 微信加表情的成功率 | 备注 |
| --- | --- | --- |
| GIF | 高，最稳 | 单帧/多帧都行，本工具默认 |
| PNG | 不稳定 | 部分版本拒绝 |
| JPG | 不稳定 | 且不支持透明 |

所以这个工具默认输出 GIF，但保留 `-f png` / `-f jpg` 给需要的人。

## 特性

- **图片 → 单帧 GIF**：永远不会动，帧数恒为 1
- **视频 → 循环 GIF**：ffmpeg 解码，Pillow 组装调色板
- **保持原比例**：默认不裁切、不补边，240×135 就是 240×135
- **自动压预算**：超限时按“减色板 → 降质量 → 缩尺寸”降级，直到塞进限制
- **批量与递归**：整个文件夹一次转完，重名自动加 `-2`
- **文件名清洗**：`xxx.png@406w_270h_1s.avif` 这种 CDN 名会输出成 `xxx.gif`
- **三种平台同一套代码**：Windows / macOS / Linux，无平台分支

## 环境要求

| 组件 | 版本 | 是否必需 |
| --- | --- | --- |
| Python | 3.9+ | 必需 |
| Pillow | 9.1+ | 必需（AVIF 需要 11.3+） |
| ffmpeg | 任意近版本 | 仅视频功能需要 |
| imageio-ffmpeg | 0.4.9+ | 可选，省去自己装 ffmpeg |
| pillow-heif | 0.13+ | 可选，支持 iPhone 的 HEIC |

## 安装

### Windows 10 / 11

```powershell
# 1. 装 Python（已装可跳过）
winget install -e --id Python.Python.3.12

# 2. 装本工具
python -m pip install --upgrade pip
python -m pip install wechat-sticker-kit

# 3. 可选：视频功能需要 ffmpeg
winget install -e --id Gyan.FFmpeg

# 4. 验证
wxsticker --version
```

### macOS

```bash
brew install python ffmpeg
python3 -m pip install wechat-sticker-kit
wxsticker --version
```

### Linux（Debian / Ubuntu）

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv ffmpeg
python3 -m pip install --user wechat-sticker-kit
wxsticker --version
```

如果提示 `externally-managed-environment`，用虚拟环境：

```bash
python3 -m venv ~/.venvs/sticker
source ~/.venvs/sticker/bin/activate
pip install wechat-sticker-kit
```

### Fedora / RHEL

```bash
sudo dnf install -y python3 python3-pip ffmpeg
python3 -m pip install --user wechat-sticker-kit
```

### 从源码（要改代码时）

```bash
git clone https://github.com/<your-name>/wechat-sticker-kit.git
cd wechat-sticker-kit
python -m pip install -e .
```

不装也能跑，加 `PYTHONPATH=src` 然后 `python -m wechat_sticker_kit` 即可。

### 可选组件

```bash
python -m pip install "wechat-sticker-kit[video]"   # 自带 ffmpeg 二进制
python -m pip install pillow-heif                    # 支持 HEIC
```

## 快速开始

```bash
wxsticker meme.png
# -> stickers/meme.gif   240x135   1 frame   29.6 KB

wxsticker clip.mp4 --duration 3
# -> stickers/clip.gif   240x135   36 frames

wxsticker ./photos -r -o D:/Stickers -s 500
# 整个目录，500px，输出到 D:/Stickers
```

控制台输出：

```text
meme.png                    -> meme.gif                  240x135      29.6 KB
clip.mp4                    -> clip.gif                  240x135      96.1 KB  [36 frames]

2 sticker(s) written to stickers, 125.7 KB total
```

## 支持的输入

**图片**：PNG、JPG、JPEG、WebP、AVIF、APNG、HEIC（需插件）、BMP、TIFF、GIF
**视频**：MP4、MOV、M4V、MKV、WebM、AVI、WMV、FLV、MPG、MPEG、3GP

扩展名和真实内容不一致也能读（解码靠内容嗅探）。AVIF 由 Pillow 11.3+ 原生支持。

## 命令行参数

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `-o, --out` | `stickers` | 输出目录 |
| `-s, --size` | `240` | 长边像素，可选 240 / 500 / 1000 |
| `-m, --mode` | `keep` | keep（原比例）/ cover / pad / fit |
| `-f, --format` | `gif` | gif / png / jpg，视频恒为 gif |
| `-b, --budget` | `gif` | gif(1MB) / chat(5MB) / platform(500KB) / tiny(100KB) / 800kb |
| `--max-kb` | — | 直接用 KB 指定上限 |
| `--bg` | `blur` | pad/fit 的背景：blur / transparent / auto / #rrggbb |
| `--anchor` | `center` | 方形裁切重心：center / top / bottom / face |
| `-r, --recursive` | 关 | 递归子目录 |
| `--dry-run` | 关 | 只打印计划，不写文件 |
| `--json` | 关 | 输出机器可读的汇总 |
| `-q, --quiet` | 关 | 只输出错误 |
| `--fps` | `12` | 视频抽帧帧率 |
| `--start` | `0` | 视频起点（秒） |
| `--duration` | 至多 5 秒 | 截取时长（秒） |
| `--no-dither` | 关 | 关抖动，体积更小但可能色带 |
| `--version` | — | 版本号 |

## 四种构图模式

| 模式 | 行为 | 适用 |
| --- | --- | --- |
| `keep` | **默认**，保持原比例，只缩到 size | 微信表情首选 |
| `cover` | 等比铺满方形，裁掉溢出 | 想要正方形时 |
| `pad` | 原图完整保留，四周补背景 | 横图转方形 |
| `fit` | 原图完整保留，补纯色 | 需要干净底色 |

```bash
wxsticker wide.jpg -m pad --bg transparent   # 方形 + 透明填充
wxsticker meme.png -m cover                  # 方形 + 裁切
```

## 体积预算与降级

| 预算名 | 字节 | 对应场景 |
| --- | --- | --- |
| `gif` | 1 MB | 动图表情常见上限（默认） |
| `chat` | 5 MB | 微信官方静态表情上限 |
| `platform` | 500 KB | 微信表情开放平台主图建议 |
| `tiny` | 100 KB | 极限压缩 |

超限时的自动降级顺序：减色板 256→128→64→32 色 → 降 JPEG 质量 88→40 → 每轮缩小 10%。返回的 `note` 会写明牺牲了什么。

## 视频转 GIF

```bash
wxsticker clip.mp4                          # 前 5 秒，12fps，240 宽
wxsticker clip.mp4 --start 3.2 --duration 2.5 --fps 15
wxsticker clip.mov -s 240 --no-dither
```

ffmpeg 的查找顺序：PATH → 环境变量 `WXSTICKER_FFMPEG` → imageio-ffmpeg 内置 → 常见安装路径（/opt/homebrew/bin、/usr/local/bin、WinGet Links 等）。

调色板是整段共用的，避免逐帧自适应造成的闪烁。

## Python API

```python
from wechat_sticker_kit import to_square, encode, video_to_gif, load_image

# 图片
im = to_square(load_image("meme.png"), size=240, mode="keep")
data, note = encode(im, fmt="gif", budget=1024 * 1024)
open("meme.gif", "wb").write(data)
print(note or "no compression needed")

# 视频
video_to_gif("clip.mp4", "clip.gif", size=240, fps=12, duration=3)
```

## 微信端：从文件到表情

1. 把生成的 GIF **当图片消息**发出去（拖进输入框是发文件，要的是图片）
2. 在聊天里长按该图 → **添加到表情**
3. 我 → 表情 → 设置 → 添加的单个表情，能看到它
4. 之后在表情面板最右侧的爱心分类里就能直接发

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| 长按没有“添加到表情” | 发成了文件消息 | 用图片按钮发，或直接粘贴 |
| 加不进去 | 格式/体积/形状不合 | 用本工具默认参数输出的 GIF |
| 添加后不动 | 本身就是单帧 | 正常，图片转 GIF 就是静止的 |
| 显示有白边 | 客户端合成了透明底 | 改 `--bg auto` 用边缘色填充 |

## 故障排查

| 报错 | 原因 | 解决 |
| --- | --- | --- |
| `ffmpeg not found` | 没装或不在 PATH | 装 ffmpeg，或 `pip install "wechat-sticker-kit[video]"` |
| `cannot read image` | 格式不支持或文件损坏 | 确认是图片；HEIC 需 `pillow-heif` |
| `ModuleNotFoundError: PIL` | 没装 Pillow | `pip install Pillow` |
| 输出被减色 | 预算太紧 | 提高 `-b` 或 `--max-kb` |
| 中文路径乱码 | 老终端编码 | 工具已强制 UTF-8；仍乱码就用 Windows Terminal |

## 项目结构

```text
src/wechat_sticker_kit/
  core.py     构图、调色板、编码、预算压缩
  video.py    ffmpeg 抽帧 + GIF 组装
  cli.py      命令行
tests/test_core.py   24 个 unittest
scripts/smoke.py     端到端冒烟检查
```

## 开发与测试

```bash
python -m unittest discover -s tests -v   # 24 个单元测试
python scripts/smoke.py                   # 8 项端到端检查
```

CI 在 ubuntu / windows / macos 三个平台跑 Python 3.9 到 3.13 的矩阵。

## 跨平台说明

| 平台 | Python | ffmpeg |
| --- | --- | --- |
| Windows | 3.9+ | winget install Gyan.FFmpeg |
| macOS | 3.9+（brew） | brew install ffmpeg |
| Linux | 3.9+ | apt / dnf install ffmpeg |

路径全部用 pathlib，不拼分隔符；标准输出强制 UTF-8，中文路径不会因为 cp936/cp1252 崩掉。

## English

Convert images and videos into GIF stickers that WeChat actually accepts.

```bash
pip install wechat-sticker-kit
wxsticker meme.png          # -> stickers/meme.gif  (240px, single frame, <1MB)
wxsticker clip.mp4          # -> stickers/clip.gif  (looping)
```

Images become a single-frame GIF, videos a looping one. Aspect ratio is preserved (no padding, no crop) unless you ask for `-m cover` / `-m pad`. Everything is squeezed under a byte budget automatically.

## License

MIT
