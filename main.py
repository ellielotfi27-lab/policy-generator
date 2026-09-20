import io
import json
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from jinja2 import Environment, FileSystemLoader
from playwright.async_api import async_playwright

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"

# ---- Same filters as the notebook ----
PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"


def to_persian_digits(text: str) -> str:
    return "".join(PERSIAN_DIGITS[int(ch)] if ch.isdigit() else ch for ch in text)


def format_price(value):
    if value is None:
        return "-"
    formatted = f"{value:,}"
    return to_persian_digits(formatted) + " ریال"


env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
env.filters["format_price"] = format_price
template = env.get_template("policy_template.html")

app = FastAPI()

UPLOAD_PAGE = """<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="initial-scale=1, width=device-width">
<title>Policy PDF Builder</title>
<style>
  * { box-sizing: border-box; }
  body {
    font-family: 'Vazirmatn', Tahoma, sans-serif;
    background: #f3f5f9;
    margin: 0;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
  }
  .page-title {
    text-align: center;
    color: #2952e3;
    font-size: 30px;
    font-weight: 800;
    margin-bottom: 6px;
  }
  .page-subtitle {
    text-align: center;
    color: #6b7280;
    font-size: 14px;
    margin-bottom: 32px;
  }
  .card {
    background: #fff;
    width: 440px;
    max-width: 100%;
    border-radius: 16px;
    box-shadow: 0 10px 30px rgba(20, 30, 60, 0.08);
    padding: 24px;
  }
  .upload-box {
    background: #eef2fb;
    border-radius: 12px;
    padding: 36px 20px;
    text-align: center;
  }
  .upload-icon { font-size: 34px; margin-bottom: 10px; }
  .upload-label {
    font-size: 14px;
    color: #33415c;
    font-weight: 600;
    margin-bottom: 16px;
  }
  .file-name {
    font-size: 12px;
    color: #6b7280;
    margin-top: 10px;
    min-height: 16px;
  }
  input[type=file] { display: none; }
  .upload-btn, .generate-btn {
    display: inline-block;
    background: #2952e3;
    color: #fff;
    font-size: 14px;
    font-weight: 600;
    border: none;
    border-radius: 10px;
    padding: 10px 22px;
    cursor: pointer;
  }
  .generate-btn {
    width: 100%;
    margin-top: 20px;
    padding: 12px;
  }
  .generate-btn:disabled { opacity: 0.55; cursor: default; }
  #status {
    margin-top: 14px;
    text-align: center;
    font-size: 13px;
    color: #6b7280;
    min-height: 18px;
  }
  .spinner {
    display: inline-block; width: 13px; height: 13px; margin-left: 6px;
    border: 2px solid #cbd3e6; border-top-color: #2952e3; border-radius: 50%;
    animation: spin 0.8s linear infinite; vertical-align: middle;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>
</head>
<body>
<div>
  <div class="page-title">Policy PDF Builder</div>
  <div class="page-subtitle">فایل JSON را انتخاب کن و PDF گواهی بیمه‌نامه را بساز</div>

  <div class="card">
    <div class="upload-box">
      <div class="upload-icon">📄</div>
      <div class="upload-label">فایل JSON خود را انتخاب کن</div>
      <label class="upload-btn" for="jsonFile">Upload JSON File</label>
      <input type="file" id="jsonFile" accept="application/json">
      <div class="file-name" id="fileName"></div>
    </div>
    <button class="generate-btn" id="genBtn">Generate PDF</button>
    <div id="status"></div>
  </div>
</div>

<script>
const fileInput = document.getElementById('jsonFile');
const fileNameEl = document.getElementById('fileName');
const btn = document.getElementById('genBtn');
const statusEl = document.getElementById('status');

fileInput.addEventListener('change', () => {
  fileNameEl.textContent = fileInput.files.length ? fileInput.files[0].name : '';
});

btn.addEventListener('click', async () => {
  if (!fileInput.files.length) {
    statusEl.textContent = 'اول یک فایل JSON انتخاب کن';
    return;
  }

  btn.disabled = true;
  statusEl.innerHTML = 'در حال ساخت PDF <span class="spinner"></span>';

  const formData = new FormData();
  formData.append('file', fileInput.files[0]);

  try {
    const res = await fetch('/generate-pdf', { method: 'POST', body: formData });
    if (!res.ok) {
      const errText = await res.text();
      throw new Error(errText || ('HTTP ' + res.status));
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'policy.pdf';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    statusEl.textContent = 'آماده شد، دانلود شروع شد ✅';
  } catch (e) {
    statusEl.textContent = 'خطا: ' + e.message;
  } finally {
    btn.disabled = false;
  }
});
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def index():
    return UPLOAD_PAGE


@app.post("/generate-pdf")
async def generate_pdf(file: UploadFile = File(...)):
    raw = await file.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="فایل JSON معتبر نیست")

    try:
        html_out = template.render(**data)
    except Exception as exc:  # keeps the field names/structure errors visible
        raise HTTPException(status_code=400, detail=f"خطا در رندر قالب: {exc}")

    # Write the rendered HTML next to index.css so the relative
    # stylesheet link (./index.css) resolves exactly like in the notebook.
    with tempfile.NamedTemporaryFile(
        dir=TEMPLATES_DIR, suffix=".html", delete=False
    ) as tmp:
        tmp.write(html_out.encode("utf-8"))
        tmp_path = Path(tmp.name)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.goto(f"file://{tmp_path.resolve()}")
            await page.wait_for_timeout(800)  # let fonts/images load
            pdf_bytes = await page.pdf(
                width="595px",
                height="842px",
                print_background=True,
                margin={"top": "0px", "bottom": "0px", "left": "0px", "right": "0px"},
            )
            await browser.close()
    finally:
        tmp_path.unlink(missing_ok=True)

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=policy.pdf"},
    )
