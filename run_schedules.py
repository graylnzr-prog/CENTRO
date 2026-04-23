from pathlib import Path

from app.jobs import run_due_schedules


if __name__ == "__main__":
    output_dir = Path(__file__).resolve().parent / "output" / "reports"
    result = run_due_schedules(output_dir=output_dir)
    print(result)
