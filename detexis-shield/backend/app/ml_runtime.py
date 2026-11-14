"""Optional model loading; any failure leaves rule detection available."""
import json
import logging
import os
import math
from functools import lru_cache
from pathlib import Path

from detexis_shield.features import FEATURE_SCHEMA_VERSION

FEATURE_NAMES = ["payload_len", "special_char_ratio", "num_params", "path_depth"]
log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def load_model(path):
    import joblib  # Optional dependency. Only load trusted, locally trained artifacts.
    root = Path(path)
    metadata = json.loads((root / "metadata.json").read_text())
    if metadata["schema_version"] != FEATURE_SCHEMA_VERSION or metadata["feature_names"] != FEATURE_NAMES:
        raise ValueError("model schema mismatch")
    if not 0 <= metadata["threshold"] <= 1 or metadata.get("evaluation_status") != "validated":
        raise ValueError("model has no validated operating threshold")
    return joblib.load(root / "model.joblib"), metadata


@lru_cache(maxsize=1)
def warn_unavailable(path):
    log.warning("ML unavailable; using rules", exc_info=False)


def classify(features):
    path = os.getenv("SHIELD_MODEL_DIR")
    if not path:
        return None
    try:
        model, metadata = load_model(path)
        probability = float(model.predict_proba([[features[n] for n in FEATURE_NAMES]])[0][1])
        if not math.isfinite(probability) or not 0 <= probability <= 1:
            raise ValueError("invalid model probability")
        result = {"probability": probability, "alert": probability > metadata["threshold"],
                  "model_version": metadata["model_version"], "reasons": []}
        if result["alert"] and metadata.get("model_kind") == "xgboost":
            try:
                import shap
                import numpy as np
                values = shap.TreeExplainer(model).shap_values(np.asarray([[features[n] for n in FEATURE_NAMES]]))[0]
                result["reasons"] = [{"feature": FEATURE_NAMES[i], "contribution": float(values[i])}
                                     for i in sorted(range(len(values)), key=lambda i: abs(values[i]), reverse=True)[:3]]
            except Exception:
                result["explanation_status"] = "unavailable"
        return result
    except Exception:
        warn_unavailable(path)
        return None
