<p align="center">
  <h1 align="center">🛡️ FraudShield AI</h1>
  <p align="center"><strong>Real-Time Fraud Detection for the Unbanked</strong></p>
  <p align="center">
    Case Study 2 — ML Track (Fraud & Anomaly Detection) • SDG 8.10 Financial Inclusion
  </p>
</p>

---

## 📌 Overview

FraudShield AI is a **3-layer ensemble fraud detection system** designed to protect ASEAN e-wallet users — especially the unbanked population — from digital fraud in real time. It combines supervised ML, unsupervised anomaly detection, and interpretable rule-based scoring into a single < 100ms API, backed by SHAP explainability and privacy-first PII handling.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Incoming Transaction                      │
│                          │                                  │
│            ┌─────────────┼─────────────┐                    │
│            ▼             ▼             ▼                    │
│   ┌────────────┐ ┌─────────────┐ ┌──────────────┐          │
│   │  LightGBM  │ │   PyOD      │ │  Behavioral  │          │
│   │ Supervised │ │ Iso-Forest  │ │   Profiler   │          │
│   │   (55%)    │ │   (25%)     │ │    (20%)     │          │
│   └─────┬──────┘ └──────┬──────┘ └──────┬───────┘          │
│         └────────────────┼──────────────┘                   │
│                    Score Fusion                             │
│                     │       │                               │
│              ┌──────┼───────┼──────┐                        │
│              ▼      ▼       ▼      ▼                        │
│          APPROVE   FLAG   BLOCK  + SHAP Reasons             │
└─────────────────────────────────────────────────────────────┘
```

| Layer | Model | Purpose |
|---|---|---|
| **Layer 1** | LightGBM Classifier | Learns known fraud patterns from labeled data |
| **Layer 2** | PyOD Isolation Forest | Detects novel/unseen fraud as anomalies (zero-day) |
| **Layer 3** | Behavioral Profiler | Interpretable rule-based risk from domain logic |

---

## 📊 Case Study Requirements Mapping

| Requirement | Our Solution | Status |
|---|---|---|
| **Develop ML model** for real-time fraud detection | 3-layer ensemble (LightGBM + PyOD + Behavioral) trained on 2M transactions | ✅ |
| **Achieve < 100ms latency** | API latency ~34ms avg (measured via internal timer) | ✅ |
| **Minimize false positives** (target < 2% FPR) | 0.00% FPR on test set (4,500 fraud / 295,500 legit) | ✅ |
| **Maximize fraud detection rate** (recall) | 99.96% recall on test set | ✅ |
| **Explainability** — why a transaction was flagged | SHAP TreeExplainer provides per-feature risk contributions | ✅ |
| **Privacy & data protection** (SDG 8.10) | SHA-256 PII hashing before inference + differential privacy for aggregates | ✅ |
| **Handle class imbalance** (~1.5% fraud rate) | SMOTE resampling + stratified splits preserve fraud distribution | ✅ |
| **Data leakage prevention** | Dropped `session_duration_seconds` (AUC=1.0) and `recipient_risk_profile_score` (AUC=0.94) | ✅ |
| **Feature engineering** | 10 engineered features (velocity score, drain detection, temporal risk, etc.) | ✅ |
| **Demo / visualization** | Interactive glassmorphic dashboard with live scoring stream | ✅ |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- `data/ewallet_transaction.csv` in the project root

### 1. Install Dependencies

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
.\venv\Scripts\activate
# Activate (macOS/Linux)
source venv/bin/activate

# Install packages
pip install -r requirements.txt
```

### 2. Train the Models

```bash
set PYTHONPATH=.          # Windows
export PYTHONPATH=.       # Linux/macOS

python -m src.model_training --evaluate
```

This will:
- Load & preprocess 2M rows from `data/ewallet_transaction.csv`
- Drop leaked features (`session_duration_seconds`, `recipient_risk_profile_score`)
- Engineer 10 new features
- Train LightGBM (SMOTE + early stopping) and PyOD Isolation Forest
- Evaluate the full ensemble on a held-out test set
- Save models to `models/` and metrics to `models/metrics_report.txt`

### 3. Start the API Server

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

The API will:
- Load models and SHAP explainer
- Warm up SHAP to eliminate cold-start latency
- Serve requests on `http://localhost:8000`
- Auto-generate API docs at `http://localhost:8000/docs`

### 4. Open the Dashboard

Open `dashboard/index.html` in your browser. It will:
- Connect to the API at `http://localhost:8000`
- Simulate live transactions every 1.2 seconds
- Show real-time scoring, risk gauge, per-layer breakdown, and SHAP reasons

---

## 🐳 Docker

```bash
# Build
docker build -t fraudshield-ai .

# Run (models must be pre-trained and in models/)
docker run -p 8000:8000 fraudshield-ai
```

> **Note:** The Dockerfile assumes models are already trained and present in `models/`. Run the training step locally first, then build the Docker image.

---

## 📁 Project Structure

```
vhack/
├── api/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application + endpoints
│   ├── schemas.py              # Pydantic request/response models
│   └── risk_engine.py          # Real-time inference pipeline
├── src/
│   ├── __init__.py
│   ├── data_preprocessing.py   # Data loading, cleaning, stratified splits
│   ├── feature_engineering.py  # 10 engineered features + transforms
│   ├── model_training.py       # LightGBM + PyOD + ensemble training
│   ├── behavioral_profiler.py  # Rule-based interpretable risk scoring
│   ├── score_fusion.py         # Weighted ensemble score combination
│   ├── privacy_module.py       # SHA-256 PII hashing + differential privacy
│   └── explainability.py       # SHAP-based feature attribution
├── dashboard/
│   ├── index.html              # Live demo dashboard
│   ├── style.css               # Glassmorphic dark-mode styling
│   └── app.js                  # Real-time transaction simulation
├── models/                     # Saved model artifacts (after training)
├── data/                       # Dataset (not committed to git)
├── requirements.txt
├── Dockerfile
├── .gitignore
└── README.md
```

---

## 🔌 API Endpoints

### `POST /api/v1/score-transaction`

Score a single transaction in real time.

**Request Body:**
```json
{
  "transaction_id": "TXN_1234",
  "name_sender": "C12345",
  "name_recipient": "M67890",
  "transfer_type": "CASH_OUT",
  "amount": 4500.00,
  "avg_transaction_amount_30d": 50.0,
  "amount_vs_avg_ratio": 90.0,
  "transaction_hour": 3,
  "is_weekend": 1,
  "is_new_device": 1,
  "failed_login_attempts": 3,
  "is_proxy_ip": 1,
  "ip_risk_score": 0.92,
  "sender_account_fully_drained": 1,
  "account_age_days": 5,
  "tx_count_24h": 12,
  "country_mismatch": 1,
  "is_new_recipient": 1,
  "established_user_new_recipient": 0
}
```

**Response:**
```json
{
  "transaction_id": "TXN_1234",
  "risk_score": 0.9984,
  "decision": "BLOCK",
  "layer_scores": {
    "lightgbm": 1.0,
    "isolation_forest": 1.0,
    "behavioral": 0.992
  },
  "reasons": [
    "Account fully drained to new recipient",
    "Amount significantly exceeds user's 30-day average",
    "High risk contribution from: IP Reputation Score",
    "High risk contribution from: Amount vs Historical Average"
  ],
  "privacy": {
    "pii_hashed": true,
    "hash_algorithm": "SHA-256",
    "dp_applied": false
  },
  "latency_ms": 34.21
}
```

### `GET /api/v1/health`

Returns API health status and model loading state.

### `GET /api/v1/dashboard-stats`

Returns aggregate statistics for the dashboard (totals, avg latency, fraud rate).

---

## 🔒 Privacy & Compliance

| Mechanism | Implementation |
|---|---|
| **PII Hashing** | SHA-256 with salt applied to sender/recipient names *before* any model inference |
| **Differential Privacy** | Laplace noise (ε=5.0) available for aggregate exports |
| **No Raw PII in Models** | Identity columns dropped during preprocessing; model never sees raw names |
| **PDPA/GDPR Ready** | Hashed identifiers support right-to-erasure; audit trail in API logs |

---

## 🧠 Data Leakage Analysis

Two features were removed after thorough analysis:

| Feature | AUC | Reason for Removal |
|---|---|---|
| `session_duration_seconds` | **1.0000** | Perfect separator — fraud sessions always ~22s vs legit ~359s. Impossible in practice. |
| `recipient_risk_profile_score` | **0.9409** | Likely derived from fraud labels — only 520 unique values with strong correlation. |

Additionally, raw `amount` and `avg_transaction_amount_30d` are **log-transformed and dropped** to prevent scale dominance.

---

## 🛠️ Tech Stack

| Component | Technology |
|---|---|
| ML Classifier | LightGBM |
| Anomaly Detection | PyOD (Isolation Forest) |
| Explainability | SHAP (TreeExplainer) |
| API Framework | FastAPI + Uvicorn |
| Dashboard | HTML/CSS/JS + Chart.js |
| Data Processing | Pandas + NumPy |
| Imbalance Handling | SMOTE (imbalanced-learn) |
| Privacy | SHA-256 hashing + Laplace noise |

---

## 📊 Performance Metrics

| Metric | Value | Target |
|---|---|---|
| Ensemble AUC-PR | 1.0000 | ≥ 0.80 |
| Fraud Detection Rate (Recall) | 99.96% | ≥ 85% |
| False Positive Rate | 0.00% | ≤ 2.0% |
| Max F1 Score | 0.9999 | ≥ 0.70 |
| API Latency (avg) | ~34ms | < 100ms |

---

<p align="center">
  Built with ❤️ for vHack 2026 — Protecting the unbanked, one transaction at a time.
</p>
