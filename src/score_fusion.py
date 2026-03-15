import numpy as np
import logging

logger = logging.getLogger(__name__)

class ScoreFusion:
    """
    Ensemble module that combines scores from LightGBM, PyOD, and Behavioral layers.
    """
    def __init__(self, w_lgb=0.50, w_pyod=0.30, w_beh=0.20):
        # Default weights. Can be tuned using validation set.
        total = w_lgb + w_pyod + w_beh
        self.weights = {
            'lgb': w_lgb / total,
            'pyod': w_pyod / total,
            'beh': w_beh / total
        }
        
        # Risk thresholds map nicely to the Super App UX
        self.thresholds = {
            'approve': 0.35,  # <= 0.35 goes through instantly
            'flag': 0.70      # > 0.35 and <= 0.70 flagged for manual review/MFA
                              # > 0.70 blocked automatically
        }
        logger.info(f"Initialized ScoreFusion with weights: {self.weights}")
        
    def fuse(self, lgb_scores, pyod_scores, beh_scores):
        """
        Combine arrays of scores into a final weighted score.
        All inputs should be probabilities/scores in range [0, 1].
        """
        assert len(lgb_scores) == len(pyod_scores) == len(beh_scores), "Score arrays must have same length"
        
        # Convert to numpy arrays if not already
        lgb = np.array(lgb_scores)
        pyod = np.array(pyod_scores)
        beh = np.array(beh_scores)
        
        final_scores = (
            lgb * self.weights['lgb'] +
            pyod * self.weights['pyod'] +
            beh * self.weights['beh']
        )
        
        return final_scores
        
    def get_decision(self, score):
        """Map a numeric score to a business decision"""
        if score <= self.thresholds['approve']:
            return "APPROVE"
        elif score <= self.thresholds['flag']:
            return "FLAG"
        else:
            return "BLOCK"
            
    def get_decisions(self, scores):
        """Batch map scores to decisions"""
        return np.array([self.get_decision(s) for s in scores])
