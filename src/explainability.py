import shap
import warnings
import numpy as np
import pandas as pd
import logging

# Suppress SHAP deprecation warnings that cause latency spikes
warnings.filterwarnings("ignore", category=DeprecationWarning, module="shap")

logger = logging.getLogger(__name__)

class ModelExplainer:
    """
    SHAP-based explainability module for the LightGBM classifier.
    Extracts the top features driving a specific fraud score.
    """
    def __init__(self, lgb_model):
        self.model = lgb_model
        try:
            self.explainer = shap.TreeExplainer(self.model)
            logger.info("SHAP TreeExplainer initialized successfully")
        except Exception as e:
            logger.error(f"Could not initialize SHAP explainer: {e}")
            self.explainer = None
            
        self.feature_names_map = {
            'log_amount': 'Transaction Amount (log)',
            'log_avg_30d': '30-Day Average Spend',
            'amount_vs_avg_ratio': 'Amount vs Historical Average',
            'velocity_score': 'Behavioral Velocity',
            'device_ip_risk': 'Device & IP Risk',
            'drain_new_recipient': 'Account Drain to New Recipient',
            'login_velocity': 'Login Attempts vs Transactions',
            'account_maturity_risk': 'Account Age/Maturity',
            'ip_risk_score': 'IP Reputation Score',
            'sender_account_fully_drained': 'Account Drained Flag',
            'is_new_device': 'Unknown Device Flag',
            'failed_login_attempts': 'Failed Login Attempts',
            'country_device_risk': 'Foreign Device Risk',
            'weekend_night_flag': 'Weekend Night Activity',
            'tx_count_24h': '24-Hour Transaction Volume',
        }
            
    def explain_instance(self, X_instance: pd.DataFrame, top_k=3):
        """
        Explain a single prediction by returning the top K features 
        pushing the score towards fraud.
        """
        if self.explainer is None:
            return ["Explanation engine unavailable"]
            
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                shap_values = self.explainer.shap_values(X_instance)
            
            # LightGBM: shap_values is a list [class_0_vals, class_1_vals]
            if isinstance(shap_values, list):
                vals = shap_values[1][0]
            else:
                vals = shap_values[0]
                
            features = X_instance.columns
            feature_impacts = sorted(
                [(features[i], vals[i]) for i in range(len(features))],
                key=lambda x: x[1], reverse=True
            )
            
            reasons = []
            for feat, impact in feature_impacts[:top_k]:
                if impact > 0.05:
                    friendly_name = self.feature_names_map.get(feat, feat)
                    reasons.append(f"High risk contribution from: {friendly_name}")
                    
            if not reasons:
                reasons.append("Model detected subtle multi-feature pattern.")
                
            return reasons
            
        except Exception as e:
            logger.error(f"SHAP explanation failed: {e}")
            return ["Model flagged transaction patterns"]
