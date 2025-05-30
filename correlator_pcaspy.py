"""
Correlator pcaspy and IOC Elements of the LSiCorrelator IOC
"""

from __future__ import absolute_import, division, print_function, unicode_literals

import argparse
import os
import sys
import time
import traceback

# pylint: disable=wrong-import-position
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Dict

sys.path.insert(1, os.path.join(os.getenv("EPICS_KIT_ROOT"), "support", "lsicorr_vendor", "master"))
sys.path.insert(2, os.path.join(os.getenv("EPICS_KIT_ROOT"), "ISIS", "inst_servers", "master"))

from server_common.file_path_manager import FILEPATH_MANAGER  # pylint: disable=import-error
from pcaspy import Driver, SimpleServer  # pylint: disable=import-error
from pcaspy.alarm import Alarm, Severity  # pylint: disable=import-error
from server_common.channel_access import ChannelAccess  # pylint: disable=import-error
from server_common.helpers import (  # pylint: disable=import-error
    get_macro_values,
    register_ioc_start,
)
from server_common.utilities import print_and_log  # pylint: disable=import-error

from config import PV, Constants, Defaults, LSiPVSeverity, Macro
from correlator_driver_functions import LSiCorrelatorVendorInterface, _error_handler
from pvdb import STATIC_PV_DATABASE, Records

NANOSECONDS_TO_SECONDS = 1e9


def get_base_pv(reason: str) -> str:
    """
    Trims trailing :SP off a PV name
    @param reason (str): The PV name to trim
    @return (str): The trimmed PV name
    """
    return reason[:-3]


THREADPOOL = ThreadPoolExecutor()


def remove_non_ascii(text_to_check: str) -> str:
    """
    Removes non-ascii and other characters from the supplied text
    @param text_to_check (str): The text to check
    @return (str): The cleaned text
    """
    # Remove anything other than alphanumerics and dashes/underscores
    parsed_text = [char for char in text_to_check if char.isalnum() or char in "-_"]
    return "".join(parsed_text)


class LSiCorrelatorIOC(Driver):
    """
    A class containing pcaspy and IOC elements of the LSiCorrelator IOC.
    """

    # pylint: disable=too-many-instance-attributes
    def __init__(self, pv_prefix: str, macros: Dict[str, str]) -> None:
        """
        A class containing pcaspy and IOC elements of the LSiCorrelator IOC.
        @param pv_prefix (str): The prefix to use for all PVs
        @param macros (Dict[str, str]): A dictionary of macros to use for the IOC
        """
        super().__init__()

        try:
            self.user_filepath = macros[Macro.FILEPATH.name]
        except KeyError as key_error:
            raise RuntimeError(
                f"No file path specified to save data to: {key_error}".format(key_error)
            ) from key_error

        self.simulated = macros[Macro.SIMULATE.name] == "1"  # type: bool
        if self.simulated:
            print("WARNING! Started in simulation mode")

        self.driver = LSiCorrelatorVendorInterface(macros, simulated=self.simulated)
        self.macros = macros
        self.pv_prefix = pv_prefix
        self.already_started = False

        # Set up the PV database
        defaults = Defaults.defaults
        defaults[Records.CONNECTED.value] = self.driver.is_connected

        self.alarm_status = Alarm.NO_ALARM
        self.alarm_severity = Severity.NO_ALARM

        if not os.path.isdir(self.user_filepath):
            self.update_error_pv_print_and_log(
                f"LSiCorrelatorDriver: {self.user_filepath} is invalid file path",
                LSiPVSeverity.MAJOR.value,
            )

        for record, default_value in defaults.items():
            # Write defaults to device
            print_and_log(f"setting {record.name} to default {default_value}")
            self.update_pv_and_write_to_device(record.name, record.convert_to_pv(default_value))

        self.updatePVs()

    def update_error_pv_print_and_log(
        self, error: str, severity: LSiPVSeverity = LSiPVSeverity.INFO, src: str = "LSI"
    ) -> None:  # pylint: disable=line-too-long
        """
        Updates the error PV with the provided error message, then prints and logs the error
        @param error (str): The error message to write to the error PV
        @param severity (LSiPVSeverity): The severity of the error
        @param src (str): The source of the error
        """
        self.update_pv_and_write_to_device(Records.ERRORMSG.name, error)
        print_and_log(error, str(severity), src)

    def set_disconnected_alarms(self, in_alarm: bool):
        """
        Sets disconnected alarms if in_alarm is True
        @param in_alarm (bool): Whether to set the disconnected alarms or
        not (True = set, False = clear)
        """
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

    def get_converted_pv_value(self, reason: str) -> Any:
        """
        If the supplied reason has a defining record, applies the convert_from_pv
        transformation to current pv value else returns current pv value.
        @param reason (str): The name of the PV to get the value of (without the prefix)
        @return (Any): The converted PV value
        """
        pv_value = self.read(reason)
        try:
            record = Records[reason].value
            sanitised_value = record.convert_from_pv(pv_value)
        except KeyError:
            # reason has no defining record
            sanitised_value = pv_value
        return sanitised_value

    def update_param_and_fields(self, reason: str, value: Any) -> None:
        """
        Updates given param, VAL field, and alarm status/severity in PCASpy driver
        @param reason (str): The name of the PV to get the value of (without the prefix)
        @param value (Any): Value to update the PV, pv.VAL field, and alarm status/severity with
        """
        try:
            self.setParam(reason, value)
            self.setParam(f"{reason}.VAL", value)
            self.setParamStatus(reason, self.alarm_status, self.alarm_severity)
        except ValueError as err:
            self.update_error_pv_print_and_log(f"Error setting PV {reason} to {value}:")
            self.update_error_pv_print_and_log(f"{err}")

    @_error_handler
    def update_pv_and_write_to_device(
        self, reason: str, value: Any, update_setpoint: bool = False
    ) -> None:  # pylint: disable=line-too-long
        """
        Helper function to update the value of a PV held in this driver and sets the value
        on the device.
        @param reason (str): The name of the PV to set
        @param value (Any): The new value to set the PV to
        @param update_setpoint (bool): Whether to update the setpoint of the device or not
        (defaults to False) - if True, reason:SP pv will be updated
        """

        try:
            record = Records[reason]
        except KeyError:
            self.update_error_pv_print_and_log(f"Can't update PV {reason}, PV not found")
            record = None

        if record is not None:
            # Need to go through both input sanitisers to make sure we set enum values correctly
            value_for_lsi_driver = record.value.convert_from_pv(value)
            new_pv_value = record.value.convert_to_pv(value_for_lsi_driver)
            try:
                record.value.set_on_device(self.driver.device, value_for_lsi_driver)
            except ValueError as error:
                self.update_error_pv_print_and_log(f"Can't update PV {reason}, invalid value")
                self.update_error_pv_print_and_log(str(error))
                return
            else:
                # No error raised, set new value to pv/params
                self.update_param_and_fields(reason, new_pv_value)
                if update_setpoint:
                    self.update_param_and_fields(f"{reason}:SP", new_pv_value)

        # Update PVs after any write
        self.updatePVs()

    def set_array_pv_value(self, reason: str, value: Any) -> None:
        """
        Helper function to update the value of an array PV and the array PV fields (NORD)
        @param reason (str): The name of the PV to set
        @param value (Any): The new value to set the PV to
        """

        self.update_pv_and_write_to_device(reason, value)
        self.setParam(f"{reason}.NORD", len(value))

    @_error_handler
    def write(self, reason: str, value: Any) -> None:
        """
        Handle write to PV
        @param reason (str): The name of the PV to set
        @param value (Any): The new value to set the PV to
        """

        print_and_log(f"LSiCorrelatorDriver: Processing PV write for reason {reason} value {value}")
        if reason == Records.START.name and not self.already_started:
            THREADPOOL.submit(self.take_data)
        elif reason == Records.START.name and self.already_started:
            self.update_error_pv_print_and_log("LSI --- Cannot configure: Measurement active")

        if reason.endswith(":SP"):
            # Update both SP and non-SP fields
            THREADPOOL.submit(
                self.update_pv_and_write_to_device, get_base_pv(reason), value, update_setpoint=True
            )
        else:
            THREADPOOL.submit(self.update_pv_and_write_to_device, reason, value)

    @_error_handler
    def read(self, reason: str) -> Any:
        """
        Handle read of PV
        @param reason (str): The name of the PV to get the value of (without the prefix)
        @return (Any): The value of the PV
        """

        self.updatePVs()  # Update PVs before any read so that they are up to date.
        if reason.endswith(":SP"):
            pv_value = self.getParam(get_base_pv(reason))
        else:
            pv_value = self.getParam(reason)
        return pv_value

    def wait(self, wait_in_seconds) -> None:
        """
        Wait for a specified number of seconds
        @param wait_in_seconds (float): The number of seconds to wait
        """
        self.update_pv_and_write_to_device(Records.WAITING.name, True)
        time.sleep(wait_in_seconds)
        self.update_pv_and_write_to_device(Records.WAITING.name, False)

    @_error_handler
    def take_data(self) -> None:
        """
        Sends settings parameters to the LSi driver and takes data (and saves the data)
        from the LSi Correlator with the given number of repetitions.
        Sends IOC into alarm if no data is returned (as the correlator may be disconnected).
        """
        try:
            self.driver.configure()
        except RuntimeError as error:
            self.update_error_pv_print_and_log(str(error))

        no_repetitions = self.get_converted_pv_value(Records.REPETITIONS.name)
        wait_in_seconds = self.get_converted_pv_value(Records.WAIT.name)
        wait_at_start = self.get_converted_pv_value(Records.WAIT_AT_START.name)
        min_time_lag_ns = self.get_converted_pv_value(Records.MIN_TIME_LAG.name)
        # Convert min time lag to seconds for comparison against lag data
        min_time_lag = min_time_lag_ns / NANOSECONDS_TO_SECONDS
        self.already_started = True
        first_repetition = 1

        self.update_pv_and_write_to_device(Records.TAKING_DATA.name, True)

        for repeat in range(first_repetition, no_repetitions + 1):
            self.update_pv_and_write_to_device(Records.CURRENT_REPETITION.name, repeat)

            if repeat == first_repetition and wait_at_start or repeat != first_repetition:
                self.wait(wait_in_seconds)

            self.update_pv_and_write_to_device(Records.RUNNING.name, True)
            self.driver.take_data(min_time_lag)
            self.update_pv_and_write_to_device(Records.RUNNING.name, False)

            if self.driver.has_data:
                self.set_array_pv_value(Records.CORRELATION_FUNCTION.name, self.driver.corr)
                self.set_array_pv_value(Records.LAGS.name, self.driver.lags)

                # Save data to file
                with open(self.get_user_filename(), "w+", encoding="utf-8") as user_file, open(
                    self.get_archive_filename(), "w+", encoding="utf-8"
                ) as archive_file:
                    self.driver.save_data(
                        min_time_lag, user_file, archive_file, self.get_metadata()
                    )
            else:
                # No data returned, correlator may be disconnected
                self.update_pv_and_write_to_device(Records.CONNECTED.name, False)
                self.update_error_pv_print_and_log(
                    "LSiCorrelatorDriver: No data read, device could be disconnected",
                    LSiPVSeverity.INVALID,
                )
                self.set_disconnected_alarms(True)

        self.update_pv_and_write_to_device(Records.TAKING_DATA.name, False)
        self.already_started = False
        # Set start PV back to NO, purely for aesthetics (this PV is actually always ready)
        self.update_param_and_fields(Records.START.name, 0)
        self.update_param_and_fields(f"{Records.START.name}:SP", 0)

    def get_metadata(self) -> Dict:
        """
        Get the metadata to be saved with the data
        @return (Dict): A dictionary containing meta data to be saved
        """
        metadata = {}
        metadata_records = Defaults.metadata_records
        for record in metadata_records:
            metadata[record.name] = self.get_converted_pv_value(record.name)
        return metadata

    def get_archive_filename(self) -> str:
        """
        Returns a filename which the archive data file will be saved with.

        If device is simulated do not attempt to get instrument name or run number
        from channel access.
        If simulated save file in user directory instead of usual data directory.
        @return (str): Filename to save archive data to
        """
        if self.simulated:
            full_filename = os.path.join(
                self.user_filepath, Constants.SIMULATE_ARCHIVE_DAT_FILE_NAME
            )
        else:
            timestamp = datetime.now().strftime("%Y-%m-%dT%H_%M_%S")
            run_number = ChannelAccess.caget(PV.RUNNUMBER.add_prefix(prefix=self.pv_prefix))
            instrument = ChannelAccess.caget(PV.INSTNAME.add_prefix(prefix=self.pv_prefix))
            filename = f"{instrument}{run_number}_DLS_{timestamp}.txt"

            full_filename = os.path.join(Constants.DATA_DIR, filename)
        return full_filename

    def get_user_filename(self) -> str:
        """
        Returns a filename given the current run number and title.

        If device is simulated do not attempt to get run number or title from channel access
        @return (str): Filename to save user data to
        """

        if self.simulated:
            filename = Constants.SIMULATE_USER_DAT_FILE_NAME
        else:
            run_number = ChannelAccess.caget(PV.RUNNUMBER.add_prefix(prefix=self.pv_prefix))
            print_and_log(f"run number = {run_number}")
            timestamp = datetime.now().strftime("%Y-%m-%dT%H_%M_%S")  # pylint: disable=unused-variable

            experiment_name = self.get_converted_pv_value(Records.EXPERIMENTNAME.name)

            if experiment_name == "":
                # No name supplied, use run title
                experiment_name = ChannelAccess.caget(PV.TITLE.add_prefix(prefix=self.pv_prefix))

            # Remove characters that are not allowed in filename and replace with underscore (_)
            compressed_experiment_name = remove_non_ascii(experiment_name)  # pylint: disable=unused-variable
            filename = f"{run_number}_{compressed_experiment_name}_{timestamp}.dat"

        # Update last used filename PV
        full_filename = os.path.join(self.user_filepath, filename)
        self.update_pv_and_write_to_device(Records.OUTPUTFILE.name, full_filename)

        return full_filename


def serve_forever(ioc_name: str, pv_prefix: str, macros: Dict[str, str]) -> None:
    """
    Serve the PVs for the remote ioc server forever.

    @param ioc_name (str): The name of the IOC to run, including the ioc name (i.e. "LSICORR_01")
    @param pv_prefix (str): The prefix to use for the PVs
    @param macros (Dict[str, str]): The macros to use for the PVs - A dictionary
    containing IOC macros
    @return: None
    """

    ioc_name_with_pv_prefix = "{pv_prefix}{ioc_name}:".format(
        pv_prefix=pv_prefix, ioc_name=ioc_name
    )  # pylint: disable=line-too-long, consider-using-f-string
    print_and_log(ioc_name_with_pv_prefix)
    server = SimpleServer()

    server.createPV(ioc_name_with_pv_prefix, STATIC_PV_DATABASE)

    # Run heartbeat IOC, this is done with a different prefix
    server.createPV(
        prefix="f{pv_prefix}CS:IOC:{ioc_name}:DEVIOS:",
        pvdb={"HEARTBEAT": {"type": "int", "value": 0}},
    )

    # Looks like it does nothing, but this creates *and automatically registers* the driver
    # (via metaclasses in pcaspy). See declaration of DriverType in pcaspy/driver.py for details
    # of how it achieves this.

    LSiCorrelatorIOC(pv_prefix, macros)

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

    parser.add_argument("--ioc_name", required=True, type=str)
    parser.add_argument(
        "--pv_prefix", required=True, type=str, help="The PV prefix of this instrument."
    )

    args = parser.parse_args()

    FILEPATH_MANAGER.initialise(os.path.normpath(os.getenv("ICPCONFIGROOT")), "", "")

    print("IOC started")

    macros = get_macro_values()

    serve_forever(args.ioc_name, args.pv_prefix, macros)


if __name__ == "__main__":
    main()
