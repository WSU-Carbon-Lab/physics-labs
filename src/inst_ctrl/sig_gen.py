"""
Instrument control for the Signal Generator - Siglent SDG2042X and Philips PM5139.

This module provides Python interfaces for controlling Siglent SDG2042X arbitrary
waveform generators and Philips PM5139 signal generators via USB, Ethernet, or
GPIB connections using PyVISA.

Examples
--------
Basic usage:
    >>> from inst_ctrl import SiglentSDG2042X
    >>> with SiglentSDG2042X() as sig_gen:
    ...     sig_gen.channel = 1
    ...     sig_gen.waveform_type = 'SINE'
    ...     sig_gen.frequency = 1000
    ...     sig_gen.amplitude = 1.0
    ...     sig_gen.output_state = True

Configure waveform with all parameters:
    >>> with SiglentSDG2042X() as sig_gen:
    ...     sig_gen.channel = 1
    ...     sig_gen.configure_waveform('SINE', frequency=1000, amplitude=2.0, offset=0.5, phase=45)
    ...     sig_gen.output_state = True

Use pint units (requires pint package):
    >>> sig_gen = SiglentSDG2042X(unit_mode='pint')
    >>> sig_gen.connect()
    ...     freq = sig_gen.frequency
    ...     print(f"Frequency: {freq}")

Philips PM5139 (same API, drop-in replacement):
    >>> from inst_ctrl import PhilipsPM5139
    >>> with PhilipsPM5139() as sig_gen:
    ...     sig_gen.channel = 1
    ...     sig_gen.waveform_type = 'SINE'
    ...     sig_gen.frequency = 1000
    ...     sig_gen.amplitude = 1.0
    ...     sig_gen.output_state = True
"""

from __future__ import annotations

import re
import pyvisa
from pyvisa import constants as pyvisa_constants
from pyvisa.resources import MessageBasedResource
from typing import Optional, Union, List, Dict, Any, Tuple, cast
try:
    from pint import UnitRegistry  # pyright: ignore[reportMissingImports]

    ureg: Optional[UnitRegistry] = UnitRegistry()
except Exception:
    ureg = None


class SiglentError(Exception):
    """Base exception for all Siglent instrument errors."""
    pass


class SiglentConnectionError(SiglentError):
    """Raised when connection to instrument fails."""
    def __init__(self, message: str, pyvisa_error: Optional[Exception] = None) -> None:
        super().__init__(message)
        self.pyvisa_error = pyvisa_error


class SiglentValidationError(SiglentError):
    """Raised when invalid parameter values are provided."""
    def __init__(self, message: str, pyvisa_error: Optional[Exception] = None) -> None:
        super().__init__(message)
        self.pyvisa_error = pyvisa_error


class SiglentCommandError(SiglentError):
    """Raised when instrument command execution fails."""
    def __init__(self, message: str, pyvisa_error: Optional[Exception] = None) -> None:
        super().__init__(message)
        self.pyvisa_error = pyvisa_error


class ParameterLimits:
    """
    Parameter limits for Siglent SDG2042X waveform generator.

    Provides validation limits for frequency, amplitude, offset, and phase parameters.
    Limits can be adjusted if needed, but warnings are issued when changed.

    Attributes
    ----------
    freq_min : float
        Minimum frequency in Hz (default: 1e-6).
    freq_max : float
        Maximum frequency in Hz (default: 40e6).
    amp_min : float
        Minimum amplitude in V (default: 0.002).
    amp_max : float
        Maximum amplitude in V (default: 20.0).
    offset_min : float
        Minimum offset in V (default: -10.0).
    offset_max : float
        Maximum offset in V (default: 10.0).
    phase_min : float
        Minimum phase in degrees (default: 0.0).
    phase_max : float
        Maximum phase in degrees (default: 360.0).

    Examples
    --------
    >>> limits = ParameterLimits()
    ...     limits.freq_max = 50e6
    ...     limits.reset_to_defaults()
    """

    def __init__(self) -> None:
        self._freq_min = 1e-6
        self._freq_max = 40e6
        self._amp_min = 0.002
        self._amp_max = 20.0
        self._offset_min = -10.0
        self._offset_max = 10.0
        self._phase_min = 0.0
        self._phase_max = 360.0

    @property
    def freq_min(self) -> float:
        """
        Minimum frequency limit in Hz.

        Returns
        -------
        float
            Minimum frequency in Hz.
        """
        return self._freq_min

    @freq_min.setter
    def freq_min(self, value: float) -> None:
        """
        Set minimum frequency limit.

        Parameters
        ----------
        value : float
            Minimum frequency in Hz.
        """
        print(f"WARNING: Changing frequency minimum from {self._freq_min} Hz to {value} Hz")
        print("Ensure this matches your instrument specifications!")
        self._freq_min = value

    @property
    def freq_max(self) -> float:
        """
        Maximum frequency limit in Hz.

        Returns
        -------
        float
            Maximum frequency in Hz.
        """
        return self._freq_max

    @freq_max.setter
    def freq_max(self, value: float) -> None:
        """
        Set maximum frequency limit.

        Parameters
        ----------
        value : float
            Maximum frequency in Hz.
        """
        print(f"WARNING: Changing frequency maximum from {self._freq_max} Hz to {value} Hz")
        print("Ensure this matches your instrument specifications!")
        self._freq_max = value

    @property
    def amp_min(self) -> float:
        """
        Minimum amplitude limit in V.

        Returns
        -------
        float
            Minimum amplitude in V.
        """
        return self._amp_min

    @amp_min.setter
    def amp_min(self, value: float) -> None:
        """
        Set minimum amplitude limit.

        Parameters
        ----------
        value : float
            Minimum amplitude in V.
        """
        print(f"WARNING: Changing amplitude minimum from {self._amp_min} V to {value} V")
        print("Ensure this matches your instrument specifications!")
        self._amp_min = value

    @property
    def amp_max(self) -> float:
        """
        Maximum amplitude limit in V.

        Returns
        -------
        float
            Maximum amplitude in V.
        """
        return self._amp_max

    @amp_max.setter
    def amp_max(self, value: float) -> None:
        """
        Set maximum amplitude limit.

        Parameters
        ----------
        value : float
            Maximum amplitude in V.
        """
        print(f"WARNING: Changing amplitude maximum from {self._amp_max} V to {value} V")
        print("Ensure this matches your instrument specifications!")
        self._amp_max = value

    @property
    def offset_min(self) -> float:
        """
        Minimum offset limit in V.

        Returns
        -------
        float
            Minimum offset in V.
        """
        return self._offset_min

    @offset_min.setter
    def offset_min(self, value: float) -> None:
        """
        Set minimum offset limit.

        Parameters
        ----------
        value : float
            Minimum offset in V.
        """
        print(f"WARNING: Changing offset minimum from {self._offset_min} V to {value} V")
        print("Ensure this matches your instrument specifications!")
        self._offset_min = value

    @property
    def offset_max(self) -> float:
        """
        Maximum offset limit in V.

        Returns
        -------
        float
            Maximum offset in V.
        """
        return self._offset_max

    @offset_max.setter
    def offset_max(self, value: float) -> None:
        """
        Set maximum offset limit.

        Parameters
        ----------
        value : float
            Maximum offset in V.
        """
        print(f"WARNING: Changing offset maximum from {self._offset_max} V to {value} V")
        print("Ensure this matches your instrument specifications!")
        self._offset_max = value

    @property
    def phase_min(self) -> float:
        """
        Minimum phase limit in degrees.

        Returns
        -------
        float
            Minimum phase in degrees.
        """
        return self._phase_min

    @phase_min.setter
    def phase_min(self, value: float) -> None:
        """
        Set minimum phase limit.

        Parameters
        ----------
        value : float
            Minimum phase in degrees.
        """
        print(f"WARNING: Changing phase minimum from {self._phase_min} degrees to {value} degrees")
        print("Ensure this matches your instrument specifications!")
        self._phase_min = value

    @property
    def phase_max(self) -> float:
        """
        Maximum phase limit in degrees.

        Returns
        -------
        float
            Maximum phase in degrees.
        """
        return self._phase_max

    @phase_max.setter
    def phase_max(self, value: float) -> None:
        """
        Set maximum phase limit.

        Parameters
        ----------
        value : float
            Maximum phase in degrees.
        """
        print(f"WARNING: Changing phase maximum from {self._phase_max} degrees to {value} degrees")
        print("Ensure this matches your instrument specifications!")
        self._phase_max = value

    def reset_to_defaults(self) -> None:
        """
        Reset all parameter limits to factory defaults.

        Examples
        --------
        >>> limits = ParameterLimits()
        ...     limits.freq_max = 50e6
        ...     limits.reset_to_defaults()
        """
        self._freq_min = 1e-6
        self._freq_max = 40e6
        self._amp_min = 0.002
        self._amp_max = 20.0
        self._offset_min = -10.0
        self._offset_max = 10.0
        self._phase_min = 0.0
        self._phase_max = 360.0
        print("Parameter limits reset to factory defaults")


class SiglentSDG2042X:
    """
    Interface for Siglent SDG2042X arbitrary waveform generator.

    Provides control over waveform parameters, output settings, and channel configuration.
    Supports USB, Ethernet, and GPIB connections.

    Parameters
    ----------
    resource_name : str, optional
        Direct VISA resource name (e.g., 'USB0::0x0483::0x7540::SDG2042X12345678::INSTR').
    timeout : int, optional
        Communication timeout in milliseconds. Default is 5000.
    unit_mode : str, optional
        Unit return mode: 'tuple' for (value, unit) tuples, 'pint' for pint Quantity objects.
        Default is 'tuple'. Requires pint package for 'pint' mode.

    Attributes
    ----------
    VALID_WAVEFORMS : list[str]
        Valid waveform type strings: 'SINE', 'SQUARE', 'RAMP', 'PULSE', 'NOISE', 'ARB', 'DC', 'PRBS', 'IQ'.
    limits : ParameterLimits
        Parameter validation limits.

    Examples
    --------
    Basic usage:
        >>> with SiglentSDG2042X() as sig_gen:
        ...     sig_gen.channel = 1
        ...     sig_gen.waveform_type = 'SINE'
        ...     sig_gen.frequency = 1000
        ...     sig_gen.amplitude = 1.0
        ...     sig_gen.output_state = True

    Use pint units:
        >>> sig_gen = SiglentSDG2042X(unit_mode='pint')
        ...     sig_gen.connect()
        ...     freq = sig_gen.frequency
    """

    VALID_WAVEFORMS = ['SINE', 'SQUARE', 'RAMP', 'PULSE', 'NOISE', 'ARB', 'DC', 'PRBS', 'IQ']

    def __init__(
        self,
        resource_name: Optional[str] = None,
        timeout: int = 5000,
        unit_mode: str = 'tuple'
    ) -> None:
        self.rm = pyvisa.ResourceManager()
        self.instrument: Optional[MessageBasedResource] = None
        self.resource_name = resource_name
        self.timeout = timeout
        self._active_channel = 1
        self.limits = ParameterLimits()
        self._unit_mode: Optional[str] = None
        self.unit_mode = unit_mode

    def __enter__(self) -> SiglentSDG2042X:
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type: Optional[type], exc_val: Optional[Exception], exc_tb: Optional[object]) -> None:
        """Context manager exit."""
        self.disconnect()

    @property
    def unit_mode(self) -> Optional[str]:
        """
        Unit return mode.

        Returns
        -------
        str
            Current unit mode: 'tuple' or 'pint'.

        Examples
        --------
        >>> sig_gen = SiglentSDG2042X(unit_mode='pint')
        ...     mode = sig_gen.unit_mode
        """
        return self._unit_mode

    @unit_mode.setter
    def unit_mode(self, value: str) -> None:
        """
        Set unit return mode.

        Parameters
        ----------
        value : str
            Unit mode: 'tuple' for (value, unit) tuples, 'pint' for pint Quantity objects.

        Raises
        ------
        SiglentValidationError
            If mode is invalid.

        Examples
        --------
        >>> sig_gen = SiglentSDG2042X()
        ...     sig_gen.unit_mode = 'pint'
        """
        if value not in ['pint', 'tuple']:
            raise SiglentValidationError(
                f"Unit mode must be 'pint' or 'tuple', got '{value}'"
            )
        self._unit_mode = value

    def _ensure_connected(self) -> None:
        """Verify instrument is connected before operation."""
        if not self.instrument:
            raise SiglentConnectionError(
                "Not connected to instrument. Use 'with SiglentSDG2042X() as sig_gen:' "
                "or call sig_gen.connect() before using properties."
            )

    def _get_instrument(self) -> MessageBasedResource:
        """
        Get instrument resource with type narrowing.

        Returns
        -------
        MessageBasedResource
            Connected instrument resource.

        Raises
        ------
        SiglentConnectionError
            If instrument is not connected.
        """
        self._ensure_connected()
        return cast(MessageBasedResource, self.instrument)

    def _parse_parameter_response(self, response: str) -> Dict[str, str]:
        """
        Parse parameter response string into dictionary.

        Parameters
        ----------
        response : str
            Response string from instrument.

        Returns
        -------
        dict[str, str]
            Dictionary of parameter key-value pairs.
        """
        import re

        header_match = re.match(r'C\d+:BSWV\s+(.+)', response)
        if header_match:
            params_string = header_match.group(1)
        else:
            params_string = response

        params: Dict[str, str] = {}
        parts = params_string.split(',')
        i = 0
        while i < len(parts):
            key = parts[i].strip() if i < len(parts) else ''
            if i + 1 < len(parts):
                value = parts[i + 1].strip()
                params[key] = value
            i += 2
        return params

    def _extract_numeric_value(self, value_string: str) -> float:
        """
        Extract numeric value from string.

        Parameters
        ----------
        value_string : str
            String containing numeric value.

        Returns
        -------
        float
            Extracted numeric value.

        Raises
        ------
        ValueError
            If numeric value cannot be extracted.
        """
        import re
        match = re.match(r'([+-]?[\d.]+(?:[eE][+-]?\d+)?)', value_string)
        if match:
            return float(match.group(1))
        raise ValueError(f"Could not extract numeric value from: {value_string}")

    def _extract_value_and_unit(self, value_string: str) -> Tuple[float, str]:
        """
        Extract numeric value and unit from string.

        Parameters
        ----------
        value_string : str
            String containing value and optional unit.

        Returns
        -------
        tuple[float, str]
            Tuple of (value, unit_string).

        Raises
        ------
        ValueError
            If value cannot be extracted.
        """
        import re
        match = re.match(r'([+-]?[\d.]+(?:[eE][+-]?\d+)?)(.+)?', value_string)
        if match:
            value = float(match.group(1))
            unit = match.group(2).strip() if match.group(2) else ''
            return value, unit
        raise ValueError(f"Could not extract value and unit from: {value_string}")

    def _format_quantity(self, value: float, unit_str: str, pint_unit: str) -> Union[Any, Tuple[float, str]]:
        """
        Format quantity based on unit mode.

        Parameters
        ----------
        value : float
            Numeric value.
        unit_str : str
            Unit string.
        pint_unit : str
            Pint unit string.

        Returns
        -------
        pint.Quantity or tuple[float, str]
            Formatted quantity based on unit_mode setting.
        """
        if self._unit_mode == 'pint' and ureg is not None:
            return ureg.Quantity(value, pint_unit)
        else:
            return (value, unit_str)

    def connect(self) -> None:
        """
        Establish connection to Siglent SDG2042X waveform generator.

        Attempts connection using resource name if provided, otherwise performs
        auto-discovery on available VISA resources.

        Raises
        ------
        SiglentConnectionError
            If connection fails or instrument is not a Siglent SDG.

        Examples
        --------
        >>> sig_gen = SiglentSDG2042X()
        >>> sig_gen.connect()
        Connected to: Siglent Technologies,SDG2042X,SDG2042X12345678,2.01.01.35R1
        Resource: USB0::0x0483::0x7540::SDG2042X12345678::INSTR
        """
        if self.resource_name:
            try:
                self.instrument = cast(MessageBasedResource, self.rm.open_resource(self.resource_name))
                self.instrument.timeout = self.timeout
                idn = self.instrument.query('*IDN?').strip()
                print(f"Connected to: {idn}")
                print(f"Resource: {self.resource_name}")
                return
            except pyvisa.Error as e:
                raise SiglentConnectionError(
                    f"Could not connect to {self.resource_name}. Check resource name and connections.",
                    pyvisa_error=e
                )

        try:
            resources = self.rm.list_resources()
        except pyvisa.Error as e:
            raise SiglentConnectionError(
                "Could not list VISA resources. Ensure NI-VISA is installed and instruments are connected.",
                pyvisa_error=e
            )

        for resource in resources:
            try:
                test_instr: MessageBasedResource = cast(MessageBasedResource, self.rm.open_resource(resource))
                test_instr.timeout = 2000
                idn = test_instr.query('*IDN?').strip()
                if 'Siglent' in idn and 'SDG' in idn:
                    self.instrument = test_instr
                    self.instrument.timeout = self.timeout
                    self.resource_name = resource
                    print(f"Connected to: {idn}")
                    print(f"Resource: {resource}")
                    return
                else:
                    test_instr.close()
            except pyvisa.Error:
                continue

        raise SiglentConnectionError(
            "No Siglent SDG instrument found. Check connections and power."
        )

    def disconnect(self) -> None:
        """
        Close connection to instrument.

        Raises
        ------
        SiglentConnectionError
            If closing connection fails.

        Examples
        --------
        >>> sig_gen = SiglentSDG2042X()
        >>> sig_gen.connect()
        >>> sig_gen.disconnect()
        """
        if self.instrument:
            try:
                self.instrument.close()
            except pyvisa.Error as e:
                raise SiglentConnectionError(
                    "Error closing instrument connection",
                    pyvisa_error=e
                )

    @property
    def channel(self) -> int:
        """
        Active channel number.

        Returns
        -------
        int
            Current active channel (1 or 2).

        Examples
        --------
        >>> with SiglentSDG2042X() as sig_gen:
        ...     sig_gen.channel = 1
        ...     current_ch = sig_gen.channel
        """
        return self._active_channel

    @channel.setter
    def channel(self, value: int) -> None:
        """
        Set active channel.

        Parameters
        ----------
        value : int
            Channel number: 1 or 2.

        Raises
        ------
        SiglentValidationError
            If channel number is invalid.

        Examples
        --------
        >>> with SiglentSDG2042X() as sig_gen:
        ...     sig_gen.channel = 1
        ...     sig_gen.frequency = 1000
        """
        if value not in [1, 2]:
            raise SiglentValidationError(
                f"Channel must be 1 or 2, got {value}"
            )
        self._active_channel = value

    @property
    def frequency(self) -> Union[Any, Tuple[float, str]]:
        """
        Waveform frequency.

        Returns
        -------
        pint.Quantity or tuple[float, str]
            Frequency value. Format depends on unit_mode setting.

        Raises
        ------
        SiglentCommandError
            If query fails or response cannot be parsed.

        Examples
        --------
        >>> with SiglentSDG2042X() as sig_gen:
        ...     sig_gen.channel = 1
        ...     freq, unit = sig_gen.frequency
        ...     print(f"Frequency: {freq} {unit}")
        """
        self._ensure_connected()
        try:
            instrument = self._get_instrument()
            response = instrument.query(f'C{self._active_channel}:BSWV?').strip()
            params = self._parse_parameter_response(response)

            if 'FRQ' in params:
                freq_string = params['FRQ']
                freq_value, unit_str = self._extract_value_and_unit(freq_string)

                if 'KHZ' in unit_str.upper():
                    return self._format_quantity(freq_value, unit_str, 'kilohertz')
                elif 'MHZ' in unit_str.upper():
                    return self._format_quantity(freq_value, unit_str, 'megahertz')
                else:
                    return self._format_quantity(freq_value, unit_str, 'hertz')

            raise SiglentCommandError(
                f"Could not parse frequency from response: {response}"
            )
        except pyvisa.Error as e:
            raise SiglentCommandError(
                f"Failed to query frequency on channel {self._active_channel}",
                pyvisa_error=e
            )

    @frequency.setter
    def frequency(self, value: Union[float, int]) -> None:
        """
        Set waveform frequency.

        Parameters
        ----------
        value : float or int
            Frequency in Hz. Must be within limits.freq_min and limits.freq_max.

        Raises
        ------
        SiglentValidationError
            If frequency is outside valid range.
        SiglentCommandError
            If command fails.

        Examples
        --------
        >>> with SiglentSDG2042X() as sig_gen:
        ...     sig_gen.channel = 1
        ...     sig_gen.frequency = 1000
        ...     sig_gen.frequency = 1e6
        """
        self._ensure_connected()
        freq_hz = float(value)

        if not (self.limits.freq_min <= freq_hz <= self.limits.freq_max):
            raise SiglentValidationError(
                f"Frequency {freq_hz} Hz is outside valid range [{self.limits.freq_min}, {self.limits.freq_max}] Hz.\n"
                f"To use this frequency, adjust the limit:\n"
                f"  sig_gen.limits.freq_max = {freq_hz}\n"
                f"WARNING: Verify this is within your instrument's actual specifications!"
            )
        try:
            instrument = self._get_instrument()
            cmd = f'C{self._active_channel}:BSWV FRQ,{freq_hz}'
            instrument.write(cmd)
        except pyvisa.Error as e:
            raise SiglentCommandError(
                f"Failed to set frequency to {freq_hz} Hz on channel {self._active_channel}",
                pyvisa_error=e
            )

    @property
    def amplitude(self) -> Union[Any, Tuple[float, str]]:
        """
        Waveform amplitude.

        Returns
        -------
        pint.Quantity or tuple[float, str]
            Amplitude value. Format depends on unit_mode setting.

        Raises
        ------
        SiglentCommandError
            If query fails or response cannot be parsed.

        Examples
        --------
        >>> with SiglentSDG2042X() as sig_gen:
        ...     sig_gen.channel = 1
        ...     amp, unit = sig_gen.amplitude
        ...     print(f"Amplitude: {amp} {unit}")
        """
        self._ensure_connected()
        try:
            instrument = self._get_instrument()
            response = instrument.query(f'C{self._active_channel}:BSWV?').strip()
            params = self._parse_parameter_response(response)

            if 'AMP' in params:
                amp_string = params['AMP']
                amp_value, unit_str = self._extract_value_and_unit(amp_string)

                if 'MV' in unit_str.upper():
                    return self._format_quantity(amp_value, unit_str, 'millivolt')
                else:
                    return self._format_quantity(amp_value, unit_str, 'volt')

            raise SiglentCommandError(
                f"Could not parse amplitude from response: {response}"
            )
        except pyvisa.Error as e:
            raise SiglentCommandError(
                f"Failed to query amplitude on channel {self._active_channel}",
                pyvisa_error=e
            )

    @amplitude.setter
    def amplitude(self, value: Union[float, int]) -> None:
        """
        Set waveform amplitude.

        Parameters
        ----------
        value : float or int
            Amplitude in V. Must be within limits.amp_min and limits.amp_max.

        Raises
        ------
        SiglentValidationError
            If amplitude is outside valid range.
        SiglentCommandError
            If command fails.

        Examples
        --------
        >>> with SiglentSDG2042X() as sig_gen:
        ...     sig_gen.channel = 1
        ...     sig_gen.amplitude = 1.0
        ...     sig_gen.amplitude = 2.5
        """
        self._ensure_connected()
        amp_v = float(value)

        if not (self.limits.amp_min <= amp_v <= self.limits.amp_max):
            raise SiglentValidationError(
                f"Amplitude {amp_v} V is outside valid range [{self.limits.amp_min}, {self.limits.amp_max}] V.\n"
                f"To use this amplitude, adjust the limit:\n"
                f"  sig_gen.limits.amp_max = {amp_v}\n"
                f"WARNING: Verify this is within your instrument's actual specifications!"
            )
        try:
            instrument = self._get_instrument()
            cmd = f'C{self._active_channel}:BSWV AMP,{amp_v}'
            instrument.write(cmd)
        except pyvisa.Error as e:
            raise SiglentCommandError(
                f"Failed to set amplitude to {amp_v} V on channel {self._active_channel}",
                pyvisa_error=e
            )

    @property
    def offset(self) -> Union[Any, Tuple[float, str]]:
        """
        Waveform DC offset.

        Returns
        -------
        pint.Quantity or tuple[float, str]
            Offset value. Format depends on unit_mode setting.

        Raises
        ------
        SiglentCommandError
            If query fails or response cannot be parsed.

        Examples
        --------
        >>> with SiglentSDG2042X() as sig_gen:
        ...     sig_gen.channel = 1
        ...     offset, unit = sig_gen.offset
        ...     print(f"Offset: {offset} {unit}")
        """
        self._ensure_connected()
        try:
            instrument = self._get_instrument()
            response = instrument.query(f'C{self._active_channel}:BSWV?').strip()
            params = self._parse_parameter_response(response)

            if 'OFST' in params:
                offset_string = params['OFST']
                offset_value, unit_str = self._extract_value_and_unit(offset_string)

                if 'MV' in unit_str.upper():
                    return self._format_quantity(offset_value, unit_str, 'millivolt')
                else:
                    return self._format_quantity(offset_value, unit_str, 'volt')

            raise SiglentCommandError(
                f"Could not parse offset from response: {response}"
            )
        except pyvisa.Error as e:
            raise SiglentCommandError(
                f"Failed to query offset on channel {self._active_channel}",
                pyvisa_error=e
            )

    @offset.setter
    def offset(self, value: Union[float, int]) -> None:
        """
        Set waveform DC offset.

        Parameters
        ----------
        value : float or int
            Offset in V. Must be within limits.offset_min and limits.offset_max.

        Raises
        ------
        SiglentValidationError
            If offset is outside valid range.
        SiglentCommandError
            If command fails.

        Examples
        --------
        >>> with SiglentSDG2042X() as sig_gen:
        ...     sig_gen.channel = 1
        ...     sig_gen.offset = 0.5
        ...     sig_gen.offset = -1.0
        """
        self._ensure_connected()
        offset_v = float(value)

        if not (self.limits.offset_min <= offset_v <= self.limits.offset_max):
            raise SiglentValidationError(
                f"Offset {offset_v} V is outside valid range [{self.limits.offset_min}, {self.limits.offset_max}] V.\n"
                f"To use this offset, adjust the limit:\n"
                f"  sig_gen.limits.offset_max = {offset_v}\n"
                f"WARNING: Verify this is within your instrument's actual specifications!"
            )
        try:
            instrument = self._get_instrument()
            cmd = f'C{self._active_channel}:BSWV OFST,{offset_v}'
            instrument.write(cmd)
        except pyvisa.Error as e:
            raise SiglentCommandError(
                f"Failed to set offset to {offset_v} V on channel {self._active_channel}",
                pyvisa_error=e
            )

    @property
    def phase(self) -> Union[Any, Tuple[float, str]]:
        """
        Waveform phase.

        Returns
        -------
        pint.Quantity or tuple[float, str]
            Phase value in degrees. Format depends on unit_mode setting.

        Raises
        ------
        SiglentCommandError
            If query fails or response cannot be parsed.

        Examples
        --------
        >>> with SiglentSDG2042X() as sig_gen:
        ...     sig_gen.channel = 1
        ...     phase, unit = sig_gen.phase
        ...     print(f"Phase: {phase} {unit}")
        """
        self._ensure_connected()
        try:
            instrument = self._get_instrument()
            response = instrument.query(f'C{self._active_channel}:BSWV?').strip()
            params = self._parse_parameter_response(response)

            if 'PHSE' in params:
                phase_string = params['PHSE']
                phase_value, unit_str = self._extract_value_and_unit(phase_string)
                return self._format_quantity(phase_value, unit_str, 'degree')

            raise SiglentCommandError(
                f"Could not parse phase from response: {response}"
            )
        except pyvisa.Error as e:
            raise SiglentCommandError(
                f"Failed to query phase on channel {self._active_channel}",
                pyvisa_error=e
            )

    @phase.setter
    def phase(self, value: Union[float, int]) -> None:
        """
        Set waveform phase.

        Parameters
        ----------
        value : float or int
            Phase in degrees. Must be within limits.phase_min and limits.phase_max.

        Raises
        ------
        SiglentValidationError
            If phase is outside valid range.
        SiglentCommandError
            If command fails.

        Examples
        --------
        >>> with SiglentSDG2042X() as sig_gen:
        ...     sig_gen.channel = 1
        ...     sig_gen.phase = 45.0
        ...     sig_gen.phase = 90
        """
        self._ensure_connected()
        phase_deg = float(value)

        if not (self.limits.phase_min <= phase_deg <= self.limits.phase_max):
            raise SiglentValidationError(
                f"Phase {phase_deg} degrees is outside valid range [{self.limits.phase_min}, {self.limits.phase_max}] degrees.\n"
                f"To use this phase, adjust the limit:\n"
                f"  sig_gen.limits.phase_max = {phase_deg}\n"
                f"WARNING: Verify this is within your instrument's actual specifications!"
            )
        try:
            instrument = self._get_instrument()
            cmd = f'C{self._active_channel}:BSWV PHSE,{phase_deg}'
            instrument.write(cmd)
        except pyvisa.Error as e:
            raise SiglentCommandError(
                f"Failed to set phase to {phase_deg} degrees on channel {self._active_channel}",
                pyvisa_error=e
            )

    @property
    def waveform_type(self) -> str:
        """
        Waveform type.

        Returns
        -------
        str
            Current waveform type string.

        Raises
        ------
        SiglentCommandError
            If query fails or response cannot be parsed.

        Examples
        --------
        >>> with SiglentSDG2042X() as sig_gen:
        ...     sig_gen.channel = 1
        ...     wv_type = sig_gen.waveform_type
        ...     print(f"Waveform: {wv_type}")
        """
        self._ensure_connected()
        try:
            instrument = self._get_instrument()
            response = instrument.query(f'C{self._active_channel}:BSWV?').strip()
            params = self._parse_parameter_response(response)

            if 'WVTP' in params:
                return params['WVTP']

            raise SiglentCommandError(
                f"Could not parse waveform type from response: {response}"
            )
        except pyvisa.Error as e:
            raise SiglentCommandError(
                f"Failed to query waveform type on channel {self._active_channel}",
                pyvisa_error=e
            )

    @waveform_type.setter
    def waveform_type(self, value: str) -> None:
        """
        Set waveform type.

        Parameters
        ----------
        value : str
            Waveform type: 'SINE', 'SQUARE', 'RAMP', 'PULSE', 'NOISE', 'ARB', 'DC', 'PRBS', 'IQ'.

        Raises
        ------
        SiglentValidationError
            If waveform type is invalid.
        SiglentCommandError
            If command fails.

        Examples
        --------
        >>> with SiglentSDG2042X() as sig_gen:
        ...     sig_gen.channel = 1
        ...     sig_gen.waveform_type = 'SINE'
        ...     sig_gen.waveform_type = 'SQUARE'
        """
        self._ensure_connected()
        if value.upper() not in self.VALID_WAVEFORMS:
            raise SiglentValidationError(
                f"Invalid waveform type '{value}'.\n"
                f"Valid types: {', '.join(self.VALID_WAVEFORMS)}"
            )
        try:
            instrument = self._get_instrument()
            cmd = f'C{self._active_channel}:BSWV WVTP,{value.upper()}'
            instrument.write(cmd)
        except pyvisa.Error as e:
            raise SiglentCommandError(
                f"Failed to set waveform type to {value} on channel {self._active_channel}",
                pyvisa_error=e
            )

    @property
    def output_state(self) -> bool:
        """
        Output enable state.

        Returns
        -------
        bool
            True if output enabled, False if disabled.

        Raises
        ------
        SiglentCommandError
            If query fails or response cannot be parsed.

        Examples
        --------
        >>> with SiglentSDG2042X() as sig_gen:
        ...     sig_gen.channel = 1
        ...     is_on = sig_gen.output_state
        ...     print(f"Output: {'ON' if is_on else 'OFF'}")
        """
        self._ensure_connected()
        try:
            instrument = self._get_instrument()
            response = instrument.query(f'C{self._active_channel}:OUTP?').strip()
            params = response.split(',')
            if len(params) > 0:
                state = params[0].strip()
                return state == 'ON'
            raise SiglentCommandError(
                f"Could not parse output state from response: {response}"
            )
        except pyvisa.Error as e:
            raise SiglentCommandError(
                f"Failed to query output state on channel {self._active_channel}",
                pyvisa_error=e
            )

    @output_state.setter
    def output_state(self, value: bool) -> None:
        """
        Enable or disable output.

        Parameters
        ----------
        value : bool
            True to enable output, False to disable.

        Raises
        ------
        SiglentCommandError
            If command fails.

        Examples
        --------
        >>> with SiglentSDG2042X() as sig_gen:
        ...     sig_gen.channel = 1
        ...     sig_gen.output_state = True
        ...     sig_gen.output_state = False
        """
        self._ensure_connected()
        state_str = 'ON' if value else 'OFF'
        try:
            instrument = self._get_instrument()
            cmd = f'C{self._active_channel}:OUTP {state_str}'
            instrument.write(cmd)
        except pyvisa.Error as e:
            raise SiglentCommandError(
                f"Failed to set output state to {state_str} on channel {self._active_channel}",
                pyvisa_error=e
            )

    @property
    def load_impedance(self) -> Union[Any, Tuple[float, str], str]:
        """
        Load impedance setting.

        Returns
        -------
        pint.Quantity or tuple[float, str] or str
            Load impedance. Returns 'HiZ' for high impedance, otherwise formatted quantity
            based on unit_mode setting.

        Raises
        ------
        SiglentCommandError
            If query fails or response cannot be parsed.

        Examples
        --------
        >>> with SiglentSDG2042X() as sig_gen:
        ...     sig_gen.channel = 1
        ...     load = sig_gen.load_impedance
        ...     print(f"Load: {load}")
        """
        self._ensure_connected()
        try:
            instrument = self._get_instrument()
            response = instrument.query(f'C{self._active_channel}:OUTP?').strip()
            params = response.split(',')
            for i, param in enumerate(params):
                if 'LOAD' in param and i + 1 < len(params):
                    load_value = params[i + 1].strip()
                    if load_value == 'HZ':
                        return 'HiZ'
                    try:
                        load_num = float(load_value)
                        return self._format_quantity(load_num, load_value, 'ohm')
                    except ValueError:
                        return load_value
            raise SiglentCommandError(
                f"Could not parse load impedance from response: {response}"
            )
        except pyvisa.Error as e:
            raise SiglentCommandError(
                f"Failed to query load impedance on channel {self._active_channel}",
                pyvisa_error=e
            )

    @load_impedance.setter
    def load_impedance(self, value: Union[str, int, float]) -> None:
        """
        Set load impedance.

        Parameters
        ----------
        value : str or int or float
            Load impedance. Can be 'HiZ' or 'HZ' for high impedance, or numeric value in ohms.

        Raises
        ------
        SiglentCommandError
            If command fails.

        Examples
        --------
        >>> with SiglentSDG2042X() as sig_gen:
        ...     sig_gen.channel = 1
        ...     sig_gen.load_impedance = 'HiZ'
        ...     sig_gen.load_impedance = 50
        """
        self._ensure_connected()

        if isinstance(value, str):
            load_str = value.upper()
        else:
            load_str = str(int(value))

        try:
            instrument = self._get_instrument()
            current_state = 'ON' if self.output_state else 'OFF'
            cmd = f'C{self._active_channel}:OUTP {current_state},LOAD,{load_str}'
            instrument.write(cmd)
        except pyvisa.Error as e:
            raise SiglentCommandError(
                f"Failed to set load impedance to {load_str} on channel {self._active_channel}",
                pyvisa_error=e
            )

    def check_connection(self) -> bool:
        """
        Verify instrument connection and communication.

        Returns
        -------
        bool
            True if instrument responds correctly.

        Raises
        ------
        SiglentCommandError
            If communication fails.

        Examples
        --------
        >>> sig_gen = SiglentSDG2042X()
        >>> sig_gen.connect()
        >>> if sig_gen.check_connection():
        ...     print("Instrument is responding")
        """
        self._ensure_connected()
        try:
            instrument = self._get_instrument()
            idn = instrument.query('*IDN?')
            print(f"Instrument responding: {idn.strip()}")
            return True
        except pyvisa.Error as e:
            raise SiglentCommandError(
                "Communication error during connection check",
                pyvisa_error=e
            )

    def reset(self) -> None:
        """
        Reset instrument to default state.

        Raises
        ------
        SiglentCommandError
            If reset command fails.

        Examples
        --------
        >>> with SiglentSDG2042X() as sig_gen:
        ...     sig_gen.reset()
        """
        self._ensure_connected()
        try:
            instrument = self._get_instrument()
            instrument.write('*RST')
        except pyvisa.Error as e:
            raise SiglentCommandError(
                "Reset command failed",
                pyvisa_error=e
            )

    def list_waveforms(self) -> List[Dict[str, str]]:
        """
        List available arbitrary waveforms stored in instrument.

        Returns
        -------
        list[dict[str, str]]
            List of dictionaries with 'index' and 'name' keys for each waveform.

        Raises
        ------
        SiglentCommandError
            If query fails.

        Examples
        --------
        >>> with SiglentSDG2042X() as sig_gen:
        ...     waveforms = sig_gen.list_waveforms()
        ...     for wv in waveforms:
        ...         print(f"Index {wv['index']}: {wv['name']}")
        """
        self._ensure_connected()
        try:
            instrument = self._get_instrument()
            response = instrument.query('STL?').strip()
            waveforms: List[Dict[str, str]] = []
            parts = response.split(',')
            for i in range(0, len(parts), 2):
                if i + 1 < len(parts):
                    index = parts[i].strip()
                    name = parts[i + 1].strip().strip('"')
                    waveforms.append({'index': index, 'name': name})
            return waveforms
        except pyvisa.Error as e:
            raise SiglentCommandError(
                "Failed to retrieve waveform list",
                pyvisa_error=e
            )

    def get_duty_cycle(self) -> Union[Any, Tuple[float, str]]:
        """
        Get duty cycle for SQUARE or PULSE waveforms.

        Returns
        -------
        pint.Quantity or tuple[float, str]
            Duty cycle in percent. Format depends on unit_mode setting.

        Raises
        ------
        SiglentCommandError
            If query fails or waveform type does not support duty cycle.

        Examples
        --------
        >>> with SiglentSDG2042X() as sig_gen:
        ...     sig_gen.channel = 1
        ...     sig_gen.waveform_type = 'SQUARE'
        ...     duty, unit = sig_gen.get_duty_cycle()
        ...     print(f"Duty cycle: {duty} {unit}")
        """
        self._ensure_connected()
        try:
            instrument = self._get_instrument()
            response = instrument.query(f'C{self._active_channel}:BSWV?').strip()
            params = self._parse_parameter_response(response)

            if 'DUTY' in params:
                duty_string = params['DUTY']
                duty_value, unit_str = self._extract_value_and_unit(duty_string)
                return self._format_quantity(duty_value, unit_str, 'percent')

            raise SiglentCommandError(
                f"Could not parse duty cycle from response: {response}. "
                f"Duty cycle only available for SQUARE/PULSE waveforms."
            )
        except pyvisa.Error as e:
            raise SiglentCommandError(
                f"Failed to query duty cycle on channel {self._active_channel}",
                pyvisa_error=e
            )

    def set_duty_cycle(self, duty: Union[float, int]) -> None:
        """
        Set duty cycle for SQUARE or PULSE waveforms.

        Parameters
        ----------
        duty : float or int
            Duty cycle in percent (0-100).

        Raises
        ------
        SiglentValidationError
            If duty cycle is outside valid range.
        SiglentCommandError
            If command fails or waveform type does not support duty cycle.

        Examples
        --------
        >>> with SiglentSDG2042X() as sig_gen:
        ...     sig_gen.channel = 1
        ...     sig_gen.waveform_type = 'SQUARE'
        ...     sig_gen.set_duty_cycle(50.0)
        """
        self._ensure_connected()
        duty_percent = float(duty)

        if not (0 <= duty_percent <= 100):
            raise SiglentValidationError(
                f"Duty cycle must be between 0 and 100%, got {duty_percent}%"
            )
        try:
            instrument = self._get_instrument()
            cmd = f'C{self._active_channel}:BSWV DUTY,{duty_percent}'
            instrument.write(cmd)
        except pyvisa.Error as e:
            raise SiglentCommandError(
                f"Failed to set duty cycle to {duty_percent}% on channel {self._active_channel}. "
                f"Ensure waveform type is SQUARE or PULSE.",
                pyvisa_error=e
            )

    def get_symmetry(self) -> Union[Any, Tuple[float, str]]:
        """
        Get symmetry for RAMP waveforms.

        Returns
        -------
        pint.Quantity or tuple[float, str]
            Symmetry in percent. Format depends on unit_mode setting.

        Raises
        ------
        SiglentCommandError
            If query fails or waveform type does not support symmetry.

        Examples
        --------
        >>> with SiglentSDG2042X() as sig_gen:
        ...     sig_gen.channel = 1
        ...     sig_gen.waveform_type = 'RAMP'
        ...     sym, unit = sig_gen.get_symmetry()
        ...     print(f"Symmetry: {sym} {unit}")
        """
        self._ensure_connected()
        try:
            instrument = self._get_instrument()
            response = instrument.query(f'C{self._active_channel}:BSWV?').strip()
            params = self._parse_parameter_response(response)

            if 'SYM' in params:
                sym_string = params['SYM']
                sym_value, unit_str = self._extract_value_and_unit(sym_string)
                return self._format_quantity(sym_value, unit_str, 'percent')

            raise SiglentCommandError(
                f"Could not parse symmetry from response: {response}. "
                f"Symmetry only available for RAMP waveforms."
            )
        except pyvisa.Error as e:
            raise SiglentCommandError(
                f"Failed to query symmetry on channel {self._active_channel}",
                pyvisa_error=e
            )

    def set_symmetry(self, symmetry: Union[float, int]) -> None:
        """
        Set symmetry for RAMP waveforms.

        Parameters
        ----------
        symmetry : float or int
            Symmetry in percent (0-100).

        Raises
        ------
        SiglentValidationError
            If symmetry is outside valid range.
        SiglentCommandError
            If command fails or waveform type does not support symmetry.

        Examples
        --------
        >>> with SiglentSDG2042X() as sig_gen:
        ...     sig_gen.channel = 1
        ...     sig_gen.waveform_type = 'RAMP'
        ...     sig_gen.set_symmetry(50.0)
        """
        self._ensure_connected()
        sym_percent = float(symmetry)

        if not (0 <= sym_percent <= 100):
            raise SiglentValidationError(
                f"Symmetry must be between 0 and 100%, got {sym_percent}%"
            )
        try:
            instrument = self._get_instrument()
            cmd = f'C{self._active_channel}:BSWV SYM,{sym_percent}'
            instrument.write(cmd)
        except pyvisa.Error as e:
            raise SiglentCommandError(
                f"Failed to set symmetry to {sym_percent}% on channel {self._active_channel}. "
                f"Ensure waveform type is RAMP.",
                pyvisa_error=e
            )

    def get_pulse_width(self) -> Union[Any, Tuple[float, str]]:
        """
        Get pulse width for PULSE waveforms.

        Returns
        -------
        pint.Quantity or tuple[float, str]
            Pulse width in seconds. Format depends on unit_mode setting.

        Raises
        ------
        SiglentCommandError
            If query fails or waveform type does not support pulse width.

        Examples
        --------
        >>> with SiglentSDG2042X() as sig_gen:
        ...     sig_gen.channel = 1
        ...     sig_gen.waveform_type = 'PULSE'
        ...     width, unit = sig_gen.get_pulse_width()
        ...     print(f"Pulse width: {width} {unit}")
        """
        self._ensure_connected()
        try:
            instrument = self._get_instrument()
            response = instrument.query(f'C{self._active_channel}:BSWV?').strip()
            params = self._parse_parameter_response(response)

            if 'WIDTH' in params:
                width_string = params['WIDTH']
                width_value, unit_str = self._extract_value_and_unit(width_string)
                return self._format_quantity(width_value, unit_str, 'second')

            raise SiglentCommandError(
                f"Could not parse pulse width from response: {response}. "
                f"Pulse width only available for PULSE waveforms."
            )
        except pyvisa.Error as e:
            raise SiglentCommandError(
                f"Failed to query pulse width on channel {self._active_channel}",
                pyvisa_error=e
            )

    def set_pulse_width(self, width: Union[float, int]) -> None:
        """
        Set pulse width for PULSE waveforms.

        Parameters
        ----------
        width : float or int
            Pulse width in seconds.

        Raises
        ------
        SiglentCommandError
            If command fails or waveform type does not support pulse width.

        Examples
        --------
        >>> with SiglentSDG2042X() as sig_gen:
        ...     sig_gen.channel = 1
        ...     sig_gen.waveform_type = 'PULSE'
        ...     sig_gen.set_pulse_width(1e-3)
        """
        self._ensure_connected()
        width_s = float(width)

        try:
            instrument = self._get_instrument()
            cmd = f'C{self._active_channel}:BSWV WIDTH,{width_s}'
            instrument.write(cmd)
        except pyvisa.Error as e:
            raise SiglentCommandError(
                f"Failed to set pulse width to {width_s} s on channel {self._active_channel}. "
                f"Ensure waveform type is PULSE.",
                pyvisa_error=e
            )

    def get_rise_time(self) -> Union[Any, Tuple[float, str]]:
        """
        Get rise time for PULSE waveforms.

        Returns
        -------
        pint.Quantity or tuple[float, str]
            Rise time in seconds. Format depends on unit_mode setting.

        Raises
        ------
        SiglentCommandError
            If query fails or waveform type does not support rise time.

        Examples
        --------
        >>> with SiglentSDG2042X() as sig_gen:
        ...     sig_gen.channel = 1
        ...     sig_gen.waveform_type = 'PULSE'
        ...     rise, unit = sig_gen.get_rise_time()
        ...     print(f"Rise time: {rise} {unit}")
        """
        self._ensure_connected()
        try:
            instrument = self._get_instrument()
            response = instrument.query(f'C{self._active_channel}:BSWV?').strip()
            params = self._parse_parameter_response(response)

            if 'RISE' in params:
                rise_string = params['RISE']
                rise_value, unit_str = self._extract_value_and_unit(rise_string)
                return self._format_quantity(rise_value, unit_str, 'second')

            raise SiglentCommandError(
                f"Could not parse rise time from response: {response}. "
                f"Rise time only available for PULSE waveforms."
            )
        except pyvisa.Error as e:
            raise SiglentCommandError(
                f"Failed to query rise time on channel {self._active_channel}",
                pyvisa_error=e
            )

    def set_rise_time(self, rise_time: Union[float, int]) -> None:
        """
        Set rise time for PULSE waveforms.

        Parameters
        ----------
        rise_time : float or int
            Rise time in seconds.

        Raises
        ------
        SiglentCommandError
            If command fails or waveform type does not support rise time.

        Examples
        --------
        >>> with SiglentSDG2042X() as sig_gen:
        ...     sig_gen.channel = 1
        ...     sig_gen.waveform_type = 'PULSE'
        ...     sig_gen.set_rise_time(1e-6)
        """
        self._ensure_connected()
        rise_s = float(rise_time)

        try:
            instrument = self._get_instrument()
            cmd = f'C{self._active_channel}:BSWV RISE,{rise_s}'
            instrument.write(cmd)
        except pyvisa.Error as e:
            raise SiglentCommandError(
                f"Failed to set rise time to {rise_s} s on channel {self._active_channel}. "
                f"Ensure waveform type is PULSE.",
                pyvisa_error=e
            )

    def get_fall_time(self) -> Union[Any, Tuple[float, str]]:
        """
        Get fall time for PULSE waveforms.

        Returns
        -------
        pint.Quantity or tuple[float, str]
            Fall time in seconds. Format depends on unit_mode setting.

        Raises
        ------
        SiglentCommandError
            If query fails or waveform type does not support fall time.

        Examples
        --------
        >>> with SiglentSDG2042X() as sig_gen:
        ...     sig_gen.channel = 1
        ...     sig_gen.waveform_type = 'PULSE'
        ...     fall, unit = sig_gen.get_fall_time()
        ...     print(f"Fall time: {fall} {unit}")
        """
        self._ensure_connected()
        try:
            instrument = self._get_instrument()
            response = instrument.query(f'C{self._active_channel}:BSWV?').strip()
            params = self._parse_parameter_response(response)

            if 'FALL' in params:
                fall_string = params['FALL']
                fall_value, unit_str = self._extract_value_and_unit(fall_string)
                return self._format_quantity(fall_value, unit_str, 'second')

            raise SiglentCommandError(
                f"Could not parse fall time from response: {response}. "
                f"Fall time only available for PULSE waveforms."
            )
        except pyvisa.Error as e:
            raise SiglentCommandError(
                f"Failed to query fall time on channel {self._active_channel}",
                pyvisa_error=e
            )

    def set_fall_time(self, fall_time: Union[float, int]) -> None:
        """
        Set fall time for PULSE waveforms.

        Parameters
        ----------
        fall_time : float or int
            Fall time in seconds.

        Raises
        ------
        SiglentCommandError
            If command fails or waveform type does not support fall time.

        Examples
        --------
        >>> with SiglentSDG2042X() as sig_gen:
        ...     sig_gen.channel = 1
        ...     sig_gen.waveform_type = 'PULSE'
        ...     sig_gen.set_fall_time(1e-6)
        """
        self._ensure_connected()
        fall_s = float(fall_time)

        try:
            instrument = self._get_instrument()
            cmd = f'C{self._active_channel}:BSWV FALL,{fall_s}'
            instrument.write(cmd)
        except pyvisa.Error as e:
            raise SiglentCommandError(
                f"Failed to set fall time to {fall_s} s on channel {self._active_channel}. "
                f"Ensure waveform type is PULSE.",
                pyvisa_error=e
            )

    def select_arbitrary_waveform(self, index: Optional[int] = None, name: Optional[str] = None) -> None:
        """
        Select arbitrary waveform by index or name.

        Parameters
        ----------
        index : int, optional
            Waveform index. Must specify either index or name.
        name : str, optional
            Waveform name. Must specify either index or name.

        Raises
        ------
        SiglentValidationError
            If neither or both parameters are specified.
        SiglentCommandError
            If command fails.

        Examples
        --------
        >>> with SiglentSDG2042X() as sig_gen:
        ...     sig_gen.channel = 1
        ...     sig_gen.waveform_type = 'ARB'
        ...     sig_gen.select_arbitrary_waveform(index=1)
        ...     sig_gen.select_arbitrary_waveform(name='MyWaveform')
        """
        self._ensure_connected()
        if index is None and name is None:
            raise SiglentValidationError(
                "Must specify either 'index' or 'name' parameter.\n"
                "Use list_waveforms() to see available options."
            )
        if index is not None and name is not None:
            raise SiglentValidationError(
                "Specify either 'index' or 'name', not both."
            )
        try:
            instrument = self._get_instrument()
            if index is not None:
                cmd = f'C{self._active_channel}:ARWV INDEX,{index}'
            else:
                cmd = f'C{self._active_channel}:ARWV NAME,"{name}"'
            instrument.write(cmd)
        except pyvisa.Error as e:
            raise SiglentCommandError(
                f"Failed to select arbitrary waveform. Use list_waveforms() to verify selection.",
                pyvisa_error=e
            )

    def configure_waveform(
        self,
        waveform_type: str,
        frequency: Union[float, int],
        amplitude: Union[float, int],
        offset: Union[float, int] = 0,
        phase: Union[float, int] = 0
    ) -> None:
        """
        Configure waveform with all parameters in a single command.

        Parameters
        ----------
        waveform_type : str
            Waveform type: 'SINE', 'SQUARE', 'RAMP', 'PULSE', 'NOISE', 'ARB', 'DC', 'PRBS', 'IQ'.
        frequency : float or int
            Frequency in Hz.
        amplitude : float or int
            Amplitude in V.
        offset : float or int, optional
            DC offset in V. Default is 0.
        phase : float or int, optional
            Phase in degrees. Default is 0.

        Raises
        ------
        SiglentValidationError
            If parameters are invalid or outside valid ranges.
        SiglentCommandError
            If command fails.

        Examples
        --------
        >>> with SiglentSDG2042X() as sig_gen:
        ...     sig_gen.channel = 1
        ...     sig_gen.configure_waveform('SINE', frequency=1000, amplitude=2.0, offset=0.5, phase=45)
        ...     sig_gen.output_state = True
        """
        self._ensure_connected()

        if waveform_type.upper() not in self.VALID_WAVEFORMS:
            raise SiglentValidationError(
                f"Invalid waveform type '{waveform_type}'.\n"
                f"Valid types: {', '.join(self.VALID_WAVEFORMS)}"
            )

        freq_hz = float(frequency)
        amp_v = float(amplitude)
        offset_v = float(offset)
        phase_deg = float(phase)

        if not (self.limits.freq_min <= freq_hz <= self.limits.freq_max):
            raise SiglentValidationError(
                f"Frequency {freq_hz} Hz is outside valid range [{self.limits.freq_min}, {self.limits.freq_max}] Hz.\n"
                f"To use this frequency, adjust the limit:\n"
                f"  sig_gen.limits.freq_max = {freq_hz}\n"
                f"WARNING: Verify this is within your instrument's actual specifications!"
            )

        if not (self.limits.amp_min <= amp_v <= self.limits.amp_max):
            raise SiglentValidationError(
                f"Amplitude {amp_v} V is outside valid range [{self.limits.amp_min}, {self.limits.amp_max}] V.\n"
                f"To use this amplitude, adjust the limit:\n"
                f"  sig_gen.limits.amp_max = {amp_v}\n"
                f"WARNING: Verify this is within your instrument's actual specifications!"
            )

        if not (self.limits.offset_min <= offset_v <= self.limits.offset_max):
            raise SiglentValidationError(
                f"Offset {offset_v} V is outside valid range [{self.limits.offset_min}, {self.limits.offset_max}] V.\n"
                f"To use this offset, adjust the limit:\n"
                f"  sig_gen.limits.offset_max = {offset_v}\n"
                f"WARNING: Verify this is within your instrument's actual specifications!"
            )

        try:
            instrument = self._get_instrument()
            cmd = f'C{self._active_channel}:BSWV WVTP,{waveform_type.upper()},FRQ,{freq_hz},AMP,{amp_v},OFST,{offset_v},PHSE,{phase_deg}'
            instrument.write(cmd)
        except pyvisa.Error as e:
            raise SiglentCommandError(
                f"Failed to configure waveform with parameters: type={waveform_type}, "
                f"freq={freq_hz}, amp={amp_v}, offset={offset_v}, phase={phase_deg}",
                pyvisa_error=e
            )

    def get_all_parameters(self) -> str:
        """
        Get all waveform parameters as raw response string.

        Returns
        -------
        str
            Raw parameter response string from instrument.

        Raises
        ------
        SiglentCommandError
            If query fails.

        Examples
        --------
        >>> with SiglentSDG2042X() as sig_gen:
        ...     sig_gen.channel = 1
        ...     params = sig_gen.get_all_parameters()
        ...     print(params)
        """
        self._ensure_connected()
        try:
            instrument = self._get_instrument()
            response = instrument.query(f'C{self._active_channel}:BSWV?').strip()
            return response
        except pyvisa.Error as e:
            raise SiglentCommandError(
                f"Failed to query all parameters on channel {self._active_channel}",
                pyvisa_error=e
            )


class PhilipsPM5139:
    """
    Interface for Philips/Fluke PM5139 signal generator.

    Provides the same public API as SiglentSDG2042X for drop-in replacement.
    Controls frequency, amplitude, offset, waveform type, and output via GPIB or RS-232.
    Supports unit_mode 'tuple' or 'pint'. Single-channel; phase and pulse/rise/fall
    are no-op or raise where unsupported.

    Parameters
    ----------
    resource_name : str, optional
        VISA resource (e.g. 'GPIB0::20::INSTR' or 'ASRL1::INSTR').
    timeout : int, optional
        Communication timeout in milliseconds. Default is 5000.
    unit_mode : str, optional
        Unit return mode: 'tuple' or 'pint'. Default is 'tuple'.

    Attributes
    ----------
    VALID_WAVEFORMS : list[str]
        Valid waveform types: 'SINE', 'SQUARE', 'RAMP', 'PULSE', 'ARB', 'DC'.
    limits : ParameterLimits
        Parameter validation limits (PM5139 ranges).

    Examples
    --------
    >>> from inst_ctrl import PhilipsPM5139
    >>> with PhilipsPM5139() as sig_gen:
    ...     sig_gen.channel = 1
    ...     sig_gen.waveform_type = 'SINE'
    ...     sig_gen.frequency = 1000
    ...     sig_gen.amplitude = 1.0
    ...     sig_gen.output_state = True
    """

    VALID_WAVEFORMS = ['SINE', 'SQUARE', 'RAMP', 'PULSE', 'ARB', 'DC']

    _WAVEFORM_TO_PM5139: Dict[str, str] = {
        'SINE': 'SINE',
        'SQUARE': 'SQUARE',
        'RAMP': 'TRNGLE',
        'PULSE': 'POSPULSE',
        'ARB': 'ARB',
        'DC': 'DC',
    }

    _PM5139_TO_WAVEFORM: Dict[str, str] = {
        'SINE': 'SINE',
        'SQR': 'SQUARE',
        'SQUARE': 'SQUARE',
        'TRNGLE': 'RAMP',
        'POSSAWTOOTH': 'RAMP',
        'SAWTOOTH': 'RAMP',
        'NEGSAWTOOTH': 'RAMP',
        'POSPULSE': 'PULSE',
        'NEGPULSE': 'PULSE',
        'HAVERSINE': 'SINE',
        'ARB': 'ARB',
        'DC': 'DC',
    }

    def __init__(
        self,
        resource_name: Optional[str] = None,
        timeout: int = 5000,
        unit_mode: str = 'tuple'
    ) -> None:
        self.rm = pyvisa.ResourceManager()
        self.instrument: Optional[MessageBasedResource] = None
        self.resource_name = resource_name
        self.timeout = timeout
        self.limits = ParameterLimits()
        self.limits.freq_min = 1e-4
        self.limits.freq_max = 20e6
        self.limits.amp_min = 0.0
        self.limits.amp_max = 20.0
        self.limits.offset_min = -10.0
        self.limits.offset_max = 10.0
        self._unit_mode: Optional[str] = None
        self.unit_mode = unit_mode

    def __enter__(self) -> PhilipsPM5139:
        self.connect()
        return self

    def __exit__(self, exc_type: Optional[type], exc_val: Optional[Exception], exc_tb: Optional[object]) -> None:
        self.disconnect()

    @property
    def unit_mode(self) -> Optional[str]:
        return self._unit_mode

    @unit_mode.setter
    def unit_mode(self, value: str) -> None:
        if value not in ['pint', 'tuple']:
            raise SiglentValidationError(
                f"Unit mode must be 'pint' or 'tuple', got '{value}'"
            )
        self._unit_mode = value

    def _ensure_connected(self) -> None:
        if not self.instrument:
            raise SiglentConnectionError(
                "Not connected to instrument. Use 'with PhilipsPM5139() as sig_gen:' "
                "or call sig_gen.connect() before using properties."
            )

    def _get_instrument(self) -> MessageBasedResource:
        self._ensure_connected()
        return cast(MessageBasedResource, self.instrument)

    def _extract_value_and_unit(self, value_string: str) -> Tuple[float, str]:
        match = re.match(r'([+-]?[\d.]+(?:[eE][+-]?\d+)?)(.+)?', value_string.strip())
        if match:
            value = float(match.group(1))
            unit = match.group(2).strip() if match.group(2) else ''
            return value, unit
        raise ValueError(f"Could not extract value and unit from: {value_string}")

    def _format_quantity(self, value: float, unit_str: str, pint_unit: str) -> Union[Any, Tuple[float, str]]:
        if self._unit_mode == 'pint' and ureg is not None:
            return ureg.Quantity(value, pint_unit)
        return (value, unit_str)

    def _configure_serial(self, resource: str) -> None:
        if not resource.upper().startswith('ASRL'):
            return
        instr = self.instrument
        if instr is None:
            return
        try:
            ser = cast(Any, instr)
            if hasattr(ser, 'baud_rate'):
                ser.baud_rate = 9600
            if hasattr(ser, 'data_bits'):
                ser.data_bits = 8
            if hasattr(ser, 'parity'):
                ser.parity = pyvisa_constants.Parity.none
            if hasattr(ser, 'write_termination'):
                ser.write_termination = '\n'
            if hasattr(ser, 'read_termination'):
                ser.read_termination = '\n'
            instr.write('\x1B2')
        except (pyvisa.Error, AttributeError):
            pass

    def connect(self) -> None:
        if self.resource_name:
            try:
                self.instrument = cast(MessageBasedResource, self.rm.open_resource(self.resource_name))
                self.instrument.timeout = self.timeout
                self._configure_serial(self.resource_name)
                idn = self.instrument.query('*IDN?').strip()
                if 'PM5139' not in idn or 'PHILIPS' not in idn or 'PM5138A' not in idn:
                    self.instrument.close()
                    self.instrument = None
                    raise SiglentConnectionError(
                        f"Resource {self.resource_name} is not a Philips PM5139 (got: {idn})."
                    )
                print(f"Connected to: {idn}")
                print(f"Resource: {self.resource_name}")
                return
            except pyvisa.Error as e:
                raise SiglentConnectionError(
                    f"Could not connect to {self.resource_name}. Check resource name and connections.",
                    pyvisa_error=e
                )
        try:
            resources = self.rm.list_resources()
        except pyvisa.Error as e:
            raise SiglentConnectionError(
                "Could not list VISA resources. Ensure NI-VISA is installed and instruments are connected.",
                pyvisa_error=e
            )
        for resource in resources:
            try:
                test_instr = cast(MessageBasedResource, self.rm.open_resource(resource))
                test_instr.timeout = 2000
                self._configure_serial(resource)
                idn = test_instr.query('*IDN?').strip()
                if 'FLUKE' in idn and 'PM5139' in idn:
                    self.instrument = test_instr
                    self.instrument.timeout = self.timeout
                    self.resource_name = resource
                    print(f"Connected to: {idn}")
                    print(f"Resource: {resource}")
                    return
                test_instr.close()
            except pyvisa.Error:
                continue
        raise SiglentConnectionError(
            "No Fluke PM5139 instrument found. Check connections and power."
        )

    def disconnect(self) -> None:
        if self.instrument:
            try:
                self.instrument.close()
            except pyvisa.Error as e:
                raise SiglentConnectionError(
                    "Error closing instrument connection",
                    pyvisa_error=e
                )
            self.instrument = None

    @property
    def channel(self) -> int:
        return 1

    @channel.setter
    def channel(self, value: int) -> None:
        if value != 1:
            raise SiglentValidationError(
                f"PM5139 is single-channel; channel must be 1, got {value}"
            )

    @property
    def frequency(self) -> Union[Any, Tuple[float, str]]:
        self._ensure_connected()
        try:
            instrument = self._get_instrument()
            response = instrument.query('FREQ?').strip()
            value, unit_str = self._extract_value_and_unit(response)
            u = unit_str.upper()
            if 'KHZ' in u or 'KH' in u:
                return self._format_quantity(value, unit_str, 'kilohertz')
            if 'MHZ' in u or 'MH' in u:
                return self._format_quantity(value, unit_str, 'megahertz')
            return self._format_quantity(value, unit_str, 'hertz')
        except pyvisa.Error as e:
            raise SiglentCommandError("Failed to query frequency", pyvisa_error=e)
        except ValueError as e:
            raise SiglentCommandError(str(e))

    @frequency.setter
    def frequency(self, value: Union[float, int]) -> None:
        self._ensure_connected()
        freq_hz = float(value)
        if not (self.limits.freq_min <= freq_hz <= self.limits.freq_max):
            raise SiglentValidationError(
                f"Frequency {freq_hz} Hz is outside valid range [{self.limits.freq_min}, {self.limits.freq_max}] Hz."
            )
        try:
            self._get_instrument().write(f'FREQ {freq_hz}')
        except pyvisa.Error as e:
            raise SiglentCommandError(f"Failed to set frequency to {freq_hz} Hz", pyvisa_error=e)

    def _parse_lrn(self) -> str:
        instrument = self._get_instrument()
        return instrument.query('*LRN?').strip()

    @property
    def amplitude(self) -> Union[Any, Tuple[float, str]]:
        self._ensure_connected()
        try:
            lrn = self._parse_lrn()
            m = re.search(r'AMPLT(?:UDE)?\s+([+-]?[\d.]+(?:[eE][+-]?\d+)?)', lrn, re.IGNORECASE)
            if m:
                value = float(m.group(1))
                return self._format_quantity(value, 'V', 'volt')
            instrument = self._get_instrument()
            response = instrument.query('AMPLTUDE?').strip()
            value, unit_str = self._extract_value_and_unit(response)
            return self._format_quantity(value, unit_str or 'V', 'volt')
        except pyvisa.Error as e:
            raise SiglentCommandError("Failed to query amplitude", pyvisa_error=e)
        except ValueError as e:
            raise SiglentCommandError(str(e))

    @amplitude.setter
    def amplitude(self, value: Union[float, int]) -> None:
        self._ensure_connected()
        amp_v = float(value)
        if not (self.limits.amp_min <= amp_v <= self.limits.amp_max):
            raise SiglentValidationError(
                f"Amplitude {amp_v} V is outside valid range [{self.limits.amp_min}, {self.limits.amp_max}] V."
            )
        try:
            self._get_instrument().write(f'AMPLTUDE {amp_v}')
        except pyvisa.Error as e:
            raise SiglentCommandError(f"Failed to set amplitude to {amp_v} V", pyvisa_error=e)

    @property
    def offset(self) -> Union[Any, Tuple[float, str]]:
        self._ensure_connected()
        try:
            lrn = self._parse_lrn()
            pattern = re.compile(r'DCOFF(?:SET)?\s+([+-]?[\d.]+(?:[eE][+-]?\d+)?)', re.IGNORECASE)
            for m in pattern.finditer(lrn):
                value = float(m.group(1))
                return self._format_quantity(value, 'V', 'volt')
            instrument = self._get_instrument()
            response = instrument.query('DCOFFSET?').strip()
            value, unit_str = self._extract_value_and_unit(response)
            return self._format_quantity(value, unit_str or 'V', 'volt')
        except pyvisa.Error as e:
            raise SiglentCommandError("Failed to query offset", pyvisa_error=e)
        except ValueError as e:
            raise SiglentCommandError(str(e))

    @offset.setter
    def offset(self, value: Union[float, int]) -> None:
        self._ensure_connected()
        offset_v = float(value)
        if not (self.limits.offset_min <= offset_v <= self.limits.offset_max):
            raise SiglentValidationError(
                f"Offset {offset_v} V is outside valid range [{self.limits.offset_min}, {self.limits.offset_max}] V."
            )
        try:
            self._get_instrument().write(f'DCOFFSET {offset_v}')
        except pyvisa.Error as e:
            raise SiglentCommandError(f"Failed to set offset to {offset_v} V", pyvisa_error=e)

    @property
    def phase(self) -> Union[Any, Tuple[float, str]]:
        return self._format_quantity(0.0, 'DEG', 'degree')

    @phase.setter
    def phase(self, value: Union[float, int]) -> None:
        pass

    @property
    def waveform_type(self) -> str:
        self._ensure_connected()
        try:
            response = self._get_instrument().query('WAVEFORM?').strip().upper()
            return self._PM5139_TO_WAVEFORM.get(response, response)
        except pyvisa.Error as e:
            raise SiglentCommandError("Failed to query waveform type", pyvisa_error=e)

    @waveform_type.setter
    def waveform_type(self, value: str) -> None:
        self._ensure_connected()
        uv = value.upper()
        if uv not in self.VALID_WAVEFORMS:
            raise SiglentValidationError(
                f"Invalid waveform type '{value}'. Valid types: {', '.join(self.VALID_WAVEFORMS)}"
            )
        cmd = self._WAVEFORM_TO_PM5139.get(uv, uv)
        if cmd == 'DC':
            try:
                self._get_instrument().write('AMPLTUDE 0')
                self._get_instrument().write('DCON')
            except pyvisa.Error as e:
                raise SiglentCommandError("Failed to set DC waveform", pyvisa_error=e)
            return
        try:
            self._get_instrument().write(f'WAVEFORM {cmd}')
        except pyvisa.Error as e:
            raise SiglentCommandError(f"Failed to set waveform type to {value}", pyvisa_error=e)

    @property
    def output_state(self) -> bool:
        self._ensure_connected()
        try:
            lrn = self._parse_lrn().upper().replace(' ', '')
            if 'ACOFF' in lrn:
                return False
            if 'ACON' in lrn:
                return True
            return False
        except pyvisa.Error as e:
            raise SiglentCommandError("Failed to query output state", pyvisa_error=e)

    @output_state.setter
    def output_state(self, value: bool) -> None:
        self._ensure_connected()
        ac = 'ACON' if value else 'ACOFF'
        dc = 'DCON' if value else 'DCOFF'
        try:
            self._get_instrument().write(f'{ac}; {dc}')
        except pyvisa.Error as e:
            raise SiglentCommandError(f"Failed to set output state to {value}", pyvisa_error=e)

    @property
    def load_impedance(self) -> Union[Any, Tuple[float, str], str]:
        self._ensure_connected()
        try:
            lrn = self._parse_lrn()
            u = lrn.upper()
            if 'LOWIMP' in u:
                rest = u.split('LOWIMP', 1)[-1].strip()
                if rest.startswith('OFF'):
                    return self._format_quantity(50.0, 'ohm', 'ohm') if (self._unit_mode == 'pint' and ureg) else (50.0, 'ohm')
            return 'HiZ'
        except pyvisa.Error as e:
            raise SiglentCommandError("Failed to query load impedance", pyvisa_error=e)

    @load_impedance.setter
    def load_impedance(self, value: Union[str, int, float]) -> None:
        self._ensure_connected()
        if isinstance(value, str):
            s = value.upper()
            if s in ('HIZ', 'HIGH', 'LOW'):
                load_cmd = 'LOWIMP ON'
            elif s == '50':
                load_cmd = 'LOWIMP OFF'
            else:
                raise SiglentValidationError(f"Load impedance must be 'HiZ' or 50, got '{value}'")
        else:
            v = float(value)
            if abs(v - 50) < 0.1:
                load_cmd = 'LOWIMP OFF'
            else:
                raise SiglentValidationError(f"PM5139 supports only 50 ohm or HiZ (low Z); got {value}")
        try:
            self._get_instrument().write(load_cmd)
        except pyvisa.Error as e:
            raise SiglentCommandError(f"Failed to set load impedance to {value}", pyvisa_error=e)

    def check_connection(self) -> bool:
        self._ensure_connected()
        try:
            idn = self._get_instrument().query('*IDN?')
            print(f"Instrument responding: {idn.strip()}")
            return True
        except pyvisa.Error as e:
            raise SiglentCommandError("Communication error during connection check", pyvisa_error=e)

    def reset(self) -> None:
        self._ensure_connected()
        try:
            self._get_instrument().write('*RST')
        except pyvisa.Error as e:
            raise SiglentCommandError("Reset command failed", pyvisa_error=e)

    def get_all_parameters(self) -> str:
        self._ensure_connected()
        try:
            return self._parse_lrn()
        except pyvisa.Error as e:
            raise SiglentCommandError("Failed to query all parameters", pyvisa_error=e)

    def list_waveforms(self) -> List[Dict[str, str]]:
        return [{'index': str(i), 'name': f'ARB{i}'} for i in range(1, 25)]

    def select_arbitrary_waveform(self, index: Optional[int] = None, name: Optional[str] = None) -> None:
        self._ensure_connected()
        if index is None and name is None:
            raise SiglentValidationError(
                "Must specify either 'index' or 'name' parameter. Use list_waveforms() to see options."
            )
        if index is not None and name is not None:
            raise SiglentValidationError("Specify either 'index' or 'name', not both.")
        if index is not None:
            if not (1 <= index <= 24):
                raise SiglentValidationError(f"ARB index must be 1-24, got {index}")
            try:
                self._get_instrument().write(f'ARBITRARY {index}')
            except pyvisa.Error as e:
                raise SiglentCommandError("Failed to select arbitrary waveform", pyvisa_error=e)
            return
        if name is not None:
            match = re.match(r'ARB(\d+)', name.upper())
            if match:
                idx = int(match.group(1))
                if 1 <= idx <= 24:
                    self._get_instrument().write(f'ARBITRARY {idx}')
                    return
            raise SiglentValidationError(
                "PM5139 supports selection by index (1-24) only; name must match ARB<n>."
            )

    def get_duty_cycle(self) -> Union[Any, Tuple[float, str]]:
        self._ensure_connected()
        try:
            response = self._get_instrument().query('DUTYCYCLE?').strip()
            value, unit_str = self._extract_value_and_unit(response)
            return self._format_quantity(value, unit_str or '%', 'percent')
        except pyvisa.Error:
            try:
                lrn = self._parse_lrn()
                for part in lrn.split(';'):
                    if 'DUTYCYCLE' in part.upper() or 'DUTY' in part.upper():
                        m = re.search(r'([+-]?[\d.]+)', part)
                        if m:
                            v = float(m.group(1))
                            return self._format_quantity(v, '%', 'percent')
            except (pyvisa.Error, ValueError):
                pass
            return self._format_quantity(50.0, '%', 'percent')

    def set_duty_cycle(self, duty: Union[float, int]) -> None:
        self._ensure_connected()
        duty_percent = float(duty)
        if not (0 <= duty_percent <= 100):
            raise SiglentValidationError(f"Duty cycle must be between 0 and 100%, got {duty_percent}%")
        try:
            self._get_instrument().write(f'DUTYCYCLE {duty_percent}')
        except pyvisa.Error as e:
            raise SiglentCommandError(f"Failed to set duty cycle to {duty_percent}%", pyvisa_error=e)

    def get_symmetry(self) -> Union[Any, Tuple[float, str]]:
        self._ensure_connected()
        try:
            lrn = self._parse_lrn()
            if 'SYMMETRY ON' in lrn.upper():
                return self._format_quantity(50.0, '%', 'percent')
            return self.get_duty_cycle()
        except pyvisa.Error as e:
            raise SiglentCommandError("Failed to query symmetry", pyvisa_error=e)

    def set_symmetry(self, symmetry: Union[float, int]) -> None:
        self._ensure_connected()
        sym_percent = float(symmetry)
        if not (0 <= sym_percent <= 100):
            raise SiglentValidationError(f"Symmetry must be between 0 and 100%, got {sym_percent}%")
        try:
            if abs(sym_percent - 50.0) < 0.01:
                self._get_instrument().write('SYMMETRY ON')
            else:
                self._get_instrument().write('SYMMETRY OFF')
                self._get_instrument().write(f'DUTYCYCLE {sym_percent}')
        except pyvisa.Error as e:
            raise SiglentCommandError(f"Failed to set symmetry to {sym_percent}%", pyvisa_error=e)

    def get_pulse_width(self) -> Union[Any, Tuple[float, str]]:
        raise SiglentValidationError("PM5139 does not support pulse width parameter.")

    def set_pulse_width(self, width: Union[float, int]) -> None:
        raise SiglentValidationError("PM5139 does not support pulse width parameter.")

    def get_rise_time(self) -> Union[Any, Tuple[float, str]]:
        raise SiglentValidationError("PM5139 does not support rise time parameter.")

    def set_rise_time(self, rise_time: Union[float, int]) -> None:
        raise SiglentValidationError("PM5139 does not support rise time parameter.")

    def get_fall_time(self) -> Union[Any, Tuple[float, str]]:
        raise SiglentValidationError("PM5139 does not support fall time parameter.")

    def set_fall_time(self, fall_time: Union[float, int]) -> None:
        raise SiglentValidationError("PM5139 does not support fall time parameter.")

    def configure_waveform(
        self,
        waveform_type: str,
        frequency: Union[float, int],
        amplitude: Union[float, int],
        offset: Union[float, int] = 0,
        phase: Union[float, int] = 0
    ) -> None:
        self._ensure_connected()
        uv = waveform_type.upper()
        if uv not in self.VALID_WAVEFORMS:
            raise SiglentValidationError(
                f"Invalid waveform type '{waveform_type}'. Valid types: {', '.join(self.VALID_WAVEFORMS)}"
            )
        freq_hz = float(frequency)
        amp_v = float(amplitude)
        offset_v = float(offset)
        if not (self.limits.freq_min <= freq_hz <= self.limits.freq_max):
            raise SiglentValidationError(
                f"Frequency {freq_hz} Hz is outside valid range [{self.limits.freq_min}, {self.limits.freq_max}] Hz."
            )
        if not (self.limits.amp_min <= amp_v <= self.limits.amp_max):
            raise SiglentValidationError(
                f"Amplitude {amp_v} V is outside valid range [{self.limits.amp_min}, {self.limits.amp_max}] V."
            )
        if not (self.limits.offset_min <= offset_v <= self.limits.offset_max):
            raise SiglentValidationError(
                f"Offset {offset_v} V is outside valid range [{self.limits.offset_min}, {self.limits.offset_max}] V."
            )
        if abs(offset_v) + amp_v / 2 > 10:
            raise SiglentValidationError(
                "AC peak + DC offset must not exceed +/-10 V."
            )
        cmd = self._WAVEFORM_TO_PM5139.get(uv, uv)
        try:
            instr = self._get_instrument()
            if cmd == 'DC':
                instr.write('AMPLTUDE 0')
                instr.write('DCOFFSET 0')
                instr.write('DCON')
            else:
                instr.write(f'WAVEFORM {cmd}; FREQ {freq_hz}; AMPLTUDE {amp_v}; DCOFFSET {offset_v}')
        except pyvisa.Error as e:
            raise SiglentCommandError(
                f"Failed to configure waveform: type={waveform_type}, freq={freq_hz}, amp={amp_v}, offset={offset_v}",
                pyvisa_error=e
            )
