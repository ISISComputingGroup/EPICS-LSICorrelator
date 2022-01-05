"""
Contains Unit Tests for LSI Correlator
"""
from tempfile import NamedTemporaryFile
import unittest
import numpy as np  # pylint: disable=import-error


from correlator_driver_functions import LSiCorrelatorVendorInterface
from pvdb import Records

from test_utils import test_data

# pylint: disable=line-too-long, invalid-name

macros = {
    "SIMULATE": "1",
    "ADDR": "127.0.0.1",
    "FIRMWARE_REVISION": "4.0.0.3"
    }


class LSICorrelatorTests(unittest.TestCase):
    """
    Unit tests for the LSi Correlator
    """

    def setUp(self):
        """
        Set up the test case
        """
        self.driver = LSiCorrelatorVendorInterface(macros, simulated=True)

        self.mocked_api = self.driver.mocked_api
        self.device = self.driver.device
        self.mocked_api.disconnected = False

    def test_GIVEN_device_disconnected_WHEN_data_taken_THEN_device_reads_no_data_and_disconnected(self):
        """
        Test that the device reads no data when disconnected
        """
        self.assertTrue(self.driver.is_connected)
        self.device.disconnected = True

        self.driver.take_data(0)

        self.assertFalse(self.driver.has_data)
        self.assertFalse(self.driver.is_connected)

    def test_GIVEN_device_connected_WHEN_data_taken_THEN_device_reads_has_data_and_connected(self):
        """
        Test that the device reads data when connected
        """
        self.driver.take_data(0)

        self.assertTrue(self.driver.has_data)
        self.assertTrue(self.driver.is_connected)

    def test_GIVEN_device_connected_WHEN_data_taken_THEN_driver_updated_with_correlation_and_time_lags(self):
        """
        Test that the driver updates with the correlation and time lags
        """

        self.mocked_api.corr = test_data.corr
        self.mocked_api.lags = test_data.lags
        self.driver.take_data(0)

        self.assertTrue(np.allclose(self.driver.corr, test_data.corr_without_nans))
        self.assertTrue(np.allclose(self.driver.lags, test_data.lags_without_nans))

    def test_GIVEN_device_has_data_WHEN_data_retrieved_from_device_THEN_time_trace_made_and_no_nans_in_correlation(self):
        """
        Test that the time trace is made and no nans in correlation
        """
        self.device.Correlation = test_data.corr
        self.device.Lags = test_data.lags
        self.device.TraceChA = test_data.trace_a
        self.device.TraceChB = test_data.trace_b

        corr, lags, trace_a, trace_b, trace_time = self.driver.get_data_as_arrays(0)

        self.assertTrue(np.allclose(corr, test_data.corr_without_nans))
        self.assertTrue(np.allclose(lags, test_data.lags_without_nans))
        self.assertTrue(np.allclose(trace_a, test_data.trace_a))
        self.assertTrue(np.allclose(trace_b, test_data.trace_b))
        self.assertTrue(np.allclose(trace_time, test_data.trace_time))

    def test_WHEN_data_taken_THEN_start_called(self):
        """
        Test that the start method is called when data is taken
        """
        self.driver.take_data(0)
        self.device.start.assert_called_once()

    def test_WHEN_data_taken_AND_measurement_on_THEN_update_called_WHEN_measurement_off_THEN_update_not_called(self):
        """
        Test that the update method is called when data is taken and measurement is on
        """
        starting_update_count = self.mocked_api.update_count
        self.driver.take_data(0)
        self.assertGreater(self.mocked_api.update_count, starting_update_count)
        self.assertFalse(self.mocked_api.update_called_when_measurement_not_on)

    def test_WHEN_save_data_THEN_metadata_written_AND_correlation_data_written_AND_traces_written(self):
        """
        Test that the metadata and correlation data are written and the traces are written
        """
        # Gather some dummy data that matches the test_data.dat file
        self.device.Correlation = test_data.corr
        self.device.Lags = test_data.lags
        self.device.TraceChA = test_data.trace_a
        self.device.TraceChB = test_data.trace_b

        metadata = {
            Records.SCATTERING_ANGLE.name: 110,
            Records.MEASUREMENTDURATION.name: 10,
            Records.LASER_WAVELENGTH.name: 642,
            Records.SOLVENT_REFRACTIVE_INDEX.name: 1.33,
            Records.SOLVENT_VISCOSITY.name: 1,
            Records.SAMPLE_TEMP.name: 298
        }

        # Save data to two temporary files that are discarded
        with NamedTemporaryFile(mode="w+") as user_file, NamedTemporaryFile(mode="w+") as archive_file:

            self.driver.save_data(0, user_file, archive_file, metadata)

            # Read test_data.dat
            with open(test_data.test_data_file, mode="r") as test_data_file:

                test_actual_data = test_data_file.read()

                # Go back to start of files after write and ignore firstline that has timestamp on it
                for file in [user_file, archive_file]:
                    file.seek(0)
                    file.readline()

                    # Assert content is equal
                    self.assertEqual(test_actual_data, file.read())


if __name__ == '__main__':
    unittest.main()
