<div dir="rtl">

# مساعد تشغيل الصالون

![مساعد تشغيل الصالون](docs/screenshots/00-cover.jpg)

نظام تشغيل للمتاجر الصغيرة، والصالون هو المثال: العاملات يكملن يرسلن رسايل وصور زي ما متعودين، ومساعد ذكي يرتب كل شي بدال ما يضيع في المحادثات. **المحادثة للشغل، ولوحة التحكم للرؤية والإعدادات.**

> مشروع عرض (Demo) ضمن معرض أعمال عادل الأسمري، ببيانات تجريبية ومو لصالون معيّن.

## الشاشات

| | |
| --- | --- |
| ![الرئيسية](docs/screenshots/01-home.jpg) **الرئيسية:** يوم الصالون، قائمة النظافة بصور الإثبات، النواقص، الطلبيات، الحضور | ![محادثة العاملة](docs/screenshots/02-chat-staff.jpg) **العاملة ترسل:** «خلصت الصبغة البنية» و«الاستشوار الثاني ما يسخن» |
| ![موافقة صاحبة الصالون](docs/screenshots/04-chat-owner.jpg) **صاحبة الصالون:** ملخص الثامنة، تعديل الكمية، ثم «موافقة» تروح للمندوب | ![تحضير المديرة](docs/screenshots/03-chat-manager.jpg) **المديرة تحضّر:** «ريم طلعت 5 العصر» و«مين حاضر؟» |
| ![الطلبيات](docs/screenshots/05-orders.jpg) **الطلبيات:** عند المناديب ورد المندوب والفواتير | ![الحضور](docs/screenshots/06-attendance.jpg) **الحضور:** اليوم وسجل أسبوعي بالساعات |
| ![مهام النظافة](docs/screenshots/07-tasks.jpg) **مهام النظافة:** قائمة يومية تنقفل بالصور | ![المخزون](docs/screenshots/08-inventory.jpg) **المخزون:** كل قسم وعاملته والحد الأدنى لكل صنف |

<p align="center"><img src="docs/screenshots/09-mobile.jpg" width="280" alt="اللوحة على الجوال"></p>

## المشكلة ← الحل ← النتيجة

| المشكلة | الحل في النظام |
| --- | --- |
| الصبغة تخلص فجأة، والطلب من المورد يضيع بين الرسايل | العاملة ترسل «خلصت الصبغة البنية» ← تنسجل، وإذا نزلت تحت الحد الأدنى تنضاف لطلبية الليلة ← الساعة 8 ملخص واحد لصاحبة الصالون ← توافق ← تروح للمندوب ← ويتابعه إذا ما رد |
| ما أحد يدري هل التعقيم انعمل فعلاً | قائمة نظافة يومية بدون مواعيد، وكل مهمة تنقفل بصورة. وقت المراجعة يذكّر العاملة باللي باقي، وبعد المهلة ينبّه صاحبة الصالون |
| الاستشوار خربان والكل يدري إلا الإدارة | «الاستشوار الثاني ما يسخن» ← حالته «معطل» في اللوحة + تنبيه فوري |
| الفواتير في درج | صورة الفاتورة ← تنطابق مع الطلبية المفتوحة (ومع مفتاح الذكاء الاصطناعي يقرأ المورد والمبلغ والأصناف من الصورة) ← مصروف + الأصناف تنضاف للمخزون |
| ما أحد متأكد مين داومت ومتى طلعت | المديرة ترسل «وصلت نورة وريم» أو «سارة طلعت» ← الحضور والخروج والغياب ينسجل، وسجل أسبوعي بالساعات في اللوحة |
| صاحبة الصالون تسأل كل صباح «وش الوضع؟» | تقرير صباحي برسالة وحدة: النواقص، مهام أمس، الحضور، الأعطال، المصاريف |

## المكونات

```
salon-ops-assistant/
├─ backend/            FastAPI + APScheduler + SQLAlchemy (Postgres)
│  ├─ app/engine.py        قلب المساعد: استقبال الرسالة وتنفيذ السيناريو
│  ├─ app/classifier.py    تصنيف الرسالة (نقص / إثبات مهمة / عطل / فاتورة) بالذكاء الاصطناعي، وقواعد نصية كخطة بديلة
│  ├─ app/orders.py        تجميع الطلبية، الموافقة، الإرسال للمندوب، المتابعة
│  ├─ app/cleaning.py      جدول النظافة والتذكير والتصعيد
│  ├─ app/attendance.py    تحضير العاملات من رسائل المديرة
│  ├─ app/reports.py       تقرير الصباح
│  ├─ app/messaging.py     طبقة القنوات: المحاكي / تيليجرام / واتساب
│  ├─ app/telegram_bot.py  قناة تيليجرام (روابط دعوة لكل شخص)
│  ├─ app/seed.py          «صالون التجميل» التجريبي — كل شي بيانات مو كود
│  └─ tests/               20 اختبار للسيناريوهات من البداية للنهاية
├─ frontend/           Next.js 16 — لوحة عربية RTL
│  └─ app/  الرئيسية، المخزون، مهام النظافة، الحضور، الطلبيات، المحاكي، الإعدادات
├─ docker-compose.yml        تشغيل كامل على جهازك
├─ docker-compose.prod.yml   السيرفر: Postgres + الخلفية + Caddy (HTTPS تلقائي)
└─ DEPLOY.md                 خطوات الحسابات والنشر
```

**قاعدة التصميم:** الأقسام والأصناف والمهام والأدوار كلها بيانات. نفس النواة تشتغل لكوفي أو مغسلة بملف بيانات ثاني.

## التشغيل على جهازك

```bash
cp .env.example .env        # حط مفتاح OpenRouter إذا عندك (اختياري)
docker compose up --build
```

- اللوحة: http://localhost:3000
- توثيق الـ API: http://localhost:8000/docs

أول تشغيل يعبّي صالون تجريبي ببيانات أسبوعين (طلبيات، فواتير، مهام، أعطال سابقة). زر **«إعادة بيانات العرض»** في المحاكي يرجعها لبدايتها، واسم الصالون يتغير من الإعدادات.

> إذا تغيّر شكل قاعدة البيانات بعد تحديث الكود، الخلفية تعيد بناء بيانات العرض تلقائياً عند التشغيل.

### بدون Docker (للتطوير)

```bash
# الخلفية
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgresql+psycopg://salon:salon@localhost:5432/salon
uvicorn app.main:app --reload

# اللوحة
cd frontend && npm install && npm run dev
```

## القنوات

| القناة | متى | ملاحظات |
| --- | --- | --- |
| **المحاكي** | العرض والفيديو | داخل اللوحة، تختار أي شخص وتكتب كأنك هو. كل الرسايل تظهر فيه دائماً |
| **تيليجرام** | العرض المباشر على الجوالات | مجاني بدون حدود. كل شخص يمسح QR خاص فيه من الإعدادات مرة وحدة |
| **واتساب** | مع عميل حقيقي | الكود جاهز (Cloud API + webhook + قوالب خارج نافذة 24 ساعة). من 1 أكتوبر 2026 ميتا تحاسب على كل رسالة خدمة |

الرد على أي رسالة يرجع لنفس القناة اللي جت منها. الرسايل اللي يبدأها المساعد تروح للقناة المختارة في الإعدادات.

## الذكاء الاصطناعي والتكلفة

- النموذج الافتراضي: `google/gemini-2.5-flash-lite` عبر OpenRouter (0.10$ لكل مليون توكن إدخال). الرسالة مع صورة تقريباً 2,000 توكن، يعني **أقل من سنت لكل 20 رسالة**.
- إذا قراءة الفواتير العربية ما كانت دقيقة كفاية، غيّر `OPENROUTER_MODEL` لنموذج أقوى من OpenRouter. التكلفة تظل سنتات بحجم العرض.
- بدون مفتاح: قواعد نصية تفهم «خلصت/باقي/ما يسخن/فاتورة» وتطابق الأسماء العامية، وتسأل سؤال توضيحي إذا ما فهمت. الصور بدون تعليق تحتاج المفتاح.

## الاختبارات

```bash
cd backend
DATABASE_URL=postgresql+psycopg://salon:salon@localhost:5432/salon pytest -q
```

تغطي السيناريوهات الخمسة، مراجعة قائمة النظافة، السؤال التوضيحي، تعديلات صاحبة الصالون على الطلبية، مسار الذكاء الاصطناعي (برد وهمي)، الرجوع للقواعد إذا فشل النموذج، وربط تيليجرام.

## خارج النطاق (تطوير لاحق)

الرسايل الصوتية، الشكاوي، الطلب من مواقع إلكترونية، اقتراح الحد الأدنى من معدل الاستهلاك، تعدد الصوالين والاشتراكات.

</div>

---

## English summary

**Salon Ops Assistant** is a demo operations system for small shops, using a beauty salon as the example. Staff keep messaging a chat assistant the way they already message each other; the assistant turns those messages into structured operations and a manager dashboard.

- **Stock shortages → supplier orders:** "the brown dye ran out" updates stock; anything below its minimum joins tonight's order, the owner approves one 8 PM summary, and the order goes to the supplier's rep with follow-ups.
- **Cleaning checklist with photo proof:** a daily list closed by photos, a review reminder, then escalation to the owner.
- **Device issues, staff attendance, invoices, and a single morning report.**
- **Channels:** an in-dashboard chat simulator (used for this demo), Telegram, and WhatsApp Cloud API (code ready, not enabled).
- **Understanding messages:** Arabic rule-based parsing works with no API key; an optional vision model via OpenRouter reads photos and invoices.

**Stack:** Python, FastAPI, APScheduler, SQLAlchemy, PostgreSQL, Next.js (Arabic RTL), Docker Compose. 20 end-to-end tests.

```bash
cp .env.example .env
docker compose up --build   # dashboard: http://localhost:3000
```
