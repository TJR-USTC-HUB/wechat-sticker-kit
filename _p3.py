
import io
p = r"C:\Users\jiaryWin\OneDrive\文档\deepseek-harness\default-workspace\wechat-sticker-kit\src\wechat_sticker_kit\cli.py"
s = io.open(p, encoding="utf-8").read()

old = '''    out_dir = Path(args.out)
    results = []
    failures = []
'''
new = '''    out_dir = Path(args.out)
    results = []
    failures = []
    seen = {}
'''
assert old in s
s = s.replace(old, new, 1)

old2 = '''        try:
            if is_video:
                dst = out_dir / (safe_stem(src.name) + ".gif")'''
new2 = '''        stem = safe_stem(src.name)
        count = seen.get(stem, 0) + 1
        seen[stem] = count
        suffix = "" if count == 1 else "-%d" % count

        try:
            if is_video:
                dst = out_dir / (stem + suffix + ".gif")'''
assert old2 in s
s = s.replace(old2, new2, 1)

old3 = '''                    budget=file_budget, anchor=args.anchor, bg=bg, fill=fill,
                ))'''
new3 = '''                    budget=file_budget, anchor=args.anchor, bg=bg, fill=fill,
                    suffix=suffix,
                ))'''
assert old3 in s
s = s.replace(old3, new3, 1)
io.open(p, "w", encoding="utf-8", newline="\n").write(s)
print("collision handling added")
