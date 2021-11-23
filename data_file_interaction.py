from typing import Dict, TextIO, Tuple
from io import StringIO
import numpy as np
from datetime import datetime
from pvdb import Records
from dataclasses import dataclass


FILE_SCHEME = """{datetime}
Pseudo Cross Correlation
Scattering angle:\t{scattering_angle:.1f}
Duration (s):\t{duration:d}
Wavelength (nm):\t{wavelength:.1f}
Refractive index:\t{refractive_index:.3f}
Viscosity (mPas):\t{viscosity:.3f}
Temperature (K):\t{temperature:.1f}
Laser intensity (mW):\t0.0
Average Count rate  A (kHz):\t{avg_count_A:.1f}
Average Count rate  B (kHz):\t{avg_count_B:.1f}
Intercept:\t1.0000
Cumulant 1st\t-Inf
Cumulant 2nd\t-Inf\tNaN
Cumulant 3rd\t-Inf\tNaN

Lag time (s)         g2-1
{correlation_function}
Count Rate History (KHz)  CR CHA / CR CHB
{count_rate_history}"""

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
    def create_file_data(data_arrays: DataArrays, user_file: TextIO, archive_file: TextIO, metadata: Dict):
        data_file = DataFile(data_arrays, user_file, archive_file, metadata)
        correlation_string, raw_channel_data_string = data_file._format_correlation_and_raw_channel_data()
        data_file._structure_file_data(correlation_string, raw_channel_data_string)
        return data_file

    def __init__(self, data_arrays: DataArrays, user_file: TextIO, archive_file: TextIO, metadata: Dict) -> None:
        self.data_arrays: DataArrays = data_arrays
        self.user_file: TextIO = user_file
        self.archive_file: TextIO = archive_file
        self.metadata: Dict = metadata
        self.save_file = None

    def _format_correlation_and_raw_channel_data(self) -> Tuple[StringIO, StringIO]:
        correlation_data = np.vstack((self.data_arrays.time_lags, self.data_arrays.correlation)).T
        raw_channel_data = np.vstack((self.data_arrays.trace_time, self.data_arrays.trace_a, self.data_arrays.trace_b)).T
        correlation_file = StringIO()
        np.savetxt(correlation_file, correlation_data, delimiter='\t', fmt='%1.6e')
        correlation_string = correlation_file.getvalue()
        raw_channel_data_file = StringIO()
        np.savetxt(raw_channel_data_file, raw_channel_data, delimiter='\t', fmt='%.6f')
        raw_channel_data_string = raw_channel_data_file.getvalue()
        return correlation_string, raw_channel_data_string

    def _structure_file_data(self, correlation_string, raw_channel_data_string):
        """
        Write the correlation function, time lags, traces and metadata to user and archive files.

        Args:
            min_time_lag (float): The minimum time lag to include
            user_file (TextIO): The user file to write metadata, correlation, time_lags and the traces to
            archive_file (TextIO): The archive file to write metadata, correlation, time_lags and the traces to
            metadata (dict): A dictionary of metadata to write to the file
        """
        correlation_string, raw_channel_data_string = self._format_correlation_and_raw_channel_data()
        self.save_file = FILE_SCHEME.format(
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
            count_rate_history=raw_channel_data_string
        )

    def write_to_file(self):
        for dat_file in [self.user_file, self.archive_file]:
            dat_file.write(self.save_file)
