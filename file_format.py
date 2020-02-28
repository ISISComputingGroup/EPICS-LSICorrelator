FILE_SCHEME = """{datetime}
Pseudo Cross Correlation
Scattering angle:\t{scattering_angle}
Duration (s):\t{duration}
Wavelength (nm):\t{wavelength}
Refractive index:\t{refractive_index}
Viscosity (mPas):\t{viscosity}
Temperature (K):\t{temperature}
Laser intensity (mW):\t0.0
Average Count rate A (kHz):\t{avg_count_A}
Average Count rate B (kHz):\t{avg_count_B}
Intercept:\t1.0000
Cumulant 1st\t-Inf
Cumulant 2nd\t-Inf\tNaN
Cumulant 3rd\t-Inf\tNaN

Lag time (s)         g2-1
{correlation_function}

Count Rate History (KHz)  CR CHA / CR CHB
{count_rate_history}"""