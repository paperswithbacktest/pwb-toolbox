import importlib
import os
import sys
import types

import pytest


def test_missing_token(monkeypatch):
    monkeypatch.delenv("HF_ACCESS_TOKEN", raising=False)
    monkeypatch.setitem(sys.modules, "datasets", types.ModuleType("datasets"))
    dummy_pd = types.ModuleType("pandas")
    dummy_pd.DataFrame = object
    dummy_pd.MultiIndex = types.SimpleNamespace(from_product=lambda *a, **k: [])
    dummy_pd.to_datetime = lambda x: x
    dummy_pd.concat = lambda *a, **k: None
    dummy_pd.merge = lambda *a, **k: None
    dummy_pd.isna = lambda x: False
    monkeypatch.setitem(sys.modules, "pandas", dummy_pd)
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    ds = importlib.import_module("pwb_toolbox.datasets")
    importlib.reload(ds)
    with pytest.raises(ValueError, match="HF_ACCESS_TOKEN not set"):
        ds._get_hf_token()
