try:
    from src.config import WEIGHTS
except ModuleNotFoundError:
    from config import WEIGHTS

def compute_index(cough, environment, physiology):
    score = (
        WEIGHTS['cough']*cough +
        WEIGHTS['environment']*environment +
        WEIGHTS['physiology']*physiology
    )
    return round(score,2)