"""
Tests for the ML model manager.
"""

import pytest
import numpy as np
from app.ml.model_manager import ModelManager
from app.core.exceptions import ModelNotLoadedError, ModelPredictionError


class TestModelManagerMockMode:
    def setup_method(self):
        self.manager = ModelManager()

    def test_not_loaded_initially(self):
        assert not self.manager.is_loaded

    def test_load_mock_mode(self):
        self.manager.load_models(model_dir="./models", mock_mode=True)
        assert self.manager.is_loaded
        assert self.manager.is_mock
        assert "mock" in self.manager.model_version.lower()

    def test_predict_requires_loading(self):
        features = np.zeros(8)
        with pytest.raises(ModelNotLoadedError):
            self.manager.predict(features)

    def test_mock_predict(self):
        self.manager.load_models(model_dir="./models", mock_mode=True)
        features = np.array([1.5, 20.0, 0.001, 100.0, 45.0, 0.5, 50.0, 40.0])
        msd, prob, confidence = self.manager.predict(features)
        assert isinstance(msd, float)
        assert isinstance(prob, float)
        assert isinstance(confidence, float)
        assert msd >= 0
        assert 0 <= prob <= 1

    def test_mock_predict_deterministic(self):
        """Same features should produce same mock results."""
        self.manager.load_models(model_dir="./models", mock_mode=True)
        features = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
        r1 = self.manager.predict(features)
        r2 = self.manager.predict(features)
        assert r1 == r2


class TestModelFeatureValidation:
    def setup_method(self):
        self.manager = ModelManager()
        self.manager.load_models(model_dir="./models", mock_mode=True)

    def test_wrong_feature_count(self):
        with pytest.raises(ModelPredictionError, match="Expected 8"):
            self.manager.predict(np.zeros(5))

    def test_nan_features(self):
        features = np.array([1, 2, np.nan, 4, 5, 6, 7, 8])
        with pytest.raises(ModelPredictionError, match="NaN"):
            self.manager.predict(features)

    def test_inf_features(self):
        features = np.array([1, 2, 3, np.inf, 5, 6, 7, 8])
        with pytest.raises(ModelPredictionError, match="infinite"):
            self.manager.predict(features)

    def test_2d_features_rejected(self):
        with pytest.raises(ModelPredictionError, match="1D"):
            self.manager.predict(np.zeros((1, 8)))


class TestModelManagerRealMode:
    def test_missing_models_raises(self):
        manager = ModelManager()
        with pytest.raises(ModelNotLoadedError, match="not found"):
            manager.load_models(model_dir="./nonexistent_dir", mock_mode=False)
