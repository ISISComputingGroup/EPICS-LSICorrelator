from __future__ import print_function, unicode_literals, division, absolute_import

import argparse
import sys
import os
import traceback

import six

from pcaspy import SimpleServer, Driver
from pcaspy.alarm import Alarm, Severity
from concurrent.futures import ThreadPoolExecutor
import numpy as np

from time import sleep
from datetime import datetime
from pathlib import Path

sys.path.insert(1, 'C:\\Instrument\\Dev\\LSI-Correlator')
sys.path.insert(2, os.path.join(os.getenv("EPICS_KIT_ROOT"), "ISIS", "inst_servers", "master"))

from LSI import LSI_Param
from LSICorrelator import LSICorrelator

from pvdb import STATIC_PV_DATABASE, Records, PvNames
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


def get_base_pv(reason: str):
    """ Trims trailing :SP off a PV name """
    return reason[:-3]


THREADPOOL = ThreadPoolExecutor()


class LSiCorrelatorDriver(Driver):
    """
    A driver for the LSi Correlator
    """

    def __init__(self, pv_prefix, host: str, firmware_revision: str, filepath: str):
        """
        A driver for the LSi Correlator

        Args:
            pv_prefix: the pv prefix
            host: The IP address of the LSi Correlator
            firmware: The firmware revision of the LSi Correlator
            filepath: The directory in which to place data files
        """
        super(LSiCorrelatorDriver, self).__init__()

        self.device = LSICorrelator(host, firmware_revision)

        self.SettingPVs = get_pv_configs(self.device)

        self.PVValues = {
            PvNames.CORRELATIONTYPE: LSI_Param.CorrelationType.AUTO,
            PvNames.NORMALIZATION: LSI_Param.Normalization.COMPENSATED,
            PvNames.MEASUREMENTDURATION: 10,
            PvNames.SWAPCHANNELS: LSI_Param.SwapChannels.ChA_ChB,
            PvNames.SAMPLINGTIMEMULTIT: LSI_Param.SamplingTimeMultiT.ns200,
            PvNames.TRANSFERRATE: LSI_Param.TransferRate.ms100,
            PvNames.OVERLOADLIMIT: 20,
            PvNames.OVERLOADINTERVAL: 400,
            PvNames.ERRORMSG: "",
            PvNames.START: 0,
            PvNames.STOP: 0,
            PvNames.REPETITIONS: 2,
            PvNames.CURRENT_REPEAT: 0,
            PvNames.CORRELATION_FUNCTION: [],
            PvNames.LAGS: [],
            PvNames.FILENAME: "",
            PvNames.FILEPATH: "",
            PvNames.CONNECTED: self.device.isConnected(),
            PvNames.RUNNING: False,
            PvNames.SCATTERING_ANGLE: 2.2,
            PvNames.SAMPLE_TEMP: 300,
            PvNames.SOLVENT_VISCOSITY: 1100,
            PvNames.SOLVENT_REFRACTIVE_INDEX: 1.1,
            PvNames.LASER_WAVELENGTH: 440,
            PvNames.SIM: 0,
            PvNames.DISABLE: 0
        }

        self.alarm_status = Alarm.NO_ALARM
        self.alarm_severity = Severity.NO_ALARM

        if os.path.isdir(filepath):
            self.PVValues[PvNames.FILEPATH] = filepath
        else:
            self.update_error_pv_print_and_log("LSiCorrelatorDriver: {} is invalid file path".format(filepath), "MAJOR")

        for pv, preset in self.PVValues.items():
            # Write defaults to device
            print_and_log("setting {} to {}".format(pv, preset))
            self.update_pv_value(pv, Records[pv].value.convert_to_pv(preset))

        self.updatePVs()

    def update_error_pv_print_and_log(self, error: str, severity: str = "INFO", src: str = "LSI") -> None:
        """
        Updates the error PV with the provided error message, then prints and logs the error

        Args:
            error: The error message
            severity (optional): Gives the severity of the message. Expected serverities are MAJOR, MINOR and INFO.
            src (optional): Gives the source of the message. Default source is LSI (from this IOC).
        """

        self.update_pv_value(PvNames.ERRORMSG, error)
        print_and_log(error, severity, src)

    def set_disconnected_alarms(self, in_alarm: bool):
        """ Sets disconnected alarms if in_alarm is True """
        if in_alarm:
            severity = Severity.INVALID_ALARM
            status = Alarm.TIMEOUT_ALARM
        else:
            severity = Severity.NO_ALARM
            status = Alarm.NO_ALARM

        self.alarm_status = status
        self.alarm_severity = severity

        for record in Records:
            self.setParamStatus(record.value.name, status, severity)
        # for pv in self.SettingPVs.keys():
        #     self.setParamStatus(pv, status, severity)

    def get_pv_value(self, reason):
        """
        Returns the value of a PV held in this driver

        Args:
            reason (str): The name of the PV to get the value of
        """
        if reason.endswith(":SP"):
            # Return value of base PV, not setpoint
            reason = get_base_pv(reason)

        if reason in self.SettingPVs:
            # Need to convert internal state to PV (e.g. enum number)
            pv_value = Records[reason].value.convert_to_pv(self.PVValues[reason])
        else:
            pv_value = self.getParam(reason)

        return pv_value

    @_error_handler
    def update_pv_value(self, reason, value):
        """
        Helper function to update the value of a PV held in this driver

        Args:
            reason (str): The name of the PV to set
            value: The new value for the PV
        """

        if reason in self.SettingPVs:
            # Non-field PVs also get updated internally
            sanitised_value = Records[reason].value.convert_from_pv(value)
            sanitised_value_for_pv = Records[reason].value.convert_to_pv(sanitised_value)
            try:
                Records[reason].value.set_on_device(sanitised_value)
                self.setParam(reason, sanitised_value_for_pv)
                self.setParam("{reason}.VAL".format(reason=reason), sanitised_value_for_pv)
            except ValueError as err:
                self.update_error_pv_print_and_log("Error setting PV {pv} to {value}:".format(pv=reason, value=value))
                self.update_error_pv_print_and_log("{}".format(err))
            except KeyError:
                self.update_error_pv_print_and_log("Can't write to PV {}, PV not found".format(reason))
            else:
                # Update local variable if setting has worked
                self.PVValues[reason] = sanitised_value
        else:
            # Update PV with given value
            self.setParam(reason, value)
            self.setParamStatus(reason, self.alarm_status, self.alarm_severity)

    def set_array_pv_value(self, reason, value):
        """
        Helper function to update the value of an array PV and the array PV fields (NORD)
        Args:
            reason (str): The name of the PV to set
            value: The new values to write to the array
        """
        self.update_pv_value(reason, value)
        self.update_pv_value("{reason}.NORD".format(reason=reason), len(value))

    @_error_handler
    def write(self, reason: str, value):
        """
        Handle write to PV
        Args:
            reason: PV to set value of
            value: Value to set
        """
        print_and_log("LSiCorrelatorDriver: Processing PV write for reason {}".format(reason))
        if reason == PvNames.START:
            THREADPOOL.submit(self.take_data)

        if reason.endswith(":SP") and get_base_pv(reason) in STATIC_PV_DATABASE.keys():
            # Update both SP and non-SP fields
            THREADPOOL.submit(self.update_pv_value, reason, value)
            THREADPOOL.submit(self.update_pv_value, get_base_pv(reason), value)
        elif reason in STATIC_PV_DATABASE.keys():
            THREADPOOL.submit(self.update_pv_value, reason, value)
        else:
            self.update_error_pv_print_and_log("LSiCorrelatorDriver: Could not write to PV '{}': not known".format(reason), "MAJOR")

        # Update PVs after any write.
        self.updatePVs()

    @_error_handler
    def read(self, reason):
        """
        Handle read of PV
        Args:
            reason (str): PV to read value of
        """
        self.updatePVs()  # Update PVs before any read so that they are up to date.

        try:
            PV_value = self.get_pv_value(reason)
        except KeyError:
            self.update_error_pv_print_and_log("LSiCorrelatorDriver: Could not read from PV '{}': not known".format(reason), "MAJOR")
            PV_value = None

        return PV_value

    def get_data_as_arrays(self):
        """
        Converts the correlation function, time lags and raw traces as numpy arrays.
        The correlation function and time lags are filtered to finite values only.

        Returns:
            Corr (ndarray): The finite values of the correlation function
            Lags (ndarray): Time lags where the correlation function is finite
            trace_A (ndarray): Raw photon counts for channel A
            trace_B (ndarray): Raw photon counts for channel B
        """
        corr = np.asarray(self.device.Correlation)
        lags = np.asarray(self.device.Lags)

        lags = lags[np.isfinite(corr)]
        corr = corr[np.isfinite(corr)]

        trace_a = np.asarray(self.device.TraceChA)
        trace_b = np.asarray(self.device.TraceChB)

        return corr, lags, trace_a, trace_b

    @_error_handler
    def take_data(self):
        """
        Sends settings parameters to the LSi driver and takes data from the LSi Correlator with the given number of repetitions.

        Args:
            number_of_repetitions (int): The number of repetitions to perform.
        """
        self.device.configure()

        for repeat in range(1, self.PVValues[PvNames.REPETITIONS]+1):
            self.update_pv_value(PvNames.CURRENT_REPEAT, repeat)

            self.device.start()

            while self.device.MeasurementOn():
                sleep(0.5)
                self.update_pv_value(PvNames.RUNNING, True)
                self.device.update()

            self.update_pv_value(PvNames.RUNNING, False)

            if self.device.Correlation is None:
                # No data returned, correlator may be disconnected
                self.update_pv_value(PvNames.CONNECTED, False)
                self.update_error_pv_print_and_log("LSiCorrelatorDriver: No data read, device could be disconnected", "INVALID")
                self.set_disconnected_alarms(True)
            else:
                Corr, Lags, trace_A, trace_B = self.get_data_as_arrays()

                self.set_array_pv_value(PvNames.CORRELATION_FUNCTION, Corr)
                self.set_array_pv_value(PvNames.LAGS, Lags)

                self.save_data(Corr, Lags, trace_A, trace_B)

    def add_timestamp_to_filename(self):
        """
        Adds a timestamp to the current filepath/filename
        """

        filepath = self.get_pv_value(PvNames.FILEPATH)
        filename = self.get_pv_value(PvNames.FILENAME)
        timestamp = datetime.now().strftime("%Y-%m-%dT%H_%M_%S")

        return "{filepath}/{filename}_{timestamp}".format(filepath=filepath, filename=filename, timestamp=timestamp)

    def save_data(self, correlation, time_lags, trace_A, trace_B):
        """
        Write the correlation function and time lags to file.

        Args:
            correlation (float array): The correlation function
            time_lags (float array): The time lags
        """

        filename = self.add_timestamp_to_filename()

        correlation_data = np.vstack((time_lags, correlation)).T
        raw_channel_data = np.vstack((trace_A, trace_B)).T
        metadata_variables = [
            PvNames.SCATTERING_ANGLE,
            PvNames.SAMPLE_TEMP,
            PvNames.SOLVENT_VISCOSITY,
            PvNames.SOLVENT_REFRACTIVE_INDEX,
            PvNames.LASER_WAVELENGTH,
            PvNames.CORRELATIONTYPE,
            PvNames.NORMALIZATION,
            PvNames.MEASUREMENTDURATION,
            PvNames.SWAPCHANNELS,
            PvNames.SAMPLINGTIMEMULTIT,
            PvNames.TRANSFERRATE,
            PvNames.OVERLOADLIMIT,
            PvNames.OVERLOADINTERVAL,
            PvNames.REPETITIONS,
            PvNames.CURRENT_REPEAT
        ]

        with open(filename, 'w') as f:

            for metadata_variable in metadata_variables:
                f.write("# {variable}: {value}\n".format(variable=metadata_variable,
                                                         value=self.get_pv_value(metadata_variable)))
            np.savetxt(f, correlation_data, delimiter=',', header='Time Lags,Correlation Function', fmt='%1.4e')
            np.savetxt(f, raw_channel_data, delimiter=',', header='\nTraceA,TraceB', fmt='%1.4e')


def serve_forever(ioc_number: int, pv_prefix: str):
    """
    Server the PVs for the remote ioc server
    Args:
        ioc_numer: The number of the IOC to be run (e.g. 1 for LSICORR_01)
        pv_prefix: prefix for the pvs
        subsystem_prefix: prefix for the PVs published by the remote IOC server
        gateway_pvlist_path: The path to the gateway pvlist file to generate
        gateway_acf_path: The path to the gateway access security file to generate
        gateway_restart_script_path: The path to the script to call to restart the remote ioc gateway

    Returns:

    """
    ioc_name = "LSICORR_{:02d}".format(ioc_number)
    ioc_name_with_pv_prefix = "{pv_prefix}{ioc_name}:".format(pv_prefix=pv_prefix, ioc_name=ioc_name)
    print_and_log(ioc_name_with_pv_prefix)
    server = SimpleServer()

    server.createPV(ioc_name_with_pv_prefix, STATIC_PV_DATABASE)
    #server.createPV(ioc_name_with_pv_prefix, FIELDS_DATABASE)

    # Looks like it does nothing, but this creates *and automatically registers* the driver
    # (via metaclasses in pcaspy). See declaration of DriverType in pcaspy/driver.py for details
    # of how it achieves this.
    ip_address = '127.0.0.1'
    firmware_revision = '4.0.0.3'
    filepath = "C:\\Data"
    LSiCorrelatorDriver(pv_prefix, ip_address, firmware_revision, filepath)

    # Clean up sys.argv path
    exepath = str(Path(sys.argv[0]))

    ioc_data_source = IocDataSource(SQLAbstraction("iocdb", "iocdb", "$iocdb"))
    ioc_data_source.insert_ioc_start(ioc_name, os.getpid(), exepath, STATIC_PV_DATABASE, ioc_name_with_pv_prefix)

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

    parser.add_argument("--ioc_number", default=1, type=int)

    parser.add_argument("--pv_prefix", required=True, type=six.text_type,
                        help="The PV prefix of this instrument.")

    args = parser.parse_args()

    FILEPATH_MANAGER.initialise(os.path.normpath(os.getenv("ICPCONFIGROOT")), "", "")

    print("IOC started")

    serve_forever(
        args.ioc_number,
        args.pv_prefix,
    )


if __name__ == "__main__":
    main()
