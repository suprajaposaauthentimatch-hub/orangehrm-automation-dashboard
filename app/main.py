import logging
from pathlib import Path
from datetime import datetime
from uuid import uuid4

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait

from .automation import run_automation
from .config import settings
from .schemas import AutomationInput

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
app = FastAPI(title="OrangeHRM Dashboard Automation", version="1.0.0")
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
capture_views: dict[str, dict] = {}

def _capture_dashboard(url: str, destination: Path) -> None:
    """Render a dashboard snapshot page in headless Chrome and save the full page."""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1440,1200")
    browser = webdriver.Chrome(options=options)
    try:
        browser.get(url)
        WebDriverWait(browser, 15).until(
            lambda current: current.execute_script("return document.readyState") == "complete"
        )
        WebDriverWait(browser, 10).until(
            lambda current: current.find_elements("css selector", ".form-grid")
        )
        browser.set_script_timeout(5)
        browser.execute_async_script(
            "Promise.race([document.fonts.ready, new Promise(resolve => setTimeout(resolve, 1500))])"
            ".then(() => arguments[0]())"
        )
        page_height = browser.execute_script(
            "return Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)"
        )
        browser.set_window_size(1440, min(max(int(page_height), 1000), 2400))
        browser.save_screenshot(str(destination))
    finally:
        browser.quit()

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(request, "index.html", {"result": None, "form": {}})

@app.get("/_capture/{snapshot_id}", response_class=HTMLResponse, name="capture_snapshot")
async def capture_snapshot(request: Request, snapshot_id: str):
    view = capture_views.get(snapshot_id)
    if view is None:
        return HTMLResponse("Snapshot not found", status_code=404)
    return templates.TemplateResponse(request, "index.html", view)

@app.post("/run", response_class=HTMLResponse)
def start_automation(request: Request,
                     username: str = Form(...), password: str = Form(...),
                     first_name: str = Form(...), last_name: str = Form(...),
                     employee_id: str = Form(...)):
    form = {"username": username, "first_name": first_name, "last_name": last_name, "employee_id": employee_id}
    snapshot_id = uuid4().hex
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    before_path = settings.artifacts_dir / f"dashboard_before_{stamp}.png"
    after_path = settings.artifacts_dir / f"dashboard_after_{stamp}.png"
    capture_views[snapshot_id] = {"result": None, "form": form}
    capture_url = str(request.url_for("capture_snapshot", snapshot_id=snapshot_id))
    try:
        _capture_dashboard(capture_url, before_path)
        logging.getLogger(__name__).info("Saved dashboard before-run screenshot: %s", before_path.name)
    except Exception:
        logging.getLogger(__name__).exception("Could not capture dashboard before-run screenshot")
    try:
        payload = AutomationInput(username=username, password=password, first_name=first_name,
                                  last_name=last_name, employee_id=employee_id)
        result = run_automation(payload)
    except Exception as exc:
        logging.getLogger(__name__).exception("Request validation or workflow error")
        result = {"status": "failure", "message": f"Could not start automation: {type(exc).__name__}: {exc}",
                  "steps": [], "inserted": {"employee_id": employee_id, "first_name": first_name, "last_name": last_name},
                  "employees": [], "screenshot_before": None, "screenshot_after": None,
                  "csv_path": None, "xlsx_path": None}
    capture_views[snapshot_id] = {"result": result, "form": form}
    try:
        _capture_dashboard(capture_url, after_path)
        logging.getLogger(__name__).info("Saved dashboard after-run screenshot: %s", after_path.name)
        result["dashboard_screenshot_before"] = str(before_path) if before_path.exists() else None
        result["dashboard_screenshot_after"] = str(after_path)
    except Exception:
        logging.getLogger(__name__).exception("Could not capture dashboard after-run screenshot")
        result["dashboard_screenshot_before"] = str(before_path) if before_path.exists() else None
        result["dashboard_screenshot_after"] = None
    finally:
        capture_views.pop(snapshot_id, None)
    return templates.TemplateResponse(request, "index.html", {"result": result, "form": form})
