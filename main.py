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
  body { font-family: sans-serif; max-width: 460px; margin: 70px auto; text-align: center; color:#222; }
  h2 { margin-bottom: 24px; }
  input[type=file] { margin-bottom: 16px; }
  button {
    padding: 10px 28px; font-size: 15px; cursor: pointer;
    background:#003575; color:#fff; border:none; border-radius:8px;
  }
  button:disabled { opacity:0.6; cursor:default; }
  #status { margin-top: 18px; color:#555; min-height: 20px; }
  .spinner {
    display:inline-block; width:14px; height:14px; margin-left:8px;
    border:2px solid #ccc; border-top-color:#003575; border-radius:50%;
    animation: spin 0.8s linear infinite; vertical-align:middle;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>
</head>
<body>
  <h2>ساخت PDF گواهی بیمه‌نامه</h2>
  <input type="file" id="jsonFile" accept="application/json"><br>
  <button id="genBtn">Generate PDF</button>
  <div id="status"></div>

<script>
const btn = document.getElementById('genBtn');
const statusEl = document.getElementById('status');

btn.addEventListener('click', async () => {
  const fileInput = document.getElementById('jsonFile');
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
