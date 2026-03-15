import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

class FeatureEngineer:
    def __init__(self):
        pass
        
    def _apply_log_transforms(self, df):
        """Apply log1p to heavily skewed monetary features and drop raw columns"""
        logger.info("Applying log1p transform to amounts")
        if 'amount' in df.columns:
            df['log_amount'] = np.log1p(df['amount'])
            df.drop(columns=['amount'], inplace=True)
        if 'avg_transaction_amount_30d' in df.columns:
            df['log_avg_30d'] = np.log1p(df['avg_transaction_amount_30d'])
            df.drop(columns=['avg_transaction_amount_30d'], inplace=True)
        return df
        
    def _create_temporal_features(self, df):
        """Create time-based risk features"""
        logger.info("Creating temporal features")
        if 'transaction_hour' in df.columns:
            # High risk: Midnight to 5 AM
            df['hour_risk_bucket'] = pd.cut(
                df['transaction_hour'], 
                bins=[-1, 5, 8, 17, 21, 24],
                labels=['highest', 'high', 'low', 'medium', 'highest_eve'],
                ordered=False
            ).astype(str)
            
            # Weekend night flag (highest risk combo)
            if 'is_weekend' in df.columns:
                df['weekend_night_flag'] = ((df['is_weekend'] == 1) & (df['transaction_hour'].isin([0, 1, 2, 3, 4, 5]))).astype(int)
        
        return df
        
    def _create_composite_risk_scores(self, df):
        """Create composite features combining multiple signals"""
        logger.info("Creating composite risk features")
        
        # Velocity score: high ratio of normal spend AND failed logins points to urgency
        if all(c in df.columns for c in ['amount_vs_avg_ratio', 'failed_login_attempts']):
            df['velocity_score'] = df['amount_vs_avg_ratio'] * (1 + df['failed_login_attempts'])
            
        # Device/IP risk: new device from risky IP
        if all(c in df.columns for c in ['is_new_device', 'ip_risk_score']):
            df['device_ip_risk'] = df['is_new_device'] * df['ip_risk_score']
            
        # Drain to unknown: emptying account to new person
        if all(c in df.columns for c in ['sender_account_fully_drained', 'is_new_recipient']):
            df['drain_new_recipient'] = df['sender_account_fully_drained'] * df['is_new_recipient']
            
        # Country/Device risk: foreign IP + new device = high takeover risk
        if all(c in df.columns for c in ['country_mismatch', 'is_new_device']):
            df['country_device_risk'] = df['country_mismatch'] * df['is_new_device']
            
        # Login velocity: brute force signal
        if all(c in df.columns for c in ['failed_login_attempts', 'tx_count_24h']):
            df['login_velocity'] = df['failed_login_attempts'] * df['tx_count_24h']
            
        # Account maturity risk
        if 'account_age_days' in df.columns:
            # Add 1 to avoid div by zero. Less mature -> higher risk score.
            df['account_maturity_risk'] = 1 / np.log1p(df['account_age_days'] + 1)
            
        return df
        
    def transform(self, df, training=False):
        """Main execution pipeline"""
        df = df.copy()
        
        df = self._apply_log_transforms(df)
        df = self._create_temporal_features(df)
        df = self._create_composite_risk_scores(df)
        
        # OHE for categorical features
        if 'hour_risk_bucket' in df.columns:
            df = pd.get_dummies(df, columns=['hour_risk_bucket'], drop_first=True)
            
        # Ensure all columns are float or int for LightGBM
        for c in df.columns:
            if df[c].dtype == object or df[c].dtype.name == 'category' or df[c].dtype == bool:
                df[c] = df[c].astype(float)
                
        return df

if __name__ == "__main__":
    from src.data_preprocessing import DataPreprocessor
    try:
        preprocessor = DataPreprocessor('data/ewallet_transaction.csv')
        df = preprocessor.load_data(nrows=1000)
        
        engineer = FeatureEngineer()
        df_engineered = engineer.transform(df, training=True)
        
        logger.info(f"Engineered dataset shape: {df_engineered.shape}")
        logger.info(f"New engineered columns: {[c for c in df_engineered.columns if c not in df.columns]}")
        print("Feature engineering test successful.")
    except Exception as e:
        print(f"Test failed: {e}")
