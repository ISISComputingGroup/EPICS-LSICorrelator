from __future__ import print_function, unicode_literals, division, absolute_import

import sys
import os
import traceback
from typing import Dict, TextIO, Tuple

import six

import numpy as np

from time import sleep

from data_file_interaction import DataArrays, DataFile

sys.path.insert(1, os.path.join(os.getenv("EPICS_KIT_ROOT"), "support", "lsicorr_vendor", "master"))
sys.path.insert(2, os.path.join(os.getenv("EPICS_KIT_ROOT"), "ISIS", "inst_servers", "master"))

from LSICorrelator import LSICorrelator
from mocked_correlator_api import MockedCorrelatorAPI

from server_common.utilities import print_and_log
from config import Constants, Macro


def _error_handler(func):
    @six.wraps(func)
    def _wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:
            print_and_log(traceback.format_exc(), src="lsi ")
    return _wrapper


class LSiCorrelatorVendorInterface:
    """
    An interface to the LSiCorrelator vendor api.
    """

    def __init__(self, macros: Dict[str, str], simulated: bool = False):
        """
        An interface to the LSiCorrelator vendor api.

        Args:
            macros: Dictionary of macros for this IOC
            simulated: If True, a mocked API is used instead of the real vendor driver
        """
        self.macros = macros

        try:
            host = macros[Macro.ADDRESS.name]
        except KeyError:
            raise RuntimeError("No IP address specified, cannot start")
        firmware_revision = macros.get(Macro.FIRMWARE_REVISION.name, Macro.FIRMWARE_REVISION.value["default"])

        if simulated:
            self.mocked_api = MockedCorrelatorAPI()
            self.device = self.mocked_api.device
        else:
            self.device = LSICorrelator(host, firmware_revision)

        self.is_connected = self.device.isConnected()
        self.corr = None
        self.lags = None
        self.has_data = False

    def remove_data_with_time_lags_lower_than_minimum(self, lags: np.ndarray, corr: np.ndarray, min_time_lag: float) -> Tuple[np.ndarray, np.ndarray]:
        """
        Remove lags and corresponding corr values which have lags values below the minimum time lag
        
        Args:
            lags (ndarray): The original time lags values to remove values from
            corr (ndarray): The original correlation function to remove values from
            min_time_lag (float): The minimum time lag to include

        Returns:
            lags (ndarray): The correlation function values whose corresponding time lag is greater than or equal to min_time_lag
            corr (ndarray): Time lags that are greater than min_time_lag
        """
        indices = []
        for count in range(0, len(lags)):
            if lags[count] < min_time_lag:
                indices.append(count)

        lags = np.delete(lags,indices)
        corr = np.delete(corr,indices)

        return lags, corr

    def get_data_as_arrays(self, min_time_lag) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Collects the correlation function, time lags, raw traces and time trace as numpy arrays.
        The correlation function and time lags are filtered to finite values only.

        Args:
            min_time_lag (float): The minimum time lag to include

        Returns:
            Corr (ndarray): The finite values of the correlation function whose corresponding time lag is greater than or equal to min_time_lag
            Lags (ndarray): Time lags where the correlation function is finite that are greater than or equal to min_time_lag
            trace_A (ndarray): Raw photon counts for channel A
            trace_B (ndarray): Raw photon counts for channel B
            trace_time (ndarray): Time trace constructed from length of raw data
        """
        corr = np.asarray(self.device.Correlation)
        lags = np.asarray(self.device.Lags)

        lags, corr = self.remove_data_with_time_lags_lower_than_minimum(lags, corr, min_time_lag)

        lags = lags[np.isfinite(corr)]
        corr = corr[np.isfinite(corr)]

        trace_a = np.asarray(self.device.TraceChA)
        trace_b = np.asarray(self.device.TraceChB)

        # Time axis is number of data points collected * scaling factor
        trace_time = np.arange(len(trace_a))*Constants.DELTA_T

        return corr, lags, trace_a, trace_b, trace_time

    def configure(self):
        """
        Writes the configuration settings to the vendor driver
        """
        self.device.configure()

    @_error_handler
    def take_data(self, min_time_lag):
        """
        Starts taking data from the LSi Correlator once with the currently configure device settings.

        Args:
            min_time_lag (float): The minimum time lag to include
        """
        self.device.start()

        while self.device.MeasurementOn():
            sleep(Constants.SLEEP_BETWEEN_MEASUREMENTS)
            self.device.update()

        if self.device.Correlation is None:
            self.has_data = False
            self.is_connected = False
        else:
            self.has_data = True
            corr, lags, _, _, _ = self.get_data_as_arrays(min_time_lag)
            self.corr = corr
            self.lags = lags

    def save_data(self, min_time_lag: float, user_file: TextIO, archive_file: TextIO, metadata: Dict):
        """
        Save the data to file.

        Args:
            min_time_lag (float): The minimum time lag to include.
            user_file (TextIO): The user file to write data to.
            archive_file (TextIO): The archive file to write data to.
            metadata (Dict): Metadata to write to the file with.
        """
        correlation, time_lags, trace_a, trace_b, trace_time = self.get_data_as_arrays(min_time_lag)
        data_arrays = DataArrays(correlation, time_lags, trace_a, trace_b, trace_time)
        data_file = DataFile.create_file_data(data_arrays, user_file, archive_file, metadata)
        data_file.write_to_file()
