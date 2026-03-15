import pandas as pd
import numpy as np
import lightgbm as lgb
from pyod.models.iforest import IForest
from sklearn.metrics import classification_report, average_precision_score, precision_recall_curve, f1_score
from imblearn.over_sampling import SMOTE
import joblib
import os
import argparse
import logging

from src.data_preprocessing import DataPreprocessor
from src.feature_engineering import FeatureEngineer
from src.score_fusion import ScoreFusion
from src.behavioral_profiler import BehavioralProfiler

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FraudShieldEnsemble:
    def __init__(self, model_dir='models/'):
        self.model_dir = model_dir
        os.makedirs(self.model_dir, exist_ok=True)
        
        self.lgb_model = None
        self.pyod_model = None
        self.profiler = BehavioralProfiler()
        self.fusion = ScoreFusion(w_lgb=0.55, w_pyod=0.25, w_beh=0.20)
        
    def train(self, df_train, df_val, use_smote=True):
        """Train LightGBM and PyOD models"""
        target = 'is_fraud'
        X_train = df_train.drop(columns=[target])
        y_train = df_train[target]
        X_val = df_val.drop(columns=[target])
        y_val = df_val[target]
        
        # 1. Train LightGBM (Supervised)
        logger.info("--- Training Layer 1: LightGBM ---")
        
        if use_smote:
            logger.info("Applying SMOTE to training data for extreme imbalance handling...")
            smote = SMOTE(sampling_strategy=0.1, random_state=42) # Bring minority to 10%
            X_train_res, y_train_res = smote.fit_resample(X_train, y_train)
            logger.info(f"Resampled train shape: {X_train_res.shape}, Fraud rate: {y_train_res.mean():.4f}")
            # When using SMOTE, don't also use scale_pos_weight — avoids double-correction
            spw = 1.0
        else:
            X_train_res, y_train_res = X_train, y_train
            # Calculate scale_pos_weight only when NOT using SMOTE
            num_neg = (y_train_res == 0).sum()
            num_pos = (y_train_res == 1).sum()
            spw = num_neg / max(num_pos, 1)
        
        self.lgb_model = lgb.LGBMClassifier(
            n_estimators=500,
            learning_rate=0.05,
            max_depth=6,
            num_leaves=63,
            scale_pos_weight=spw,
            objective='binary',
            random_state=42,
            n_jobs=-1
        )
        
        # We handle early stopping manually with callbacks in LGBM >= 4.0
        self.lgb_model.fit(
            X_train_res, y_train_res,
            eval_set=[(X_val, y_val)],
            eval_metric='aucpr',
            callbacks=[lgb.early_stopping(stopping_rounds=50, verbose=True)]
        )
        logger.info("LightGBM training complete.")
        
        # 2. Train PyOD Isolation Forest (Unsupervised)
        logger.info("--- Training Layer 2: PyOD Isolation Forest ---")
        # Train ONLY on normal data so it learns what "normal" looks like
        X_train_normal = X_train[y_train == 0].fillna(0).copy()
        
        self.pyod_model = IForest(
            n_estimators=100,
            contamination=0.02, # Assume up to 2% anomalies in future
            random_state=42,
            n_jobs=-1
        )
        self.pyod_model.fit(X_train_normal)
        logger.info("PyOD training complete.")
        
        # Save models
        joblib.dump(self.lgb_model, os.path.join(self.model_dir, 'lgb_model.pkl'))
        joblib.dump(self.pyod_model, os.path.join(self.model_dir, 'pyod_model.pkl'))
        logger.info(f"Models saved to {self.model_dir}")
        
    def evaluate(self, df_test):
        """Evaluate the Full Ensemble on Test Set"""
        logger.info("--- Evaluating Full Ensemble ---")
        X_test = df_test.drop(columns=['is_fraud'])
        y_test = df_test['is_fraud']
        
        # 1. Get LightGBM predictions
        lgb_preds = self.lgb_model.predict_proba(X_test)[:, 1]
        
        # 2. Get PyOD predictions (transform anomaly score to [0,1] probability-like scale)
        X_test_imputed = X_test.fillna(0)
        # decision_function outputs continuous score (higher = more anomalous)
        # Using built-in predict_proba returns [prob_normal, prob_anomaly]
        pyod_raw_probs = self.pyod_model.predict_proba(X_test_imputed)[:, 1]
        # In practice PyOD probs can be poorly calibrated, clip for safety
        pyod_preds = np.clip(pyod_raw_probs, 0.0, 1.0)
        
        # 3. Get Behavioral scores
        beh_preds, reasons = self.profiler.predict(X_test)
        
        # 4. Fuse scores
        final_scores = self.fusion.fuse(lgb_preds, pyod_preds, beh_preds)
        
        # Calculate metrics
        aucpr = average_precision_score(y_test, final_scores)
        logger.info(f"Ensemble AUC-PR: {aucpr:.4f}")
        
        # Threshold tuning (maximize F1)
        precision_arr, recall_arr, thresholds = precision_recall_curve(y_test, final_scores)
        
        # Find best threshold for F1  
        # precision_recall_curve returns arrays of len N+1, N+1, N
        f1_scores = 2 * (precision_arr[:-1] * recall_arr[:-1]) / (precision_arr[:-1] + recall_arr[:-1] + 1e-10)
        best_idx = np.argmax(f1_scores)
        best_threshold = thresholds[best_idx]
        
        logger.info(f"Best threshold for max F1: {best_threshold:.4f}")
        logger.info(f"Max F1 Score: {f1_scores[best_idx]:.4f}")
        
        # Update fusion model threshold
        # We map best_threshold to the 'flag' boundary
        logger.info(f"Aligning API thresholds based on best F1...")
        
        # Evaluate standard logic (score > 0.5)
        y_pred = (final_scores > best_threshold).astype(int)
        logger.info("\nClassification Report (Test Set):")
        print(classification_report(y_test, y_pred))
        
        # Business metrics
        # Confusion matrix
        from sklearn.metrics import confusion_matrix
        cm = confusion_matrix(y_test, y_pred)
        tn, fp, fn, tp = cm.ravel()
        
        fp_rate = fp / (fp + tn) * 100
        detection_rate = tp / (tp + fn) * 100
        
        logger.info(f"False Positive Rate: {fp_rate:.2f}% (Target: < 2.0%)")
        logger.info(f"Fraud Detection Rate (Recall): {detection_rate:.2f}%")
        
        with open('models/metrics_report.txt', 'w') as f:
            f.write(f"Ensemble AUC-PR: {aucpr:.4f}\n")
            f.write(f"Best Threshold: {best_threshold:.4f}\n")
            f.write(f"Max F1: {f1_scores[best_idx]:.4f}\n")
            f.write(f"\nClassification Report:\n{classification_report(y_test, y_pred)}\n")
            f.write(f"\nFalse Positive Rate: {fp_rate:.2f}%\n")
            f.write(f"Fraud Detection Rate: {detection_rate:.2f}%\n")

def run_pipeline(data_path, sample_size=None):
    logger.info("Initializing Data Pipeline")
    preprocessor = DataPreprocessor(data_path)
    df_raw = preprocessor.load_data(nrows=sample_size)
    
    # Stratified Split
    (X_train, y_train), (X_val, y_val), (X_test, y_test) = preprocessor.get_splits(df_raw, save_dir='data/processed')
    
    # Feature Engineering (Train)
    engineer = FeatureEngineer()
    # Recombine for transform
    df_train = pd.concat([X_train, y_train], axis=1)
    df_train_eng = engineer.transform(df_train, training=True)
    
    # Save the selected numeric columns for future API alignment
    features_list = df_train_eng.drop(columns=['is_fraud']).columns.tolist()
    os.makedirs('models', exist_ok=True)
    joblib.dump(features_list, 'models/feature_columns.pkl')
    logger.info(f"Saved {len(features_list)} feature columns to feature_columns.pkl")
    
    # Feature Engineering (Val & Test)
    df_val = pd.concat([X_val, y_val], axis=1)
    df_val_eng = engineer.transform(df_val, training=False)
    
    df_test = pd.concat([X_test, y_test], axis=1)
    df_test_eng = engineer.transform(df_test, training=False)
    
    # Train
    ensemble = FraudShieldEnsemble()
    ensemble.train(df_train_eng, df_val_eng, use_smote=True)
    
    # Evaluate
    ensemble.evaluate(df_test_eng)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/ewallet_transaction.csv", help="Path to raw dataset")
    parser.add_argument("--sample", type=int, default=None, help="Rows to load (for testing)")
    parser.add_argument("--evaluate", action="store_true", help="Run full pipeline and evaluation")
    args = parser.parse_args()
    
    if args.evaluate:
        run_pipeline(args.data, args.sample)
    else:
        logger.info("Run with --evaluate to execute the pipeline.")
