"""
Contains the data_file_interaction class which is used to interact with the data file.
"""

from dataclasses import dataclass
from datetime import datetime
from io import StringIO
from typing import Dict, TextIO, Tuple

import numpy as np  # pylint: disable=import-error

from config import Schema
from pvdb import Records


@dataclass
class DataArrays:
    """
    A data transfer object to store the relevant data ndarrays.
    """

    correlation: np.ndarray
    time_lags: np.ndarray
    trace_a: np.ndarray
    trace_b: np.ndarray
    trace_time: np.ndarray


class DataFile:
    """
    A data transfer object to store and format data to write to file.
    """

    @staticmethod
    def create_file_data(
        data_arrays: DataArrays, user_file: TextIO, archive_file: TextIO, metadata: Dict
    ) -> "DataFile":  # pylint: disable=line-too-long
        """
        Create a data transfer object to store and format data to write to file.
        @param data_arrays (DataArrays): A data transfer object to store the relevant data ndarrays.
        @param user_file (TextIO): The user file to write metadata, correlation, time_lags and
        the traces to
        @param archive_file (TextIO): The archive file to write metadata, correlation, time_lags and
        the traces to
        @param metadata (Dict): A dictionary of metadata to write to the file
        @return (DataFile): A data transfer object to store and format data to write to file.
        """
        data_file = DataFile(data_arrays, user_file, archive_file, metadata)
        correlation_string, raw_channel_data_string = (
            data_file._format_correlation_and_raw_channel_data()
        )  # pylint: disable=line-too-long, protected-access
        data_file._structure_file_data(correlation_string, raw_channel_data_string)  # pylint: disable=protected-access
        return data_file

    def __init__(
        self, data_arrays: DataArrays, user_file: TextIO, archive_file: TextIO, metadata: Dict
    ) -> None:  # pylint: disable=line-too-long
        """
        Initialize the data transfer object.
        @param data_arrays (DataArrays): A data transfer object to store the relevant data ndarrays
        @param user_file (TextIO): The user file to write metadata, correlation,
        time_lags and the traces to
        @param archive_file (TextIO): The archive file to write metadata, correlation,
        time_lags and the traces to
        @param metadata (Dict): A dictionary of metadata to write to the file
        """
        self.data_arrays: DataArrays = data_arrays
        self.user_file: TextIO = user_file
        self.archive_file: TextIO = archive_file
        self.metadata: Dict = metadata
        self.save_file = None

    def _format_correlation_and_raw_channel_data(self) -> Tuple[StringIO, StringIO]:
        """
        A private method to format the correlation function and raw channel data to write to file.
        @return (Tuple): A tuple (str, str) of the correlation function and raw channel data
        to write to file.
        """

        correlation_data = np.vstack((self.data_arrays.time_lags, self.data_arrays.correlation)).T

        raw_channel_data = np.vstack(
            (self.data_arrays.trace_time, self.data_arrays.trace_a, self.data_arrays.trace_b)
        ).T

        correlation_file = StringIO()
        np.savetxt(correlation_file, correlation_data, delimiter="\t", fmt="%1.6e")
        correlation_string = correlation_file.getvalue()
        raw_channel_data_file = StringIO()
        np.savetxt(raw_channel_data_file, raw_channel_data, delimiter="\t", fmt="%.6f")
        raw_channel_data_string = raw_channel_data_file.getvalue()
        return correlation_string, raw_channel_data_string

    def _structure_file_data(self, correlation_string, raw_channel_data_string) -> None:
        """
        Write the correlation function, time lags, traces and metadata to user and archive files.
        @param correlation_string (StringIO): The correlation function to write to file.
        @param raw_channel_data_string (StringIO): The raw channel data to write to file.
        @return (None): None
        """
        correlation_string, raw_channel_data_string = (
            self._format_correlation_and_raw_channel_data()
        )  # pylint: disable=line-too-long
        self.save_file = Schema.FILE_SCHEME.format(
            datetime=datetime.now().strftime("%m/%d/%Y\t%H:%M %p"),
            scattering_angle=self.metadata[Records.SCATTERING_ANGLE.name],
            duration=self.metadata[Records.MEASUREMENTDURATION.name],
            wavelength=self.metadata[Records.LASER_WAVELENGTH.name],
            refractive_index=self.metadata[Records.SOLVENT_REFRACTIVE_INDEX.name],
            viscosity=self.metadata[Records.SOLVENT_VISCOSITY.name],
            temperature=self.metadata[Records.SAMPLE_TEMP.name],
            avg_count_A=np.mean(self.data_arrays.trace_a),
            avg_count_B=np.mean(self.data_arrays.trace_b),
            correlation_function=correlation_string,
            count_rate_history=raw_channel_data_string,
        )

    def write_to_file(self) -> None:
        """
        Write the correlation function, time lags, traces and metadata to user and archive files.
        @return (None): None
        """
        for dat_file in [self.user_file, self.archive_file]:
            dat_file.write(self.save_file)
