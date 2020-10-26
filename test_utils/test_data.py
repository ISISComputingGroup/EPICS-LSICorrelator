import numpy as np

import os

current_path = os.path.dirname(os.path.realpath(__file__))

corr, lags = np.genfromtxt(os.path.join(current_path, "correlation_function.csv"), delimiter=",", unpack=True)
trace_a, trace_b, trace_time = np.genfromtxt(os.path.join(current_path, "raw_data.csv"), delimiter=',', unpack=True)
test_data_file = os.path.join(current_path, "test_data.dat")

lags_without_nans = lags[np.isfinite(corr)]
corr_without_nans = corr[np.isfinite(corr)]
