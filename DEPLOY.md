# خطواتك أنت (تحتاج حساباتك)

الكود كامل ومجرّب. هذي الخطوات تحتاج حساباتك، وكل وحدة مستقلة: تقدر تعرض المشروع على جهازك بعد الخطوة 2 بس.

## 1. شغّله على جهازك (5 دقايق)

1. افتح Docker Desktop.
2. في Terminal:
   ```bash
   cd ~/Downloads/salon-ops-assistant
   cp .env.example .env
   docker compose up --build
   ```
3. افتح http://localhost:3000 وجرّب المحاكي.

## 2. مفتاح OpenRouter (عشان يقرأ الصور والفواتير)

1. من https://openrouter.ai/keys أنشئ مفتاح جديد باسم `salon-ops`. يفضل تحط له حد صرف بسيط (مثلاً 2$).
2. حطه في `.env`:
   ```
   OPENROUTER_API_KEY=sk-or-...
   ```
3. `docker compose up -d --build backend`
4. في الإعدادات بيظهر «نموذج google/gemini-2.5-flash-lite». جرّب في المحاكي: سارة ← صورة «فاتورة لمسة» بدون كتابة.

## 3. بوت تيليجرام (للعرض المباشر على الجوالات)

1. في تيليجرام افتح **@BotFather** ← `/newbot`
   - الاسم: `مساعد صالون رونق`
   - المعرّف: مثل `RawnaqSalonOpsBot` (لازم ينتهي بـ bot)
2. انسخ التوكن وحطه في `.env`:
   ```
   TELEGRAM_BOT_TOKEN=123456:ABC...
   ```
3. `docker compose up -d --build backend`
4. في اللوحة: **الإعدادات ← قناة الرسائل ← تيليجرام**.
5. تحت «الفريق» اضغط **رابط الدعوة** لأي شخص، وامسح الـ QR من جوالك واضغط Start.
   - جوال واحد يقدر يجرب أكثر من دور: امسح كود شخص ثاني ويتحول الربط له.
6. اختياري من BotFather: `/setuserpic` (صورة للبوت) و`/setdescription`.

> تيليجرام يشتغل بطريقة polling: البوت يسحب الرسايل بنفسه، فما يحتاج رابط عام ولا ngrok، ويشتغل من اللابتوب في أي مكان.

## 4. النشر: الخلفية على Azure

1. **تأكد من الحساب:** في https://portal.azure.com ← Cost Management ← Credits. الـ VM المجاني (B1s أو B2ats v2، 750 ساعة شهرياً) لمدة 12 شهر للعملاء الجدد، بس لازم تحوّل الحساب لـ Pay-as-you-go خلال 30 يوم عشان تستمر الخدمات المجانية.
2. **أنشئ VM:**
   - Image: Ubuntu Server 24.04 LTS
   - Size: `Standard_B2ats_v2` (أو `B1s`) — تأكد إنه مكتوب عليه *Free services eligible*
   - Authentication: SSH key
   - Inbound ports: SSH (22) و HTTP (80) و HTTPS (443)
   - بعد الإنشاء: Public IP ← خلّه **Static** عشان ما يتغير
3. **ثبّت Docker على السيرفر:**
   ```bash
   ssh azureuser@<IP>
   curl -fsSL https://get.docker.com | sudo sh
   sudo usermod -aG docker $USER && exit
   ```
4. **ارفع المشروع** (من جهازك):
   ```bash
   cd ~/Downloads
   rsync -av --exclude node_modules --exclude .next salon-ops-assistant azureuser@<IP>:~/
   ```
   أو ارفعه على GitHub واعمل `git clone` في السيرفر.
5. **جهّز `.env` على السيرفر:**
   ```bash
   cd ~/salon-ops-assistant && cp .env.example .env && nano .env
   ```
   ```
   API_DOMAIN=<IP>.sslip.io          # مثال: 20.74.12.5.sslip.io — يعطيك HTTPS بدون شراء دومين
   POSTGRES_PASSWORD=<كلمة سر قوية>
   PUBLIC_BASE_URL=https://<IP>.sslip.io
   CORS_ORIGINS=https://<اسم-مشروعك>.vercel.app
   OPENROUTER_API_KEY=...
   TELEGRAM_BOT_TOKEN=...
   ```
   > لا تشغّل البوت على جهازك والسيرفر بنفس الوقت: تيليجرام يعطي الرسايل لواحد بس.
6. **شغّل:**
   ```bash
   docker compose -f docker-compose.prod.yml up -d --build
   curl https://<IP>.sslip.io/health
   ```

## 5. النشر: اللوحة على Vercel

1. ارفع المشروع على GitHub (مستودع جديد، مثلاً `salon-ops-assistant`).
2. في https://vercel.com ← Add New Project ← اختر المستودع.
3. **Root Directory:** `frontend`
4. **Environment Variables:**
   ```
   NEXT_PUBLIC_API_URL=https://<IP>.sslip.io
   ```
5. Deploy. بعدها حدّث `CORS_ORIGINS` في `.env` السيرفر برابط Vercel الفعلي، و:
   ```bash
   docker compose -f docker-compose.prod.yml up -d backend
   ```

> **تنبيه أمان:** اللوحة المنشورة مفتوحة لأي أحد عنده الرابط. هذا مقبول لبيانات عرض وهمية. مع عميل حقيقي نضيف تسجيل دخول.

## 6. الواتساب (لاحقاً مع عميل حقيقي)

الكود جاهز. اللي تحتاجه وقتها:
1. تطبيق في https://developers.facebook.com بمنتج WhatsApp، ورقم (تجريبي أو رقم العميل).
2. في `.env`: `WHATSAPP_TOKEN`، `WHATSAPP_PHONE_NUMBER_ID`، `WHATSAPP_APP_SECRET`.
3. Webhook URL: `https://<الدومين>/webhook/whatsapp`، و Verify token = `WHATSAPP_VERIFY_TOKEN`، واشترك في `messages`.
4. قالب Utility باسم `salon_update` بلغة العربية، نصه متغير واحد: `{{1}}` — يُستخدم للرسايل اللي يبدأها النظام بعد ما تقفل نافذة الـ24 ساعة.
5. وسيلة دفع في Meta Business: من 1 أكتوبر 2026 كل رسالة خدمة تنحسب.

---

# سيناريو العرض: «يوم في صالون» (فيديو دقيقة)

صوّر الشاشة من المحاكي واللوحة جنب بعض:

1. **(0:00)** الرئيسية: «هذا يوم الصالون: مهام النظافة بصورها، والنواقص، وطلبية الليلة».
2. **(0:10)** المحاكي ← سارة: «خلصت الصبغة البنية». المساعد يرد، وطلبية الليلة تتحدث.
3. **(0:20)** سارة: «الاستشوار خربان» ← يسأل «أي واحد؟» ← «الثالث» ← تنبيه لصاحبة الصالون.
4. **(0:30)** مريم ترسل صورة بعد التعقيم ← المهمة تنقفل والصورة تطلع في الخط الزمني.
5. **(0:38)** «ملخص الثامنة الآن» ← منيرة: «الصبغة البنية 8» ثم «موافقة» ← المندوب أبو فهد يستلم الطلب.
6. **(0:50)** سارة ترسل صورة الفاتورة ← المصروف ينسجل والمخزون يرتفع.
7. **(0:57)** «تقرير الصباح الآن» ← رسالة وحدة فيها كل شي.

**مع صديقك صاحب الصالون (مباشر):** شغّل قناة تيليجرام، خله يمسح QR «صاحبة الصالون» من جواله، وأنت من جوالك «سارة». بعد «ملخص الثامنة الآن» الملخص يوصل على جواله ويرد «موافقة» بنفسه.
