from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from api.schemas import TransactionInput, RiskResponse, DashboardStats
from api.risk_engine import RiskEngine
import uvicorn
import logging
import asyncio
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="FraudShield AI API",
    description="Real-Time Fraud Detection for ASEAN E-Wallets",
    version="1.0.0"
)

# Enable CORS for the dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global engine instance
engine = None

# Simple stats tracking for dashboard
stats = {
    "total": 0,
    "approve": 0,
    "flag": 0,
    "block": 0,
    "latency_sum": 0.0
}

@app.on_event("startup")
async def startup_event():
    global engine
    logger.info("Initializing Risk Engine and loading models...")
    engine = RiskEngine()

@app.get("/api/v1/health")
def health_check():
    return {"status": "healthy", "models_loaded": engine.lgb_model is not None}

@app.post("/api/v1/score-transaction", response_model=RiskResponse)
async def score_transaction(txn: TransactionInput):
    if not engine:
        raise HTTPException(status_code=503, detail="Risk Engine not initialized")
        
    response = engine.predict(txn)
    
    # Update stats
    stats["total"] += 1
    stats[response.decision.lower()] += 1
    stats["latency_sum"] += response.latency_ms
    
    return response

@app.get("/api/v1/dashboard-stats", response_model=DashboardStats)
def get_dashboard_stats():
    total = max(stats["total"], 1)
    fraud_rate = (stats["block"] + stats["flag"]) / total * 100
    
    return DashboardStats(
        total_transactions=stats["total"],
        approved=stats["approve"],
        flagged=stats["flag"],
        blocked=stats["block"],
        avg_latency_ms=stats["latency_sum"] / total,
        fraud_rate_estimate=round(fraud_rate, 2)
    )

# Serve the dashboard at /dashboard/
dashboard_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'dashboard')
if os.path.isdir(dashboard_dir):
    app.mount("/dashboard", StaticFiles(directory=dashboard_dir, html=True), name="dashboard")

@app.get("/")
def root():
    """Redirect to the dashboard."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/dashboard/")

if __name__ == "__main__":
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
