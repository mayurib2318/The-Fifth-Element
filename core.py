"""
core.py
══════════════════════════════════════════════════════════════════════════════
MisinfoRadar v3 — SHARED CORE MODULE
All logic lives here. Every other file imports ONLY from this file.

New in v3:
  ✦ URL scraping   — paste any news/article URL
  ✦ File upload    — .txt  .csv  .json  supported
  ✦ RSS/live feeds — BBC, Reuters, AP, Guardian (real-time)
  ✦ Social text    — direct paste with hashtag / mention cleaning
══════════════════════════════════════════════════════════════════════════════
"""

import re, math, random, logging, unicodedata, json, csv, io, os, sys
import urllib.request, urllib.parse
from typing import Optional

import networkx as nx

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# §1  INPUT FETCHERS  (URL · File · RSS · Plain text)
# ─────────────────────────────────────────────────────────────────────────────

# Public RSS feeds that work without an API key
LIVE_FEEDS = {
    "BBC World":        "http://feeds.bbci.co.uk/news/world/rss.xml",
    "Reuters":          "https://feeds.reuters.com/reuters/topNews",
    "AP News":          "https://rsshub.app/apnews/topics/apf-topnews",
    "The Guardian":     "https://www.theguardian.com/world/rss",
    "Al Jazeera":       "https://www.aljazeera.com/xml/rss/all.xml",
    "NPR Top Stories":  "https://feeds.npr.org/1001/rss.xml",
}


def _html_to_text(html: str) -> str:
    """Strip HTML tags and decode entities."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer",
                          "header", "aside", "form", "noscript"]):
            tag.decompose()
        return " ".join(soup.get_text(separator=" ").split())
    except ImportError:
        text = re.sub(r"<[^>]+>", " ", html)
        return re.sub(r"\s+", " ", text).strip()


def fetch_url(url: str) -> dict:
    """
    Scrape text content from any article/news URL.

    Returns:
        {"ok": True,  "text": str, "title": str, "source": url}
        {"ok": False, "error": str}
    """
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        req = urllib.request.Request(
            url, headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml",
            }
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            raw_html = resp.read().decode(charset, errors="ignore")

        # Try newspaper3k first (best quality)
        try:
            from newspaper import Article
            art = Article(url)
            art.download(); art.parse()
            
            title = art.title or ""
            text  = art.text or _html_to_text(raw_html)
            return {"ok": True, "text": text, "title": title, "source": url}
        except Exception:
            pass

        # BeautifulSoup fallback
        title = ""
        m = re.search(r"<title[^>]*>(.*?)</title>", raw_html, re.I | re.S)
        if m:
            title = re.sub(r"<[^>]+>", "", m.group(1)).strip()

        # Extract main article paragraphs
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(raw_html, "html.parser")
            for tag in soup(["script","style","nav","footer",
                              "header","aside","form","noscript"]):
                tag.decompose()
            # Prefer <article>, <main>, then all <p> tags
            container = (soup.find("article")
                         or soup.find("main")
                         or soup.find("div", {"class": re.compile(r"article|content|story", re.I)})
                         or soup)
            paras = [p.get_text(" ", strip=True)
                     for p in container.find_all("p")
                     if len(p.get_text(strip=True)) > 40]
            text = " ".join(paras) if paras else _html_to_text(raw_html)
        except Exception:
            text = _html_to_text(raw_html)

        if len(text.strip()) < 50:
            return {"ok": False, "error": "Could not extract readable text from this URL."}

        return {"ok": True, "text": text[:8000], "title": title, "source": url}

    except Exception as e:
        return {"ok": False, "error": f"Failed to fetch URL: {e}"}


def parse_uploaded_file(filename: str, content: bytes) -> dict:
    """
    Parse uploaded file content.
    Supported: .txt  .csv  .json

    Returns:
        {"ok": True, "items": [{"text": str, "label": str}, …]}
        {"ok": False, "error": str}
    """
    ext = os.path.splitext(filename.lower())[1]

    try:
        if ext == ".txt":
            text = content.decode("utf-8", errors="ignore").strip()
            if not text:
                return {"ok": False, "error": "File is empty."}
            return {"ok": True, "items": [{"text": text, "label": filename}]}

        elif ext == ".csv":
            text_io = io.StringIO(content.decode("utf-8", errors="ignore"))
            reader  = csv.DictReader(text_io)
            rows    = list(reader)
            if not rows:
                return {"ok": False, "error": "CSV has no rows."}

            # Auto-detect text column
            col = None
            for candidate in ["text", "content", "body", "article",
                               "headline", "title", "news", "post"]:
                if candidate in (rows[0] or {}):
                    col = candidate
                    break
            if col is None:
                col = list(rows[0].keys())[0]  # first column

            items = []
            for i, row in enumerate(rows[:500]):   # max 500 rows
                t = row.get(col, "").strip()
                if t:
                    items.append({"text": t,
                                  "label": row.get("label", row.get("id", f"row_{i+1}"))})
            if not items:
                return {"ok": False, "error": f"No text found in column '{col}'."}
            return {"ok": True, "items": items, "column_used": col}

        elif ext == ".json":
            data = json.loads(content.decode("utf-8", errors="ignore"))
            if isinstance(data, str):
                return {"ok": True, "items": [{"text": data, "label": filename}]}
            if isinstance(data, dict):
                text = (data.get("text") or data.get("content")
                        or data.get("body") or data.get("article") or "")
                if text:
                    return {"ok": True,
                            "items": [{"text": str(text),
                                       "label": data.get("title", filename)}]}
                return {"ok": False, "error": "JSON has no 'text' / 'content' field."}
            if isinstance(data, list):
                items = []
                for i, item in enumerate(data[:500]):
                    if isinstance(item, str):
                        items.append({"text": item, "label": f"item_{i+1}"})
                    elif isinstance(item, dict):
                        t = (item.get("text") or item.get("content")
                             or item.get("body") or item.get("headline") or "")
                        if t:
                            items.append({"text": str(t),
                                          "label": item.get("title",
                                                            item.get("id", f"item_{i+1}"))})
                if not items:
                    return {"ok": False, "error": "No text items found in JSON array."}
                return {"ok": True, "items": items}

        else:
            return {"ok": False,
                    "error": f"Unsupported file type '{ext}'. Use .txt .csv or .json"}

    except Exception as e:
        return {"ok": False, "error": f"File parse error: {e}"}


def fetch_rss_feed(feed_name: str, max_items: int = 10) -> dict:
    """
    Fetch latest headlines from a live RSS feed.

    Returns:
        {"ok": True,  "items": [{"text": str, "title": str, "link": str}, …], "feed": name}
        {"ok": False, "error": str}
    """
    url = LIVE_FEEDS.get(feed_name)
    if not url:
        return {"ok": False, "error": f"Unknown feed '{feed_name}'."}

    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 MisinfoRadar/3.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return {"ok": False, "error": f"Could not fetch feed: {e}"}

    # Parse RSS/Atom with regex (no feedparser needed)
    items  = []
    titles = re.findall(r"<title[^>]*><!\[CDATA\[(.*?)\]\]>|<title[^>]*>(.*?)</title>",
                        raw, re.S)
    descs  = re.findall(r"<description[^>]*><!\[CDATA\[(.*?)\]\]>|<description[^>]*>(.*?)</description>",
                        raw, re.S)
    links  = re.findall(r"<link>([^<]+)</link>|<link href=\"([^\"]+)\"", raw)

    for i in range(min(max_items, len(titles))):
        title = (titles[i][0] or titles[i][1]).strip()
        desc  = ""
        if i < len(descs):
            desc = (descs[i][0] or descs[i][1]).strip()
        link  = ""
        if i < len(links):
            link = (links[i][0] or links[i][1]).strip()

        # Skip feed-level title (first <title> is usually the feed name)
        if i == 0 and not link:
            continue

        # Combine title + description for analysis
        combined = f"{title}. {_html_to_text(desc)}" if desc else title
        combined = re.sub(r"\s+", " ", combined).strip()

        if len(combined) > 20:
            items.append({
                "text":  combined[:2000],
                "title": title,
                "link":  link,
            })

    if not items:
        return {"ok": False, "error": "Feed returned no readable items."}

    return {"ok": True, "items": items[:max_items], "feed": feed_name}


# ─────────────────────────────────────────────────────────────────────────────
# §2  TEXT PREPROCESSING
# ─────────────────────────────────────────────────────────────────────────────

LANGUAGE_NAMES = {
    "en":"English","hi":"Hindi","fr":"French","de":"German","es":"Spanish",
    "ar":"Arabic","zh-cn":"Chinese","pt":"Portuguese","ru":"Russian","it":"Italian",
}

try:
    from langdetect import detect as _ld_detect, DetectorFactory
    DetectorFactory.seed = 42
    _LANGDETECT = True
except ImportError:
    _LANGDETECT = False

try:
    from deep_translator import GoogleTranslator as _GT
    _TRANSLATOR_AVAIL = True
except ImportError:
    _TRANSLATOR_AVAIL = False

_translator_obj = None
def _get_translator():
    global _translator_obj
    if _translator_obj is None and _TRANSLATOR_AVAIL:
        try: _translator_obj = _GT(source="auto", target="en")
        except Exception: pass
    return _translator_obj

def detect_language(text: str) -> str:
    if not _LANGDETECT or not text.strip(): return "en"
    try: return _ld_detect(text)
    except Exception: return "en"

def translate_to_english(text: str, lang: str = "en") -> str:
    if lang in ("en","en-us") or not text.strip(): return text
    t = _get_translator()
    if t is None: return text
    try: return t.translate(text) or text
    except Exception: return text

def clean_text(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = re.sub(r"http\S+|www\.\S+", "[URL]", text)
    text = re.sub(r"@\w+", "[USER]", text)
    text = re.sub(r"#(\w+)", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"[^\w\s.,!?'\"()\-]", "", text)
    return text

def preprocess_text(text: str) -> dict:
    lang        = detect_language(text)
    translated  = translate_to_english(text, lang)
    cleaned     = clean_text(translated)
    return {
        "original": text, "detected_lang": lang,
        "lang_name": LANGUAGE_NAMES.get(lang, lang.upper()),
        "translated": translated, "cleaned": cleaned,
        "was_translated": lang not in ("en","en-us"),
    }

# ─────────────────────────────────────────────────────────────────────────────
# §3  EMOTION DETECTION
# ─────────────────────────────────────────────────────────────────────────────

EMOTION_LABELS   = ["joy","fear","anger","sadness","surprise","disgust","neutral"]
VIRALITY_WEIGHTS = {
    "fear":0.90,"anger":0.85,"disgust":0.70,
    "surprise":0.65,"sadness":0.50,"joy":0.40,"neutral":0.20,
}
EMOTION_KEYWORDS = {
    "fear":    ["afraid","scary","terrifying","danger","threat","warning","panic",
                "emergency","crisis","deadly","killer","lethal","toxic","poisonous",
                "kill","die","death","dead","risk","unsafe","hazard"],
    "anger":   ["angry","outrage","furious","hate","disgraceful","unacceptable",
                "attack","corrupt","liar","cheat","scam","fraud","evil",
                "criminal","illegal","injustice","betrayal","lie"],
    "disgust": ["disgusting","revolting","filthy","sick","nasty","vile",
                "repulsive","awful","horrible","gross","appalling"],
    "surprise":["shocking","unbelievable","incredible","breaking","urgent",
                "unexpected","revealed","exposed","secret","hidden",
                "bombshell","exclusive","leaked"],
    "joy":     ["happy","great","wonderful","love","amazing","excellent",
                "fantastic","joy","celebrate","brilliant","awesome","best",
                "perfect","beautiful"],
    "sadness": ["sad","tragic","devastating","lost","died","grief",
                "mourning","heartbreak","suffer","pain","devastated","horrific"],
    "neutral": [],
}
HF_LABEL_MAP = {
    "LABEL_0":"sadness","LABEL_1":"joy","LABEL_2":"love","LABEL_3":"anger",
    "LABEL_4":"fear","LABEL_5":"surprise","love":"joy","optimism":"joy",
    "pessimism":"sadness","anticipation":"surprise","trust":"joy",
}

_emo_pipe   = None
_emo_loaded = False

def _load_emotion_model():
    global _emo_pipe, _emo_loaded
    if _emo_loaded: return
    try:
        from transformers import pipeline
        _emo_pipe   = pipeline("text-classification",
                               model="bhadresh-savani/distilbert-base-uncased-emotion",
                               top_k=None, truncation=True, max_length=512)
        _emo_loaded = True
        logger.info("Emotion model ready.")
    except Exception as e:
        logger.warning("Emotion transformer unavailable (%s). Using rule-based.", e)

def _emo_rule(text: str) -> dict:
    tl = text.lower()
    raw   = {e: float(sum(1 for kw in kws if kw in tl)) for e,kws in EMOTION_KEYWORDS.items()}
    total = sum(raw.values()) or 1.0
    return {e: round(raw[e]/total,4) for e in EMOTION_LABELS}

def detect_emotion(text: str) -> dict:
    _load_emotion_model()
    if not text or not text.strip():
        return {"dominant_emotion":"neutral","emotion_scores":{e:0.0 for e in EMOTION_LABELS},
                "virality_amplifier":0.20,"model_used":"none"}
    model_used = "rule_based"
    if _emo_loaded and _emo_pipe:
        try:
            raw    = _emo_pipe(text[:512])[0]
            scores = {}
            for item in raw:
                lbl = HF_LABEL_MAP.get(item["label"].lower(), item["label"].lower())
                if lbl not in EMOTION_LABELS: lbl = "neutral"
                scores[lbl] = round(scores.get(lbl,0) + item["score"], 4)
            for e in EMOTION_LABELS: scores.setdefault(e,0.0)
            model_used = "transformer"
        except Exception: scores = _emo_rule(text)
    else:
        scores = _emo_rule(text)
    dominant = max(scores, key=scores.get)
    return {"dominant_emotion":dominant,"emotion_scores":scores,
            "virality_amplifier":VIRALITY_WEIGHTS[dominant],"model_used":model_used}

# ─────────────────────────────────────────────────────────────────────────────
# §4  MISINFORMATION DETECTION
# ─────────────────────────────────────────────────────────────────────────────

MISINFO_PATTERNS = [
    (r"\b(breaking|urgent|must[- ]read|share immediately|share before (they|it is) (removed|deleted|banned))\b",0.15),
    (r"\b(they don.t want you to know|mainstream media won.t tell|hidden truth|banned information)\b",0.20),
    (r"\b(deep state|new world order|great reset|wake up sheeple|illuminati)\b",0.25),
    (r"\b(doctors hate|big pharma|cure cancer|100.?% effective|natural cure|doctors won.t tell)\b",0.20),
    (r"\b(many people are saying|sources say|everyone knows|it.?s obvious that)\b",0.10),
    (r"\b(unbelievable|jaw.?dropping|you won.t believe|mind.?blowing)\b",0.10),
    (r"\b(government is hiding|they are trying to|banned from|suppressed)\b",0.15),
    (r"\b(microchip|5g (kills?|causes?|radiation)|chemtrails?|flat earth|moon landing.{0,20}fake)\b",0.30),
    (r"\b(drink (bleach|urine)|bleach cures|miracle cure)\b",0.35),
    (r"[A-Z]{4,}.*[A-Z]{4,}.*[A-Z]{4,}",0.08),
    (r"!{3,}",0.06),
]
CREDIBILITY_PATTERNS = [
    r"\b(according to (scientists?|researchers?|study|studies|the (who|cdc|fda|nih)))\b",
    r"\b(peer.?reviewed|published in|journal of|university of|institute of)\b",
    r"\b(data shows?|evidence (suggests?|indicates?)|research (indicates?|shows?|finds?))\b",
    r"https?://[^\s]+(\.gov|\.edu)[^\s]*\b",
    r"\b(clinical trial|randomized|double.blind|meta.?analysis)\b",
]

_mis_re  = [(re.compile(p,re.I),w) for p,w in MISINFO_PATTERNS]
_cred_re = [re.compile(p,re.I) for p in CREDIBILITY_PATTERNS]

_mis_pipe   = None
_mis_loaded = False

def _load_misinfo_model():
    global _mis_pipe, _mis_loaded
    if _mis_loaded: return
    try:
        from transformers import pipeline
        _mis_pipe   = pipeline("text-classification",
                               model="hamzab/roberta-fake-news-classification",
                               truncation=True, max_length=512, top_k=None)
        _mis_loaded = True
        logger.info("Misinfo model ready.")
    except Exception as e:
        logger.warning("Misinfo transformer unavailable (%s). Using rule-based.", e)

def _mis_rule(text: str) -> tuple:
    flags, raw = [], 0.0
    for pat,w in _mis_re:
        matches = pat.findall(text)
        if matches:
            raw += w * len(matches)
            for m in matches[:2]:
                f = (m if isinstance(m,str) else m[0]).strip()[:40]
                if f and f not in flags: flags.append(f)
    cred  = sum(1 for p in _cred_re if p.search(text))
    score = round(max(0.0, min(raw - cred*0.10, 0.95)), 3)
    conf  = round(min(0.45 + (len(flags)+cred)*0.04, 0.88), 3)
    return score, conf, flags[:5]

def detect_misinformation(text: str) -> dict:
    _load_misinfo_model()
    if not text or not text.strip():
        return {"is_misinformation":False,"misinfo_probability":0.0,
                "confidence":0.0,"label":"UNCERTAIN","red_flags":[],"model_used":"none"}
    red_flags = []
    if _mis_loaded and _mis_pipe:
        try:
            results    = _mis_pipe(text[:512])[0]
            score_map  = {r["label"].upper(): r["score"] for r in results}
            fake_score = (score_map.get("FAKE") or score_map.get("LABEL_1")
                          or score_map.get("MISLEADING", 0.0))
            confidence = max(r["score"] for r in results)
            _,_,red_flags = _mis_rule(text)
            model_used = "transformer"
        except Exception as e:
            logger.warning("Misinfo inference failed: %s", e)
            fake_score, confidence, red_flags = _mis_rule(text)
            model_used = "rule_based"
    else:
        fake_score, confidence, red_flags = _mis_rule(text)
        model_used = "rule_based"

    label = ("LIKELY FAKE" if fake_score >= 0.65 else
             "UNCERTAIN"   if fake_score >= 0.40 else "LIKELY REAL")
    return {"is_misinformation":fake_score >= 0.50,"misinfo_probability":round(float(fake_score),3),
            "confidence":round(float(confidence),3),"label":label,
            "red_flags":red_flags,"model_used":model_used}

# ─────────────────────────────────────────────────────────────────────────────
# §5  GRAPH + SIR SIMULATION
# ─────────────────────────────────────────────────────────────────────────────

_SEED = 42

def build_network(n_nodes:int=150, network_type:str="scale_free", virality:float=0.5) -> nx.DiGraph:
    m = max(1, int(2 + virality*3))
    if network_type == "scale_free":
        base = nx.barabasi_albert_graph(n_nodes, m, seed=_SEED)
    elif network_type == "small_world":
        k = max(2, int(4 + virality*4))
        base = nx.watts_strogatz_graph(n_nodes, k, 0.3, seed=_SEED)
    else:
        base = nx.erdos_renyi_graph(n_nodes, 0.04+virality*0.08, seed=_SEED)
    G   = nx.DiGraph(base)
    rng = random.Random(_SEED)
    for node in G.nodes():
        G.nodes[node]["credibility"] = round(rng.random(), 2)
    for u,v in G.edges():
        G.edges[u,v]["weight"] = round(rng.random(), 2)
    return G

def simulate_spread(G:nx.DiGraph, base_prob:float=0.25, max_steps:int=15) -> dict:
    source     = max(G.nodes(), key=lambda n: G.out_degree(n))
    rng        = random.Random(_SEED+1)
    infected   = {source}
    susceptible = set(G.nodes()) - infected
    timeline   = [{"step":0,"new":1,"total":1,"rate":0.0}]
    for step in range(1, max_steps+1):
        newly = set()
        for node in list(infected):
            for nbr in G.successors(node):
                if nbr not in susceptible: continue
                w    = G.edges[node,nbr].get("weight",0.5)
                cred = G.nodes[nbr].get("credibility",0.5)
                if rng.random() < base_prob * w * (1.0 - cred*0.25):
                    newly.add(nbr)
        infected |= newly; susceptible -= newly
        prev = len(infected) - len(newly)
        timeline.append({"step":step,"new":len(newly),"total":len(infected),
                          "rate":round(len(newly)/max(prev,1),4)})
        if not newly: break
    total = G.number_of_nodes()
    return {"total_nodes":total,"total_infected":len(infected),
            "reach_pct":round(len(infected)/total*100,1),
            "peak_step":len(timeline)-1,"timeline":timeline}

def graph_metrics(G:nx.DiGraph) -> dict:
    try: clustering = round(nx.average_clustering(G.to_undirected()),4)
    except: clustering = 0.0
    try: largest_cc = len(max(nx.weakly_connected_components(G),key=len))
    except: largest_cc = G.number_of_nodes()
    degrees = dict(G.out_degree())
    avg_deg = round(sum(degrees.values())/max(len(degrees),1),2)
    return {"nodes":G.number_of_nodes(),"edges":G.number_of_edges(),
            "avg_out_degree":avg_deg,"density":round(nx.density(G),4),
            "avg_clustering":clustering,"largest_component":largest_cc,
            "top_influencers":sorted(degrees,key=degrees.get,reverse=True)[:5]}

def propagation_risk_score(metrics:dict, virality:float) -> float:
    return round(min(0.40*virality + 0.25*min(metrics["density"]*25,1.0)
                     + 0.20*min(metrics["avg_out_degree"]/20,1.0)
                     + 0.15*metrics["avg_clustering"], 1.0), 3)

# ─────────────────────────────────────────────────────────────────────────────
# §6  PROPAGATION PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

RISK_TIERS = [
    (0.80,"CRITICAL","🔴","Extremely high spread. Immediate intervention required."),
    (0.65,"HIGH",    "🟠","High spread risk. Flag and escalate for review."),
    (0.45,"MODERATE","🟡","Moderate potential. Attach a contextual warning label."),
    (0.25,"LOW",     "🟢","Limited spread expected. Standard monitoring sufficient."),
    (0.00,"MINIMAL", "⚪","Very low risk. No special action required."),
]

def get_risk_tier(score:float) -> dict:
    for threshold,name,icon,desc in RISK_TIERS:
        if score >= threshold:
            return {"name":name,"icon":icon,"label":f"{icon} {name}","description":desc}
    return {"name":"MINIMAL","icon":"⚪","label":"⚪ MINIMAL","description":"Very low risk."}

def compute_virality(emotion:dict, misinfo:dict, text_len:int) -> float:
    m  = misinfo["misinfo_probability"]
    e  = emotion["virality_amplifier"]
    url= 0.8 if "[URL]" in str(misinfo.get("red_flags","")) else 0.3
    lf = 1.0 - abs(min(text_len/280,1.0)-0.5)
    return round(min(0.40*m + 0.35*e + 0.15*url + 0.10*lf, 1.0), 3)

def build_recommendations(misinfo:dict, emotion:dict, risk:float) -> list:
    recs = []
    if misinfo["is_misinformation"]:
        recs.append("🚨 Flag content for fact-checker review before further amplification.")
    if misinfo["red_flags"]:
        recs.append(f"⚠️  Red-flag phrases: {', '.join(repr(f) for f in misinfo['red_flags'][:3])}")
    emo = emotion["dominant_emotion"]
    if emo in ("fear","anger","disgust"):
        recs.append(f"😤 High-{emo} content — add share friction "
                    f"(e.g. 'Are you sure you want to share this?').")
    if risk >= 0.65:
        recs.append("📊 Deploy counter-narrative content in the same feed.")
        recs.append("🔔 Alert human moderators for manual review.")
    elif risk >= 0.45:
        recs.append("ℹ️  Attach a contextual fact-check label to this post.")
    else:
        recs.append("✅ Standard automated monitoring is sufficient.")
    return recs

def predict_propagation(text:str, network_type:str="scale_free",
                        simulate:bool=True, network_size:int=200) -> dict:
    """Full end-to-end prediction pipeline."""
    pre      = preprocess_text(text)
    clean    = pre["cleaned"]
    emotion  = detect_emotion(clean)
    misinfo  = detect_misinformation(clean)
    virality = compute_virality(emotion, misinfo, len(clean))

    gm_data = sim_data = None
    risk    = virality
    if simulate:
        G       = build_network(network_size, network_type, virality)
        gm_data = graph_metrics(G)
        risk    = propagation_risk_score(gm_data, virality)
        sim_data = simulate_spread(G, base_prob=0.10+virality*0.40, max_steps=15)

    return {
        "input":          {"text_snippet":text[:200]+("…" if len(text)>200 else ""),
                           "lang_name":pre["lang_name"],"was_translated":pre["was_translated"]},
        "emotion":        emotion,
        "misinformation": misinfo,
        "virality_score": virality,
        "risk_score":     risk,
        "risk_tier":      get_risk_tier(risk),
        "graph_metrics":  gm_data,
        "simulation":     sim_data,
        "recommendations":build_recommendations(misinfo,emotion,risk),
        "network_type":   network_type,
    }

# ─────────────────────────────────────────────────────────────────────────────
# §7  SVG CHART GENERATORS  (pure Python, server-side, zero JS)
# ─────────────────────────────────────────────────────────────────────────────

EMOTION_COLORS = {
    "fear":"#f87171","anger":"#fb923c","disgust":"#c084fc",
    "surprise":"#facc15","sadness":"#60a5fa","joy":"#4ade80","neutral":"#94a3b8",
}

def _risk_color(s:float) -> str:
    return ("#f87171" if s>=0.80 else "#fb923c" if s>=0.65
            else "#facc15" if s>=0.45 else "#4ade80" if s>=0.25 else "#94a3b8")

def _misinfo_color(p:float) -> str:
    return "#f87171" if p>=0.60 else "#facc15" if p>=0.40 else "#4ade80"

def svg_risk_gauge(score:float, size:int=180) -> str:
    cx=cy=size//2; r=size//2-20; color=_risk_color(score); angle=score*180
    def polar(deg):
        rad=math.radians(180-deg); return cx+r*math.cos(rad),cy-r*math.sin(rad)
    x0,y0=polar(0); x1,y1=polar(180); x2,y2=polar(angle)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size//2+45}">'
            f'<path d="M {x0:.1f},{y0:.1f} A {r},{r} 0 0 1 {x1:.1f},{y1:.1f}" fill="none" stroke="#2e3250" stroke-width="12" stroke-linecap="round"/>'
            f'<path d="M {x0:.1f},{y0:.1f} A {r},{r} 0 0 1 {x2:.1f},{y2:.1f}" fill="none" stroke="{color}" stroke-width="12" stroke-linecap="round"/>'
            f'<text x="{cx}" y="{cy+8}" text-anchor="middle" font-size="32" font-weight="900" fill="{color}">{round(score*100)}</text>'
            f'<text x="{cx}" y="{cy+28}" text-anchor="middle" font-size="12" fill="#94a3b8">out of 100</text>'
            f'</svg>')

def svg_misinfo_donut(prob:float, size:int=140) -> str:
    cx=cy=size//2; r=size//2-16; color=_misinfo_color(prob)
    circ=2*math.pi*r; off=circ*(1-prob)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}">'
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#2e3250" stroke-width="10"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" stroke-width="10"'
            f' stroke-dasharray="{circ:.2f}" stroke-dashoffset="{off:.2f}"'
            f' stroke-linecap="round" transform="rotate(-90 {cx} {cy})"/>'
            f'<text x="{cx}" y="{cy+7}" text-anchor="middle" font-size="22" font-weight="900" fill="{color}">{round(prob*100)}%</text>'
            f'</svg>')

def svg_emotion_bars(scores:dict, width:int=340) -> str:
    sorted_emos=sorted(scores.items(),key=lambda x:-x[1])
    lw,bh,gap,px_,py_=76,20,10,8,8
    avail=width-lw-px_*2-48; n=len(sorted_emos)
    height=py_*2+n*(bh+gap)-gap
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">']
    for i,(emo,score) in enumerate(sorted_emos):
        y=py_+i*(bh+gap); bw=max(int(avail*score),0)
        color=EMOTION_COLORS.get(emo,"#94a3b8")
        parts.append(f'<text x="{lw}" y="{y+bh-4}" text-anchor="end" font-size="12" fill="#94a3b8">{emo}</text>'
                     f'<rect x="{lw+px_}" y="{y}" width="{bw}" height="{bh}" rx="4" fill="{color}" opacity="0.85"/>'
                     f'<text x="{lw+px_+bw+5}" y="{y+bh-4}" font-size="11" fill="#cbd5e1">{round(score*100)}%</text>')
    parts.append("</svg>"); return "".join(parts)

def svg_timeline(timeline:list, color:str="#6366f1", width:int=700, height:int=220) -> str:
    if not timeline: return f'<svg width="{width}" height="{height}"></svg>'
    pad={"t":20,"r":20,"b":42,"l":55}
    w=width-pad["l"]-pad["r"]; h=height-pad["t"]-pad["b"]
    totals=[t["total"] for t in timeline]; max_y=max(totals) if totals else 1; n=len(totals)
    def px_(i): return pad["l"]+(i/max(n-1,1))*w
    def py_(v): return pad["t"]+h-(v/max_y)*h
    pts=[(px_(i),py_(v)) for i,v in enumerate(totals)]
    area=(f"M {pts[0][0]:.1f},{py_(0):.1f} "+" ".join(f"L {x:.1f},{y:.1f}" for x,y in pts)
          +f" L {pts[-1][0]:.1f},{py_(0):.1f} Z")
    line="M "+" L ".join(f"{x:.1f},{y:.1f}" for x,y in pts)
    y_ticks="".join(f'<line x1="{pad["l"]-5}" y1="{py_(round(max_y*i/4)):.1f}" x2="{pad["l"]}" y2="{py_(round(max_y*i/4)):.1f}" stroke="#2e3250" stroke-width="1"/>'
                    f'<text x="{pad["l"]-8}" y="{py_(round(max_y*i/4))+4:.1f}" text-anchor="end" font-size="11" fill="#94a3b8">{round(max_y*i/4)}</text>'
                    for i in range(5))
    x_ticks="".join(f'<text x="{px_(i):.1f}" y="{height-6}" text-anchor="middle" font-size="11" fill="#94a3b8">S{timeline[i]["step"]}</text>'
                    for i in range(0,n,max(1,n//8)))
    dots="".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{color}" stroke="#0f1117" stroke-width="1.5"/>' for x,y in pts)
    grid="".join(f'<line x1="{pad["l"]}" y1="{py_(round(max_y*i/4)):.1f}" x2="{pad["l"]+w}" y2="{py_(round(max_y*i/4)):.1f}" stroke="#1e2235" stroke-width="1"/>' for i in range(5))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
            f'<defs><linearGradient id="ag" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="{color}" stop-opacity="0.35"/><stop offset="100%" stop-color="{color}" stop-opacity="0.03"/></linearGradient></defs>'
            f'{grid}<path d="{area}" fill="url(#ag)"/><path d="{line}" fill="none" stroke="{color}" stroke-width="2.5" stroke-linejoin="round"/>'
            f'{dots}{y_ticks}{x_ticks}'
            f'<line x1="{pad["l"]}" y1="{pad["t"]}" x2="{pad["l"]}" y2="{pad["t"]+h}" stroke="#2e3250" stroke-width="1.5"/>'
            f'<line x1="{pad["l"]}" y1="{pad["t"]+h}" x2="{pad["l"]+w}" y2="{pad["t"]+h}" stroke="#2e3250" stroke-width="1.5"/>'
            f'</svg>')