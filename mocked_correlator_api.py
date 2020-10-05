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

        self.device.MeasurementOn = MagicMock(side_effect=self.is_measurement_on)

        self.device.measurement_on = False
        self.device.disconnected = False

        self.fake_data = np.linspace(0, elements_in_float_array, elements_in_float_array)


    def is_measurement_on(self):
        return self.device.measurement_on

    def start(self):
        """
        Switches the measurement on for 1 second, then off again to simulate the device taking a 1 second measurement
        """
        print("Starting!")
        self.device.measurement_on = True
        sleep(1.0)
        self.device.measurement_on = False

        if not self.device.disconnected:
            fake_data = self.fake_data
        else:
            fake_data = None

        # print(self.fake_data)

        self.device.Correlation = fake_data
        self.device.Lags = fake_data
        self.device.TraceChA = fake_data
        self.device.TraceChB = fake_data

        print("Done!")

    def configure(self):
        if self.device.MeasurementOn():
            raise RuntimeError("LSI --- Cannot configure: Measurement active")

        if self.device.disconnected:
            raise RuntimeError("LSI --- Cannot configure: Correlator disconnected or measurement active")
