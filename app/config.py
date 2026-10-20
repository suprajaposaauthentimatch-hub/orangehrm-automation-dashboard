from pathlib import Path
import os

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")

class Settings:
    orangehrm_url: str = os.getenv("ORANGEHRM_URL", "https://opensource-demo.orangehrmlive.com/")
    headless: bool = os.getenv("HEADLESS", "false").lower() == "true"
    wait_seconds: int = int(os.getenv("WAIT_SECONDS", "20"))
    artifacts_dir: Path = Path(os.getenv("ARTIFACTS_DIR", str(ROOT_DIR / "artifacts"))).resolve()

settings = Settings()
settings.artifacts_dir.mkdir(parents=True, exist_ok=True)
