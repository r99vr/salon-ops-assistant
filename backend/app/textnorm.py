"""أدوات النص العربي: توحيد الكتابة، استخراج الأرقام، ومطابقة الأصناف.

تُستخدم كخطة بديلة لما ما يكون فيه مفتاح ذكاء اصطناعي، وكتحقق إضافي على نتيجة النموذج.
"""
import re
from difflib import SequenceMatcher

_DIACRITICS = re.compile(r"[ؗ-ًؚ-ْـ]")
_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

STOPWORDS = {
    "في", "من", "على", "عن", "الى", "الي", "و", "يا", "تم", "خلاص", "مره", "شوي", "عندنا",
    "عندي", "اللي", "هذا", "هذي", "هذه", "ذا", "ذي", "كذا", "الحين", "الان", "بعد", "مع",
    "لو", "ان", "انه", "انها", "قد", "صار", "صارت", "لنا", "فيه", "فيها", "حق", "حقت",
    "رقم", "كل", "تكفين", "لا", "ما", "مو", "يعني", "مافي", "تراه", "ترا", "تراها",
}

NUMBER_WORDS = {
    "صفر": 0, "واحد": 1, "واحده": 1, "وحده": 1, "حبه": 1, "اثنين": 2, "ثنتين": 2, "اثنتين": 2,
    "ثلاث": 3, "ثلاثه": 3, "اربع": 4, "اربعه": 4, "خمس": 5, "خمسه": 5, "ست": 6, "سته": 6,
    "سبع": 7, "سبعه": 7, "ثمان": 8, "ثمانيه": 8, "تسع": 9, "تسعه": 9, "عشر": 10, "عشره": 10,
    "نص": 0.5, "نصف": 0.5,
}
# المثنى العامي: علبتين، قارورتين، كرتونين ...
_DUAL = re.compile(r"^[؀-ۿ]{2,}تين$|^[؀-ۿ]{3,}ين$")

ORDINALS = {
    "الاول": "1", "اول": "1", "الثاني": "2", "ثاني": "2", "الثالث": "3", "ثالث": "3",
    "الرابع": "4", "رابع": "4", "الخامس": "5", "خامس": "5",
}

SHORTAGE_WORDS = [
    "خلص", "خلصت", "خلصو", "خلصوا", "ناقص", "ناقصه", "نقص", "نقصت", "قرب يخلص", "قربت تخلص",
    "باقي", "مافيه", "ما فيه", "ما عاد", "ماعاد", "انتهى", "انتهت", "نفد", "نفذ", "نفدت", "نفذت",
    "نبي", "نحتاج", "محتاجين", "اطلبو", "اطلبوا", "اطلبي",
]
ISSUE_WORDS = [
    "خربان", "خربانه", "خرب", "خربت", "عطلان", "عطلانه", "معطل", "معطله", "تعطل", "تعطلت",
    "ما يشتغل", "مايشتغل", "ما تشتغل", "ماتشتغل", "ما يسخن", "مايسخن", "ما تسخن", "ماتسخن",
    "ما يشغل", "مايشغل", "طفى", "طفت", "يطفي", "يقطع", "فيه مشكله", "فيها مشكله", "يصدر صوت",
    "صوت غريب", "يحترق", "ريحه حريق", "مكسور", "مكسوره", "انكسر", "انكسرت", "ما يشفط", "ضعيف",
    "يهرب", "يسرب", "ما يرش", "مايرش",
]
INVOICE_WORDS = ["فاتوره", "الفاتوره", "فواتير", "استلمنا", "استلمت", "وصلت الطلبيه", "وصل الطلب", "وصلت البضاعه", "سند"]
PROOF_WORDS = ["تم", "خلصت التنظيف", "نظفت", "عقمت", "خلصت التعقيم", "جاهز", "انتهيت", "سويت", "مسحت", "غسلت", "رتبت"]
APPROVE_WORDS = ["موافق", "موافقه", "اعتمد", "اعتمدي", "معتمد", "تمام", "اوكي", "ok", "اوك", "ارسل", "ارسلها", "ارسلوها", "اطلب", "اطلبها", "توكل", "يلا", "نعم", "ايه", "اي", "وافقت", "اكيد"]
REJECT_WORDS = ["الغ", "الغي", "الغاء", "لا ترسل", "لاترسل", "وقف", "وقفي", "لا تطلب", "مو الحين", "ارفض", "مرفوض"]
REMOVE_WORDS = ["شيل", "شيلي", "احذف", "احذفي", "بدون", "الغ", "الغي", "لا تطلب", "شطب"]


def normalize(text: str) -> str:
    if not text:
        return ""
    t = text.translate(_ARABIC_DIGITS)
    t = _DIACRITICS.sub("", t)
    t = re.sub("[إأآٱ]", "ا", t)
    t = t.replace("ة", "ه").replace("ى", "ي").replace("ؤ", "و").replace("ئ", "ي")
    t = re.sub(r"[^\w\s\.]", " ", t)
    t = re.sub(r"\s+", " ", t).strip().lower()
    return t


def strip_al(word: str) -> str:
    for p in ("وال", "بال", "فال", "كال", "لل", "ال"):
        if word.startswith(p) and len(word) - len(p) >= 2:
            return word[len(p):]
    return word


def tokens(text: str) -> list[str]:
    out = []
    for w in normalize(text).split():
        w = ORDINALS.get(w, w)
        w = strip_al(w)
        if w and w not in STOPWORDS:
            out.append(w)
    return out


def contains_any(text: str, words: list[str]) -> bool:
    n = " " + normalize(text) + " "
    for w in words:
        nw = normalize(w)
        if f" {nw} " in n or (len(nw) >= 4 and nw in n):
            return True
    return False


def extract_remaining(text: str) -> float | None:
    """يستخرج الكمية الباقية من جمل مثل: «باقي علبتين» «باقي 3» «خلصت» (=0)."""
    n = normalize(text)
    m = re.search(r"(?:باقي|بقي|تبقي|عندنا|متبقي)\s+(?:بس|فقط|حوالي|تقريبا)?\s*([\w\.]+)", n)
    if m:
        val = _word_to_number(m.group(1))
        if val is not None:
            return val
    if contains_any(text, ["خلص", "خلصت", "خلصو", "خلصوا", "انتهى", "انتهت", "نفد", "نفذ", "نفدت", "نفذت", "مافيه", "ما فيه", "ما عاد", "ماعاد", "صفر"]):
        return 0.0
    return None


def _word_to_number(w: str) -> float | None:
    w = w.strip()
    try:
        return float(w)
    except ValueError:
        pass
    if w in NUMBER_WORDS:
        return float(NUMBER_WORDS[w])
    if _DUAL.match(w) and w not in NUMBER_WORDS:
        return 2.0
    return None


def extract_quantity(text: str) -> float | None:
    """أول رقم أو كلمة عدد في النص."""
    for w in normalize(text).split():
        try:
            return float(w)
        except ValueError:
            if w in NUMBER_WORDS:
                return float(NUMBER_WORDS[w])
    return None


def score(query: str, name: str, aliases: str = "") -> float:
    """درجة تطابق من 0 إلى 1 بين نص الرسالة واسم الصنف وأسمائه البديلة."""
    q = tokens(query)
    if not q:
        return 0.0
    best = 0.0
    for cand in [name] + [a for a in (aliases or "").split(",") if a.strip()]:
        c = tokens(cand)
        if not c:
            continue
        hits = 0.0
        for ct in c:
            m = max((_tok_sim(ct, qt) for qt in q), default=0)
            hits += m
        s = hits / len(c)
        # مكافأة إذا كل الكلمات المميزة موجودة
        if s >= 0.99:
            s += 0.1 * min(len(c), 3)
        best = max(best, s)
    return best


def _tok_sim(a: str, b: str) -> float:
    if a == b:
        return 1.0
    if a.isdigit() or b.isdigit():
        return 0.0
    if len(a) >= 3 and len(b) >= 3 and (a in b or b in a):
        return 0.85
    r = SequenceMatcher(None, a, b).ratio()
    return r if r >= 0.75 else 0.0
