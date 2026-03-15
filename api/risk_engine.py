import pandas as pd
import numpy as np
import joblib
import os
import time
import logging

from src.feature_engineering import FeatureEngineer
from src.behavioral_profiler import BehavioralProfiler
from src.score_fusion import ScoreFusion
from src.privacy_module import PrivacyProtector
from src.explainability import ModelExplainer
from api.schemas import TransactionInput, RiskResponse, LayerScores, PrivacyInfo

logger = logging.getLogger(__name__)

class RiskEngine:
    def __init__(self, model_dir='models/'):
        self.model_dir = model_dir
        self.engineer = FeatureEngineer()
        self.profiler = BehavioralProfiler()
        self.privacy = PrivacyProtector()
        # Same weights as in training
        self.fusion = ScoreFusion(w_lgb=0.55, w_pyod=0.25, w_beh=0.20)
        
        # Load artifacts
        try:
            self.lgb_model = joblib.load(os.path.join(model_dir, 'lgb_model.pkl'))
            self.pyod_model = joblib.load(os.path.join(model_dir, 'pyod_model.pkl'))
            self.feature_columns = joblib.load(os.path.join(model_dir, 'feature_columns.pkl'))
            self.explainer = ModelExplainer(self.lgb_model)
            
            # Warm up SHAP to avoid cold-start latency on first real request
            warmup_df = pd.DataFrame([{c: 0.0 for c in self.feature_columns}])
            self.explainer.explain_instance(warmup_df, top_k=1)
            logger.info("Successfully loaded ML models, feature map, and warmed up SHAP explainer")
        except Exception as e:
            logger.error(f"Failed to load models: {e}. Is the training pipeline complete?")
            self.lgb_model = None
            self.explainer = None
            
    def predict(self, txn: TransactionInput) -> RiskResponse:
        start_time = time.time()
        
        # 0. Apply Privacy Masking
        safe_txn_dict = self.privacy.prepare_for_inference(txn.model_dump())
        
        # 1. Convert to DataFrame
        df = pd.DataFrame([safe_txn_dict])
        
        # 2. Drop non-model columns (same as DataPreprocessor does during training)
        cols_to_drop = ['transaction_id', 'name_sender', 'name_recipient']
        df.drop(columns=[c for c in cols_to_drop if c in df.columns], inplace=True)
        
        # 3. Encode categorical transfer_type inline
        df['transfer_type'] = (df['transfer_type'] == 'CASH_OUT').astype(int)
        
        # 4. Apply Feature Engineering pipeline
        df_eng = self.engineer.transform(df, training=False)
        
        # 4. Align columns precisely with what the model expects
        # Add missing columns with 0, drop extra columns
        for col in self.feature_columns:
            if col not in df_eng.columns:
                df_eng[col] = 0.0
        X = df_eng[self.feature_columns]
        
        # 5. Get predictions from 3 layers
        # Layer 1: LightGBM
        if self.lgb_model:
            lgb_score = self.lgb_model.predict_proba(X)[:, 1][0]
            # Layer 2: PyOD
            # Impute NaN/missing just in case
            X_imputed = X.fillna(0)
            pyod_score = np.clip(self.pyod_model.predict_proba(X_imputed)[:, 1][0], 0.0, 1.0)
        else:
            # Fallback if ML models missing
            lgb_score = 0.0
            pyod_score = 0.0
            
        # Layer 3: Behavioral
        beh_score, beh_reasons = self.profiler.predict(df_eng)
        beh_score = beh_score[0]
        reasons = [r.strip() for r in beh_reasons[0].split('|') if "Normal behavior" not in r]
        
        # Get AI explanation from SHAP if score is high
        if self.explainer and lgb_score > 0.35:
            shap_reasons = self.explainer.explain_instance(X, top_k=2)
            reasons.extend(shap_reasons)
            
        if not reasons:
            reasons.append("Normal behavior pattern")
            
        # 6. Fuse scores
        final_score = self.fusion.fuse([lgb_score], [pyod_score], [beh_score])[0]
        decision = self.fusion.get_decision(final_score)
        
        latency = (time.time() - start_time) * 1000
        
        return RiskResponse(
            transaction_id=txn.transaction_id,
            risk_score=round(float(final_score), 4),
            decision=decision,
            layer_scores=LayerScores(
                lightgbm=round(float(lgb_score), 4),
                isolation_forest=round(float(pyod_score), 4),
                behavioral=round(float(beh_score), 4)
            ),
            reasons=reasons,
            privacy=PrivacyInfo(pii_hashed=True, hash_algorithm="SHA-256", dp_applied=False),
            latency_ms=round(latency, 2)
        )
