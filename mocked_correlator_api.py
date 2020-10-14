from mock import MagicMock
from pvdb import Records

import numpy as np
from time import time

elements_in_float_array = Records.CORRELATION_FUNCTION.value.database_entries["CORRELATION_FUNCTION"]["count"]

DATA_USED_IN_IOC_SYSTEM_TESTS = np.linspace(0, elements_in_float_array, elements_in_float_array)


class MockedCorrelatorAPI:
    def __init__(self):
        self.device = MagicMock()

        self.device.start = MagicMock(side_effect=self.start)
        self.device.configure = MagicMock(side_effect=self.configure)

        self.device.MeasurementOn = MagicMock(side_effect=self.is_measurement_on)
        self.device.update = MagicMock(side_effect=self.update)

        self.device.measurement_on = False
        self.device.disconnected = False

        self.corr = DATA_USED_IN_IOC_SYSTEM_TESTS
        self.lags = DATA_USED_IN_IOC_SYSTEM_TESTS
        self.trace_a = DATA_USED_IN_IOC_SYSTEM_TESTS
        self.trace_b = DATA_USED_IN_IOC_SYSTEM_TESTS

        self.update_count = 0
        self.update_called_when_measurement_not_on = False
        self.collection_time = 1.0
        self.last_start_time = time()

    def is_measurement_on(self) -> bool:
        """
        If the collection time has passed switch the measurement off.
        Then returns whether the measurement is still on.
        """
        if self.device.measurement_on and self.collection_time < time() - self.last_start_time:
            self.device.measurement_on = False
            print("Done!")
        return self.device.measurement_on

    def start(self):
        """
        Switches the measurement on. This will be switched off after the collection time has passed by a
         call either to update or is_measurement_on.
        """
        if not self.device.measurement_on:
            print("Starting!")
            self.device.measurement_on = True
            self.last_start_time = time()
        else:
            print("LSI --- Cannot start: Data connection is currently active")

    def configure(self):
        if self.device.MeasurementOn():
            raise RuntimeError("LSI --- Cannot configure: Measurement active")

        if self.device.disconnected:
            raise RuntimeError("LSI --- Cannot configure: Correlator disconnected or measurement active")

    def update(self):
        """
        Update correlation, lags and trace data. 
        Record the amount of calls that are made and if they are made when the measurement is off.
        Switch off the measurement when the collection time has passed.
        """
        # Record call information
        if not self.device.measurement_on:
            self.update_called_when_measurement_not_on = True
        self.update_count += 1

        # Update correlation, lags and trace data
        self.device.Correlation = None if self.device.disconnected else self.corr
        self.device.Lags = self.lags
        self.device.TraceChA = self.trace_a
        self.device.TraceChB = self.trace_b
