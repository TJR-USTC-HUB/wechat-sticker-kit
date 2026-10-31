
import io
p = r"C:\Users\jiaryWin\OneDrive\文档\deepseek-harness\default-workspace\wechat-sticker-kit\src\wechat_sticker_kit\core.py"
s = io.open(p, encoding="utf-8").read()
old = '''    base = str(name).split("@", 1)[0]
    low = base.lower()
    for ext in sorted({e for e in INPUT_SUFFIXES} | {".jpeg"}, key=len, reverse=True):
        if low.endswith(ext):
            base = base[: -len(ext)]
            break
    return base or "sticker"'''
new = '''    base = str(name).split("@", 1)[0]
    exts = sorted({e for e in INPUT_SUFFIXES} | {".jpeg"}, key=len, reverse=True)
    shrinking = True
    while shrinking:
        shrinking = False
        low = base.lower()
        for ext in exts:
            if low.endswith(ext) and len(base) > len(ext):
                base = base[: -len(ext)]
                shrinking = True
                break
    return base or "sticker"'''
assert old in s, "anchor missing"
io.open(p, "w", encoding="utf-8", newline="\n").write(s.replace(old, new, 1))
print("safe_stem fixed")
