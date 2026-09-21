"""
Central place for model IDs, paths, and other constants.

Swapping a model for the explainer, judge, or cost-comparison run should
only ever require editing this file.

Model IDs current as of Sept 2026 — verify at https://console.groq.com/docs/models
before the demo in case Groq's catalog changed (preview models especially
can be deprecated with little notice).
"""

from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


EXPLAINER_MODEL = "openai/gpt-oss-120b"


JUDGE_MODEL = "openai/gpt-oss-120b"

# A cheap/fast model, used only for the "cost at 100x" comparison in the report.
CHEAP_MODEL = "openai/gpt-oss-20b"

MAX_TOKENS_EXPLAINER = 800
MAX_TOKENS_JUDGE = 600

# --- Paths --------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
PROMPTS_DIR = ROOT / "prompts"
RESULTS_DIR = ROOT / "results"

GOLDEN_SET_PATH = DATA_DIR / "golden_set.jsonl"
CALIBRATION_SET_PATH = DATA_DIR / "calibration_set.jsonl"
