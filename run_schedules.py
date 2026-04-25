import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from app.jobs import run_due_schedules


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent
    data_dir = Path(os.getenv("APP_DATA_DIR") or str(base_dir)).resolve()
    output_dir = data_dir / "output" / "reports"
    result = run_due_schedules(output_dir=output_dir)
    print(result)
