from __future__ import print_function, unicode_literals, division, absolute_import

import sys
import os
import traceback
from io import StringIO
from typing import Dict, TextIO, Tuple
import time

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
from server_common.channel_access import ChannelAccess
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
            host = macros["ADDR"]
        except KeyError:
            raise RuntimeError("No IP address specified, cannot start")
        firmware_revision = macros.get("FIRMWARE_REVISION", "4.0.0.3")

        if simulated:
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
    def take_data(self, wait_in_seconds=0):
        """
        Starts taking data from the LSi Correlator once with the currently configure device settings.
        """
        time.sleep(wait_in_seconds)
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

    def get_archive_filename(self):
        """
        Returns a filename which the archive data file will be saved with
        """
        timestamp = datetime.now().strftime("%Y-%m-%dT%H_%M_%S")
        run_number = ChannelAccess.caget(RUNNUMBER_PV.format(pv_prefix=self.pv_prefix))
        instrument = ChannelAccess.caget(INSTNAME_PV.format(pv_prefix=self.pv_prefix))
        
        filename = "{instrument}{run_number}_DLS_{timestamp}.txt".format(instrument=instrument,
                                                                         run_number=run_number,
                                                                         timestamp=timestamp)

        full_filename = os.path.join(DATA_DIR, filename)
        print_and_log("filename1: {}".format(full_filename))
        return full_filename

    def get_user_filename(self):
        """ Returns a filename given the current run number and title """
        run_number = ChannelAccess.caget(RUNNUMBER_PV.format(pv_prefix=self.pv_prefix))
        print_and_log("run number = {}".format(run_number))
        timestamp = datetime.now().strftime("%Y-%m-%dT%H_%M_%S")

        experiment_name = self.get_converted_pv_value(Records.EXPERIMENTNAME.name)

        if experiment_name == "":
            # No name supplied, use run title
            experiment_name = ChannelAccess.caget(TITLE_PV.format(pv_prefix=self.pv_prefix))

        filename = "{run_number}_{experiment_name}_{timestamp}.dat".format(
            run_number=run_number, experiment_name=remove_non_ascii(experiment_name), timestamp=timestamp
            )

        # Update last used filename PV
        full_filename = os.path.join(self.user_filepath, filename)
        print_and_log("filename: {}".format(full_filename))
        self.update_pv_and_write_to_device(Records.OUTPUTFILE.name, full_filename)

        return full_filename


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
