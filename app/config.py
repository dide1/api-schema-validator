import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

REPO_PATH = Path(os.getenv("REPO_PATH", ".")).resolve()
SCHEMAS_DIR = Path(os.getenv("SCHEMAS_DIR", "./schemas"))
