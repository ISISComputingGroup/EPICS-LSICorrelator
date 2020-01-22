from __future__ import print_function, unicode_literals, division, absolute_import

import argparse
import sys
import os
import traceback
import six

from pcaspy import SimpleServer, Driver
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))
sys.path.insert(1, 'C:\\Instrument\\Dev\\LSI-Correlator')
sys.path.insert(2, 'C:\\Instrument\\Apps\\EPICS\\ISIS\\inst_servers\\master\\')

from LSI import LSI_Param
from LSICorrelator import LSICorrelator

from pvdb import STATIC_PV_DATABASE, PvNames
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


def get_pv_data_type(reason):
    """
    Returns the data type of the given PV
    Args:
        reason (string): The PV to get the data type of
    """

    return STATIC_PV_DATABASE[reason].type


def needs_rounding(reason):
    """
    Returns True if the PV is a float acting as an integer (has zero precision). Otherwise False
    Args:
        reason (string): The PV which has been written to
    """
    pv = STATIC_PV_DATABASE[reason]

    if 'prec' in pv and pv['type'] == 'float' and pv['prec'] == 0:
        return True
    else:
        return False


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

        self._correlation_type = LSI_Param.CorrelationType.AUTO
        self._normalization = LSI_Param.Normalization.COMPENSATED
        self._measurement_duration = 300
        self._swap_channels = LSI_Param.SwapChannels.ChA_ChB
        self._sampling_time_multi_t = LSI_Param.SamplingTimeMultiT.ns200
        self._transfer_rate = LSI_Param.TransferRate.ms100
        self._overload_limit = 20
        self._overload_time_interval = 400
        self._error_message = ""

        self.updatePVs()

    @_error_handler
    def write(self, reason, value):
        """
        Handle write to PV
        Args:
            reason (str): PV to set value of
            value: Value to set
        """
        print_and_log("LSiCorrelatorDriver: Processing PV write for reason {}".format(reason))

        if reason in STATIC_PV_DATABASE.keys():
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

        if reason == PvNames.MEASUREMENTDURATION:
            return self._measurement_duration
        elif reason in PvNames.ERRORMSG:
            return self._error_message
        elif reason in STATIC_PV_DATABASE.keys():
            return 300.0
        else:
            print_and_log("LSiCorrelatorDriver: Could not read from PV '{}': not known".format(reason), "MAJOR")

        #if reason == PvNames.INSTRUMENT:
        #    return six.binary_type(self._remote_pv_prefix if self._remote_pv_prefix is not None else "NONE")
        #else:
        #    print_and_log("RemoteIocListDriver: Could not read from PV '{}': not known".format(reason), "MAJOR")

    @_error_handler
    def update_pv_value(self, reason, value):
        """
        Adds a PV update to the thread pool

        Args:
            reason (str): PV to read
            value: The value to set
        """

        if needs_rounding(reason):
            value = round(value)

        if reason == PvNames.MEASUREMENTDURATION:
            try:
                self.write_measurement_duration(value)
            except ValueError as err:
                print_and_log("Error setting PV {pv} to {value}: {error}".format(pv=reason, value=value, error=err))
                self._error_message = "{}".format(err)
            else:
                # Only update value if LSi code hasn't returned a ValueError
                self._measurement_duration = value

    def get_device_setting_function(self, reason):
        """
        Returns the setter on the LSi device driver for the requested PV

        Args:
            reason (string): The PV being written to
        """
        pv_lookup = {
            "CORRELATIONTYPE": self.device.setCorrelationType,
            "NORMALIZATION": self.device.setNormalization,
            "MEASUREMENTDURATION": self.device.setMeasurementDuration,
            "SWAPCHANNELS": self.device.setSwapChannels,
            "SAMPLINGTIMEMULTIT": self.device.setSamplingTimeMultiT,
            "TRANSFERRATE": self.device.setTransferRate,
            "OVERLOADLIMIT": self.device.setOverloadLimit,
            "OVERLOADINTERVAL": self.device.setOverloadTimeInterval
        }

        return pv_lookup[reason]

    def write_measurement_duration(self, value):
        """
        Sets the measurment duration in the LSi Correlator class to value
        Args:
            value (float): The duration of the measurement in seconds
        """
        device_setter = self.get_device_setting_function("MEASUREMENTDURATION")
        device_setter(value)

    def apply_setting(self, pv, value):
        """
        Updates a setting PV with value.

        Args:
            reason (string): The name of the PV to update
            value : The new value of the PV
        """

        pass

    def take_data(self, number_of_repetitions):
        pass

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

    #ioc_data_source = IocDataSource(SQLAbstraction("iocdb", "iocdb", "$iocdb"))
    #ioc_data_source.insert_ioc_start("LSI", os.getpid(), sys.argv[0], STATIC_PV_DATABASE, "TE:NDW1836:LSI:")


if __name__ == "__main__":
    main()
