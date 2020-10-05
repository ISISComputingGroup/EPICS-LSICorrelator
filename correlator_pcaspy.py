from __future__ import print_function, unicode_literals, division, absolute_import

import argparse
import sys
import os
import traceback
from typing import Dict

import six

from pcaspy import SimpleServer, Driver
from pcaspy.tools import ServerThread
from pcaspy.alarm import Alarm, Severity
from concurrent.futures import ThreadPoolExecutor

from datetime import datetime

sys.path.insert(1, os.path.join(os.getenv("EPICS_KIT_ROOT"), "support", "lsicorr_vendor", "master"))
sys.path.insert(2, os.path.join(os.getenv("EPICS_KIT_ROOT"), "ISIS", "inst_servers", "master"))

from LSI import LSI_Param
#from LSICorrelator import LSICorrelator
from correlator_driver_functions import LSiCorrelatorDriver

from mocked_correlator_api import MockedCorrelatorAPI

from pvdb import STATIC_PV_DATABASE, Records
from BlockServer.core.file_path_manager import FILEPATH_MANAGER
from server_common.utilities import print_and_log
from server_common.channel_access import ChannelAccess
from server_common.helpers import register_ioc_start, get_macro_values
from file_format import FILE_SCHEME

from mock import MagicMock

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


def get_base_pv(reason: str):
    """ Trims trailing :SP off a PV name """
    return reason[:-3]


THREADPOOL = ThreadPoolExecutor()

# Magic number, seems to be time between measurements.
DELTA_T = 0.0524288

# PVs from the DAE to get information about instrument
RUNNUMBER_PV = "{pv_prefix}DAE:RUNNUMBER"
TITLE_PV = "{pv_prefix}DAE:TITLE"
INSTNAME_PV = "{pv_prefix}DAE:INSTNAME"


def remove_non_ascii(text_to_check):
    """
    Removes non-ascii and other characters from the supplied text
    """
    # Remove anything other than alphanumerics and dashes/underscores
    parsed_text = [char for char in text_to_check if char.isalnum() or char in '-_']
    return ''.join(parsed_text)


class LSiPcaspy(Driver):
    """
    A driver for the LSi Correlator
    """

    def __init__(self, host: str, pv_prefix: str, firmware_revision: str, filepath: str, macros: Dict[str, str]):
        """
        A driver for the LSi Correlator

        Args:
            host: The IP address of the LSi Correlator
            firmware_revision: The firmware revision of the LSi Correlator
            filepath: The directory in which to place data files
            macros: Dictionary of macros for this IOC
        """
        super().__init__()

        self.driver = LSiCorrelatorDriver(host, pv_prefix, firmware_revision, filepath, macros)

        self.macros = macros

        self.pv_prefix = pv_prefix

        defaults = {
            Records.CORRELATIONTYPE.value: LSI_Param.CorrelationType.AUTO,
            Records.NORMALIZATION.value: LSI_Param.Normalization.COMPENSATED,
            Records.MEASUREMENTDURATION.value: 10,
            Records.SWAPCHANNELS.value: LSI_Param.SwapChannels.ChA_ChB,
            Records.SAMPLINGTIMEMULTIT.value: LSI_Param.SamplingTimeMultiT.ns200,
            Records.TRANSFERRATE.value: LSI_Param.TransferRate.ms100,
            Records.OVERLOADLIMIT.value: 20,
            Records.OVERLOADINTERVAL.value: 400,
            Records.REPETITIONS.value: 2,
            Records.CURRENT_REPETITION.value: 0,
            Records.CONNECTED.value: self.driver.is_connected,
            Records.RUNNING.value: False,
            Records.SCATTERING_ANGLE.value: 2.2,
            Records.SAMPLE_TEMP.value: 300,
            Records.SOLVENT_VISCOSITY.value: 1100,
            Records.SOLVENT_REFRACTIVE_INDEX.value: 1.1,
            Records.LASER_WAVELENGTH.value: 440,
            Records.OUTPUTFILE.value: "No data taken yet",
            Records.SIM.value: 0,
            Records.DISABLE.value: 0
        }

        self.user_filepath = filepath

        self.alarm_status = Alarm.NO_ALARM
        self.alarm_severity = Severity.NO_ALARM

        if not os.path.isdir(filepath):
            self.update_error_pv_print_and_log("LSiCorrelatorDriver: {} is invalid file path".format(filepath), "MAJOR")

        for record, default_value in defaults.items():
            # Write defaults to device
            print_and_log("setting {} to default {}".format(record.name, default_value))
            self.update_pv_and_write_to_device(record.name, record.convert_to_pv(default_value))

        self.updatePVs()

    def update_error_pv_print_and_log(self, error: str, severity: str = "INFO", src: str = "LSI") -> None:
        """
        Updates the error PV with the provided error message, then prints and logs the error

        Args:
            error: The error message
            severity (optional): Gives the severity of the message. Expected serverities are MAJOR, MINOR and INFO.
            src (optional): Gives the source of the message. Default source is LSI (from this IOC).
        """

        self.update_pv_and_write_to_device(Records.ERRORMSG.name, error)
        print_and_log(error, severity, src)

    def set_disconnected_alarms(self, in_alarm: bool):
        """ Sets disconnected alarms if in_alarm is True """
        ### Maybe have a method in the new class like is_device_disconnected() which this method can poll?
        if in_alarm:
            severity = Severity.INVALID_ALARM
            status = Alarm.TIMEOUT_ALARM
        else:
            severity = Severity.NO_ALARM
            status = Alarm.NO_ALARM

        self.alarm_status = status
        self.alarm_severity = severity

        for record in Records:
            self.setParamStatus(record.name, status, severity)

    def get_converted_pv_value(self, reason):
        """
        If the supplied reason has a defining record, applies the convert_from_pv transformation to current pv value
        else returns current pv value.

        Args:
            reason (str): The name of the PV to get the value of
        """
        pv_value = self.read(reason)

        try:
            record = Records[reason].value
            sanitised_value = record.convert_from_pv(pv_value)
        except KeyError:
            # reason has no defining record
            sanitised_value = pv_value

        return sanitised_value

    def update_param_and_fields(self, reason, value):
        """
        Updates given param, VAL field, and alarm status/severity in PCASpy driver
        """
        try:
            self.setParam(reason, value)
            self.setParam("{reason}.VAL".format(reason=reason), value)
            self.setParamStatus(reason, self.alarm_status, self.alarm_severity)
        except ValueError as err:
            self.update_error_pv_print_and_log("Error setting PV {pv} to {value}:".format(pv=reason, value=value))
            self.update_error_pv_print_and_log("{}".format(err))

    @_error_handler
    def update_pv_and_write_to_device(self, reason, value, update_setpoint: bool = False):
        """
        Helper function to update the value of a PV held in this driver and sets the value on the device.

        Args:
            reason (str): The name of the PV to set
            value: The new value for the PV
            update_setpoint: If True, also updates reason:SP pv
        """

        try:
            record = Records[reason]
        except KeyError:
            self.update_error_pv_print_and_log("Can't update PV {}, PV not found".format(reason))
            record = None

        if record is not None:
            # Need to go through both input sanitisers to make sure we set enum values correctly
            value_for_lsi_driver = record.value.convert_from_pv(value)
            new_pv_value = record.value.convert_to_pv(value_for_lsi_driver)
            try:
                record.value.set_on_device(self.driver.device, value_for_lsi_driver)
            except ValueError as e:
                self.update_error_pv_print_and_log("Can't update PV {}, invalid value".format(reason))
                self.update_error_pv_print_and_log(str(e))
                return
            else:
                # No error raised, set new value to pv/params
                self.update_param_and_fields(reason, new_pv_value)
                if update_setpoint:
                    self.update_param_and_fields("{reason}:SP".format(reason=reason), new_pv_value)

        # Update PVs after any write
        self.updatePVs()

    def set_array_pv_value(self, reason, value):
        """
        Helper function to update the value of an array PV and the array PV fields (NORD)
        Args:
            reason (str): The name of the PV to set
            value: The new values to write to the array
        """
        self.update_pv_and_write_to_device(reason, value)
        self.setParam("{reason}.NORD".format(reason=reason), len(value))

    @_error_handler
    def write(self, reason: str, value):
        """
        Handle write to PV
        Args:
            reason: PV to set value of
            value: Value to set
        """
        print_and_log("LSiCorrelatorDriver: Processing PV write for reason {} value {}".format(reason, value))
        if reason == Records.START.name:
            THREADPOOL.submit(self.take_data)

        if reason.endswith(":SP"):
            # Update both SP and non-SP fields
            THREADPOOL.submit(self.update_pv_and_write_to_device, get_base_pv(reason), value, update_setpoint=True)
        else:
            THREADPOOL.submit(self.update_pv_and_write_to_device, reason, value)

    @_error_handler
    def read(self, reason):
        """
        Handle read of PV
        Args:
            reason (str): PV to read value of
        """

        self.updatePVs()  # Update PVs before any read so that they are up to date.

        if reason.endswith(":SP"):
            pv_value = self.getParam(get_base_pv(reason))
        else:
            pv_value = self.getParam(reason)

        return pv_value

    @_error_handler
    def take_data(self):
        """
        Sends settings parameters to the LSi driver and takes data from the LSi Correlator with the given number of
        repetitions.
        """
        try:
            self.driver.configure()
        except RuntimeError as e:
            self.update_error_pv_print_and_log(str(e))

        no_repetitions = self.get_converted_pv_value(Records.REPETITIONS.name)
        for repeat in range(1, no_repetitions+1):
            self.update_pv_and_write_to_device(Records.CURRENT_REPETITION.name, repeat)

            self.update_pv_and_write_to_device(Records.RUNNING.name, True)

            self.driver.take_data()

            self.update_pv_and_write_to_device(Records.RUNNING.name, False)

            if self.driver.has_data:
                self.set_array_pv_value(Records.CORRELATION_FUNCTION.name, self.driver.corr)
                self.set_array_pv_value(Records.LAGS.name, self.driver.lags)
                self.driver.save_data(self.get_user_filename(), self.get_archive_filename(), self.get_metadata())
            else:
                # No data returned, correlator may be disconnected
                self.update_pv_and_write_to_device(Records.CONNECTED.name, False)
                self.update_error_pv_print_and_log("LSiCorrelatorDriver: No data read, device could be disconnected",
                                                   "INVALID")
                self.set_disconnected_alarms(True)

        # Attempt to set start PV back to NO, purely for aesthetics (this PV is actually always ready)
        self.update_param_and_fields(Records.START.name, 0)
        self.update_param_and_fields("{pv}:SP".format(pv=Records.START.name), 0)

    def get_metadata(self) -> Dict:
        """
        Returns a dictionary containing meta data to be saved
        """
        metadata = {}
        metadata_records = [
            Records.SCATTERING_ANGLE,
            Records.MEASUREMENTDURATION,
            Records.LASER_WAVELENGTH,
            Records.SOLVENT_REFRACTIVE_INDEX,
            Records.SOLVENT_VISCOSITY,
            Records.SAMPLE_TEMP
        ]
        for record in metadata_records:
            metadata[record.name] = self.get_converted_pv_value(record.name)
        
        return metadata

    def get_archive_filename(self):
        """
        Returns a filename which the archive data file will be saved with
        """
        filename = "{instrument}{run_number}_DLS_{timestamp}.txt"
        timestamp = datetime.now().strftime("%Y-%m-%dT%H_%M_%S")
        run_number = ChannelAccess.caget(RUNNUMBER_PV.format(pv_prefix=self.pv_prefix))
        instrument = ChannelAccess.caget(INSTNAME_PV.format(pv_prefix=self.pv_prefix))
        
        filename = "{instrument}{run_number}_DLS_{timestamp}.txt".format(instrument=instrument,
                                                                         run_number=run_number,
                                                                         timestamp=timestamp)

        full_filename = os.path.join(DATA_DIR, filename)
        return full_filename

    def get_user_filename(self):
        """ Returns a filename given the current run number and title """
        run_number = ChannelAccess.caget(RUNNUMBER_PV.format(pv_prefix=self.pv_prefix))
        timestamp = datetime.now().strftime("%Y-%m-%dT%H_%M_%S")

        experiment_name = self.get_converted_pv_value(Records.EXPERIMENTNAME.name)

        if experiment_name == "":
            # No name supplied, use run title
            experiment_name = ChannelAccess.caget(TITLE_PV.format(pv_prefix=self.pv_prefix))

        filename = "{run_number}_{experiment_name}_{timestamp}.dat".format(
            run_number=run_number, experiment_name=remove_non_ascii(experiment_name), timestamp=timestamp
            )

        self.filename = filename
        # Update last used filename PV
        self.update_pv_and_write_to_device(Records.OUTPUTFILE.name, os.path.join(self.user_filepath, filename))

        full_filepath = os.path.join(self.user_filepath, filename)

        return full_filepath


def serve_forever(ioc_name: str, pv_prefix: str, macros: Dict[str, str]):
    """
    Server the PVs for the remote ioc server
    Args:
        ioc_name: The name of the IOC to be run, including ioc number (e.g. LSICORR_01)
        pv_prefix: prefix for the pvs
        macros: Dictionary containing IOC macros
    Returns:

    """
    ioc_name_with_pv_prefix = "{pv_prefix}{ioc_name}:".format(pv_prefix=pv_prefix, ioc_name=ioc_name)
    print_and_log(ioc_name_with_pv_prefix)
    server = SimpleServer()

    server.createPV(ioc_name_with_pv_prefix, STATIC_PV_DATABASE)

    # Looks like it does nothing, but this creates *and automatically registers* the driver
    # (via metaclasses in pcaspy). See declaration of DriverType in pcaspy/driver.py for details
    # of how it achieves this.
    ip_address = '127.0.0.1'
    firmware_revision = '4.0.0.3'
    # driver = LSiCorrelatorDriver(ip_address, pv_prefix, firmware_revision, USER_FILE_DIR, macros)
    LSiPcaspy(ip_address, pv_prefix, firmware_revision, USER_FILE_DIR, macros)

    register_ioc_start(ioc_name, STATIC_PV_DATABASE, ioc_name_with_pv_prefix)

    try:
        while True:
            server.process(0.1)
    except Exception:
        print_and_log(traceback.format_exc())
        raise


def main():
    """
    Parse the command line arguments and run the remote IOC server.
    """
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="Runs a remote IOC server.",
    )

    parser.add_argument("--ioc_number", default=1, type=int)

    parser.add_argument("--pv_prefix", required=True, type=six.text_type,
                        help="The PV prefix of this instrument.")

    args = parser.parse_args()

    FILEPATH_MANAGER.initialise(os.path.normpath(os.getenv("ICPCONFIGROOT")), "", "")

    print("IOC started")

    ioc_name = "LSICORR_{:02d}".format(args.ioc_number)

    macros = get_macro_values()

    serve_forever(
        ioc_name,
        args.pv_prefix,
        macros
    )


if __name__ == "__main__":
    main()