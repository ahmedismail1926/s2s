"""Single place for all settings of the S2S demo."""
from pathlib import Path

ROOT = Path(__file__).parent
AUDIO_DIR = ROOT / "audio"
OUT_DIR = ROOT / "out"
KB_PATH = ROOT / "kb.json"

SEED = 0
MODELS = ["gemini-3.8-live", "gemini-3.1-flash-live-preview"]
TTS_MODEL = "gemini-3.8-flash-tts"
TTS_VOICE = "Kore"
IN_RATE = 16000
OUT_RATE = 24000
CHUNK_MS = 30
SILENCE_MS = 300
PASSES = 3
GAP_S = 5.0
MAX_RETRIES = 3
BACKOFF_S = 5.0
TURN_TIMEOUT_S = 40.0
TOP_K = 3
VAD_SILENCE_MS: int | None = 200  # None = server default; set by bench.py --vad-ms
RAW_NAME = "raw.jsonl"


def vad_label() -> str:
    """Describe the VAD setting in use."""
    return "server default automatic VAD" if VAD_SILENCE_MS is None else f"automatic VAD, silence_duration_ms={VAD_SILENCE_MS}, other settings default"
EXCLUDE_MATCHED = {"q11", "q12"}

PRICE_PER_M = {"audio_in": 3.00, "audio_out": 12.00, "text_in": 0.75, "text_out": 4.50}
CLAIMED = {"ttfa_p50": 1.77, "ttfa_p95": 2.49, "total_p50": 2.50, "success": "14/14", "cost_min": 0.0164}

SYSTEM_PROMPT = (
    "انت موظف خدمة عملاء مصري. جاوب بس من نتايج الأداة search_kb. "
    "لازم تنادي search_kb لكل سؤال. خلّي الرد قصير ومناسب للكلام (جملة أو جملتين). "
    "لو ملقيتش إجابة في النتايج قول إنك مالقيتش المعلومة دي."
)

QUESTIONS = [
    "ما هي مواعيد العمل عندكم؟",
    "إزاي أقدر أعمل حساب جديد؟",
    "نسيت كلمة السر، أعمل إيه؟",
    "كام سعر الاشتراك الشهري؟",
    "إزاي ألغي الاشتراك بتاعي؟",
    "بتقبلوا الدفع بالفيزا؟",
    "الشحن بياخد قد إيه؟",
    "أقدر أرجّع المنتج بعد الاستلام؟",
    "رقم خدمة العملاء كام؟",
    "فين أقرب فرع ليكم؟",
    "إزاي أتابع حالة طلبي؟",
    "هل في خصم للطلبة؟",
    "إزاي أغيّر عنواني؟",
    "في ضمان على المنتجات؟",
]
