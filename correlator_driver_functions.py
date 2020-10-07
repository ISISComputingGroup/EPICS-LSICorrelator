from __future__ import print_function, unicode_literals, division, absolute_import

import sys
import os
import traceback
from io import StringIO
from typing import Dict, TextIO, Tuple

import six

import numpy as np

from time import sleep
from datetime import datetime

sys.path.insert(1, os.path.join(os.getenv("EPICS_KIT_ROOT"), "support", "lsicorr_vendor", "master"))
sys.path.insert(2, os.path.join(os.getenv("EPICS_KIT_ROOT"), "ISIS", "inst_servers", "master"))

from LSICorrelator import LSICorrelator
from mocked_correlator_api import MockedCorrelatorAPI

from pvdb import Records
from server_common.utilities import print_and_log
from file_format import FILE_SCHEME


def _error_handler(func):
    @six.wraps(func)
    def _wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:
            print_and_log(traceback.format_exc(), src="lsi ")
    return _wrapper


# Magic number, seems to be time between measurements.
DELTA_T = 0.0524288


class LSiCorrelatorDriver:
    """
    A driver for the LSi Correlator
    """

    def __init__(self, macros: Dict[str, str]):
        """
        A driver for the LSi Correlator

        Args:
            macros: Dictionary of macros for this IOC
        """
        self.macros = macros

        try:
            host = macros["ADDR"]
        except KeyError:
            raise RuntimeError("No IP address specified, cannot start")
        firmware_revision = macros.get("FIRMWARE_REVISION", "4.0.0.3")

        if macros["SIMULATE"] == "1":
            print("WARNING! Started in simulation mode")
            self.mocked_api = MockedCorrelatorAPI()
            self.device = self.mocked_api.device
        else:
            self.device = LSICorrelator(host, firmware_revision)

        self.is_connected = self.device.isConnected()
        self.corr = None
        self.lags = None
        self.has_data = False

    def get_data_as_arrays(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Collects the correlation function, time lags, raw traces and time trace as numpy arrays.
        The correlation function and time lags are filtered to finite values only.

        Returns:
            Corr (ndarray): The finite values of the correlation function
            Lags (ndarray): Time lags where the correlation function is finite
            trace_A (ndarray): Raw photon counts for channel A
            trace_B (ndarray): Raw photon counts for channel B
            trace_time (ndarray): Time trace constructed from length of raw data
        """
        corr = np.asarray(self.device.Correlation)
        lags = np.asarray(self.device.Lags)

        lags = lags[np.isfinite(corr)]
        corr = corr[np.isfinite(corr)]

        trace_a = np.asarray(self.device.TraceChA)
        trace_b = np.asarray(self.device.TraceChB)

        # Time axis is number of data points collected * scaling factor
        trace_time = np.arange(len(trace_a))*DELTA_T

        return corr, lags, trace_a, trace_b, trace_time

    def configure(self):
        """
        Writes the configuration settings to the vendor driver
        """
        self.device.configure()

    @_error_handler
    def take_data(self):
        """
        Starts taking data from the LSi Correlator once with the currently configure device settings.
        """
        self.device.start()

        while self.device.MeasurementOn():
            sleep(0.5)
            self.device.update()

        if self.device.Correlation is None:
            self.has_data = False
            self.is_connected = False
        else:
            self.has_data = True
            corr, lags, _, _, _ = self.get_data_as_arrays()
            self.corr = corr
            self.lags = lags

    def save_data(self, user_file: TextIO, archive_file: TextIO, metadata: Dict):
        """
        Write the correlation function, time lags, traces and metadata to user and archive files.

        Args:
            user_file (TextIO): The user file to write metadata, correlation, time_lags and the traces to
            archive_file (TextIO): The archive file to write metadata, correlation, time_lags and the traces to
            metadata (dict): A dictionary of metadata to write to the file
        """
        correlation, time_lags, trace_a, trace_b, trace_time = self.get_data_as_arrays()

        correlation_data = np.vstack((time_lags, correlation)).T
        raw_channel_data = np.vstack((trace_time, trace_a, trace_b)).T

        # Populate the save file as a string
        correlation_file = StringIO()
        np.savetxt(correlation_file, correlation_data, delimiter='\t', fmt='%1.6e')
        correlation_string = correlation_file.getvalue()
        raw_channel_data_file = StringIO()
        np.savetxt(raw_channel_data_file, raw_channel_data, delimiter='\t', fmt='%.6f')
        raw_channel_data_string = raw_channel_data_file.getvalue()

        save_file = FILE_SCHEME.format(
            datetime=datetime.now().strftime("%m/%d/%Y\t%H:%M %p"),
            scattering_angle=metadata[Records.SCATTERING_ANGLE.name],
            duration=metadata[Records.MEASUREMENTDURATION.name],
            wavelength=metadata[Records.LASER_WAVELENGTH.name],
            refractive_index=metadata[Records.SOLVENT_REFRACTIVE_INDEX.name],
            viscosity=metadata[Records.SOLVENT_VISCOSITY.name],
            temperature=metadata[Records.SAMPLE_TEMP.name],
            avg_count_A=np.mean(trace_a),
            avg_count_B=np.mean(trace_b),
            correlation_function=correlation_string,
            count_rate_history=raw_channel_data_string
        )

        for dat_file in [user_file, archive_file]:
            dat_file.write(save_file)
