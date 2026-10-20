# OrangeHRM Dashboard-Driven Automation

A FastAPI dashboard triggers a Python Selenium workflow against the OrangeHRM public demo. The user enters credentials and employee details; the application logs in, opens PIM, creates and verifies the employee, extracts the employee list, exports the visible rows, and logs out.

## Assignment coverage

- HTML/CSS dashboard fields for username, password, first name, last name, and employee ID.
- Dashboard submit action starts the Selenium workflow.
- OrangeHRM login, PIM navigation, employee creation, saved-ID verification, employee-list extraction, and logout.
- Dashboard result displays success/failure, submitted employee details, completed steps, and extracted employee rows when available.
- Explicit waits, selector fallbacks, exception handling, and step logs.
- Credentials are entered per run, masked in the input model, excluded from log messages, and not stored in `.env`.
- CSV and Excel exports are written to `artifacts/`.
- Separate screenshots are saved for the FastAPI dashboard and the OrangeHRM browser.

## Windows setup and run in VS Code using CMD

### 1. Install prerequisites

Install Python 3.10 or newer, Google Chrome, VS Code, and the Microsoft Python extension. Keep internet access available on the first Selenium run so Selenium Manager can resolve a compatible ChromeDriver.

### 2. Extract and open the project

Extract `orangehrm_dashboard.zip`. In VS Code, choose **File → Open Folder** and open the extracted `orangehrm_dashboard` folder (the folder containing `requirements.txt` and `app`).

### 3. Open Command Prompt in VS Code

Choose **Terminal → New Terminal**. If the terminal is PowerShell, use the dropdown beside the plus sign and select **Command Prompt**.

If the terminal is not already in the project folder, change to it (replace the example path with the folder you extracted):

```cmd
cd /d "C:\path\to\orangehrm_dashboard"
```

### 4. Create the environment and install dependencies

Run these commands in the CMD terminal:

```cmd
py -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if not exist .env copy .env.example .env
```

The prompt should begin with `(.venv)`. In VS Code, press **Ctrl+Shift+P**, choose **Python: Select Interpreter**, and select `.venv\Scripts\python.exe`.

### 5. Start the dashboard

```cmd
uvicorn app.main:app --reload
```

Keep the terminal open. Visit <http://127.0.0.1:8000> in Chrome.

### 6. Run the assignment

Enter credentials accepted by the configured OrangeHRM demo, plus a first name, last name, and unused employee ID. The assignment lists `Admin` / `admin123` as demo defaults; use them only if they still work for the current demo. Click **Run automation** once and keep the page open.

The dashboard reports the result after Selenium finishes. A success result means the entered ID was verified in the PIM employee list, the visible employee rows were exported, and logout completed. If the public demo fails or has changed, review the dashboard error and VS Code terminal logs.

To stop the server, focus the CMD terminal and press **Ctrl+C**. To start it again, activate the environment and run Uvicorn:

```cmd
.venv\Scripts\activate.bat
uvicorn app.main:app --reload
```

### 7. Check the generated files

Open the project’s `artifacts` folder in VS Code Explorer or File Explorer. Each run writes timestamped files:

- `dashboard_before_*.png`: the dashboard form immediately before the automation starts. The password is not filled into this screenshot.
- `dashboard_after_*.png`: the dashboard result page showing the run status and extracted employee data.
- `orangehrm_before_*.png`: OrangeHRM login page before login.
- `orangehrm_after_*.png`: OrangeHRM page after logout.
- `employees_*.csv` and `employees_*.xlsx`: exported employee rows.

Older files created before the dashboard screenshot fix may be blank or may show the OrangeHRM page even if their filename starts with `dashboard_`. Use the newly timestamped files from a run after installing this version.

The screenshots may contain the username and employee details. The password is not included, but review images before sharing them.

## Optional: run the unit tests

In CMD, with the project folder open and `.venv` active:

```cmd
pip install pytest
python -m pytest
```

These tests check form validation and password masking. They do not launch Chrome or test the live OrangeHRM site.

## Project files

| File | Purpose |
| --- | --- |
| `app/main.py` | FastAPI routes, HTML form handling, and automated before/after dashboard screenshots. A temporary internal capture route renders the dashboard for the screenshot browser. |
| `app/config.py` | Reads non-secret settings from `.env`, applies defaults, and creates the artifacts directory. |
| `app/schemas.py` | Validates input and wraps the password as Pydantic `SecretStr`. |
| `app/automation.py` | Selenium lifecycle, OrangeHRM selectors and waits, save verification, list extraction, CSV/Excel export, OrangeHRM browser screenshots, logging, and cleanup/logout. |
| `app/templates/index.html` | Dashboard form and result/status/employee-table display. |
| `app/static/styles.css` | Responsive dashboard styling. |
| `tests/test_schemas.py` | Unit tests for required values and password masking. |
| `.env.example` | Safe configuration defaults; contains no login credentials. |
| `requirements.txt` | Python package dependencies. |
| `artifacts/` | Runtime screenshots and employee exports. |

## Workflow and selector assumptions

The automation targets the current OrangeHRM open-source demo interface. It uses stable field names, visible labels, button text, and OrangeHRM `oxd-*` classes, with fallback selectors where practical. OrangeHRM can change its page layout, credentials, or demo data; a selector timeout is reported in the dashboard and terminal logs.

Employee creation is verified by waiting for an OrangeHRM success response or route change, then checking the saved employee ID on the employee page. The automation then searches/extracts the employee list. The export covers the rows visible on the current result page (up to that page’s limit); it does not traverse every pagination page.

The public demo is shared and can reset its database. A record that was successfully created and verified during a run may not remain available later. Keep the run’s screenshots and CSV/Excel exports as evidence.

## Troubleshooting

- **Chrome does not start:** Update Chrome and confirm it opens. Selenium Manager needs network access on its first driver setup.
- **Login fails:** Check the credentials and that the public demo is available.
- **Employee ID already exists:** Check PIM first and choose another unused ID.
- **A selector times out:** The public demo may have changed. Use the terminal traceback to identify the affected step and adjust the fallback locator in `app/automation.py`.
- **Export has only headers or no row:** Check the dashboard status and PIM list. The site may have reset, returned no matching row, or changed its list flow.
- **The browser tab icon returns 404:** A missing `favicon.ico` is cosmetic and does not affect the workflow.
- **The page takes time to return:** Selenium runs synchronously for the form request. Keep the dashboard tab open until the result appears.

