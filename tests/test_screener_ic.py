"""IC analysis smoke tests."""

import numpy as np

from qmt_quant.core.screener.ic import _spearman


def test_spearman_positive_correlation():
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    y = np.array([2.0, 4.0, 6.0, 8.0, 10.0])
    ic = _spearman(x, y)
    assert ic > 0.99
