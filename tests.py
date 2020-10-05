import unittest
import numpy as np

from correlator_driver_functions import LSiCorrelatorDriver
from pvdb import Records

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

    def test_GIVEN_device_disconnected_WHEN_data_taken_THEN_deivce_reads_no_data_and_disconnected(self):
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
        test_data = np.linspace(0, 10, 10)
        print(repr(self.driver.device))
        print(repr(self.mocked_api))

        self.mocked_api.fake_data = test_data
        self.driver.take_data()

        # print(self.driver.corr)


        self.assertTrue(np.allclose(self.driver.corr, test_data))
        #self.assertTrue(np.allclose(self.driver.lags, test_data))
