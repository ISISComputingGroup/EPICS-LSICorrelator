from __future__ import print_function, unicode_literals, division, absolute_import

import argparse
import sys
import os
import traceback
from io import StringIO
from typing import Dict

import six

import numpy as np

from time import sleep
from datetime import datetime

sys.path.insert(1, os.path.join(os.getenv("EPICS_KIT_ROOT"), "support", "lsicorr_vendor", "master"))
sys.path.insert(2, os.path.join(os.getenv("EPICS_KIT_ROOT"), "ISIS", "inst_servers", "master"))

# from LSI import LSI_Param
from LSICorrelator import LSICorrelator
from mocked_correlator_api import MockedCorrelatorAPI

from pvdb import Records
# from BlockServer.core.file_path_manager import FILEPATH_MANAGER
from server_common.utilities import print_and_log
# from server_common.channel_access import ChannelAccess
# from server_common.helpers import register_ioc_start, get_macro_values
from file_format import FILE_SCHEME

DATA_DIR = r"c:\Data"
USER_FILE_DIR = r"c:\Data"


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

# PVs from the DAE to get information about instrument
# RUNNUMBER_PV = "{pv_prefix}DAE:RUNNUMBER"
# TITLE_PV = "{pv_prefix}DAE:TITLE"
# INSTNAME_PV = "{pv_prefix}DAE:INSTNAME"


def remove_non_ascii(text_to_check):
    """
    Removes non-ascii and other characters from the supplied text
    """
    # Remove anything other than alphanumerics and dashes/underscores
    parsed_text = [char for char in text_to_check if char.isalnum() or char in '-_']
    return ''.join(parsed_text)


class LSiCorrelatorDriver():
    """
    A driver for the LSi Correlator
    """

    def __init__(self, host: str, firmware_revision: str, filepath: str, macros: Dict[str, str]):
        """
        A driver for the LSi Correlator

        Args:
            host: The IP address of the LSi Correlator
            firmware_revision: The firmware revision of the LSi Correlator
            filepath: The directory in which to place data files
            macros: Dictionary of macros for this IOC
        """
        self.macros = macros

        if macros["SIMULATE"] == "1":
            print("WARNING! Started in simulation mode")
            self.mocked_api = MockedCorrelatorAPI()
            self.device = self.mocked_api.device
        else:
            self.device = LSICorrelator(host, firmware_revision)

        self.is_connected = self.device.isConnected()
        self.corr = None
        self.lags = None

    def get_data_as_arrays(self):
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
        Sends settings parameters to the LSi driver and takes data from the LSi Correlator with the given number of
        repetitions.
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
            # print(corr)
            # print(lags)
            self.corr = corr
            self.lags = lags

    def save_data(self, user_filename: str, archive_filename: str, metadata: Dict):
        """
        Write the correlation function and time lags to file.

        Args:
            correlation (float array): The correlation function
            time_lags (float array): The time lags
            trace_a (float array): The 'raw' trace A counts from the correlator
            trace_b (float array): The 'raw' trace B from the correlator
            trace_time (float array): The elapsed time at which each raw data point was collected
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

        for filename in [user_filename, archive_filename]:
            with open(filename, 'w+') as dat_file:
                dat_file.write(save_file)
