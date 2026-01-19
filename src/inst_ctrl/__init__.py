"""
Instrument control package for Fluke multimeters, Siglent waveform generators, and Rigol power supplies.

This package provides high-level Python interfaces for controlling test and measurement
instruments via PyVISA. All instruments support multiple connection methods (GPIB, USB,
Ethernet, RS-232) and provide type-safe, well-documented APIs with comprehensive error handling.

Examples
--------
Fluke 45 Digital Multimeter:
    >>> from inst_ctrl import Fluke45, Func, Rate
    >>> with Fluke45(gpib_address=3) as dmm:
    ...     dmm.primary_function = Func.VDC
    ...     dmm.rate = Rate.FAST
    ...     voltage = dmm.primary()
    ...     print(f"Voltage: {voltage} V")

Fluke 45 Dual Display:
    >>> from inst_ctrl import Fluke45, Func, Func2
    >>> with Fluke45() as dmm:
    ...     dmm.primary_function = Func.VDC
    ...     dmm.secondary_function = Func2.FREQ
    ...     voltage, frequency = dmm.both()
    ...     print(f"Voltage: {voltage} V, Frequency: {frequency} Hz")

Fluke 8845A/8846A Digital Multimeter:
    >>> from inst_ctrl import Fluke88, Func
    >>> with Fluke88(ip_address='192.168.1.100') as dmm:
    ...     dmm.primary_function = Func.OHMS
    ...     dmm.auto_range = True
    ...     resistance = dmm.primary()
    ...     print(f"Resistance: {resistance} Ohms")

Siglent SDG2042X Waveform Generator:
    >>> from inst_ctrl import SiglentSDG2042X
    >>> with SiglentSDG2042X() as sig_gen:
    ...     sig_gen.channel = 1
    ...     sig_gen.waveform_type = 'SINE'
    ...     sig_gen.frequency = 1000
    ...     sig_gen.amplitude = 2.0
    ...     sig_gen.offset = 0.5
    ...     sig_gen.output_state = True

Siglent Configure Waveform:
    >>> with SiglentSDG2042X() as sig_gen:
    ...     sig_gen.channel = 1
    ...     sig_gen.configure_waveform('SINE', frequency=1000, amplitude=2.0, offset=0.5, phase=45)
    ...     sig_gen.output_state = True

Rigol DP800 Power Supply:
    >>> from inst_ctrl import RigolDP800, Channel
    >>> with RigolDP800(ip_address='192.168.1.100') as psu:
    ...     psu.channel = Channel.CH1
    ...     psu.voltage = 5.0
    ...     psu.current = 1.0
    ...     psu.output = True

Rigol Apply Voltage and Current:
    >>> with RigolDP800() as psu:
    ...     psu.apply(voltage=12.0, current=2.0, channel=Channel.CH1)
    ...     psu.output_on(Channel.CH1)

Rigol Measure Output:
    >>> with RigolDP800() as psu:
    ...     psu.channel = Channel.CH1
    ...     voltage = psu.measured_voltage
    ...     current = psu.measured_current
    ...     power = psu.measured_power
    ...     print(f"V: {voltage}V, I: {current}A, P: {power}W")
"""

from inst_ctrl.siglent import (
    SiglentSDG2042X,
    SiglentError,
    SiglentConnectionError,
    SiglentValidationError,
    SiglentCommandError,
    ParameterLimits,
)

from inst_ctrl.fluke import (
    Fluke45,
    Fluke88,
    FlukeError,
    FlukeConnectionError,
    FlukeValidationError,
    FlukeCommandError,
    Func,
    Func2,
    Rate,
    TriggerMode,
)

from inst_ctrl.rigol import (
    RigolDP800,
    RigolError,
    RigolConnectionError,
    RigolValidationError,
    RigolCommandError,
    Channel,
)

__all__ = [
    'SiglentSDG2042X',
    'SiglentError',
    'SiglentConnectionError',
    'SiglentValidationError',
    'SiglentCommandError',
    'ParameterLimits',
    'Fluke45',
    'Fluke88',
    'FlukeError',
    'FlukeConnectionError',
    'FlukeValidationError',
    'FlukeCommandError',
    'Func',
    'Func2',
    'Rate',
    'TriggerMode',
    'RigolDP800',
    'RigolError',
    'RigolConnectionError',
    'RigolValidationError',
    'RigolCommandError',
    'Channel',
]
