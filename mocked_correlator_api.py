from mock import MagicMock
from pvdb import Records


import numpy as np
from time import sleep

print(Records.CORRELATION_FUNCTION.value.database_entries)
elements_in_float_array = Records.CORRELATION_FUNCTION.value.database_entries["CORRELATION_FUNCTION"]["count"]


class MockedCorrelatorAPI:
    def __init__(self):
        self.device = MagicMock()

        self.device.start = MagicMock(side_effect=self.start)
        self.device.configure = MagicMock(side_effect=self.configure)
        self.measurement_on = False
        self.device.MeasurementOn = MagicMock(side_effect=self.is_measurement_on)

    def is_measurement_on(self):
        return self.measurement_on

    def start(self):
        """
        Switches the measurement on for 1 second, then off again to simulate the device taking a 1 second measurement
        """
        print("Starting!")
        self.measurement_on = True
        sleep(1.0)
        self.measurement_on = False

        fake_data = np.linspace(0, elements_in_float_array, elements_in_float_array)

        self.device.Correlation = fake_data
        self.device.Lags = fake_data
        self.device.TraceChA = fake_data
        self.device.TraceChB = fake_data

        print("Done!")

    def configure(self):
        if self.device.MeasurementOn():
            raise RuntimeError("LSI --- Cannot configure: Measurement active")
