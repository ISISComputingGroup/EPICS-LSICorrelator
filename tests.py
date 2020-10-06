import unittest
import numpy as np

from correlator_driver_functions import LSiCorrelatorDriver
from pvdb import Records

from test_utils import test_data

macros = {"SIMULATE": "1"}
pv_prefix = "TE:NDW1836"
ioc_name = "LSICORR_01"


class LSICorrelatorTests(unittest.TestCase):
    """
    Unit tests for the LSi Correlator
    """

    def setUp(self):
        self.driver = LSiCorrelatorDriver("127.0.0.1", "", "", macros)

        self.mocked_api = self.driver.mocked_api
        self.device = self.driver.device
        self.mocked_api.disconnected = False

    def test_GIVEN_device_disconnected_WHEN_data_taken_THEN_device_reads_no_data_and_disconnected(self):
        self.assertTrue(self.driver.is_connected)
        self.device.disconnected = True

        self.driver.take_data()

        self.assertFalse(self.driver.has_data)
        self.assertFalse(self.driver.is_connected)

    def test_GIVEN_device_connected_WHEN_data_taken_THEN_device_reads_has_data_and_connected(self):
        self.driver.take_data()

        self.assertTrue(self.driver.has_data)
        self.assertTrue(self.driver.is_connected)

    def test_GIVEN_device_connected_WHEN_data_taken_THEN_correlation_function_and_time_lags_returned(self):

        self.mocked_api.corr = test_data.corr
        self.mocked_api.lags = test_data.lags
        self.driver.take_data()

        self.assertTrue(np.allclose(self.driver.corr, test_data.corr_without_nans))
        self.assertTrue(np.allclose(self.driver.lags, test_data.lags_without_nans))

    def test_GIVEN_device_connected_WHEN_data_taken_THEN_start_called(self):
        self.driver.take_data()
        self.device.start.assert_called_once()


if __name__ == '__main__':
    unittest.main()
