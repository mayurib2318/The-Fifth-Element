"""
credibility.py
══════════════════════════════════════════════════════════════════════════════
MisinfoRadar v4 — Media Credibility Analyzer

Detects HOW news channels present false news as true, including:
  1. Source credibility scoring (domain reputation database)
  2. Linguistic deception patterns (hedge language, passive attribution, etc.)
  3. Manipulation tactic classification (8 specific deception types)
  4. Headline vs body mismatch detection
  5. Cross-source verification readiness check
  6. Overall trust verdict with confidence
══════════════════════════════════════════════════════════════════════════════
"""

import re
import logging
from urllib.parse import urlparse
from typing import Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# §1  SOURCE CREDIBILITY DATABASE
# ─────────────────────────────────────────────────────────────────────────────

# Score: 0.0 (no credibility) → 1.0 (maximum credibility)
SOURCE_CREDIBILITY_DB = {
    # International wire services (highest tier)
    "reuters.com":           0.95,
    "apnews.com":            0.95,
    "afp.com":               0.92,

    # Major established broadcasters
    "bbc.com":               0.90,
    "bbc.co.uk":             0.90,
    "npr.org":               0.88,
    "pbs.org":               0.88,
    "abc.net.au":            0.85,
    "dw.com":                0.85,
    "france24.com":          0.82,
    "aljazeera.com":         0.80,
    "theguardian.com":       0.82,
    "nytimes.com":           0.82,
    "washingtonpost.com":    0.80,
    "wsj.com":               0.82,
    "ft.com":                0.85,
    "economist.com":         0.87,
    "bloomberg.com":         0.83,

    # Indian outlets
    "thehindu.com":          0.82,
    "hindustantimes.com":    0.72,
    "ndtv.com":              0.74,
    "timesofindia.com":      0.70,
    "indianexpress.com":     0.78,
    "thewire.in":            0.72,
    "scroll.in":             0.70,
    "theprint.in":           0.68,
    "opindia.com":           0.30,
    "postcard.news":         0.15,
    "sudarshannews.in":      0.20,

    # Fact-checkers (authoritative)
    "snopes.com":            0.90,
    "factcheck.org":         0.92,
    "politifact.com":        0.88,
    "annenberg.usc.edu":     0.92,
    "boomlive.in":           0.85,
    "altnews.in":            0.85,
    "factchecker.in":        0.83,
    "vishvasnews.com":       0.80,

    # Government / academic
    "who.int":               0.95,
    "cdc.gov":               0.95,
    "nih.gov":               0.95,
    "un.org":                0.90,
    "nature.com":            0.97,
    "science.org":           0.97,
    "pubmed.ncbi.nlm.nih.gov": 0.96,

    # Known low-credibility / satire / partisan
    "theonion.com":          0.10,  # satire
    "babylonbee.com":        0.10,  # satire
    "infowars.com":          0.05,
    "naturalnews.com":       0.08,
    "beforeitsnews.com":     0.06,
    "worldnewsdailyreport.com": 0.04,
    "yournewswire.com":      0.05,
    "newspunch.com":         0.06,
}

# TLD credibility bonuses/penalties
TLD_SCORES = {
    ".gov": +0.20, ".edu": +0.18, ".org": +0.05,
    ".com": 0.00,  ".net": -0.02, ".info": -0.08,
    ".xyz": -0.15, ".buzz": -0.18, ".click": -0.20,
    ".online": -0.10, ".site": -0.10,
}


def score_source_domain(url: str) -> dict:
    """
    Score a news source domain for credibility.
    Returns score 0-1, tier label, and reason.
    """
    if not url or not url.strip():
        return {"score": 0.5, "tier": "UNKNOWN", "domain": "", "reason": "No URL provided",
                "known_source": False}

    try:
        parsed = urlparse(url if "://" in url else "https://" + url)
        domain = parsed.netloc.lower().lstrip("www.")
    except Exception:
        domain = ""

    # Check exact match
    score = SOURCE_CREDIBILITY_DB.get(domain)
    known = False  # default

    # Check parent domain (e.g. news.bbc.co.uk → bbc.co.uk)
    if score is None:
        parts = domain.split(".")
        for i in range(1, len(parts)):
            parent = ".".join(parts[i:])
            if parent in SOURCE_CREDIBILITY_DB:
                score = SOURCE_CREDIBILITY_DB[parent]
                break

    # TLD adjustment for unknown domains
    if score is None:
        base = 0.45  # unknown domain starts at below-average
        tld = "." + domain.split(".")[-1] if "." in domain else ""
        base += TLD_SCORES.get(tld, 0.0)
        # Very new-looking or suspicious domains
        if len(parts := domain.split(".")) == 2 and len(parts[0]) > 20:
            base -= 0.10
        score = max(0.05, min(base, 0.70))
        reason = f"Unknown domain — estimated from TLD ({tld})"
        known = False
    else:
        known = True
        reason = "Known source in credibility database"

    score = round(max(0.0, min(score, 1.0)), 3)

    if score >= 0.85:
        tier = "HIGHLY CREDIBLE"
    elif score >= 0.70:
        tier = "CREDIBLE"
    elif score >= 0.50:
        tier = "UNCERTAIN"
    elif score >= 0.30:
        tier = "LOW CREDIBILITY"
    else:
        tier = "NOT CREDIBLE"

    return {"score": score, "tier": tier, "domain": domain,
            "reason": reason, "known_source": known}


# ─────────────────────────────────────────────────────────────────────────────
# §2  LINGUISTIC DECEPTION PATTERNS
# ─────────────────────────────────────────────────────────────────────────────

DECEPTION_PATTERNS = {
    "anonymous_sourcing": {
        "patterns": [
            r"\b(sources say|sources claim|sources familiar|unnamed source|anonymous official)\b",
            r"\b(according to sources|insiders say|insiders claim|people familiar with)\b",
            r"\b(officials who (spoke|requested|asked) (on|for) condition of anonymity)\b",
            r"\b(sources in the (government|ministry|administration|party))\b",
        ],
        "weight": 0.18,
        "description": "Anonymous sourcing without verifiable attribution",
        "tactic": "Unverifiable claims — 'sources say' cannot be fact-checked",
        "severity": "HIGH",
    },
    "hedge_certainty": {
        "patterns": [
            r"\b(reportedly|allegedly|supposedly|it is claimed|it is believed)\b",
            r"\b(could be|may have|might have|is said to|is thought to)\b",
            r"\b(unconfirmed reports|rumours suggest|speculation that)\b",
        ],
        "weight": 0.12,
        "description": "Hedge language that implies truth without confirming it",
        "tactic": "Plausible deniability — legally safe but implies falsehood",
        "severity": "MEDIUM",
    },
    "false_certainty": {
        "patterns": [
            r"\b(100%|definitively proven|beyond (any )?doubt|absolutely certain)\b",
            r"\b(everyone knows|it is clear that|obviously|undeniably|it is a fact that)\b",
            r"\b(no one can deny|indisputable|irrefutable proof|slam dunk)\b",
            r"\b(this proves once and for all|case closed|definitively confirmed)\b",
        ],
        "weight": 0.15,
        "description": "Overconfident claims without supporting evidence",
        "tactic": "False certainty — asserts proof without providing it",
        "severity": "HIGH",
    },
    "emotional_framing": {
        "patterns": [
            r"\b(outrage|shocking|bombshell|explosive|scandalous|horrifying)\b",
            r"\b(devastating|alarming|disturbing|appalling|disgusting)\b",
            r"\b(you need to see this|everyone is talking about|goes viral)\b",
            r"\b(jaw.dropping|mind.blowing|unbelievable but true)\b",
        ],
        "weight": 0.14,
        "description": "Emotional amplification to bypass critical thinking",
        "tactic": "Emotional hijacking — triggers reaction before reasoning",
        "severity": "HIGH",
    },
    "misleading_headline": {
        "patterns": [
            r"\?$",                                         # Question headlines (Betteridge's law)
            r"\b(you won.t believe|this changes everything)\b",
            r"\b(what (they|he|she|the media) (won.t|don.t|doesn.t) tell you)\b",
            r"\b(the truth about|the real story|what really happened)\b",
        ],
        "weight": 0.16,
        "description": "Headline designed to mislead rather than inform",
        "tactic": "Clickbait framing — headline implies more than the content proves",
        "severity": "HIGH",
    },
    "false_balance": {
        "patterns": [
            r"\b(some people say|on the other hand|both sides|equally valid)\b",
            r"\b(experts are divided|scientists disagree|controversy surrounding)\b",
            r"\b(not everyone agrees|debated by experts|mixed views)\b",
        ],
        "weight": 0.10,
        "description": "Presenting fringe views as equally valid to scientific consensus",
        "tactic": "False equivalence — gives equal weight to unequal claims",
        "severity": "MEDIUM",
    },
    "selective_omission": {
        "patterns": [
            r"\b(but (failed|forgot|refused|declined) to mention)\b",
            r"\b(left out|omitted|ignored|conveniently (forgot|skipped|omitted))\b",
            r"\b(what (the|they|media) (didn.t|won.t|refuses to) (report|tell|say))\b",
            r"\b(buried in the (article|report|story|piece))\b",
        ],
        "weight": 0.12,
        "description": "Intentional omission of context that would change the meaning",
        "tactic": "Context stripping — true facts presented without essential context",
        "severity": "HIGH",
    },
    "fabricated_attribution": {
        "patterns": [
            r"\b(never (said|stated|claimed|tweeted|wrote) (that|this))\b",
            r"\b(quote (is|was) (taken out of context|misattributed|fabricated))\b",
            r"\b(fake (quote|screenshot|video|image|audio))\b",
            r"\b(deepfake|manipulated (video|image|audio|photo))\b",
            r"\b(photoshopped|doctored|edited to (show|suggest|imply))\b",
        ],
        "weight": 0.25,
        "description": "Fabricated or manipulated quotes, images, or videos",
        "tactic": "Direct fabrication — putting words/actions in people's mouths",
        "severity": "CRITICAL",
    },
}

# Compiled patterns
_COMPILED_PATTERNS = {
    tactic: {
        "compiled": [re.compile(p, re.I | re.M) for p in data["patterns"]],
        **{k: v for k, v in data.items() if k != "patterns"},
    }
    for tactic, data in DECEPTION_PATTERNS.items()
}


def detect_deception_tactics(text: str, headline: str = "") -> dict:
    """
    Scan text + headline for deception patterns.
    Returns list of detected tactics, overall deception score, and trust verdict.
    """
    full_text = (headline + " " + text).strip() if headline else text
    detected  = []
    raw_score = 0.0

    for tactic_name, data in _COMPILED_PATTERNS.items():
        hits = []
        for pat in data["compiled"]:
            matches = pat.findall(full_text)
            for m in matches:
                fragment = (m if isinstance(m, str) else " ".join(m)).strip()[:50]
                if fragment and fragment.lower() not in [h.lower() for h in hits]:
                    hits.append(fragment)

        if hits:
            raw_score += data["weight"] * min(len(hits), 3)
            detected.append({
                "tactic":      tactic_name,
                "label":       tactic_name.replace("_", " ").title(),
                "description": data["description"],
                "explanation": data["tactic"],
                "severity":    data["severity"],
                "examples":    hits[:2],
                "weight":      data["weight"],
            })

    # Sort by severity then weight
    sev_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    detected.sort(key=lambda x: (sev_order.get(x["severity"], 9), -x["weight"]))

    deception_score = round(min(raw_score, 1.0), 3)

    if deception_score >= 0.70:
        verdict = "HIGHLY DECEPTIVE"
        verdict_color = "#f87171"
        verdict_icon  = "🔴"
    elif deception_score >= 0.45:
        verdict = "LIKELY DECEPTIVE"
        verdict_color = "#fb923c"
        verdict_icon  = "🟠"
    elif deception_score >= 0.25:
        verdict = "SUSPICIOUS"
        verdict_color = "#facc15"
        verdict_icon  = "🟡"
    elif deception_score >= 0.10:
        verdict = "MINOR CONCERNS"
        verdict_color = "#a3e635"
        verdict_icon  = "🟡"
    else:
        verdict = "APPEARS HONEST"
        verdict_color = "#4ade80"
        verdict_icon  = "🟢"

    return {
        "deception_score":  deception_score,
        "verdict":          verdict,
        "verdict_icon":     verdict_icon,
        "verdict_label":    f"{verdict_icon} {verdict}",
        "verdict_color":    verdict_color,
        "tactics_detected": detected,
        "tactic_count":     len(detected),
    }


# ─────────────────────────────────────────────────────────────────────────────
# §3  CREDIBILITY SIGNALS (positive indicators)
# ─────────────────────────────────────────────────────────────────────────────

CREDIBILITY_SIGNALS = [
    (r"\b(according to (the )?(who|cdc|fda|nih|un|nasa|cern|icrc))\b",
     "Cites authoritative institution", 0.12),
    (r"\b(peer.?reviewed|published in|journal of|lancet|nature|science|jama|nejm|bmj)\b",
     "References peer-reviewed publication", 0.15),
    (r"\b(study of \d+|based on \d{3,}|sample size|clinical trial|randomized)\b",
     "Cites specific study methodology", 0.12),
    (r"\bhttps?://[^\s]+(\.gov|\.edu)[^\s]*",
     "Links to .gov or .edu source", 0.10),
    (r"\b(spokesperson|press release|official statement|on the record|confirmed by)\b",
     "Named, on-record attribution", 0.10),
    (r"\b(correction|update|editor.s note|this story has been updated)\b",
     "Transparent about corrections", 0.08),
    (r"\b(data from|statistics show|according to the report|the document states)\b",
     "References primary documents", 0.10),
]

_CRED_RE = [(re.compile(p, re.I), desc, w) for p, desc, w in CREDIBILITY_SIGNALS]


def detect_credibility_signals(text: str) -> dict:
    """Find positive credibility indicators in text."""
    found  = []
    score  = 0.0
    for pat, desc, w in _CRED_RE:
        if pat.search(text):
            found.append({"signal": desc, "weight": w})
            score += w
    return {
        "credibility_boost": round(min(score, 0.50), 3),
        "signals_found":     found,
        "signal_count":      len(found),
    }


# ─────────────────────────────────────────────────────────────────────────────
# §4  HEADLINE vs BODY MISMATCH DETECTOR
# ─────────────────────────────────────────────────────────────────────────────

def check_headline_body_mismatch(headline: str, body: str) -> dict:
    """
    Check if headline makes stronger claims than the body supports.
    A classic news manipulation tactic: sensational headline, hedged body.
    """
    if not headline or not body:
        return {"mismatch_detected": False, "mismatch_score": 0.0, "reason": "Insufficient data"}

    headline_l = headline.lower()
    body_l     = body.lower()

    signals = []
    mismatch_score = 0.0

    # Headline is question, body is not a confirmed answer
    if headline.strip().endswith("?"):
        signals.append("Headline poses question but body may not answer it definitively")
        mismatch_score += 0.20

    # Headline uses certainty words, body uses hedge words
    headline_certain = bool(re.search(
        r"\b(confirms|proves|reveals|exposes|admits|caught|busted|definitive)\b",
        headline_l))
    body_hedged = bool(re.search(
        r"\b(allegedly|reportedly|supposedly|unconfirmed|sources say|may have)\b",
        body_l))
    if headline_certain and body_hedged:
        signals.append("Headline claims certainty but body uses hedge language")
        mismatch_score += 0.35

    # Headline names people, body contradicts
    exclamation_headline = "!" in headline
    if exclamation_headline:
        signals.append("Sensational punctuation in headline suggests emotional bait")
        mismatch_score += 0.10

    # Headline has numbers, body doesn't support them
    headline_nums = re.findall(r"\b\d+[%xX]?\b", headline)
    body_nums     = re.findall(r"\b\d+[%xX]?\b", body)
    for n in headline_nums:
        if n not in body_nums and int(re.sub(r"\D","",n) or "0") > 10:
            signals.append(f"Headline statistic '{n}' not found in body text")
            mismatch_score += 0.15
            break

    # Headline all caps
    caps_ratio = sum(1 for c in headline if c.isupper()) / max(len(headline), 1)
    if caps_ratio > 0.5:
        signals.append("Headline uses excessive capitalisation (emotional manipulation)")
        mismatch_score += 0.12

    mismatch_score = round(min(mismatch_score, 1.0), 3)

    return {
        "mismatch_detected": mismatch_score >= 0.20,
        "mismatch_score":    mismatch_score,
        "signals":           signals,
        "reason":            signals[0] if signals else "No mismatch detected",
    }


# ─────────────────────────────────────────────────────────────────────────────
# §5  FULL CREDIBILITY ANALYSIS  (main entry point)
# ─────────────────────────────────────────────────────────────────────────────

def analyze_credibility(
    text: str,
    headline: str = "",
    source_url: str = "",
) -> dict:
    """
    Full media credibility analysis.

    Args:
        text       : Article body text
        headline   : Article headline (optional but recommended)
        source_url : URL of the source (for domain credibility scoring)

    Returns a comprehensive dict with all credibility sub-analyses.
    """
    full_text = (headline + " " + text).strip() if headline else text

    # 1. Source domain credibility
    source = score_source_domain(source_url)

    # 2. Deception tactic detection
    deception = detect_deception_tactics(text, headline)

    # 3. Credibility signals
    cred_signals = detect_credibility_signals(full_text)

    # 4. Headline mismatch
    mismatch = check_headline_body_mismatch(headline, text)

    # 5. Composite trust score
    # Source credibility is the strongest signal; deception patterns penalise it
    base     = source["score"] * 0.55                         # 55% from source reputation
    decp_pen = deception["deception_score"] * 0.30            # 30% deception penalty
    cred_bst = cred_signals["credibility_boost"] * 0.15       # 15% credibility boost
    mism_pen = mismatch["mismatch_score"] * 0.08              # small mismatch penalty

    trust_score = round(max(0.0, min(base - decp_pen + cred_bst - mism_pen, 1.0)), 3)

    if trust_score >= 0.72:
        trust_verdict = "TRUSTWORTHY"
        trust_icon    = "✅"
        trust_color   = "#4ade80"
    elif trust_score >= 0.52:
        trust_verdict = "PARTIALLY RELIABLE"
        trust_icon    = "⚠️"
        trust_color   = "#facc15"
    elif trust_score >= 0.32:
        trust_verdict = "UNRELIABLE"
        trust_icon    = "🟠"
        trust_color   = "#fb923c"
    else:
        trust_verdict = "DO NOT TRUST"
        trust_icon    = "🚫"
        trust_color   = "#f87171"

    # 6. Plain-language explanation of HOW it deceives
    how_it_deceives = _build_deception_explanation(
        deception, mismatch, source, cred_signals
    )

    # 7. Fact-check recommendations
    fact_check_steps = _build_fact_check_steps(deception, source, mismatch)

    return {
        "trust_score":        trust_score,
        "trust_verdict":      trust_verdict,
        "trust_icon":         trust_icon,
        "trust_label":        f"{trust_icon} {trust_verdict}",
        "trust_color":        trust_color,
        "source":             source,
        "deception":          deception,
        "credibility_signals": cred_signals,
        "headline_mismatch":  mismatch,
        "how_it_deceives":    how_it_deceives,
        "fact_check_steps":   fact_check_steps,
        "headline":           headline[:200] if headline else "",
        "source_url":         source_url,
    }


def _build_deception_explanation(
    deception: dict, mismatch: dict, source: dict, cred: dict
) -> list:
    """Build human-readable explanation of the specific deception methods used."""
    explanations = []

    if source["score"] < 0.40:
        explanations.append(
            f"🌐 The source domain '{source['domain']}' has very low credibility "
            f"(score: {round(source['score']*100)}%). This outlet has a history of publishing "
            "misleading or fabricated content."
        )
    elif source["score"] < 0.60 and not source["known_source"]:
        explanations.append(
            f"🌐 '{source['domain']}' is an unknown domain. Always verify news from "
            "unfamiliar sources against established outlets like Reuters, AP, or BBC."
        )

    for tactic in deception["tactics_detected"][:4]:
        name = tactic["label"]
        expl = tactic["explanation"]
        ex   = tactic["examples"]
        ex_str = f" (e.g. \"{ex[0]}\")" if ex else ""
        explanations.append(f"⚠️ **{name}**: {expl}{ex_str}")

    if mismatch["mismatch_detected"]:
        explanations.append(
            f"📰 **Headline–Body Mismatch**: {mismatch['reason']}. "
            "This is a common tactic — a sensational headline gets shared widely "
            "while the body quietly hedges the claim."
        )

    if cred["signal_count"] == 0:
        explanations.append(
            "📋 **No credibility signals found**: The article cites no named sources, "
            "no institutional references, and no primary documents."
        )

    if not explanations:
        explanations.append(
            "✅ No major deception tactics detected. The content uses standard journalistic language."
        )

    return explanations


def _build_fact_check_steps(
    deception: dict, source: dict, mismatch: dict
) -> list:
    """Practical fact-checking steps tailored to what was detected."""
    steps = [
        "🔍 Search the exact claim on Reuters, AP News, and BBC. If none of them report it, treat it as unverified.",
        "📸 Reverse-image-search any photos using Google Images (images.google.com).",
    ]

    tactics = {t["tactic"] for t in deception["tactics_detected"]}

    if "anonymous_sourcing" in tactics:
        steps.append("👤 The story uses anonymous sources. Ask: what named officials or documents support this claim?")
    if "fabricated_attribution" in tactics:
        steps.append("🎙️ Check quoted statements on the speaker's official website, verified social media, or press releases.")
    if mismatch.get("mismatch_detected"):
        steps.append("📰 Read the full article — the headline may be stronger than what the body actually proves.")
    if source["score"] < 0.55:
        steps.append(f"🌐 Verify this with a higher-credibility source (BBC, Reuters, AP). The origin site '{source['domain']}' is not well established.")
    if "emotional_framing" in tactics:
        steps.append("😤 The emotional tone is high. Ask yourself: am I being made to feel something before I can think clearly?")

    steps.append("📅 Check the publication date — old stories are often recycled with new headlines.")
    steps.append("✅ Use fact-checkers: Snopes.com, FactCheck.org, PolitiFact, or AltNews.in (India).")

    return steps