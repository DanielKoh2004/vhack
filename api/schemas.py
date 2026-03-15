from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

class TransactionInput(BaseModel):
    transaction_id: str = Field(..., example="TXN_992123")
    name_sender: str = Field(..., example="C992123")
    name_recipient: str = Field(..., example="M102345")
    transfer_type: str = Field(..., example="CASH_OUT")
    amount: float = Field(..., example=150.50)
    
    # Behavioral features
    avg_transaction_amount_30d: float = Field(0.0)
    amount_vs_avg_ratio: float = Field(1.0)
    
    # Temporal features
    transaction_hour: int = Field(..., ge=0, le=23, example=14)
    is_weekend: int = Field(0, ge=0, le=1)
    
    # Security signals
    is_new_device: int = Field(0)
    failed_login_attempts: int = Field(0)
    is_proxy_ip: int = Field(0)
    ip_risk_score: float = Field(0.0)
    
    # Account status
    sender_account_fully_drained: int = Field(0)
    account_age_days: int = Field(100)
    tx_count_24h: int = Field(1)
    
    # Trust Profile
    country_mismatch: int = Field(0)
    is_new_recipient: int = Field(0)
    established_user_new_recipient: int = Field(0)

class LayerScores(BaseModel):
    lightgbm: float = Field(..., ge=0.0, le=1.0, description="Supervised pattern detection score")
    isolation_forest: float = Field(..., ge=0.0, le=1.0, description="Anomaly detection score")
    behavioral: float = Field(..., ge=0.0, le=1.0, description="Rule-based risk score")

class PrivacyInfo(BaseModel):
    pii_hashed: bool = Field(True, description="Whether PII was cryptographically hashed before inference")
    hash_algorithm: str = Field("SHA-256", description="Hash algorithm used")
    dp_applied: bool = Field(False, description="Whether differential privacy noise was applied")

class RiskResponse(BaseModel):
    transaction_id: str
    risk_score: float = Field(..., ge=0.0, le=1.0)
    decision: str = Field(..., description="APPROVE, FLAG, or BLOCK")
    layer_scores: LayerScores
    reasons: List[str] = Field(default_factory=list)
    privacy: PrivacyInfo = Field(default_factory=PrivacyInfo)
    latency_ms: float
    
class DashboardStats(BaseModel):
    total_transactions: int
    approved: int
    flagged: int
    blocked: int
    avg_latency_ms: float
    fraud_rate_estimate: float
