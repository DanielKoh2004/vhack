import pandas as pd
import numpy as np
from sklearn.model_selection import StratifiedKFold
import os
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DataPreprocessor:
    def __init__(self, data_path='data/ewallet_transaction.csv'):
        self.data_path = data_path
        
    def load_data(self, nrows=None):
        """Load dataset and perform initial cleanup"""
        logger.info(f"Loading data from {self.data_path} (nrows={nrows})")
        df = pd.read_csv(self.data_path, nrows=nrows)
        logger.info(f"Loaded dataset: {df.shape}")
        
        # Binary encoding for transfer_type
        if 'transfer_type' in df.columns:
            df['transfer_type'] = (df['transfer_type'] == 'CASH_OUT').astype(int)
            logger.info("Encoded transfer_type: CASH_OUT=1, TRANSFER=0")
            
        # Drop identifiable columns not needed for modeling
        cols_to_drop = ['transaction_id', 'name_sender', 'name_recipient']
        cols_to_drop = [c for c in cols_to_drop if c in df.columns]
        if cols_to_drop:
            df = df.drop(columns=cols_to_drop)
            logger.info(f"Dropped ID columns: {cols_to_drop}")
            
        # Drop leaked features (identified in Leakage Analysis)
        leaked_cols = ['session_duration_seconds', 'recipient_risk_profile_score']
        leaked_cols = [c for c in leaked_cols if c in df.columns]
        if leaked_cols:
            df = df.drop(columns=leaked_cols)
            logger.warning(f"Dropped leaked features to prevent data leakage: {leaked_cols}")
            
        return df
        
    def get_splits(self, df, target_col='is_fraud', save_dir='data/processed'):
        """
        Create stratified train/val/test splits (70/15/15)
        and save indices so we can perfectly reconstruct the splits later.
        """
        logger.info("Creating Stratified Data Splits (70/15/15)")
        os.makedirs(save_dir, exist_ok=True)
        
        # We need a 70/15/15 split.
        # First split into train (70%) and temp (30%)
        from sklearn.model_selection import train_test_split
        
        X = df.drop(columns=[target_col])
        y = df[target_col]
        
        X_train, X_temp, y_train, y_temp = train_test_split(
            X, y, test_size=0.30, stratify=y, random_state=42
        )
        
        # Split temp into val (50% of 30% = 15%) and test (50% of 30% = 15%)
        X_val, X_test, y_val, y_test = train_test_split(
            X_temp, y_temp, test_size=0.50, stratify=y_temp, random_state=42
        )
        
        logger.info(f"Train split: {X_train.shape[0]} rows (Fraud rate: {y_train.mean():.4f})")
        logger.info(f"Val split  : {X_val.shape[0]} rows (Fraud rate: {y_val.mean():.4f})")
        logger.info(f"Test split : {X_test.shape[0]} rows (Fraud rate: {y_test.mean():.4f})")
        
        # Save indices
        np.save(os.path.join(save_dir, 'train_indices.npy'), X_train.index.values)
        np.save(os.path.join(save_dir, 'val_indices.npy'), X_val.index.values)
        np.save(os.path.join(save_dir, 'test_indices.npy'), X_test.index.values)
        logger.info(f"Saved indices to {save_dir}")
        
        return (X_train, y_train), (X_val, y_val), (X_test, y_test)

if __name__ == "__main__":
    # Test execution
    preprocessor = DataPreprocessor('data/ewallet_transaction.csv')
    try:
        # Load small chunk for testing
        df = preprocessor.load_data(nrows=1000)
        _ = preprocessor.get_splits(df, save_dir='data/processed_test')
        print("Data preprocessor test successful.")
    except Exception as e:
        print(f"Test failed: {e}")
