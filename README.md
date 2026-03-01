# The-Fifth-Element

# 📡 MisinfoRadar v3 — Propagation Intelligence Engine

> **Real-time misinformation detection, emotion analysis, and viral spread simulation for news articles and social media content.**

---

## 🧭 Overview

MisinfoRadar v3 is a full-stack web application that analyses any piece of text or news article URL and instantly determines:

- Whether it is likely misinformation or credible content
- The dominant emotion it triggers (fear, anger, joy, sadness, disgust, surprise, neutral)
- How virally it is likely to spread across a social network
- What category of news it belongs to (politics, health, crime, finance, etc.)
- Actionable recommendations for moderators and fact-checkers

The system combines **rule-based NLP**, optional **transformer models** (HuggingFace), and **graph-based network simulation** (NetworkX SIR model) to produce a comprehensive propagation risk report — all accessible through a sleek dark-themed web interface.

---

## ✨ Features

### 🔍 Input Methods
| Method | Description |
|---|---|
| **Plain Text** | Paste any news article, tweet, social media post, or headline |
| **URL Scraping** | Paste any article URL — text is automatically extracted using `newspaper3k` + BeautifulSoup fallback |
| **File Upload** | Upload `.txt`, `.csv`, or `.json` files containing articles or datasets |
| **Live RSS Feeds** | Pull real-time headlines from BBC World, Reuters, AP News, The Guardian, Al Jazeera, NPR |

### 🧠 Analysis Pipeline
| Stage | What It Does |
|---|---|
| **Language Detection** | Detects the language using `langdetect`; auto-translates non-English text via `deep-translator` |
| **Text Preprocessing** | Cleans URLs, mentions, hashtags, normalises unicode, removes noise |
| **Emotion Detection** | Classifies text into 7 emotions — joy, fear, anger, sadness, surprise, disgust, neutral — using a DistilBERT transformer (falls back to keyword rules if unavailable) |
| **Misinformation Detection** | Scores content using a RoBERTa fake-news classifier + 11 red-flag pattern rules (falls back to rules-only if transformer unavailable) |
| **Virality Scoring** | Computes a 0–1 virality score weighted by emotion amplifier, misinfo probability, URL presence, and text length |
| **Network Simulation** | Builds a directed social graph (Scale-Free / Small-World / Random) using NetworkX and runs a SIR epidemic simulation to model how far the content would spread |
| **Risk Scoring** | Combines virality, network density, clustering, and misinfo score into a final propagation risk score |
| **News Categorisation** | Classifies content into 10 categories: Sports, Entertainment, Finance, Politics, National, International, Science & Tech, Crime & Law, Health, Environment |

### 📊 Dashboard & Visualisations
- **Risk Gauge** — arc-style gauge showing overall propagation risk (MINIMAL → CRITICAL)
- **Emotion Bar Chart** — proportional colour-coded bars per emotion, each with a unique colour
- **Virality Timeline** — step-by-step SIR spread simulation graph
- **Misinfo Donut** — probability ring chart
- **Graph Metrics** — nodes, edges, density, clustering coefficient, largest connected component, top influencer nodes
- **News Category Card** — primary + secondary category match with confidence scores
- **Red Flag Chips** — detected misinformation phrases highlighted
- **Recommendations Panel** — actionable moderation steps based on risk tier

### 🛡️ Risk Tiers
| Score | Tier | Action |
|---|---|---|
| ≥ 0.80 | 🔴 CRITICAL | Immediate intervention required |
| ≥ 0.65 | 🟠 HIGH | Flag and escalate for review |
| ≥ 0.45 | 🟡 MODERATE | Attach a contextual warning label |
| ≥ 0.25 | 🟢 LOW | Standard monitoring sufficient |
| < 0.25 | ⚪ MINIMAL | No special action required |

### 📬 Feedback System
- Built-in feedback form with name, email, category, star rating, and message fields
- Sends feedback **directly** to the admin inbox via Gmail SMTP — no third-party service required
- Flask `/feedback` POST endpoint handles delivery server-side

### ℹ️ About Page
- Modal popup with platform description, feature list, and contact details
- Accessible from the top navigation bar

---

## 🗂️ Project Structure

```
misinforadar-v3/
│
├── core.py              # All intelligence logic — NLP, emotion, misinfo, graph, simulation
├── app.py               # Flask REST API server — /analyze, /fetch, /feedback endpoints
├── index.html           # Full frontend — single-file HTML/CSS/JS dark UI
└── README.md
```

### `core.py` — The Brain
The shared core module that every other component imports from. Contains:
- `fetch_url()` — scrape and extract article text from any URL
- `fetch_rss_feed()` — pull live headlines from major news RSS feeds
- `parse_uploaded_file()` — parse `.txt`, `.csv`, `.json` uploads
- `preprocess_text()` — language detection, translation, cleaning
- `detect_emotion()` — transformer + rule-based emotion classification
- `detect_misinformation()` — transformer + pattern-based fake news scoring
- `build_network()` — generate Scale-Free / Small-World / Random directed graphs
- `simulate_spread()` — SIR epidemic simulation on the network
- `graph_metrics()` — compute density, clustering, degree, influencer nodes
- `predict_propagation()` — full end-to-end pipeline returning complete analysis dict
- SVG chart generators for server-side rendering

### `app.py` — The Server
Flask REST API with CORS support and three endpoints:

| Endpoint | Method | Description |
|---|---|---|
| `/analyze` | POST | Runs full propagation analysis on submitted text |
| `/fetch` | POST | Fetches and extracts article text from a given URL |
| `/feedback` | POST | Receives feedback form data and sends it via Gmail SMTP |

### `index.html` — The Interface
A fully self-contained single-file frontend built with vanilla HTML, CSS, and JavaScript. Features:
- Dark space-themed UI with animated grid background, glowing orbs, and smooth transitions
- Tab-based input (Text / URL)
- Real-time animated loading with step-by-step status messages
- Canvas-based chart rendering (emotion bars, risk gauge, timeline)
- About modal, Feedback section, and full results dashboard
- Client-side rule-based analysis engine (works standalone without the backend)
- URL fetching via CORS proxy when backend is not running

---

## 🚀 Getting Started

### Prerequisites
```bash
Python 3.9+
pip
```

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/misinforadar-v3.git
cd misinforadar-v3

# 2. Install required packages
pip install flask flask-cors networkx langdetect deep-translator \
            beautifulsoup4 newspaper3k requests

# 3. (Optional) Install transformer models for higher accuracy
pip install transformers torch
```

### Configuration

Open `app.py` and set your Gmail credentials to enable the feedback email feature:

```python
SMTP_USER = "thffthlmnt@gmail.com"
SMTP_PASS = "your_gmail_app_password"   # Generate at myaccount.google.com/apppasswords
```

> **Note:** Gmail App Passwords require 2-Step Verification to be enabled on the account.

### Running the Server

```bash
python app.py
```

The API will be available at `http://localhost:5000`.

Open `index.html` in your browser. The frontend automatically connects to the Flask backend for URL fetching and feedback. The analysis engine also runs fully client-side as a fallback.

---

## 🔌 API Reference

### `POST /analyze`
Run full propagation analysis on a piece of text.

**Request:**
```json
{
  "text": "BREAKING!!! Doctors HATE this secret cure...",
  "network": "scale_free"
}
```
`network` options: `scale_free` | `small_world` | `random`

**Response:**
```json
{
  "input":          { "lang_name": "English", "was_translated": false },
  "emotion":        { "dominant_emotion": "fear", "emotion_scores": {...}, "virality_amplifier": 0.9 },
  "misinformation": { "label": "LIKELY FAKE", "misinfo_probability": 0.78, "red_flags": [...] },
  "virality_score": 0.72,
  "risk_score":     0.81,
  "risk_tier":      { "label": "🔴 CRITICAL", "description": "Immediate intervention required." },
  "graph_metrics":  { "nodes": 200, "edges": 412, "density": 0.021, ... },
  "simulation":     { "total_infected": 174, "reach_pct": 87.0, "timeline": [...] },
  "recommendations": ["🚨 Flag for fact-checker review...", "📊 Deploy counter-narrative..."]
}
```

### `POST /fetch`
Extract article text from a URL.

**Request:**
```json
{ "url": "https://www.bbc.com/news/world-12345678" }
```

**Response:**
```json
{
  "ok": true,
  "text": "Full article text...",
  "title": "Article Title",
  "source": "https://..."
}
```

### `POST /feedback`
Send user feedback directly to the admin email.

**Request:**
```json
{
  "name":     "John Doe",
  "email":    "john@example.com",
  "category": "Bug Report",
  "rating":   "★★★★☆",
  "message":  "The URL tab doesn't work on paywalled sites."
}
```

**Response:**
```json
{ "ok": true }
```

---

## 🤖 ML Models Used

| Task | Model | Fallback |
|---|---|---|
| Emotion Detection | `bhadresh-savani/distilbert-base-uncased-emotion` | Keyword rule engine |
| Misinformation Detection | `hamzab/roberta-fake-news-classification` | Pattern matching (11 rules) |
| Language Detection | `langdetect` library | Defaults to English |
| Translation | `deep-translator` (Google Translate) | Returns original text |

> Both transformer models are **optional**. The system fully operates using the built-in rule-based engines if `transformers` / `torch` are not installed — making it lightweight and easy to deploy.

---

## 🌐 Supported Languages

English, Hindi, French, German, Spanish, Arabic, Chinese, Portuguese, Russian, Italian — and any language supported by Google Translate. Non-English content is auto-detected and translated before analysis.

---

## 📦 Dependencies

| Package | Purpose |
|---|---|
| `flask` | REST API server |
| `flask-cors` | Cross-origin request support |
| `networkx` | Social graph construction and metrics |
| `langdetect` | Language identification |
| `deep-translator` | Multi-language translation |
| `beautifulsoup4` | HTML parsing and text extraction |
| `newspaper3k` | Article extraction from URLs |
| `transformers` | HuggingFace transformer models (optional) |
| `torch` | PyTorch runtime for transformers (optional) |

---

## 📸 Screenshots

| Input | Results Dashboard |
|---|---|
| Text / URL input with network selector | Risk gauge, emotion bars, virality timeline |
| Live loading animation with step labels | Category card, graph metrics, recommendations |

---

## 📄 License

MIT License — free to use, modify, and distribute.

---

## 👤 Contact

**The Fifth Element**
📧 thffthlmnt@gmail.com

---

*Built with Python, Flask, NetworkX, HuggingFace Transformers, and vanilla JavaScript.*
