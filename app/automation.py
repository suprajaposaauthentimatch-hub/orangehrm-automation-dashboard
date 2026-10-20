"""Selenium workflow for the public OrangeHRM demo site."""
import csv
import logging
from datetime import datetime
from typing import Any
from urllib.parse import urljoin

from openpyxl import Workbook
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .config import settings
from .schemas import AutomationInput

log = logging.getLogger(__name__)

def _first_visible(wait: WebDriverWait, locators: list[tuple[str, str]]):
    """Wait for and return the first visible element among resilient alternatives."""
    last_error = None
    for locator in locators:
        try:
            return wait.until(EC.visibility_of_element_located(locator))
        except TimeoutException as exc:
            last_error = exc
    raise TimeoutException(f"None of the candidate elements became visible: {locators}") from last_error

def _click_first(wait: WebDriverWait, locators: list[tuple[str, str]]) -> None:
    last_error = None
    for locator in locators:
        try:
            wait.until(EC.element_to_be_clickable(locator)).click()
            return
        except TimeoutException as exc:
            last_error = exc
    raise TimeoutException(f"None of the candidate controls became clickable: {locators}") from last_error

def _save_exports(rows: list[dict[str, str]], stamp: str) -> tuple[str, str]:
    csv_path = settings.artifacts_dir / f"employees_{stamp}.csv"
    xlsx_path = settings.artifacts_dir / f"employees_{stamp}.xlsx"
    columns = ["employee_id", "first_name", "middle_name", "last_name"]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    book = Workbook()
    sheet = book.active
    sheet.title = "Employees"
    sheet.append(columns)
    for row in rows:
        sheet.append([row.get(col, "") for col in columns])
    book.save(xlsx_path)
    return str(csv_path), str(xlsx_path)

def _read_employee_rows(driver: webdriver.Chrome, wait: WebDriverWait) -> list[dict[str, str]]:
    # OrangeHRM 5.x renders header cells with .oxd-table-header-cell (not
    # .oxd-table-cell). Keep the older selector as a fallback for prior versions.
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".oxd-table-body")))
    header_elements = wait.until(EC.presence_of_all_elements_located(
        (By.CSS_SELECTOR, ".oxd-table-header-cell")
    ))
    if not header_elements:
        header_elements = wait.until(EC.presence_of_all_elements_located(
            (By.CSS_SELECTOR, ".oxd-table-header .oxd-table-cell")
        ))
    headers = [e.text.strip().lower() for e in header_elements]
    result: list[dict[str, str]] = []
    wait.until(EC.any_of(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".oxd-table-body .oxd-table-card")),
        EC.presence_of_element_located((By.XPATH, "//*[contains(normalize-space(), 'No Records Found')]")),
    ))
    for row in driver.find_elements(By.CSS_SELECTOR, ".oxd-table-body .oxd-table-card"):
        cells = [c.text.strip() for c in row.find_elements(By.CSS_SELECTOR, ".oxd-table-cell")]
        if not cells:
            continue
        mapped = {headers[i]: cells[i] for i in range(min(len(headers), len(cells)))}
        result.append({
            "employee_id": mapped.get("id", ""),
            "first_name": mapped.get("first (& middle) name", mapped.get("first name", "")),
            "middle_name": "",
            "last_name": mapped.get("last name", ""),
        })
    return result

def run_automation(data: AutomationInput) -> dict[str, Any]:
    """Run one browser session. User-provided credentials are never written to logs."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    before_path = settings.artifacts_dir / f"orangehrm_before_{stamp}.png"
    after_path = settings.artifacts_dir / f"orangehrm_after_{stamp}.png"
    driver = None
    logged_in = False
    steps: list[str] = []
    employees: list[dict[str, str]] = []
    inserted = {"employee_id": data.employee_id, "first_name": data.first_name, "last_name": data.last_name}
    status, message = "failure", "Automation did not complete."
    try:
        log.info("Starting Chrome WebDriver (headless=%s)", settings.headless)
        options = webdriver.ChromeOptions()
        if settings.headless:
            options.add_argument("--headless=new")
        options.add_argument("--window-size=1440,1000")
        options.add_argument("--disable-notifications")
        driver = webdriver.Chrome(options=options)  # Selenium Manager resolves the driver.
        wait = WebDriverWait(driver, settings.wait_seconds)

        steps.append("Open OrangeHRM")
        log.info("Opening OrangeHRM demo")
        driver.get(settings.orangehrm_url)
        # Wait for OrangeHRM's login form to render before saving the initial
        # site screenshot; driver.get() may return before its client UI paints.
        username_field = _first_visible(wait, [
            (By.NAME, "username"),
            (By.CSS_SELECTOR, "input[placeholder='Username']"),
        ])
        # This is an OrangeHRM browser screenshot, not a screenshot of localhost.
        driver.save_screenshot(str(before_path))
        username_field.send_keys(data.username)
        _first_visible(wait, [(By.NAME, "password"), (By.CSS_SELECTOR, "input[placeholder='Password']")]).send_keys(data.password.get_secret_value())
        _click_first(wait, [(By.CSS_SELECTOR, "button[type='submit']"), (By.XPATH, "//button[normalize-space()='Login']")])
        wait.until(EC.any_of(EC.url_contains("dashboard"), EC.visibility_of_element_located((By.CSS_SELECTOR, ".oxd-sidepanel"))))
        logged_in = True
        steps.append("Log in")
        log.info("Login completed")

        _click_first(wait, [(By.LINK_TEXT, "PIM"), (By.XPATH, "//span[normalize-space()='PIM']/ancestor::a"), (By.XPATH, "//a[contains(@href,'viewPimModule')]")])
        wait.until(EC.any_of(EC.url_contains("pim"), EC.visibility_of_element_located((By.CSS_SELECTOR, ".oxd-topbar-header"))))
        steps.append("Navigate to PIM")
        log.info("Navigated to PIM")

        _click_first(wait, [(By.XPATH, "//button[normalize-space()='Add']"), (By.XPATH, "//a[contains(@href,'saveEmployee')]")])
        _first_visible(wait, [(By.NAME, "firstName"), (By.CSS_SELECTOR, "input[placeholder='First Name']")]).send_keys(data.first_name)
        _first_visible(wait, [(By.NAME, "lastName"), (By.CSS_SELECTOR, "input[placeholder='Last Name']")]).send_keys(data.last_name)
        employee_id_label = _first_visible(wait, [
            (By.XPATH, "//label[normalize-space()='Employee Id']"),
            (By.XPATH, "//label[contains(normalize-space(), 'Employee Id')]")
        ])
        id_group = employee_id_label.find_element(By.XPATH, "./ancestor::div[contains(@class, 'oxd-input-group')]")
        id_field = id_group.find_element(By.CSS_SELECTOR, "input")
        id_field.click()
        id_field.send_keys(Keys.CONTROL, "a")
        id_field.send_keys(Keys.BACKSPACE)
        id_field.send_keys(data.employee_id)
        entered_id = id_field.get_property("value")
        if entered_id != data.employee_id:
            raise RuntimeError(f"Employee ID field value did not match after typing (actual={entered_id!r})")
        add_employee_url = driver.current_url
        _click_first(wait, [(By.XPATH, "//button[normalize-space()='Save']"), (By.CSS_SELECTOR, "button[type='submit']")])
        wait.until(EC.any_of(
            EC.visibility_of_element_located((By.CSS_SELECTOR, ".oxd-toast--success")),
            EC.url_changes(add_employee_url),
        ))
        # The Add Employee form can itself contain a "Personal Details" label,
        # so body text is not evidence that the save completed. After the success
        # response/route change, confirm the saved record exposes the requested ID.
        saved_id_field = _first_visible(wait, [
            (By.XPATH, "//label[normalize-space()='Employee Id']/following::input[1]"),
            (By.CSS_SELECTOR, "input[name='employeeId']"),
        ])
        saved_id = saved_id_field.get_attribute("value")
        if saved_id and saved_id != data.employee_id:
            raise RuntimeError(f"OrangeHRM shows employee ID {saved_id}, not the submitted ID")
        if not saved_id:
            raise RuntimeError("Could not confirm the employee ID on the saved employee page")
        steps.append("Create and verify employee")
        log.info("Employee creation verified for employee ID %s", data.employee_id)

        # The save may leave OrangeHRM on Personal Details, where an Employee
        # List link is not consistently exposed. Navigate directly to its route.
        log.info("Opening employee list after successful save")
        employee_list_url = urljoin(settings.orangehrm_url.rstrip("/") + "/", "web/index.php/pim/viewEmployeeList")
        driver.get(employee_list_url)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".oxd-table-body")))
        search_id = None
        try:
            search_id = wait.until(EC.visibility_of_element_located(
                (By.XPATH, "//label[normalize-space()='Employee Id']/following::input[1]")
            ))
            search_id.clear()
            search_id.send_keys(data.employee_id)
            _click_first(wait, [(By.XPATH, "//button[normalize-space()='Search']")])
            wait.until(lambda d: (
                data.employee_id in d.find_element(By.CSS_SELECTOR, ".oxd-table-body").text
                or "No Records Found" in d.find_element(By.CSS_SELECTOR, ".oxd-table-body").text
            ))
        except TimeoutException:
            log.info("Employee list search field was not available; extracting visible page")
        employees = _read_employee_rows(driver, wait)
        employee_verified = any(r.get("employee_id") == data.employee_id for r in employees)
        if not employee_verified:
            # Keep a useful unfiltered export even when the exact ID search finds
            # no match, and report verification as incomplete rather than success.
            log.warning("Employee ID %s was not found by exact list search; retrying unfiltered extraction", data.employee_id)
            if search_id is not None:
                old_text = driver.find_element(By.CSS_SELECTOR, ".oxd-table-body").text
                search_id.clear()
                _click_first(wait, [(By.XPATH, "//button[normalize-space()='Search']")])
                try:
                    wait.until(lambda d: d.find_element(By.CSS_SELECTOR, ".oxd-table-body").text != old_text)
                except TimeoutException:
                    log.info("Unfiltered employee list did not visibly change")
                employees = _read_employee_rows(driver, wait)
        steps.append("Extract employee list")
        csv_path, xlsx_path = _save_exports(employees, stamp)
        log.info("Exported %d visible employee rows", len(employees))

        # Profile menu labels differ slightly across OrangeHRM releases.
        _click_first(wait, [(By.CSS_SELECTOR, ".oxd-userdropdown-tab"), (By.CSS_SELECTOR, "header .oxd-userdropdown-name")])
        _click_first(wait, [(By.XPATH, "//a[normalize-space()='Logout']"), (By.XPATH, "//a[contains(@href,'logout')]")])
        wait.until(EC.visibility_of_element_located((By.NAME, "username")))
        logged_in = False
        steps.append("Log out")
        if employee_verified:
            status, message = "success", "Employee was found in the PIM list; employee data was exported and the session logged out."
        else:
            status, message = "failure", f"OrangeHRM returned a save success state, but employee ID {data.employee_id} was not found in the PIM list. Check OrangeHRM manually; the visible employee list was exported and the session logged out."
    except (TimeoutException, WebDriverException, OSError, Exception) as exc:
        # Keep the UI error useful while logs carry a traceback; credentials are excluded.
        message = f"Automation failed during {steps[-1] if steps else 'startup'}: {type(exc).__name__}: {exc}"
        log.exception("Automation failed (%s)", type(exc).__name__)
    finally:
        if driver is not None:
            if logged_in:
                try:
                    cleanup_wait = WebDriverWait(driver, min(settings.wait_seconds, 8))
                    _click_first(cleanup_wait, [(By.CSS_SELECTOR, ".oxd-userdropdown-tab"), (By.CSS_SELECTOR, "header .oxd-userdropdown-name")])
                    _click_first(cleanup_wait, [(By.XPATH, "//a[normalize-space()='Logout']"), (By.XPATH, "//a[contains(@href,'logout')]")])
                    cleanup_wait.until(EC.visibility_of_element_located((By.NAME, "username")))
                    steps.append("Log out")
                    log.info("Logged out during cleanup")
                except (TimeoutException, WebDriverException):
                    log.exception("Could not log out during cleanup")
            try:
                driver.save_screenshot(str(after_path))
            except WebDriverException:
                log.exception("Could not save post-run browser screenshot")
            try:
                driver.quit()
            except WebDriverException:
                log.exception("Could not close browser cleanly")
    result = {
        "status": status, "message": message, "steps": steps, "inserted": inserted,
        "employees": employees[:100], "screenshot_before": str(before_path),
        "screenshot_after": str(after_path),
        "csv_path": locals().get("csv_path"), "xlsx_path": locals().get("xlsx_path"),
    }
    return result
