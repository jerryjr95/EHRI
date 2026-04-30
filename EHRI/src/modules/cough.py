from typing import Optional


def cough_score(score: Optional[float] = None) -> float:
    """Return a normalized cough risk score on a 1-10 scale.
    If sensor / ML score is provided, use it directly.
    """
    if score is None:
        return 1.0
    return round(min(10.0, max(1.0, score)), 2)