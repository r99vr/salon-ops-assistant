"""يولّد الصور التجريبية للمحاكي (فواتير، رفوف، صور إثبات).

التشغيل: python scripts/make_samples.py
الفواتير مكتوبة نص حقيقي عشان نموذج الصور يقدر يقرأها فعلاً في العرض.
"""
import math
import random
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1] / "app"
OUT = ROOT / "samples"
FONTS = ROOT / "fonts"
OUT.mkdir(exist_ok=True)


def font(size, weight="400Regular"):
    return ImageFont.truetype(str(FONTS / f"IBMPlexSansArabic_{weight}.ttf"), size, layout_engine=ImageFont.Layout.RAQM)


def rtl(d: ImageDraw.ImageDraw, xy, text, fnt, fill, anchor="ra"):
    d.text(xy, text, font=fnt, fill=fill, anchor=anchor, direction="rtl", language="ar")


def photo_finish(img: Image.Image, seed: int) -> Image.Image:
    """لمسة «صورة جوال»: إضاءة غير متساوية وضوضاء خفيفة وإمالة بسيطة."""
    rnd = random.Random(seed)
    w, h = img.size
    vignette = Image.new("L", (w, h), 0)
    vd = ImageDraw.Draw(vignette)
    for i in range(40):
        r = int(max(w, h) * (0.95 - i * 0.012))
        vd.ellipse([w / 2 - r, h / 2 - r, w / 2 + r, h / 2 + r], fill=int(i * 6))
    vignette = vignette.filter(ImageFilter.GaussianBlur(60))
    dark = Image.new("RGB", (w, h), (20, 18, 16))
    img = Image.composite(img, dark, vignette.point(lambda v: min(255, v + 120)))
    noise = Image.effect_noise((w, h), 10).convert("RGB")
    img = Image.blend(img, noise, 0.04)
    img = img.rotate(rnd.uniform(-1.6, 1.6), resample=Image.BICUBIC, expand=False, fillcolor=(40, 36, 32))
    return img


# ------------------------------------------------------------------ invoices
def invoice(name, supplier, cr, phone, no, lines, color, seed):
    W, H = 1100, 1500
    paper = Image.new("RGB", (W, H), (252, 251, 247))
    d = ImageDraw.Draw(paper)
    d.rectangle([0, 0, W, 190], fill=color)
    rtl(d, (W - 70, 50), supplier, font(52, "700Bold"), (255, 255, 255))
    rtl(d, (W - 70, 125), f"س.ت {cr}  •  جوال {phone}", font(26), (255, 255, 255))
    d.text((70, 60), "TAX INVOICE", font=font(30, "600SemiBold"), fill=(255, 255, 255))

    rtl(d, (W - 70, 240), "فاتورة ضريبية مبسطة", font(40, "700Bold"), (40, 40, 40))
    info = [("رقم الفاتورة", no), ("التاريخ", date.today().strftime("%Y-%m-%d")), ("العميل", "صالون التجميل"), ("طريقة الدفع", "آجل")]
    y = 320
    for k, v in info:
        rtl(d, (W - 70, y), f"{k}:", font(28, "600SemiBold"), (90, 90, 90))
        rtl(d, (W - 300, y), v, font(28), (30, 30, 30))
        y += 50

    y += 30
    d.rectangle([60, y, W - 60, y + 64], fill=(238, 236, 230))
    cols = [(W - 80, "الصنف"), (520, "الكمية"), (360, "سعر الوحدة"), (170, "الإجمالي")]
    for x, t in cols:
        rtl(d, (x, y + 14), t, font(26, "700Bold"), (50, 50, 50))
    y += 84
    subtotal = 0
    for item, qty, price in lines:
        total = qty * price
        subtotal += total
        rtl(d, (W - 80, y), item, font(30), (25, 25, 25))
        rtl(d, (520, y), str(qty), font(30), (25, 25, 25))
        rtl(d, (360, y), f"{price:.2f}", font(30), (25, 25, 25))
        rtl(d, (170, y), f"{total:.2f}", font(30), (25, 25, 25))
        y += 66
        d.line([70, y - 12, W - 70, y - 12], fill=(225, 222, 215), width=2)
    vat = round(subtotal * 0.15, 2)
    y += 30
    for k, v, bold in (("المجموع", subtotal, False), ("ضريبة القيمة المضافة 15%", vat, False), ("الإجمالي المستحق", subtotal + vat, True)):
        f = font(34 if bold else 28, "700Bold" if bold else "400Regular")
        rtl(d, (W - 80, y), k, f, (25, 25, 25))
        rtl(d, (300, y), f"{v:,.2f} ر.س", f, color if bold else (25, 25, 25))
        y += 60 if bold else 50
    # QR وهمي وتوقيع
    rnd = random.Random(seed)
    qx, qy = 90, H - 330
    for i in range(21):
        for j in range(21):
            if rnd.random() < 0.5 or (i < 7 and j < 7) or (i < 7 and j > 13) or (i > 13 and j < 7):
                d.rectangle([qx + i * 11, qy + j * 11, qx + i * 11 + 10, qy + j * 11 + 10], fill=(30, 30, 30))
    rtl(d, (W - 80, H - 300), "المستلم: ________________", font(28), (80, 80, 80))
    rtl(d, (W - 80, H - 230), "شكراً لتعاملكم معنا", font(28, "600SemiBold"), color)
    d.ellipse([W - 360, H - 190, W - 130, H - 60], outline=(70, 90, 160), width=5)
    rtl(d, (W - 245, H - 140), "مستلم", font(30, "700Bold"), (70, 90, 160), anchor="ma")

    # نحط الورقة على طاولة بزاوية بسيطة مثل صورة جوال
    bg = Image.new("RGB", (1200, 1650), (118, 96, 78))
    bgd = ImageDraw.Draw(bg)
    for i in range(0, 1650, 9):
        bgd.line([0, i, 1200, i + random.Random(i).randint(-4, 4)], fill=(110 + i % 13, 90 + i % 9, 72), width=4)
    shadow = Image.new("RGBA", paper.size, (0, 0, 0, 110)).filter(ImageFilter.GaussianBlur(4))
    bg.paste(shadow.convert("RGB"), (62, 82), shadow)
    bg.paste(paper, (50, 70))
    img = photo_finish(bg, seed).resize((900, 1238), Image.LANCZOS)
    img.save(OUT / name, quality=88)


# ------------------------------------------------------------------- scenes
def scene(name, title, palette, draw_fn, seed, chip=None):
    W, H = 1080, 1080
    img = Image.new("RGB", (W, H), palette[0])
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        c = tuple(int(palette[0][i] * (1 - t) + palette[1][i] * t) for i in range(3))
        d.line([0, y, W, y], fill=c)
    draw_fn(d, W, H, random.Random(seed))
    img = photo_finish(img, seed)
    d = ImageDraw.Draw(img)
    stamp = f"{date.today():%Y/%m/%d}"
    d.text((40, H - 70), stamp, font=font(30, "600SemiBold"), fill=(255, 196, 120))
    if chip:
        rtl(d, (W - 40, 40), chip, font(30, "600SemiBold"), (255, 255, 255))
    img.resize((900, 900), Image.LANCZOS).save(OUT / name, quality=86)


def shelf(d, W, H, rnd, boxes):
    for k in range(3):
        y = 330 + k * 260
        d.rectangle([60, y, W - 60, y + 22], fill=(196, 170, 140))
        d.rectangle([60, y + 22, W - 60, y + 34], fill=(150, 125, 100))
    for (shelf_i, x, w, h, col, label) in boxes:
        y = 330 + shelf_i * 260
        d.rounded_rectangle([x, y - h, x + w, y], 10, fill=col, outline=(60, 50, 45), width=3)
        if label:
            rtl(d, (x + w / 2, y - h / 2 - 18), label, font(30, "700Bold"), (255, 255, 255), anchor="ma")


def shelf_dye(d, W, H, rnd):
    shelf(d, W, H, rnd, [
        (0, 140, 150, 210, (92, 58, 40), "بني 5.0"),
        (1, 180, 150, 210, (40, 36, 36), "أسود"),
        (1, 350, 150, 210, (40, 36, 36), "أسود"),
        (1, 520, 150, 210, (40, 36, 36), "أسود"),
        (2, 200, 150, 210, (210, 170, 90), "أشقر"),
        (2, 370, 150, 210, (210, 170, 90), "أشقر"),
    ])
    rtl(d, (W - 90, 120), "صبغات", font(46, "700Bold"), (90, 70, 60))


def shelf_towels(d, W, H, rnd):
    shelf(d, W, H, rnd, [(0, 150 + i * 120, 110, 60, (245, 245, 240), None) for i in range(2)] +
          [(1, 150 + i * 120, 110, 60, (245, 245, 240), None) for i in range(1)])
    rtl(d, (W - 90, 120), "مناشف", font(46, "700Bold"), (90, 90, 110))


def tray(d, W, H, rnd, tool_color=(190, 195, 205)):
    d.rounded_rectangle([170, 420, W - 170, 820], 40, fill=(235, 240, 245), outline=(170, 180, 190), width=6)
    for i in range(7):
        x = 250 + i * 95
        d.rounded_rectangle([x, 470 + (i % 2) * 20, x + 26, 770], 12, fill=tool_color, outline=(120, 125, 135), width=3)
    for _ in range(14):
        x, y = rnd.randint(160, W - 160), rnd.randint(200, 900)
        r = rnd.randint(6, 16)
        d.polygon([(x, y - r * 2), (x + r / 2, y - r / 2), (x + r * 2, y), (x + r / 2, y + r / 2), (x, y + r * 2),
                   (x - r / 2, y + r / 2), (x - r * 2, y), (x - r / 2, y - r / 2)], fill=(255, 255, 255))


def brushes(d, W, H, rnd):
    d.rounded_rectangle([360, 520, 720, 900], 30, fill=(230, 210, 215))
    for i in range(9):
        a = math.radians(-35 + i * 9)
        x0, y0 = 540, 560
        x1, y1 = x0 + math.sin(a) * 430, y0 - math.cos(a) * 430
        d.line([x0, y0, x1, y1], fill=(40, 40, 45), width=16)
        d.ellipse([x1 - 28, y1 - 40, x1 + 28, y1 + 40], fill=(rnd.randint(200, 240), rnd.randint(180, 210), 190))


def floor(d, W, H, rnd):
    for i in range(-10, 20):
        d.line([i * 120, H, i * 120 + 700, 380], fill=(220, 220, 215), width=3)
    for j in range(8):
        y = 400 + j * j * 12
        d.line([0, y, W, y], fill=(220, 220, 215), width=3)
    d.ellipse([300, 520, 800, 640], fill=(255, 255, 255))


def chairs(d, W, H, rnd):
    for x in (180, 600):
        d.rounded_rectangle([x, 380, x + 300, 640], 50, fill=(30, 30, 34))
        d.rounded_rectangle([x - 10, 620, x + 310, 720], 30, fill=(40, 40, 44))
        d.rectangle([x + 130, 720, x + 170, 880], fill=(170, 170, 175))
        d.ellipse([x + 40, 860, x + 260, 910], fill=(150, 150, 155))


def towels(d, W, H, rnd):
    for i in range(6):
        d.rounded_rectangle([280, 760 - i * 70, 800, 830 - i * 70], 26, fill=(250, 250, 248), outline=(215, 215, 210), width=4)


def scent(d, W, H, rnd):
    d.rounded_rectangle([430, 420, 650, 860], 40, fill=(250, 250, 250), outline=(200, 200, 200), width=5)
    d.ellipse([500, 450, 580, 530], fill=(200, 170, 220))
    for i in range(5):
        d.arc([380 - i * 30, 200 - i * 30, 700 + i * 30, 520 + i * 30], 220, 320, fill=(255, 255, 255), width=4)


def closing(d, W, H, rnd):
    floor(d, W, H, rnd)
    chairs(d, W, H, rnd)


def dryer(d, W, H, rnd):
    d.ellipse([260, 300, 640, 640], fill=(40, 40, 46))
    d.rounded_rectangle([600, 400, 860, 540], 40, fill=(40, 40, 46))
    d.rounded_rectangle([360, 600, 480, 950], 40, fill=(50, 50, 56))
    d.ellipse([360, 400, 540, 560], fill=(80, 80, 88))
    d.line([420, 950, 380, 1080], fill=(30, 30, 30), width=14)


if __name__ == "__main__":
    invoice("invoice-lamsa.jpg", "مؤسسة لمسة للتجميل", "2050147731", "0501234567", "LM-2318",
            [("سيروم شعر", 4, 90), ("صبغة بنية", 8, 38)], (164, 52, 92), 1)
    invoice("invoice-naqaa.jpg", "شركة نقاء للمنظفات", "2050339012", "0559876543", "NQ-5590",
            [("مطهر أدوات", 5, 55), ("مناشف بيضاء", 20, 12)], (24, 112, 128), 2)
    scene("shelf-dye.jpg", "", [(236, 226, 214), (214, 200, 186)], shelf_dye, 3)
    scene("shelf-towels.jpg", "", [(232, 234, 238), (210, 214, 220)], shelf_towels, 4)
    scene("proof-sterilize.jpg", "", [(214, 232, 240), (180, 206, 220)], tray, 5)
    scene("proof-brushes.jpg", "", [(246, 232, 236), (226, 204, 212)], brushes, 6)
    scene("proof-chairs.jpg", "", [(236, 236, 240), (214, 214, 222)], chairs, 7)
    scene("proof-towels.jpg", "", [(232, 240, 236), (204, 222, 214)], towels, 8)
    scene("proof-floor.jpg", "", [(242, 240, 236), (222, 218, 210)], floor, 9)
    scene("proof-scent.jpg", "", [(238, 232, 246), (214, 204, 230)], scent, 10)
    scene("proof-closing.jpg", "", [(232, 232, 236), (200, 200, 210)], closing, 11)
    scene("dryer.jpg", "", [(236, 230, 226), (212, 204, 198)], dryer, 12)
    print("تم:", sorted(p.name for p in OUT.glob("*")))
