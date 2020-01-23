from __future__ import print_function, unicode_literals, division, absolute_import

import argparse
import sys
import os
import traceback
from collections import namedtuple
from enum import Enum
from functools import partial

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


from PVConfig import get_pv_configs

def _error_handler(func):
    @six.wraps(func)
    def _wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:
            print_and_log(traceback.format_exc(), src="lsi ")
    return _wrapper


THREADPOOL = ThreadPoolExecutor()


# SettingPVConfig is a data type to store information about the PVs used to set parameters in the LSi driver.
# convert_from_pv is a function which takes in the raw PV value and returns it in a form which can be accepted by the driver.
# convert_to_pv is a function which takes in the locally held PV value and returns a form which can be sent to the PV.
# set_on_device is the function in the LSICorrelator class which writes the requested setting.
SettingPVConfig = namedtuple("SettingPVConfig", ["convert_from_pv", "convert_to_pv", "set_on_device"])


def convert_pv_enum_to_lsi_enum(enum_class, pv_value):
    """
    Takes the value of the enum from the PV and returns the LSI_Param associated with this value

    Args:
        enum_class (Enum): The LSI_Param Enum containing the device parameters
        pv_value (int): The enumerated value from the PV
    """
    return [enum for enum in enum_class][pv_value]


def convert_lsi_enum_to_pv_value(enum_class, current_state):
    """
    Takes a driver parameter and returns its associated enum value for the PV

    Args:
        enum_class (Enum): The LSI_Param Enum containing the device parameters
        current_state: The Enum member to be looked up and written to the PV
    """

    return [enum for enum in enum_class].index(current_state)


def do_nothing(value):
    """
    No-op for outputs which do not need modifying
    """
    return value


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

        self.SettingPVs = {
            PvNames.CORRELATIONTYPE: SettingPVConfig(convert_from_pv=partial(convert_pv_enum_to_lsi_enum, LSI_Param.CorrelationType),
                                                     convert_to_pv=partial(convert_lsi_enum_to_pv_value, LSI_Param.CorrelationType),
                                                     set_on_device=self.device.setCorrelationType),

            PvNames.NORMALIZATION: SettingPVConfig(convert_from_pv=partial(convert_pv_enum_to_lsi_enum, LSI_Param.Normalization),
                                                   convert_to_pv=partial(convert_lsi_enum_to_pv_value, LSI_Param.Normalization),
                                                   set_on_device=self.device.setNormalization),

            PvNames.MEASUREMENTDURATION: SettingPVConfig(convert_from_pv=round, convert_to_pv=do_nothing,
                                                         set_on_device=self.device.setMeasurementDuration),

            PvNames.SWAPCHANNELS: SettingPVConfig(convert_from_pv=partial(convert_pv_enum_to_lsi_enum, LSI_Param.SwapChannels),
                                                  convert_to_pv=partial(convert_lsi_enum_to_pv_value, LSI_Param.SwapChannels),
                                                  set_on_device=self.device.setSwapChannels),

            PvNames.SAMPLINGTIMEMULTIT: SettingPVConfig(convert_from_pv=partial(convert_pv_enum_to_lsi_enum, LSI_Param.SamplingTimeMultiT),
                                                        convert_to_pv=partial(convert_lsi_enum_to_pv_value, LSI_Param.SamplingTimeMultiT),
                                                        set_on_device=self.device.setSamplingTimeMultiT),

            PvNames.TRANSFERRATE: SettingPVConfig(convert_from_pv=partial(convert_pv_enum_to_lsi_enum, LSI_Param.TransferRate),
                                                  convert_to_pv=partial(convert_lsi_enum_to_pv_value, LSI_Param.TransferRate),
                                                  set_on_device=self.device.setTransferRate),

            PvNames.OVERLOADLIMIT: SettingPVConfig(convert_from_pv=round, convert_to_pv=do_nothing,
                                                   set_on_device=self.device.setOverloadLimit),

            PvNames.OVERLOADINTERVAL: SettingPVConfig(convert_from_pv=round, convert_to_pv=do_nothing,
                                                      set_on_device=self.device.setOverloadTimeInterval),

            PvNames.ERRORMSG: SettingPVConfig(convert_from_pv=do_nothing, convert_to_pv=do_nothing, set_on_device=do_nothing)
        }

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
            PvNames.ERRORMSG: ""
        }
        self.updatePVs()

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

        PV_value = self.PVValues[reason]
        if isinstance(PV_value, Enum):
            []


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


if __name__ == "__main__":
    main()
