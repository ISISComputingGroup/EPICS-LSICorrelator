from __future__ import print_function, unicode_literals, division, absolute_import

import argparse
import sys
import os
import traceback

import six

from pcaspy import SimpleServer, Driver
from concurrent.futures import ThreadPoolExecutor
import numpy as np

from time import sleep

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))
sys.path.insert(1, 'C:\\Instrument\\Dev\\LSI-Correlator')
sys.path.insert(2, 'C:\\Instrument\\Apps\\EPICS\\ISIS\\inst_servers\\master\\')

from LSI import LSI_Param
from LSICorrelator import LSICorrelator

from pvdb import STATIC_PV_DATABASE, PvNames
from PVConfig import get_pv_configs
from BlockServer.core.file_path_manager import FILEPATH_MANAGER
from server_common.utilities import print_and_log
from server_common.ioc_data_source import IocDataSource
from server_common.mysql_abstraction_layer import SQLAbstraction


def _error_handler(func):
    @six.wraps(func)
    def _wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:
            print_and_log(traceback.format_exc(), src="lsi ")
    return _wrapper


THREADPOOL = ThreadPoolExecutor()


class LSiCorrelatorDriver(Driver):
    """
    A driver for the LSi Correlator
    """

    def __init__(self, pv_prefix, host, firmware_revision):
        """
        A driver for the LSi Correlator

        Args:
            pv_prefix: the pv prefix
            host (string): The IP address of the LSi Correlator
            firmware (string): The firmware revision of the LSi Correlator
        """
        super(LSiCorrelatorDriver, self).__init__()

        self.device = LSICorrelator(host, firmware_revision)

        self.SettingPVs = get_pv_configs(self.device)

        self.PVValues = {
            PvNames.CORRELATIONTYPE: LSI_Param.CorrelationType.AUTO,
            PvNames.NORMALIZATION: LSI_Param.Normalization.COMPENSATED,
            PvNames.MEASUREMENTDURATION: 300,
            PvNames.SWAPCHANNELS: LSI_Param.SwapChannels.ChA_ChB,
            PvNames.SAMPLINGTIMEMULTIT: LSI_Param.SamplingTimeMultiT.ns200,
            PvNames.TRANSFERRATE: LSI_Param.TransferRate.ms100,
            PvNames.OVERLOADLIMIT: 20,
            PvNames.OVERLOADINTERVAL: 400,
            PvNames.ERRORMSG: "",
            PvNames.TAKEDATA: 0,
            PvNames.REPETITIONS: 1,
            PvNames.CURRENT_REPEAT: 0,
            PvNames.CORRELATION_FUNCTION: [],
            PvNames.LAGS: [],
            PvNames.FILEPATH: ""
        }

        for pv, preset in self.PVValues.items():
            # Write defaults to device
            print('setting {} to {}', pv, preset)
            self.SettingPVs[pv].set_on_device(preset)

        self.updatePVs()

        self._corr = []
        self._lags = []

    def update_error_pv(self, error_message):
        """
        Helper function to update the error string PV

        Args:
            error_message (str): The string to write to the error PV
        """
        self.PVValues[PvNames.ERRORMSG] = error_message

    @_error_handler
    def write(self, reason, value):
        """
        Handle write to PV
        Args:
            reason (str): PV to set value of
            value: Value to set
        """
        print_and_log("LSiCorrelatorDriver: Processing PV write for reason {}".format(reason))

        if reason == PvNames.TAKEDATA:
            THREADPOOL.submit(self.take_data())

        elif reason in STATIC_PV_DATABASE.keys():
            THREADPOOL.submit(self.update_pv_value, reason, value)
        else:
            print_and_log("LSiCorrelatorDriver: Could not write to PV '{}': not known".format(reason), "MAJOR")

        # Update PVs after any write.
        self.updatePVs()

    @_error_handler
    def read(self, reason):
        """
        Handle read of PV
        Args:
            reason (str): PV to read value of
        """
        print_and_log("LSiCorrelatorDriver: Processing PV read for reason {}".format(reason))
        self.updatePVs()  # Update PVs before any read so that they are up to date.

        try:
            PV_value = self.PVValues[reason]

            PV_value = self.SettingPVs[reason].convert_to_pv(PV_value)

            return PV_value

        except KeyError:
            print_and_log("LSiCorrelatorDriver: Could not read from PV '{}': not known".format(reason), "MAJOR")

    @_error_handler
    def update_pv_value(self, reason, value):
        """
        Adds a PV update to the thread pool

        Args:
            reason (str): PV to read
            value: The value to set
        """

        print_and_log(value)
        print_and_log(self.SettingPVs[reason].convert_from_pv(value))

        try:
            sanitised_value = self.SettingPVs[reason].convert_from_pv(value)
            print_and_log("setting {} to {}".format(reason, sanitised_value))
            self.SettingPVs[reason].set_on_device(sanitised_value)

            self.PVValues[reason] = sanitised_value
        except ValueError as err:
            print_and_log("Error setting PV {pv} to {value}: {error}".format(pv=reason, value=value, error=err))
            self.update_error_pv("{}".format(err))
        except KeyError:
            print_and_log("Can't write to PV {}, PV not found".format(reason))

    def write_setting(self, reason, value):
        """
        Sets the measurment duration in the LSi Correlator class to value
        Args:
            value (float): The duration of the measurement in seconds
        """
        device_setter = self.get_device_setting_function(reason)
        device_setter(value)

    @_error_handler
    def take_data(self):
        """
        Sends settings parameters to the LSi driver and takes data from the LSi Correlator with the given number of repetitions.

        Args:
            number_of_repetitions (int): The number of repetitions to perform.
        """
        self.device.configure()

        for repeat in range(self.PVValues[PvNames.REPETITIONS]):
            self.PVValues[PvNames.CURRENT_REPEAT] = repeat

            self.device.start()

            while self.device.MeasurementOn():
                sleep(0.5)
                self.device.update()

            Corr = np.asarray(self.device.Correlation)
            Lags = np.asarray(self.device.Lags)

            Lags = Lags[np.isfinite(Corr)]
            Corr = Corr[np.isfinite(Corr)]

            self.PVValues[PvNames.CORRELATION_FUNCTION] = Corr
            self.PVValues[PvNames.LAGS] = Lags

            self.save_data(Corr, Lags)

    def add_repetition_to_filename(self, filename):
        """
        Adds the current repetition number to the supplied filename

        Args:
            filename (str): The filename
        """

        filename_components = filename.split('.')

        appended_filename = "{}_{}".format(filename_components[0], self.PVValues[PvNames.CURRENT_REPEAT])
        filename_components[0] = appended_filename

        return '.'.join(filename_components)

    def save_data(self, correlation, time_lags):
        """
        Write the correlation function and time lags to file.

        Args:
            correlation (float array): The correlation function
            time_lags (float array): The time lags
        """

        filename = self.add_repetition_to_filename(self.PVValues[PvNames.FILEPATH])

        with open(filename, 'w') as f:
            data = np.vstack((time_lags, correlation)).T

            np.savetxt(f, data, delimiter=',', header='Time Lags,Correlation Function', fmt='%1.4e')

    def set_remote_pv_prefix(self, remote_pv_prefix):
        """
        Set the pv prefix for the remote server.
        Args:
            remote_pv_prefix: new prefix to use

        Returns:

        """
        print_and_log("LSiCorrelatorDriver: setting instrument to {} (old: {})"
                      .format(remote_pv_prefix, self._remote_pv_prefix))
        self._remote_pv_prefix = remote_pv_prefix
        self._autosave.write_parameter(AUTOSAVE_REMOTE_PREFIX_NAME, remote_pv_prefix)

        THREADPOOL.submit(self._configuration_monitor.set_remote_pv_prefix, remote_pv_prefix)
        THREADPOOL.submit(self.restart_all_iocs)
        THREADPOOL.submit(self._gateway.set_remote_pv_prefix, remote_pv_prefix)
        self.updatePVs()
        print_and_log("LSiCorrelatorDriver: Finished setting instrument to {}".format(self._remote_pv_prefix))


def serve_forever(pv_prefix):
    """
    Server the PVs for the remote ioc server
    Args:
        pv_prefix: prefex for the pvs
        subsystem_prefix: prefix for the PVs published by the remote IOC server
        gateway_pvlist_path: The path to the gateway pvlist file to generate
        gateway_acf_path: The path to the gateway access security file to generate
        gateway_restart_script_path: The path to the script to call to restart the remote ioc gateway

    Returns:

    """
    server = SimpleServer()

    server.createPV("{}LSI:".format(pv_prefix), STATIC_PV_DATABASE)

    # Looks like it does nothing, but this creates *and automatically registers* the driver
    # (via metaclasses in pcaspy). See declaration of DriverType in pcaspy/driver.py for details
    # of how it achieves this.
    pv_prefix = 'TE:NDW1836:'
    ip_address = '127.0.0.1'
    firmware_revision = '4.0.0.3'
    LSiCorrelatorDriver(pv_prefix, ip_address, firmware_revision)

    try:
        while True:
            server.process(0.1)
    except Exception:
        print_and_log(traceback.format_exc())
        raise


def main():
    """
    Parse the command line argumnts and run the remote IOC server.
    """
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="Runs a remote IOC server.",
    )

    parser.add_argument("--pv_prefix", required=True, type=six.text_type,
                        help="The PV prefix of this instrument.")

    args = parser.parse_args()

    FILEPATH_MANAGER.initialise(os.path.normpath(os.getenv("ICPCONFIGROOT")), "", "")

    print("IOC started")

    serve_forever(
        args.pv_prefix,
    )


if __name__ == "__main__":
    main()
