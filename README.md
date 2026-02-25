

# MarketPulse
MarketPulse is an AI-ready market structure engine that transforms real-time A-share data into structured market-state signals for agents, analytics, and narrative understanding.

> A Market Structure Analyzer for A-share markets.  
> Structured market-state JSON for AI agents.

[中文说明](README_CN.md)

---

## 🚀 Overview

**market-state** is an OpenClaw skill designed to:

- Fetch real-time A-share market snapshots
- Transform raw data into structured JSON
- Enable AI agents to reason about market structure

This project **IS**:

- ✔ market structure extraction
- ✔ breadth & sentiment measurement
- ✔ liquidity concentration analysis
- ✔ foundation for Narrative Market Agent

---

## 🧠 Motivation

Most AI finance pipelines:

````

news → sentiment → narrative

```

This project focuses on:

```

market structure → data → regime analysis

```

Core idea:

> The market itself is the signal.

---

## 🧱 Architecture

```

Chat / Feishu
↓
OpenClaw Agent
↓
market-state skill (SKILL.md)
↓
exec market_state.py
↓
AKShare data
↓
Structured JSON output

````

---

## 📊 Output Components

### 1️⃣ Market Breadth

```json
{
  "advance": 4000+,
  "decline": 1000+,
  "flat": 80+
}
````

Used for:

* overall sentiment
* expansion vs contraction

---

### 2️⃣ Return Distribution

```json
{
  "p10": -1.8,
  "p50": 1.2,
  "p90": 4.4
}
```

Used for:

* broad rally detection
* concentration analysis

---

### 3️⃣ Liquidity Structure

* turnover quantiles
* top turnover stocks

Used for:

* capital concentration detection
* narrative candidates

---

### 4️⃣ Extreme Moves

Approximate:

* limit up count
* limit down count

Used for:

* emotional extremes detection

---

## 📦 JSON Schema

```json
{
  "meta": {},
  "shape": {},
  "columns": [],
  "summary": {
    "breadth": {},
    "pct_chg_quantiles": {},
    "turnover_quantiles": {},
    "limit_up_like": "",
    "limit_down_like": "",
    "top_turnover": []
  }
}
```

---

## 🔐 Skill Constraints

The SKILL.md enforces:

* Raw JSON output only
* No field renaming
* No hallucinated data
* No prediction
* No investment advice

All summaries must reference existing JSON fields.

---

## 🧪 Installation

```bash
git clone <repo_url>
cd market-state-skill
pip install akshare pandas numpy
```

---

## ▶️ Run Locally

```bash
python market_state.py
```

or:

```bash
python market_state.py hs_a
```

---

## 🤖 OpenClaw Integration

Place skill:

```
~/.openclaw/skills/market-state
```

Check:

```bash
openclaw skills list --eligible
```

Trigger via agent:

```
use market-state skill with hs_a
```

---

## 📈 Current Capability

* market structure JSON
* breadth analysis
* liquidity analysis

---

## 🚧 Roadmap

### Phase 1

* [x] market structure extraction
* [x] OpenClaw integration
* [x] Feishu support

### Phase 2

* [ ] index anchor layer
* [ ] industry structure
* [ ] market regime classification

### Phase 3

* [ ] Narrative Market Agent
* [ ] narrative inference
* [ ] multi-day memory

---

## ⚠️ Known Issues

* Eastmoney API may disconnect (fallback enabled)
* Different data sources → different columns
* LLM must be constrained to avoid hallucination

