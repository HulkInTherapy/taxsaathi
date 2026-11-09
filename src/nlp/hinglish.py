"""
Hinglish detection and normalisation.

Many users type Hindi words in Latin letters ("mujhe kitna tax lagega?"). Our retrievers and
the reranker work best on English, so we (1) detect Hinglish by counting typical Hindi marker
words and (2) replace Hinglish words/phrases with English equivalents using a hand-written
dictionary (multi-word phrases first, then single words). The list of replacements is
returned so the demo UI can show exactly what was changed.
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------- dictionaries
# Multi-word phrases are replaced before single words ("kab tak" must not become "when up to").
PHRASES: dict[str, str] = {
    "kab tak": "deadline by when",
    "aakhri tareekh": "last date deadline",
    "aakhri tarikh": "last date deadline",
    "last date kya": "last date deadline",
    "kaun sa": "which", "kaun si": "which", "kaun se": "which",
    "kon sa": "which", "kon si": "which", "kon se": "which",
    "pichle saal": "last year", "pichhle saal": "last year", "pichla saal": "last year",
    "pichle sal": "last year", "agle saal": "next year", "is saal": "this year",
    "iss saal": "this year", "is sal": "this year", "is baar": "this year",
    "is mahine": "this month",
    "se pehle": "before", "se pahle": "before", "ke pehle": "before",
    "ke baad": "after", "ke bad": "after", "se zyada": "more than", "se jyada": "more than",
    "se kam": "less than", "se upar": "above", "ke upar": "above", "ke neeche": "below",
    "naukri pesha": "salaried", "naukripesha": "salaried",
    "varishth nagrik": "senior citizen", "senior nagrik": "senior citizen",
    "mata pita": "parents", "maa baap": "parents", "maa baap ka": "parents",
    "ghar ka kiraya": "house rent", "makaan kiraya": "house rent",
    "jama karna": "deposit", "jama karein": "deposit",
    "kitna lagega": "how much is charged", "kitni lagegi": "how much is charged",
    "kitna padega": "how much need to pay", "kitna dena": "how much to pay",
    "kya hai": "what is", "kya hota hai": "what is", "kya hoti hai": "what is",
    "kaise bhare": "how to file", "kaise bharein": "how to file", "kaise bharu": "how to file",
    "chhota vyapari": "small trader", "chhote vyapari": "small traders",
    "naya regime": "new regime", "purana regime": "old regime",
}

# Single words. Empty string = drop the word (pure grammar words that only add noise).
WORDS: dict[str, str] = {
    # question words
    "kitna": "how much", "kitni": "how much", "kitne": "how many", "kitnaa": "how much",
    "kaise": "how", "kese": "how", "kaisey": "how", "kyun": "why", "kyon": "why", "kyu": "why",
    "kab": "when", "kahan": "where", "kaha": "where", "kaun": "which", "kon": "which",
    "kaunsa": "which", "konsa": "which", "kaunsi": "which", "konsi": "which",
    "kya": "", "kia": "", "kisko": "who", "kise": "who", "kiska": "whose",
    # pronouns
    "mujhe": "I", "mujhko": "I", "muje": "I", "main": "I", "mai": "I",
    "maine": "I", "mera": "my", "meri": "my", "mere": "my", "hum": "we", "hamara": "our",
    "humara": "our", "hamari": "our", "aap": "you", "aapka": "your", "aapki": "your",
    "tum": "you", "tumhara": "your", "unka": "their", "uska": "his", "ye": "this",
    "yeh": "this", "woh": "that", "vo": "that", "wo": "that", "isme": "in this",
    "ismein": "in this",
    # verbs / auxiliaries
    "hai": "is", "hain": "are", "he": "is", "hota": "is", "hoti": "is", "hote": "are",
    "hoga": "will be", "hogi": "will be", "honge": "will be", "tha": "was", "thi": "was",
    "lagega": "applicable", "lagegi": "applicable", "lagta": "charged", "lagti": "charged",
    "lagte": "charged", "lage": "charged", "lagenge": "applicable",
    "padega": "need to", "padegi": "need to", "padta": "need to", "padti": "need to",
    "padenge": "need to", "milta": "available", "milti": "available", "milte": "available",
    "milega": "available", "milegi": "available", "milenge": "available",
    "bharna": "file", "bharni": "file", "bharne": "file", "bhare": "file", "bharein": "file",
    "bharun": "file", "bharu": "file", "bhar": "file",
    "dena": "pay", "deni": "pay", "dene": "pay", "dunga": "pay", "dungi": "pay",
    "lena": "take", "leni": "take", "lene": "take",
    "sakta": "can", "sakti": "can", "sakte": "can", "chahiye": "required",
    "batao": "tell", "bataiye": "tell", "bataye": "tell", "bata": "tell", "btao": "tell",
    "samjhao": "explain", "samjhaiye": "explain", "kamata": "earn", "kamaata": "earn",
    "kamati": "earn", "kamate": "earn", "kamaya": "earned",
    "karna": "", "karni": "", "karne": "", "karte": "", "karta": "", "karti": "",
    "karo": "", "kare": "", "karein": "", "kar": "", "kiya": "", "ho": "", "raha": "",
    "rahi": "", "rahe": "",
    # connectors / particles
    "agar": "if", "agr": "if", "aur": "and", "ya": "or", "lekin": "but", "par": "on",
    "bhi": "also", "nahi": "not", "nahin": "not", "nhi": "not", "sirf": "only",
    "toh": "", "to": "", "ki": "", "ka": "", "ke": "", "ko": "", "se": "from",
    "mein": "in", "me": "in", "mei": "in", "liye": "for", "lie": "for", "wala": "",
    "wali": "", "wale": "", "vala": "", "vali": "", "vale": "", "sabse": "most",
    "zyada": "more", "jyada": "more", "kam": "less", "upar": "above", "neeche": "below",
    "niche": "below", "tak": "up to", "pehle": "before", "pahle": "before",
    "baad": "after", "bad": "after", "abhi": "now", "aaj": "today", "kuch": "some",
    "sab": "all", "har": "every", "jab": "when", "matlab": "meaning", "haan": "yes",
    # time
    "saal": "year", "sal": "year", "varsh": "year", "mahina": "month", "mahine": "month",
    "din": "days", "naya": "new", "nayi": "new", "naye": "new", "nai": "new",
    "purana": "old", "purani": "old", "purane": "old", "pichle": "last", "pichla": "last",
    "agle": "next", "agla": "next", "tareekh": "date", "tarikh": "date",
    "janvari": "january", "farvari": "february", "agast": "august", "agust": "august",
    "sitambar": "september", "aktubar": "october", "navambar": "november",
    "disambar": "december", "julai": "july",
    # money / tax vocabulary
    "tankhwah": "salary", "tankhwa": "salary", "tankha": "salary", "vetan": "salary",
    "pagaar": "salary", "pagar": "salary", "salary": "salary", "kamai": "income",
    "aay": "income", "aamdani": "income", "amdani": "income", "aamdni": "income",
    "chhoot": "exemption", "chhut": "exemption", "chhuut": "exemption", "chot": "exemption",
    "maafi": "exemption", "katauti": "deduction", "dar": "rate", "pratishat": "percent",
    "takka": "percent", "rupaye": "rupees", "rupay": "rupees", "rupye": "rupees",
    "hazaar": "thousand", "hazar": "thousand", "karod": "crore", "karor": "crore",
    "bachat": "savings", "nivesh": "investment", "niwesh": "investment",
    "bima": "insurance", "beema": "insurance", "byaaj": "interest", "byaj": "interest",
    "biyaj": "interest", "karz": "loan", "karza": "loan", "kiraya": "rent",
    "kiraaya": "rent", "jurmana": "penalty", "jurmaana": "penalty", "der": "late",
    "deri": "late", "wapas": "refund", "vapas": "refund", "jama": "deposit", "kul": "total",
    "sarkar": "government", "sarkari": "government", "vibhag": "department",
    "rasid": "receipt", "raseed": "receipt", "bikri": "sales", "kharid": "purchase",
    "kharidi": "purchase", "kharida": "purchased", "maal": "goods", "samaan": "goods",
    "saman": "goods", "seva": "service", "sewa": "service",
    # people / business
    "dukaan": "shop", "dukan": "shop", "dukaandar": "shopkeeper", "dukandar": "shopkeeper",
    "vyapari": "trader", "vyapaari": "trader", "byapari": "trader", "vyapar": "business",
    "vyapaar": "business", "dhandha": "business", "dhanda": "business", "kaam": "work",
    "naukri": "job", "chhote": "small", "chote": "small", "chhota": "small", "chota": "small",
    "chhoti": "small", "choti": "small", "bada": "large", "bade": "large", "badi": "large",
    "buzurg": "senior citizen", "budhe": "senior citizen", "bachche": "children",
    "bacche": "children", "padhai": "education", "padai": "education",
    # things (GST)
    "ghar": "house", "makaan": "house", "makan": "house", "dawai": "medicine",
    "dawa": "medicine", "dawaiyan": "medicines", "ilaaj": "treatment", "ilaj": "treatment",
    "khana": "food", "khaana": "food", "kapde": "clothes", "kapda": "clothes",
    "kapdon": "clothes", "joote": "shoes", "jootey": "shoes", "gaadi": "vehicle",
    "gadi": "vehicle", "sona": "gold", "chandi": "silver", "swasthya": "health",
}

# Words that strongly signal Hinglish (not normal English words). Used for detection only.
MARKERS = {
    "kya", "hai", "hain", "kitna", "kitni", "kitne", "mujhe", "mera", "meri", "mere", "lagega",
    "lagegi", "lagta", "padega", "padegi", "kaise", "kab", "kaun", "kaunsa", "konsa", "agar",
    "aur", "nahi", "nahin", "bhi", "ke", "ki", "ka", "ko", "se", "mein", "liye", "hota", "hoga",
    "tha", "saal", "pichle", "chhoot", "chhut", "tankhwah", "bharna", "bharni", "milta",
    "milega", "chahiye", "sakta", "sakte", "batao", "bataiye", "toh", "wala", "wali", "vyapari",
    "dukaan", "dukan", "abhi", "pehle", "baad", "naya", "purana", "purane", "naye", "kamai",
    "karna", "karni", "karte", "kar", "dena", "aap", "aapka", "hum", "humara", "yeh", "kiraya",
    "byaj", "ghar", "kamata", "zyada", "jyada", "sirf", "kyun", "kahan", "agast", "lagti",
}

DEVANAGARI_RE = re.compile(r"[ऀ-ॿ]")
WORD_RE = re.compile(r"[A-Za-z]+")


def detect_language(text: str) -> str:
    """Return 'hinglish' or 'en'. Rule: ≥2 marker words, or ≥15% of words are markers,
    or any Devanagari character."""
    if DEVANAGARI_RE.search(text):
        return "hinglish"
    words = [w.lower() for w in WORD_RE.findall(text)]
    if not words:
        return "en"
    hits = sum(1 for w in words if w in MARKERS)
    return "hinglish" if hits >= 2 or hits / len(words) >= 0.15 else "en"


def _match_case(src: str, repl: str) -> str:
    return repl.capitalize() if src[:1].isupper() and repl and repl != "I" else repl


def normalise(text: str, force: bool = False) -> dict:
    """Normalise Hinglish text to English.

    Returns {"original", "normalised", "language", "replaced": [[hinglish, english], ...]}.
    English text is returned unchanged unless force=True (avoids mangling words like "me").
    """
    language = detect_language(text)
    result = {"original": text, "normalised": text, "language": language, "replaced": []}
    if language != "hinglish" and not force:
        return result

    replaced: list[list[str]] = []
    out = text
    # 1) phrases, longest first
    # Phrase outputs are parked behind placeholders (\x01N\x02) so the single-word pass
    # below cannot re-translate them (e.g. the "to" in "need to").
    parked: list[str] = []
    for phrase in sorted(PHRASES, key=len, reverse=True):
        pattern = re.compile(r"\b" + re.escape(phrase) + r"\b", re.IGNORECASE)
        if pattern.search(out):
            replaced.append([phrase, PHRASES[phrase]])
            parked.append(PHRASES[phrase])
            out = pattern.sub(f"\x01{len(parked) - 1}\x02", out)

    # 2) single words
    had_kya = False

    def swap(m: re.Match) -> str:
        nonlocal had_kya
        word = m.group(0)
        low = word.lower()
        if low not in WORDS:
            return word
        repl = WORDS[low]
        if low in ("kya", "kia"):
            had_kya = True
        if repl.lower() != low:
            replaced.append([low, repl if repl else "(dropped)"])
        return _match_case(word, repl)

    out = WORD_RE.sub(swap, out)
    out = re.sub("\x01(\\d+)\x02", lambda m: parked[int(m.group(1))], out)
    out = re.sub(r"\s+([?.!,])", r"\1", re.sub(r"\s{2,}", " ", out)).strip()
    if had_kya and not out.endswith("?"):
        out += "?"  # "kya" marks a yes/no question
    result["normalised"] = out
    result["replaced"] = replaced
    return result
