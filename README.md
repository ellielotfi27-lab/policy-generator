# Policy PDF Builder

همون منطق نوت‌بوک (Jinja2 + Playwright) تبدیل شده به یک سرویس وب با (FastAPI)، به‌علاوه‌ی یک صفحه‌ی ساده برای آپلود JSON و دانلود PDF.

## فایل‌ها
- `main.py` — سرور (FastAPI) + همون فیلتر `format_price` و همون تنظیمات (PDF) که تو نوت‌بوک بود
- `templates/policy_template.html` و `templates/index.css` — عیناً از نوت‌بوک کپی شده، دست‌نخورده
- `sample_data.json` — همون نمونه (JSON) نوت‌بوک، برای تست
- `Dockerfile` — از ایمیج رسمی (Playwright) استفاده می‌کنه که (Chromium) از قبل توش نصبه

## مرحله ۱: تست محلی (اختیاری)
```bash
pip install -r requirements.txt
playwright install chromium
uvicorn main:app --reload
```
بعد آدرس `http://localhost:8000` رو تو مرورگر باز کن.

## مرحله ۲: پوش کردن به (GitHub)
یک ریپوی جدید بساز و کل پوشه‌ی `policy-pdf-service` رو توش پوش کن:
```bash
cd policy-pdf-service
git init
git add .
git commit -m "policy pdf service"
git branch -M main
git remote add origin <آدرس ریپوی خودت>
git push -u origin main
```

## مرحله ۳: دیپلوی روی (Render)
1. وارد render.com شو و با اکانت (GitHub) لاگین کن
2. دکمه‌ی **New +** → **Web Service** رو بزن
3. ریپوی همین پروژه رو انتخاب کن
4. تنظیمات:
   - **Runtime**: Docker (خودش از روی `Dockerfile` تشخیص می‌ده)
   - **Instance Type**: Free
5. **Create Web Service** رو بزن و صبر کن بیلد تموم بشه (چند دقیقه طول می‌کشه چون Chromium سنگینه)

بعد از بیلد، یک آدرس عمومی مثل `https://your-app.onrender.com` می‌گیری. همونو به بقیه بده.

## نکته
- سرویس (Free) روی (Render) بعد از ۱۵ دقیقه بی‌استفاده موندن می‌خوابه؛ درخواست بعدی ۳۰ تا ۵۰ ثانیه طول می‌کشه تا بیدار بشه. برای دمو مشکلی نیست.
