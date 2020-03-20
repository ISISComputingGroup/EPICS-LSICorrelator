from __future__ import print_function, unicode_literals, division, absolute_import

import argparse
import sys
import os
import traceback
from io import StringIO

import six

from pcaspy import SimpleServer, Driver
from pcaspy.alarm import Alarm, Severity
from concurrent.futures import ThreadPoolExecutor
import numpy as np

from time import sleep
from datetime import datetime
from pathlib import Path

sys.path.insert(1, os.path.join(os.getenv("EPICS_KIT_ROOT"), "Support", "lsicorr_vendor", "master"))
sys.path.insert(2, os.path.join(os.getenv("EPICS_KIT_ROOT"), "ISIS", "inst_servers", "master"))

from LSI import LSI_Param
from LSICorrelator import LSICorrelator

from pvdb import STATIC_PV_DATABASE, Records
from BlockServer.core.file_path_manager import FILEPATH_MANAGER
from server_common.utilities import print_and_log
from server_common.ioc_data_source import IocDataSource
from server_common.mysql_abstraction_layer import SQLAbstraction
from file_format import FILE_SCHEME
from pathlib import Path
from genie_python import genie as g

DATA_DIR = ""


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

# Magic number, seems to be time between measurments.
DELTA_T = 0.0524288


def remove_non_ascii(text_to_check):
    """
    Removes non-ascii and other characters from the supplied text
    """
    # Remove anything other than alphanumerics and dashes/underscores
    parsed_text = [char for char in text_to_check if char.isalnum() or char in '-_']
    return ''.join(parsed_text)

class LSiCorrelatorDriver(Driver):
    """
    A driver for the LSi Correlator
    """

    def __init__(self, host: str, firmware_revision: str, filepath: str):
        """
        A driver for the LSi Correlator

        Args:
            host: The IP address of the LSi Correlator
            firmware_revision: The firmware revision of the LSi Correlator
            filepath: The directory in which to place data files
        """
        super(LSiCorrelatorDriver, self).__init__()

        self.device = LSICorrelator(host, firmware_revision)

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
            Records.CONNECTED.value: self.device.isConnected(),
            Records.RUNNING.value: False,
            Records.SCATTERING_ANGLE.value: 2.2,
            Records.SAMPLE_TEMP.value: 300,
            Records.SOLVENT_VISCOSITY.value: 1100,
            Records.SOLVENT_REFRACTIVE_INDEX.value: 1.1,
            Records.LASER_WAVELENGTH.value: 440,
            Records.SIM.value: 0,
            Records.DISABLE.value: 0
        }

        self.user_filepath = filepath

        self.alarm_status = Alarm.NO_ALARM
        self.alarm_severity = Severity.NO_ALARM

        THREADPOOL.submit(self.update_output_file)

        if os.path.isdir(filepath):
            self.update_pv_and_write_to_device(Records.OUTPUTFILE.value.name, filepath)
            print_and_log("setting OUTPUTFILE to {}".format(filepath))
        else:
            self.update_error_pv_print_and_log("LSiCorrelatorDriver: {} is invalid file path".format(filepath), "MAJOR")

        for record, default_value in defaults.items():
            # Write defaults to device
            print_and_log("setting {} to {}".format(record.name, default_value))
            self.update_pv_and_write_to_device(record.name, record.convert_to_pv(default_value))

        self.updatePVs()

    def update_output_file(self):
        """
        Updates the PV containing the name of the user's data file
        """
        while True:
            filename = self.get_user_filename()
            self.update_pv_value_and_write_to_device(Records.OUTPUTFILE.name, filename)
            sleep(10)

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

    def get_pv_value(self, reason):
        """
        Gets the current value of reason in the PCASpy driver (the 'pv').
        If the supplied reason has an available record, the pv value is sanitised through convert_from_pv.

        Args:
            reason (str): The name of the PV to get the value of
        """
        if reason.endswith(":SP"):
            # Return value of base PV, not setpoint
            reason = get_base_pv(reason)

        pv_value = self.getParam(reason)

        try:
            record = Records[reason].value
            sanitised_value = record.convert_from_pv(pv_value)
        except KeyError:
            # Reason has no defining record
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
                record.value.set_on_device(self.device, value_for_lsi_driver)
            except ValueError as e:
                self.update_error_pv_print_and_log("Can't update PV {}, invalid value".format(reason))
                self.update_error_pv_print_and_log(str(e))
                return
            else:
                # No error raised, set new value to pv/params
                self.update_param_and_fields(reason, new_pv_value)
                if update_setpoint:
                    self.update_param_and_fields("{reason}:SP".format(reason=reason), new_pv_value)

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

        if reason.endswith(":SP"):
            pv_value = self.getParam(get_base_pv(reason))
        else:
            pv_value = self.getParam(reason)

        return pv_value

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
        """
        self.device.configure()

        no_repetitions = self.get_pv_value(Records.REPETITIONS.name)
        for repeat in range(1, no_repetitions+1):
            self.update_pv_and_write_to_device(Records.CURRENT_REPETITION.name, repeat)

            self.device.start()

            while self.device.MeasurementOn():
                sleep(0.5)
                self.device.update()
                self.update_pv_and_write_to_device(Records.RUNNING.name, True)

            self.update_pv_and_write_to_device(Records.RUNNING.name, False)

            if self.device.Correlation is None:
                # No data returned, correlator may be disconnected
                self.update_pv_and_write_to_device(Records.CONNECTED.name, False)
                self.update_error_pv_print_and_log("LSiCorrelatorDriver: No data read, device could be disconnected", "INVALID")
                self.set_disconnected_alarms(True)
            else:
                corr, lags, trace_a, trace_b = self.get_data_as_arrays()

                self.set_array_pv_value(Records.CORRELATION_FUNCTION.name, corr)
                self.set_array_pv_value(Records.LAGS.name, lags)

                # Time axis is number of data points collected * scaling factor
                time_trace = np.arange(len(self.device.TraceChA))*DELTA_T

                self.save_data(corr, lags, trace_a, trace_b, time_trace)

        # Attempt to set start PV back to NO, purely for aesthetics (this PV is actually always ready)
        self.update_param_and_fields(Records.START.name, 0)
        self.update_param_and_fields("{pv}:SP".format(pv=Records.START.name), 0)

    def get_archive_filename(self):
        """
        Returns a filename which the archive data file will be saved with
        """
        filename = "{instrument}{run_number}_DLS_{timestamp}.txt"
        timestamp = datetime.now().strftime("%Y-%m-%dT%H_%M_%S")
        return filename.format(instrument=g.get_instrument(), run_number=g.get_runnumber(), timestamp=timestamp)

    def get_user_filename(self):
        """ Returns a default filename from the current run number and title """
        experiment_name = self.get_pv_value(Records.EXPERIMENTNAME.name)
        run_number = g.get_runnumber()
        timestamp = datetime.now().strftime("%Y-%m-%dT%H_%M_%S")

        if experiment_name == "":
            filename = "{run_number}_{title}_{timestamp}.dat".format(
                run_number=run_number, title=remove_non_ascii(g.get_title()), timestamp=timestamp
            )
        else:
            filename = "{run_number}_{experiment_name}_{timestamp}.dat".format(
                run_number=run_number, experiment_name=remove_non_ascii(experiment_name), timestamp=timestamp
            )

        return filename

    def save_data(self, correlation, time_lags, trace_a, trace_b, trace_time):
        """
        Write the correlation function and time lags to file.

        Args:
            correlation (float array): The correlation function
            time_lags (float array): The time lags
            trace_a (float array): The 'raw' trace A counts from the correlator
            trace_b (float array): The 'raw' trace B from the correlator
            trace_time (float array): The elapsed time at which each raw data point was collected
        """
        user_filename = os.path.join(self.user_filepath, self.get_user_filename())
        archive_filename = os.path.join(DATA_DIR, self.get_archive_filename())

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
            scattering_angle=self.get_pv_value(Records.SCATTERING_ANGLE.name),
            duration=self.get_pv_value(Records.MEASUREMENTDURATION.name),
            wavelength=self.get_pv_value(Records.LASER_WAVELENGTH.name),
            refractive_index=self.get_pv_value(Records.SOLVENT_REFRACTIVE_INDEX.name),
            viscosity=self.get_pv_value(Records.SOLVENT_VISCOSITY.name),
            temperature=self.get_pv_value(Records.SAMPLE_TEMP.name),
            avg_count_A=np.mean(trace_a),
            avg_count_B=np.mean(trace_b),
            correlation_function=correlation_string,
            count_rate_history=raw_channel_data_string
        )

        for filename in [user_filename, archive_filename]:
            with open(filename, 'w+') as dat_file:
                dat_file.write(save_file)


def serve_forever(ioc_number: int, pv_prefix: str):
    """
    Server the PVs for the remote ioc server
    Args:
        ioc_number: The number of the IOC to be run (e.g. 1 for LSICORR_01)
        pv_prefix: prefix for the pvs

    Returns:

    """
    ioc_name = "LSICORR_{:02d}".format(ioc_number)
    ioc_name_with_pv_prefix = "{pv_prefix}{ioc_name}:".format(pv_prefix=pv_prefix, ioc_name=ioc_name)
    print_and_log(ioc_name_with_pv_prefix)
    server = SimpleServer()

    server.createPV(ioc_name_with_pv_prefix, STATIC_PV_DATABASE)

    # Looks like it does nothing, but this creates *and automatically registers* the driver
    # (via metaclasses in pcaspy). See declaration of DriverType in pcaspy/driver.py for details
    # of how it achieves this.
    ip_address = '127.0.0.1'
    firmware_revision = '4.0.0.3'
    filepath = "C:\\Data"
    LSiCorrelatorDriver(ip_address, firmware_revision, filepath)

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
