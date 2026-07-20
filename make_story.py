"""ハイライト用ストーリー画像(1080x1920)を生成する。

Instagramのストーリーは上下がUIに隠れるため、内容は安全域(上220px/下250px)の内側に置く。
JSONの仕様を受け取り、種類ごとにレイアウトを描き分ける:
  type=cover   … 表紙(大タイトル+サブ)
  type=table   … 比較表(2値カラム)
  type=points  … 箇条書き(番号付き)
  type=cta     … 最後の誘導(リンク案内)

使い方:
  python make_story.py specs/biyou_datsumo.json
"""
import json, os, sys
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
SAFE_TOP, SAFE_BOTTOM = 220, 250

FONT_B = "C:/Windows/Fonts/meiryob.ttc"   # 太字
FONT_R = "C:/Windows/Fonts/meiryo.ttc"    # 標準

THEMES = {
    "biyou": {
        "bg": "#FBEFEF", "panel": "#FFFFFF", "ink": "#4A3B3B",
        "accent": "#C98B96", "sub": "#8A7373", "line": "#EBD9DA",
        "chip_bg": "#C98B96", "chip_ink": "#FFFFFF",
    },
    "toushi": {
        "bg": "#12233F", "panel": "#1B3153", "ink": "#FFFFFF",
        "accent": "#E7B85C", "sub": "#B9C6DA", "line": "#2C4570",
        "chip_bg": "#E7B85C", "chip_ink": "#12233F",
    },
}


def font(path, size):
    return ImageFont.truetype(path, size)


def text_w(d, s, f):
    return d.textbbox((0, 0), s, font=f)[2]


def center(d, y, s, f, fill):
    d.text(((W - text_w(d, s, f)) / 2, y), s, font=f, fill=fill)


def wrap(d, s, f, max_w):
    """日本語向けの折り返し(文字単位)。"""
    lines, cur = [], ""
    for ch in s:
        if ch == "\n":
            lines.append(cur); cur = ""; continue
        if text_w(d, cur + ch, f) > max_w and cur:
            lines.append(cur); cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def rounded(d, box, r, fill, outline=None, width=1):
    d.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)


def draw_footer(d, t, note, handle):
    """下部の注記とアカウント名(安全域の内側)。"""
    f_note = font(FONT_R, 26)
    d.text((80, H - SAFE_BOTTOM - 90), note, font=f_note, fill=t["sub"])
    f_handle = font(FONT_B, 26)
    s = handle
    d.text((W - 80 - text_w(d, s, f_handle), H - SAFE_BOTTOM - 90), s, font=f_handle, fill=t["sub"])


def page_cover(img, d, t, spec):
    f_kicker = font(FONT_B, 34)
    f_title = font(FONT_B, 108)
    f_sub = font(FONT_R, 42)

    title_lines = wrap(d, spec["title"], f_title, W - 200)
    sub_lines = wrap(d, spec.get("sub", ""), f_sub, W - 260) if spec.get("sub") else []
    block_h = (130 if spec.get("kicker") else 0) + len(title_lines) * 132 + 40 + len(sub_lines) * 66
    y = SAFE_TOP + max(0, ((H - SAFE_TOP - SAFE_BOTTOM) - block_h) / 2) - 60

    if spec.get("kicker"):
        s = spec["kicker"]
        pad = 26
        tw = text_w(d, s, f_kicker)
        rounded(d, (int((W - tw) / 2 - pad), y - 12, int((W + tw) / 2 + pad), y + 56), 34, t["chip_bg"])
        center(d, y, s, f_kicker, t["chip_ink"])
        y += 130

    for line in title_lines:
        center(d, y, line, f_title, t["accent"])
        y += 132
    y += 40

    for line in sub_lines:
        center(d, y, line, f_sub, t["ink"])
        y += 66

    # 下向きの案内
    f_tap = font(FONT_R, 30)
    center(d, H - SAFE_BOTTOM - 190, spec.get("tap", "タップで next →"), f_tap, t["sub"])


def page_table(img, d, t, spec):
    f_title = font(FONT_B, 76)
    f_head = font(FONT_B, 42)
    f_label = font(FONT_B, 38)
    f_val = font(FONT_R, 38)

    rows = spec["rows"]
    cols = spec["cols"]          # 例 ["医療脱毛", "サロン脱毛"]
    x0, x1 = 70, W - 70
    label_w = 250
    col_w = (x1 - x0 - label_w) / len(cols)

    head_h, row_h = 96, 124
    table_h = head_h + row_h * len(rows)

    # 安全域の中で縦中央に置く(タイトル+表+メモを1ブロックとして計算)
    title_lines = wrap(d, spec["title"], f_title, W - 180)
    memo_lines = wrap(d, spec.get("memo", ""), font(FONT_R, 32), W - 180) if spec.get("memo") else []
    block_h = len(title_lines) * 96 + 40 + table_h + (len(memo_lines) * 46 + 40 if memo_lines else 0)
    y = SAFE_TOP + max(0, ((H - SAFE_TOP - SAFE_BOTTOM) - block_h) / 2)

    for line in title_lines:
        center(d, y, line, f_title, t["accent"])
        y += 96
    y += 40

    rounded(d, (x0, y, x1, y + table_h), 28, t["panel"])

    # ヘッダー
    for i, c in enumerate(cols):
        cx = x0 + label_w + col_w * i + col_w / 2
        d.text((cx - text_w(d, c, f_head) / 2, y + 24), c, font=f_head, fill=t["accent"])
    d.line((x0 + 20, y + head_h, x1 - 20, y + head_h), fill=t["line"], width=2)

    # 行(ラベル・値とも複数行に対応し、行の中で縦中央に置く)
    for r, row in enumerate(rows):
        ry = y + head_h + row_h * r
        lab_lines = row["label"].split("\n")
        ly = ry + (row_h - len(lab_lines) * 46) / 2
        for line in lab_lines:
            d.text((x0 + 34, ly), line, font=f_label, fill=t["ink"])
            ly += 46
        for i, v in enumerate(row["values"]):
            cx = x0 + label_w + col_w * i + col_w / 2
            vlines = wrap(d, v, f_val, col_w - 30)
            vy = ry + (row_h - len(vlines) * 46) / 2
            for line in vlines:
                d.text((cx - text_w(d, line, f_val) / 2, vy), line, font=f_val, fill=t["ink"])
                vy += 46
        if r < len(rows) - 1:
            d.line((x0 + 20, ry + row_h, x1 - 20, ry + row_h), fill=t["line"], width=2)

    if memo_lines:
        f_memo = font(FONT_R, 32)
        my = y + table_h + 40
        for line in memo_lines:
            center(d, my, line, f_memo, t["sub"])
            my += 46


def page_points(img, d, t, spec):
    f_title = font(FONT_B, 76)
    f_num = font(FONT_B, 38)
    f_head = font(FONT_B, 46)
    f_body = font(FONT_R, 34)

    # 各ボックスの高さを先に確定し、全体を縦中央に置く
    boxes = []
    for p in spec["points"]:
        body_lines = wrap(d, p["body"], f_body, W - 300) if p.get("body") else []
        boxes.append((p, body_lines, 120 + len(body_lines) * 46 if body_lines else 130))

    title_lines = wrap(d, spec["title"], f_title, W - 180)
    block_h = len(title_lines) * 96 + 40 + sum(h + 26 for _, _, h in boxes)
    y = SAFE_TOP + max(0, ((H - SAFE_TOP - SAFE_BOTTOM) - block_h) / 2)

    for line in title_lines:
        center(d, y, line, f_title, t["accent"])
        y += 96
    y += 40

    for i, (p, body_lines, box_h) in enumerate(boxes, 1):
        rounded(d, (70, y, W - 70, y + box_h), 24, t["panel"])
        # 番号バッジ
        d.ellipse((104, y + 32, 104 + 56, y + 88), fill=t["chip_bg"])
        n = str(i)
        d.text((104 + 28 - text_w(d, n, f_num) / 2, y + 40), n, font=f_num, fill=t["chip_ink"])
        d.text((190, y + 34), p["head"], font=f_head, fill=t["ink"])
        by = y + 106
        for line in body_lines:
            d.text((190, by), line, font=f_body, fill=t["sub"])
            by += 46
        y += box_h + 26


def page_cta(img, d, t, spec):
    f_title = font(FONT_B, 76)
    f_body = font(FONT_R, 40)
    f_btn = font(FONT_B, 44)

    title_lines = wrap(d, spec["title"], f_title, W - 180)
    body_lines = wrap(d, spec.get("body", ""), f_body, W - 260) if spec.get("body") else []
    block_h = len(title_lines) * 96 + 40 + len(body_lines) * 62 + 60 + 118 + (70 if spec.get("hint") else 0)
    y = SAFE_TOP + max(0, ((H - SAFE_TOP - SAFE_BOTTOM) - block_h) / 2)

    for line in title_lines:
        center(d, y, line, f_title, t["accent"])
        y += 96
    y += 40
    for line in body_lines:
        center(d, y, line, f_body, t["ink"])
        y += 62

    # 疑似ボタン(実際のリンクはIGのリンクスタンプを重ねる)
    y += 60
    bw, bh = 700, 118
    rounded(d, ((W - bw) / 2, y, (W + bw) / 2, y + bh), 59, t["chip_bg"])
    center(d, y + 34, spec.get("button", "プロフィールのリンクへ"), f_btn, t["chip_ink"])

    if spec.get("hint"):
        f_hint = font(FONT_R, 30)
        center(d, y + bh + 40, spec["hint"], f_hint, t["sub"])


DRAW = {"cover": page_cover, "table": page_table, "points": page_points, "cta": page_cta}


def main(spec_path):
    with open(spec_path, encoding="utf-8") as f:
        spec = json.load(f)

    t = THEMES[spec["theme"]]
    outdir = spec["outdir"]
    os.makedirs(outdir, exist_ok=True)

    for i, page in enumerate(spec["pages"], 1):
        img = Image.new("RGB", (W, H), t["bg"])
        d = ImageDraw.Draw(img)
        DRAW[page["type"]](img, d, t, page)
        draw_footer(d, t, page.get("note", spec.get("note", "")), spec["handle"])
        path = os.path.join(outdir, f"{i:02d}.png")
        img.save(path)
        print(f"saved {path}")


if __name__ == "__main__":
    main(sys.argv[1])
