# wechat-sticker-kit

`把任意 PNG / JPG 一键变成微信表情包` —— 方形画布、240×240 标准尺寸、自动压进 5 MB（或 500 KB）以内，支持批量与文件夹递归。

命令行一条命令，或者 `from wechat_sticker_kit import to_square` 当库用。纯 Pillow，无其它依赖。

![python](https://img.shields.io/badge/python-3.9%2B-blue)
![license](https://img.shields.io/badge/license-MIT-green)
![deps](https://img.shields.io/badge/dependencies-Pillow-orange)

---

## 为什么需要它

微信对「表情」有自己的一套规则，直接用截图当表情经常踩坑：

| 场景 | 格式 | 大小上限 | 尺寸建议 |
| --- | --- | --- | --- |
| 聊天里「添加的单个表情」 | PNG / JPG / GIF | 5 MB | 方形，240×240 起 |
| 微信表情开放平台（发表情包） | PNG / GIF | 主图建议 ≤ 500 KB | 主图 240×240，缩略图 120×120 |
| 聊天窗里的显示 | — | — | 按比例缩放，太小会糊 |

常见问题：非方形的图在表情列表里被硬裁；原图几 MB 传不上去；透明 PNG 的边被吃掉；手机拍的图带 EXIF 方向翻转 90°。这个工具把这些一次性处理掉。

## 支持的输入

PNG / JPG / **WebP** / **AVIF** / APNG / HEIC / BMP / TIFF / GIF，以及 MP4 / MOV / MKV / WebM 等视频。

AVIF 从 Pillow 11.3 起原生支持（本机是 12.3），HEIC 需要额外装 pillow-heif。
扩展名和内容不一致也没关系（比如 CDN 下下来的 xxx.png@406w_270h_1s.avif）——解码靠内容嗅探，输出名会自动去掉 @406w_270h_1s 这类后缀。

## 安装

```bash
pip install wechat-sticker-kit
```

或者从源码装：

```bash
git clone https://github.com/<your-name>/wechat-sticker-kit.git
cd wechat-sticker-kit
pip install -e .
```

## 快速开始

```bash
# 一张图 -> stickers/meme.gif（单帧静态，原比例，<=1MB）
wxsticker meme.png

# 整个文件夹，递归，输出到 out/，用 500px 高清、压到 500KB 以内
wxsticker ./photos -r -o out -s 500 -b platform

# 保留整张图不裁切，四周用模糊背景填满
wxsticker wide.jpg -m pad --bg blur

# 输出 JPG，给不支持透明的地方用
wxsticker shot.png -f jpg
```

输出示例：

```text
meme-2026.png                    -> meme-2026.gif          240x135    29.6 KB
wide-shot.jpg                    -> wide-shot.gif           240x135    41.2 KB  [palette reduced to 256 colours]

2 sticker(s) written to stickers, 102.5 KB total
```

## 为什么默认输出 GIF

实测下来，微信「添加的单个表情」对**动图 GIF 的接受度最稳定**：PNG/JPG 在部分客户端会被判为“图片太大”或直接不入库，而同样内容的 GIF（哪怕只有一帧）都能正常加进去并发送。

所以 0.3.0 起默认就是 GIF：

* 输入图片 → **单帧 GIF**，永远不会动
* 输入视频 → 多帧 GIF，正常循环
* 默认 `keep`，保持原比例，**不裁切、不补边**
* 默认预算 1 MB（动图表情的常见上限）

想回退成 PNG 就加 `-f png`，想要方形就加 `-m cover`。

## 四种构图模式

| 模式 | 做什么 | 适合 |
| --- | --- | --- |
| `keep` | **默认**：保持原比例，不裁不补，只缩到 size | 微信表情首选 |
| `pad` | 整张图完整保留，左右/上下用**模糊背景**补满 | 横图、截图，不想丢内容 |
| `fit` | 整张图完整保留，用纯色补满 | 需要干净背景、要抠图时 |
| `cover` | 等比放大铺满方形，裁掉多余部分 | 想要方形时才用 |

`--anchor` 控制裁切时的重心：`center`（默认）/ `top` / `bottom` / `face`（偏上，人像友好）。

## 参数

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `-o, --out` | `stickers` | 输出目录 |
| `-s, --size` | `240` | 边长，可选 240 / 500 / 1000 |
| `-m, --mode` | `keep` | keep（原比例）/ cover / pad / fit |
| `-f, --format` | `gif` | gif（默认）/ png / jpg |
| `-b, --budget` | `gif` | `gif`(1MB) / `chat`(5MB) / `platform`(500KB) / `tiny`(100KB) |
| `--max-kb` | — | 直接用 KB 指定上限 |
| `--bg` | `blur` | pad/fit 的背景：`blur` / `transparent`（透明填充）/ `auto` / `#rrggbb` |
| `--anchor` | `center` | 裁切重心 |
| `-r, --recursive` | 关 | 递归子文件夹 |
| `--dry-run` | 关 | 只看会输出什么，不写文件 |
| `--json` | 关 | 输出机器可读的汇总，方便脚本调用 |

超限时的降级顺序（自动，按顺序尝试）：直接保存 → 减色板 256/128/64/32 色 → 降 JPEG 质量 88→40 → 逐步缩小 10%，直到塞进预算。返回的 `note` 会写明牺牲了什么。

## 视频转 GIF 表情

视频默认走 GIF 通道（微信的动图表情上限通常按 1 MB 算，工具会自动压到这个预算内）。

```bash
wxsticker clip.mp4                       # 前 5 秒 -> stickers/clip.gif，240 宽，12fps
wxsticker clip.mp4 --start 3.2 --duration 2.5 --fps 15
wxsticker clip.mov -s 240 --no-dither     # 关抖动，更小但可能有色带
```

需要 `ffmpeg`：装了 `imageio-ffmpeg` 的话会自动用它内置的二进制；都没有就 `pip install "wechat-sticker-kit[video]"`，或者用 `WXSTICKER_FFMPEG=/path/to/ffmpeg` 指定。

解码交给 ffmpeg，调色板和 GIF 组装由 Pillow 负责——这样帧数、颜色数、抖动都在我们手里，能保证输出一定塞进预算。压不下时的降级顺序：减色板 → 隔帧丢弃 → 缩放。

## 加不进表情？先看这个

| 现象 | 大概率原因 | 处理 |
| --- | --- | --- |
| 长按图片没有「添加到表情」 | 图是以**文件**形式发的，不是图片消息 | 先发出去（当图片发），再长按 |
| 「添加的单个表情」里选不到 | 从相册选，文件传输助手的图没进相册 | 长按图片 → 保存到相册，再去选 |
| 提示图片太大 | 静态图个别版本限制很严（远低于 5 MB） | `-b tiny` 压到 100 KB 以内 |
| 添加后变形/被裁 | 非正方形被面板按方形显示 | 用 `-m pad` 或 `-m cover` 输出正方形 |
| GIF 变成静图 | 超过动图体积上限 | `-b gif`（1 MB）或降低 `--fps` |

## 当库用

```python
from PIL import Image
from wechat_sticker_kit import to_square, encode

im = Image.open("meme.png")
sticker = to_square(im, size=240, mode="pad", bg="blur")   # 240x240 RGBA
data, note = encode(sticker, fmt="png", budget=500 * 1024)
open("sticker.png", "wb").write(data)
print(note or "no compression needed")
```

## 微信里怎么用

1. 手机微信 → 文件传输助手 → 发送转换后的图；
2. 在聊天里长按图片 → **添加到表情**；
3. 之后在输入框的表情面板里就能直接发。

> 动图（GIF）会被当作静态表情处理——微信「添加的单个表情」本身支持 GIF 播放，但本工具默认只取第一帧，避免一张图变成几 MB。

## 常见问题

**为什么默认 240？** 微信表情开放平台的主图标准就是 240×240；聊天里添加的表情按比例显示，240 已经够清晰，500 更保险但体积翻几倍。

**透明背景会丢吗？** `cover` / `keep` 保留 alpha；`pad` / `fit` 本来就铺了不透明底；输出 `jpg` 时会自动压白底。

**为什么我的图被减色了？** 说明原图在这个预算下存不进 PNG，工具按上面的降级顺序处理，`note` 里会写原因。不想被减色就用 `-b chat` 或 `--max-kb 5000`。

**能批量做成一套表情包吗？** 可以：`wxsticker ./raw -r -o pack -s 240 -b platform`，再把 `pack/` 里的图按开放平台要求上传。

## English

Convert PNG/JPG images **and videos** into WeChat-ready stickers: square canvas, 240×240 preset, video→GIF (ffmpeg), automatic squeezing under the 1 MB / 5 MB / 500 KB budget, batch mode, EXIF-corrected, metadata stripped.

```bash
pip install wechat-sticker-kit
wxsticker meme.png                      # -> stickers/meme.png (240x240, PNG, <=5MB)
wxsticker ./photos -r -s 500 -b platform --mode pad
```

Modes: `cover` (crop to square), `pad` (blurred backdrop, nothing lost), `fit` (flat backdrop), `keep` (no square).
Library use: `to_square(im, 240, mode="pad")` + `encode(sticker, "png", budget)`.

## 项目结构

```text
src/wechat_sticker_kit/core.py   # 构图 + 编码 + 预算压缩
src/wechat_sticker_kit/cli.py    # 命令行
tests/test_core.py               # 15 个 unittest，无需额外依赖
```

## License

MIT © 2026 wechat-sticker-kit contributors

## 贡献

欢迎提 issue 和 PR。跑测试只需要 stdlib：

```bash
python -m unittest discover -s tests -v
```

