"""
Instrument control for the Fluke 45 and 8845A digital multimeters.

This module provides Python interfaces for controlling Fluke 45 and Fluke 8845A/8846A
digital multimeters via GPIB, RS-232, or Ethernet connections using PyVISA.

Examples
--------
Basic usage with Fluke 45:
    >>> from inst_ctrl import Fluke45, Func, Rate
    >>> with Fluke45(gpib_address=3) as dmm:
    ...     dmm.primary_function = Func.VDC
    ...     dmm.rate = Rate.FAST
    ...     voltage = dmm.primary()
    ...     print(f"Voltage: {voltage} V")

Basic usage with Fluke 8845A:
    >>> from inst_ctrl import Fluke88, Func
    >>> with Fluke88(ip_address='192.168.1.100') as dmm:
    ...     dmm.primary_function = Func.OHMS
    ...     resistance = dmm.primary()
    ...     print(f"Resistance: {resistance} Ohms")

Dual display measurement (Fluke 45 only):
    >>> with Fluke45() as dmm:
    ...     dmm.primary_function = Func.VDC
    ...     dmm.secondary_function = Func.FREQ
    ...     voltage, frequency = dmm.both()
    ...     print(f"Voltage: {voltage} V, Frequency: {frequency} Hz")
"""

from __future__ import annotations

import pyvisa
from pyvisa import constants
from pyvisa.resources import MessageBasedResource
from enum import Enum
from typing import Optional, Union, Tuple, cast


class FlukeError(Exception):
    """Base exception for all Fluke instrument errors."""
    pass


class FlukeConnectionError(FlukeError):
    """Raised when connection to instrument fails."""
    def __init__(self, message: str, pyvisa_error: Optional[Exception] = None) -> None:
        super().__init__(message)
        self.pyvisa_error = pyvisa_error


class FlukeValidationError(FlukeError):
    """Raised when invalid parameter values are provided."""
    def __init__(self, message: str, pyvisa_error: Optional[Exception] = None) -> None:
        super().__init__(message)
        self.pyvisa_error = pyvisa_error


class FlukeCommandError(FlukeError):
    """Raised when instrument command execution fails."""
    def __init__(self, message: str, pyvisa_error: Optional[Exception] = None) -> None:
        super().__init__(message)
        self.pyvisa_error = pyvisa_error


class Func(Enum):
    """
    Primary display measurement functions.

    Compatible with Fluke 45 and Fluke 88xx series multimeters.

    Attributes
    ----------
    VDC : str
        DC voltage measurement.
    VAC : str
        AC voltage measurement.
    VACDC : str
        AC+DC voltage measurement.
    ADC : str
        DC current measurement.
    AAC : str
        AC current measurement.
    OHMS : str
        Resistance measurement.
    FREQ : str
        Frequency measurement.
    DIODE : str
        Diode test.

    Examples
    --------
    >>> from inst_ctrl import Fluke45, Func
    >>> dmm = Fluke45()
    >>> dmm.connect()
    >>> dmm.primary_function = Func.VDC
    """
    VDC = 'VDC'
    VAC = 'VAC'
    VACDC = 'VACDC'
    ADC = 'ADC'
    AAC = 'AAC'
    OHMS = 'OHMS'
    FREQ = 'FREQ'
    DIODE = 'DIODE'


class Func2(Enum):
    """
    Secondary display measurement functions.

    Available on Fluke 45 only. Not supported on Fluke 88xx series.

    Attributes
    ----------
    VDC : str
        DC voltage measurement on secondary display.
    VAC : str
        AC voltage measurement on secondary display.
    ADC : str
        DC current measurement on secondary display.
    AAC : str
        AC current measurement on secondary display.
    OHMS : str
        Resistance measurement on secondary display.
    FREQ : str
        Frequency measurement on secondary display.
    DIODE : str
        Diode test on secondary display.
    CLEAR : str
        Clear secondary display.

    Examples
    --------
    >>> from inst_ctrl import Fluke45, Func, Func2
    >>> with Fluke45() as dmm:
    ...     dmm.primary_function = Func.VDC
    ...     dmm.secondary_function = Func2.FREQ
    ...     voltage, freq = dmm.both()
    """
    VDC = 'VDC2'
    VAC = 'VAC2'
    ADC = 'ADC2'
    AAC = 'AAC2'
    OHMS = 'OHMS2'
    FREQ = 'FREQ2'
    DIODE = 'DIODE2'
    CLEAR = 'CLR2'


class Rate(Enum):
    """
    Measurement rate/speed settings.

    Controls the integration time and measurement speed. Faster rates
    provide quicker measurements but lower accuracy.

    Attributes
    ----------
    SLOW : str
        Slow measurement rate (highest accuracy).
    MEDIUM : str
        Medium measurement rate (balanced).
    FAST : str
        Fast measurement rate (lowest accuracy, fastest).

    Examples
    --------
    >>> from inst_ctrl import Fluke45, Rate
    >>> with Fluke45() as dmm:
    ...     dmm.rate = Rate.FAST
    ...     value = dmm.primary()
    """
    SLOW = 'S'
    MEDIUM = 'M'
    FAST = 'F'


class TriggerMode(Enum):
    """
    Trigger modes for measurement initiation.

    Controls how measurements are triggered on the instrument.

    Attributes
    ----------
    INTERNAL : int
        Internal trigger (continuous measurements).
    EXTERNAL : int
        External trigger via front panel.
    EXTERNAL_NO_DELAY : int
        External trigger without delay.
    EXTERNAL_DELAY : int
        External trigger with delay.
    EXTERNAL_REAR_NO_DELAY : int
        External trigger via rear panel without delay.
    EXTERNAL_REAR_DELAY : int
        External trigger via rear panel with delay.

    Examples
    --------
    >>> from inst_ctrl import Fluke45, TriggerMode
    >>> with Fluke45() as dmm:
    ...     dmm.trigger_mode = TriggerMode.EXTERNAL
    ...     dmm.trigger()
    """
    INTERNAL = 1
    EXTERNAL = 4
    EXTERNAL_NO_DELAY = 2
    EXTERNAL_DELAY = 3
    EXTERNAL_REAR_NO_DELAY = 4
    EXTERNAL_REAR_DELAY = 5


class Fluke45:
    """
    Interface for Fluke 45 digital multimeter.

    Provides control over measurement functions, ranges, rates, and trigger modes.
    Supports GPIB and RS-232 connections.

    Parameters
    ----------
    resource_name : str, optional
        Direct VISA resource name (e.g., 'GPIB0::3::INSTR').
    gpib_address : int, optional
        GPIB address for automatic connection.
    serial_port : str, optional
        Serial port name (e.g., 'COM1' on Windows, '/dev/ttyUSB0' on Linux).
    timeout : int, optional
        Communication timeout in milliseconds. Default is 5000.

    Attributes
    ----------
    Func : Func
        Primary measurement function enum.
    Func2 : Func2
        Secondary measurement function enum (Fluke 45 only).
    Rate : Rate
        Measurement rate enum.
    TriggerMode : TriggerMode
        Trigger mode enum.
    DB_REFERENCES : list[int]
        Valid dB reference impedance values in ohms.

    Examples
    --------
    Connect via GPIB:
        >>> dmm = Fluke45(gpib_address=3)
        >>> dmm.connect()
        >>> dmm.primary_function = Func.VDC
        >>> voltage = dmm.primary()

    Connect via serial port:
        >>> dmm = Fluke45(serial_port='/dev/ttyUSB0')
        >>> dmm.connect()

    Use context manager:
        >>> with Fluke45(gpib_address=3) as dmm:
        ...     dmm.primary_function = Func.OHMS
        ...     resistance = dmm.primary()
    """

    Func = Func
    Func2 = Func2
    Rate = Rate
    TriggerMode = TriggerMode

    DB_REFERENCES = [50, 75, 93, 110, 125, 135, 150, 250, 300, 500, 600, 800, 900, 1000, 1200, 8000]

    def __init__(
        self,
        resource_name: Optional[str] = None,
        gpib_address: Optional[int] = None,
        serial_port: Optional[str] = None,
        timeout: int = 5000
    ) -> None:
        self.rm = pyvisa.ResourceManager()
        self.instrument: Optional[MessageBasedResource] = None
        self.resource_name = resource_name
        self.gpib_address = gpib_address
        self.serial_port = serial_port
        self.timeout = timeout
        self._is_serial = False

    def __enter__(self) -> Fluke45:
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type: Optional[type], exc_val: Optional[Exception], exc_tb: Optional[object]) -> None:
        """Context manager exit."""
        self.disconnect()

    def _ensure_connected(self) -> None:
        """Verify instrument is connected before operation."""
        if not self.instrument:
            raise FlukeConnectionError(
                "Not connected to instrument. Use 'with Fluke45() as dmm:' "
                "or call dmm.connect() before using."
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
        FlukeConnectionError
            If instrument is not connected.
        """
        self._ensure_connected()
        return cast(MessageBasedResource, self.instrument)

    def _read_response(self) -> Optional[str]:
        """
        Read response from serial connection.

        Returns
        -------
        str or None
            Response string if serial connection, None for GPIB.

        Raises
        ------
        FlukeCommandError
            If command syntax or execution error detected.
        """
        if not self._is_serial:
            return None

        try:
            instrument = self._get_instrument()
            response = instrument.read().strip()
            if response.startswith('?>'):
                raise FlukeCommandError(
                    f"Command syntax error. Meter returned: {response}"
                )
            elif response.startswith('!>'):
                raise FlukeCommandError(
                    f"Execution error. Meter returned: {response}"
                )
            if response.startswith('=>'):
                response = response[2:].strip()
            return response
        except pyvisa.Error as e:
            raise FlukeCommandError(
                "Failed to read response from instrument",
                pyvisa_error=e
            )

    def connect(self) -> None:
        """
        Establish connection to Fluke 45 multimeter.

        Attempts connection in order: GPIB address, serial port, resource name,
        then auto-discovery on GPIB bus.

        Raises
        ------
        FlukeConnectionError
            If connection fails or instrument is not a Fluke 45.

        Examples
        --------
        >>> dmm = Fluke45(gpib_address=3)
        >>> dmm.connect()
        Connected to: FLUKE,45,12345678,1.0
        Resource: GPIB0::3::INSTR
        """
        if self.gpib_address is not None:
            try:
                resource_string = f'GPIB0::{self.gpib_address}::INSTR'
                self.instrument = cast(MessageBasedResource, self.rm.open_resource(resource_string))
                self.instrument.timeout = self.timeout
                self.instrument.read_termination = '\n'
                self.instrument.write_termination = '\n'
                self._is_serial = False
                idn = self.instrument.query('*IDN?').strip()
                if 'FLUKE' in idn.upper() and '45' in idn:
                    self.resource_name = resource_string
                    print(f"Connected to: {idn}")
                    print(f"Resource: {self.resource_name}")
                    return
                else:
                    self.instrument.close()
                    raise FlukeConnectionError(
                        f"Device at GPIB address {self.gpib_address} is not a Fluke 45. Response: {idn}"
                    )
            except pyvisa.Error as e:
                raise FlukeConnectionError(
                    f"Could not connect to GPIB address {self.gpib_address}. "
                    f"Check address and connections.",
                    pyvisa_error=e
                )

        if self.serial_port:
            try:
                resource = self.rm.open_resource(
                    f'ASRL{self.serial_port}::INSTR',
                    baud_rate=9600,
                    data_bits=8,
                    parity=constants.Parity.none,
                    stop_bits=constants.StopBits.one
                )
                self.instrument = cast(MessageBasedResource, resource)
                self.instrument.timeout = self.timeout
                self.instrument.read_termination = '\n'
                self.instrument.write_termination = '\n'
                self._is_serial = True
                idn = self.instrument.query('*IDN?').strip()
                if 'FLUKE' in idn.upper() and '45' in idn:
                    self.resource_name = f'ASRL{self.serial_port}::INSTR'
                    print(f"Connected to: {idn}")
                    print(f"Resource: {self.resource_name}")
                    return
                else:
                    self.instrument.close()
                    raise FlukeConnectionError(
                        f"Device at {self.serial_port} is not a Fluke 45. Response: {idn}"
                    )
            except pyvisa.Error as e:
                raise FlukeConnectionError(
                    f"Could not connect to serial port {self.serial_port}. "
                    f"Check port name and connections.",
                    pyvisa_error=e
                )

        if self.resource_name:
            try:
                self.instrument = cast(MessageBasedResource, self.rm.open_resource(self.resource_name))
                self.instrument.timeout = self.timeout
                self.instrument.read_termination = '\n'
                self.instrument.write_termination = '\n'
                self._is_serial = 'ASRL' in self.resource_name
                idn = self.instrument.query('*IDN?').strip()
                print(f"Connected to: {idn}")
                print(f"Resource: {self.resource_name}")
                return
            except pyvisa.Error as e:
                raise FlukeConnectionError(
                    f"Could not connect to {self.resource_name}. Check resource name and connections.",
                    pyvisa_error=e
                )

        try:
            resources = self.rm.list_resources()
        except pyvisa.Error as e:
            raise FlukeConnectionError(
                "Could not list VISA resources. Ensure NI-VISA is installed and instruments are connected.",
                pyvisa_error=e
            )

        for resource in resources:
            if 'GPIB' not in resource:
                continue
            try:
                test_instr: MessageBasedResource = cast(MessageBasedResource, self.rm.open_resource(resource))
                test_instr.timeout = 2000
                test_instr.read_termination = '\n'
                test_instr.write_termination = '\n'
                idn = test_instr.query('*IDN?').strip()
                if 'FLUKE' in idn.upper() and '45' in idn:
                    self.instrument = test_instr
                    self.instrument.timeout = self.timeout
                    self.resource_name = resource
                    self._is_serial = False
                    print(f"Connected to: {idn}")
                    print(f"Resource: {resource}")
                    return
                else:
                    test_instr.close()
            except pyvisa.Error:
                continue

        raise FlukeConnectionError(
            "No Fluke 45 instrument found on GPIB. "
            "For RS-232 connection, specify serial_port parameter:\n"
            "  Fluke45(serial_port='COM1')  # Windows\n"
            "  Fluke45(serial_port='/dev/ttyUSB0')  # Linux\n"
            "For GPIB connection, specify gpib_address parameter:\n"
            "  Fluke45(gpib_address=3)  # GPIB address 3"
        )

    def disconnect(self) -> None:
        """
        Close connection to instrument.

        Raises
        ------
        FlukeConnectionError
            If closing connection fails.

        Examples
        --------
        >>> dmm = Fluke45()
        >>> dmm.connect()
        >>> dmm.disconnect()
        """
        if self.instrument:
            try:
                self.instrument.close()
            except pyvisa.Error as e:
                raise FlukeConnectionError(
                    "Error closing instrument connection",
                    pyvisa_error=e
                )

    @property
    def primary_function(self) -> None:
        """
        Primary display measurement function.

        Returns
        -------
        None
            Getter always returns None. Use setter to configure function.

        Examples
        --------
        >>> with Fluke45() as dmm:
        ...     dmm.primary_function = Func.VDC
        ...     dmm.primary_function = 'OHMS'
        """
        self._ensure_connected()
        return None

    @primary_function.setter
    def primary_function(self, value: Union[Func, str]) -> None:
        """
        Set primary display measurement function.

        Parameters
        ----------
        value : Func or str
            Measurement function. Can be Func enum or string like 'VDC', 'AAC', etc.

        Raises
        ------
        FlukeValidationError
            If invalid function specified.
        FlukeCommandError
            If command fails.

        Examples
        --------
        >>> with Fluke45() as dmm:
        ...     dmm.primary_function = Func.VDC
        ...     dmm.primary_function = 'OHMS'
        """
        self._ensure_connected()

        if isinstance(value, Func):
            cmd = value.value
        elif isinstance(value, str):
            cmd = value.upper()
            valid_values = [f.value for f in Func]
            if cmd not in valid_values:
                raise FlukeValidationError(
                    f"Invalid primary function '{value}'.\n"
                    f"Valid functions: {', '.join([f.name for f in Func])}\n"
                    f"Use Func enum or strings like 'VDC', 'AAC', etc."
                )
        else:
            raise FlukeValidationError(
                f"primary_function must be Func enum or string, got {type(value)}"
            )

        try:
            instrument = self._get_instrument()
            instrument.write(cmd)
            self._read_response()
        except pyvisa.Error as e:
            raise FlukeCommandError(
                f"Failed to set primary function to {cmd}",
                pyvisa_error=e
            )

    @property
    def secondary_function(self) -> None:
        """
        Secondary display measurement function (Fluke 45 only).

        Returns
        -------
        None
            Getter always returns None. Use setter to configure function.

        Examples
        --------
        >>> with Fluke45() as dmm:
        ...     dmm.primary_function = Func.VDC
        ...     dmm.secondary_function = Func2.FREQ
        """
        self._ensure_connected()
        return None

    @secondary_function.setter
    def secondary_function(self, value: Union[Func2, str]) -> None:
        """
        Set secondary display measurement function.

        Parameters
        ----------
        value : Func2 or str
            Secondary measurement function. Can be Func2 enum or string.

        Raises
        ------
        FlukeValidationError
            If invalid function specified.
        FlukeCommandError
            If command fails.

        Examples
        --------
        >>> with Fluke45() as dmm:
        ...     dmm.secondary_function = Func2.FREQ
        ...     dmm.secondary_function = 'CLR2'
        """
        self._ensure_connected()

        if isinstance(value, Func2):
            cmd = value.value
        elif isinstance(value, str):
            cmd = value.upper()
            valid_values = [f.value for f in Func2]
            if cmd not in valid_values:
                raise FlukeValidationError(
                    f"Invalid secondary function '{value}'.\n"
                    f"Valid functions: {', '.join([f.name for f in Func2])}\n"
                    f"Use Func2 enum or strings like 'VDC2', 'AAC2', 'CLR2', etc."
                )
        else:
            raise FlukeValidationError(
                f"secondary_function must be Func2 enum or string, got {type(value)}"
            )

        try:
            instrument = self._get_instrument()
            instrument.write(cmd)
            self._read_response()
        except pyvisa.Error as e:
            raise FlukeCommandError(
                f"Failed to set secondary function to {cmd}",
                pyvisa_error=e
            )

    @property
    def auto_range(self) -> bool:
        """
        Auto range status.

        Returns
        -------
        bool
            True if auto range enabled, False if manual range.

        Examples
        --------
        >>> with Fluke45() as dmm:
        ...     is_auto = dmm.auto_range
        ...     print(f"Auto range: {is_auto}")
        """
        self._ensure_connected()
        try:
            instrument = self._get_instrument()
            response = instrument.query('AUTO?')
            return response.strip() == '1'
        except pyvisa.Error as e:
            raise FlukeCommandError(
                "Failed to query auto range status",
                pyvisa_error=e
            )

    @auto_range.setter
    def auto_range(self, value: bool) -> None:
        """
        Enable or disable auto range.

        Parameters
        ----------
        value : bool
            True to enable auto range, False for manual range.

        Examples
        --------
        >>> with Fluke45() as dmm:
        ...     dmm.auto_range = True
        ...     dmm.auto_range = False
        """
        self._ensure_connected()
        try:
            instrument = self._get_instrument()
            if value:
                instrument.write('AUTO')
            else:
                instrument.write('RANGE 4')
            self._read_response()
        except pyvisa.Error as e:
            raise FlukeCommandError(
                f"Failed to set auto range to {value}",
                pyvisa_error=e
            )

    @property
    def range(self) -> None:
        """
        Manual range setting.

        Returns
        -------
        None
            Getter always returns None. Use setter to configure range.

        Examples
        --------
        >>> with Fluke45() as dmm:
        ...     dmm.auto_range = False
        ...     dmm.range = 3
        """
        self._ensure_connected()
        return None

    @range.setter
    def range(self, value: int) -> None:
        """
        Set manual measurement range.

        Parameters
        ----------
        value : int
            Range code from 1 to 7. Available ranges depend on measurement function:
            1: 300mV / 300Ω / 30mA
            2: 3V / 3kΩ / 300mA
            3: 30V / 30kΩ / 3A
            4: 300V / 300kΩ / (3A)
            5: 1000V / 3MΩ
            6: 30MΩ
            7: 300MΩ

        Raises
        ------
        FlukeValidationError
            If range value is invalid.
        FlukeCommandError
            If command fails.

        Examples
        --------
        >>> with Fluke45() as dmm:
        ...     dmm.primary_function = Func.VDC
        ...     dmm.auto_range = False
        ...     dmm.range = 3
        """
        self._ensure_connected()
        if not isinstance(value, int) or not (1 <= value <= 7):
            raise FlukeValidationError(
                f"Range must be an integer between 1 and 7, got {value}.\n"
                f"Range codes:\n"
                f"  1: 300mV / 300Ω / 30mA\n"
                f"  2: 3V / 3kΩ / 300mA\n"
                f"  3: 30V / 30kΩ / 3A\n"
                f"  4: 300V / 300kΩ / (3A)\n"
                f"  5: 1000V / 3MΩ\n"
                f"  6: 30MΩ\n"
                f"  7: 300MΩ\n"
                f"Note: Available ranges depend on selected function."
            )
        try:
            instrument = self._get_instrument()
            instrument.write(f'RANGE {value}')
            self._read_response()
        except pyvisa.Error as e:
            raise FlukeCommandError(
                f"Failed to set range to {value}. "
                f"Verify range is valid for current measurement function.",
                pyvisa_error=e
            )

    @property
    def rate(self) -> None:
        """
        Measurement rate setting.

        Returns
        -------
        None
            Getter always returns None. Use setter to configure rate.

        Examples
        --------
        >>> with Fluke45() as dmm:
        ...     dmm.rate = Rate.FAST
        """
        self._ensure_connected()
        return None

    @rate.setter
    def rate(self, value: Union[Rate, str]) -> None:
        """
        Set measurement rate/speed.

        Parameters
        ----------
        value : Rate or str
            Measurement rate. Can be Rate enum or string 'S', 'M', 'F'.

        Raises
        ------
        FlukeValidationError
            If rate value is invalid.
        FlukeCommandError
            If command fails.

        Examples
        --------
        >>> with Fluke45() as dmm:
        ...     dmm.rate = Rate.FAST
        ...     dmm.rate = 'S'
        """
        self._ensure_connected()

        if isinstance(value, Rate):
            cmd = value.value
        elif isinstance(value, str):
            cmd = value.upper()
            valid_values = [r.value for r in Rate]
            if cmd not in valid_values:
                raise FlukeValidationError(
                    f"Invalid rate '{value}'.\n"
                    f"Valid rates: SLOW (S), MEDIUM (M), FAST (F)\n"
                    f"Use Rate enum or strings 'S', 'M', 'F'"
                )
        else:
            raise FlukeValidationError(
                f"rate must be Rate enum or string, got {type(value)}"
            )

        try:
            instrument = self._get_instrument()
            instrument.write(f'RATE {cmd}')
            self._read_response()
        except pyvisa.Error as e:
            raise FlukeCommandError(
                f"Failed to set rate to {cmd}",
                pyvisa_error=e
            )

    def primary(self) -> float:
        """
        Trigger and read primary display measurement.

        Triggers a new measurement and returns the value from the primary display.

        Returns
        -------
        float
            Primary measurement value in current function units.

        Raises
        ------
        FlukeCommandError
            If measurement fails or response cannot be parsed.

        Examples
        --------
        >>> with Fluke45() as dmm:
        ...     dmm.primary_function = Func.VDC
        ...     voltage = dmm.primary()
        ...     print(f"Voltage: {voltage} V")
        """
        self._ensure_connected()
        try:
            instrument = self._get_instrument()
            response = instrument.query('MEAS1?')
            return float(response.strip())
        except ValueError:
            raise FlukeCommandError(
                f"Could not parse primary measurement. Response: {response}"
            )
        except pyvisa.Error as e:
            raise FlukeCommandError(
                "Failed to trigger and read primary measurement",
                pyvisa_error=e
            )

    def secondary(self) -> float:
        """
        Trigger and read secondary display measurement.

        Triggers a new measurement and returns the value from the secondary display.
        Fluke 45 only.

        Returns
        -------
        float
            Secondary measurement value in current function units.

        Raises
        ------
        FlukeCommandError
            If measurement fails or response cannot be parsed.

        Examples
        --------
        >>> with Fluke45() as dmm:
        ...     dmm.secondary_function = Func2.FREQ
        ...     frequency = dmm.secondary()
        ...     print(f"Frequency: {frequency} Hz")
        """
        self._ensure_connected()
        try:
            instrument = self._get_instrument()
            response = instrument.query('MEAS2?')
            return float(response.strip())
        except ValueError:
            raise FlukeCommandError(
                f"Could not parse secondary measurement. Response: {response}"
            )
        except pyvisa.Error as e:
            raise FlukeCommandError(
                "Failed to trigger and read secondary measurement",
                pyvisa_error=e
            )

    def both(self) -> Tuple[float, float]:
        """
        Trigger and read both primary and secondary displays.

        Triggers a new measurement and returns values from both displays.
        Fluke 45 only.

        Returns
        -------
        tuple[float, float]
            Tuple of (primary_value, secondary_value).

        Raises
        ------
        FlukeCommandError
            If measurement fails or response cannot be parsed.

        Examples
        --------
        >>> with Fluke45() as dmm:
        ...     dmm.primary_function = Func.VDC
        ...     dmm.secondary_function = Func2.FREQ
        ...     voltage, frequency = dmm.both()
        ...     print(f"Voltage: {voltage} V, Frequency: {frequency} Hz")
        """
        self._ensure_connected()
        try:
            instrument = self._get_instrument()
            response = instrument.query('MEAS?')
            values = response.strip().split(',')
            if len(values) != 2:
                raise FlukeCommandError(
                    f"Expected two values from MEAS?, got: {response}"
                )
            return float(values[0]), float(values[1])
        except ValueError:
            raise FlukeCommandError(
                f"Could not parse measurement values. Response: {response}"
            )
        except pyvisa.Error as e:
            raise FlukeCommandError(
                "Failed to trigger and read both measurements",
                pyvisa_error=e
            )

    @property
    def primary_value(self) -> float:
        """
        Read current primary display value without triggering.

        Returns the current value on the primary display without triggering
        a new measurement.

        Returns
        -------
        float
            Current primary display value.

        Raises
        ------
        FlukeCommandError
            If read fails or response cannot be parsed.

        Examples
        --------
        >>> with Fluke45() as dmm:
        ...     dmm.primary_function = Func.OHMS
        ...     resistance = dmm.primary_value
        ...     print(f"Resistance: {resistance} Ohms")
        """
        self._ensure_connected()
        try:
            instrument = self._get_instrument()
            response = instrument.query('VAL1?')
            return float(response.strip())
        except ValueError:
            raise FlukeCommandError(
                f"Could not parse primary value. Response: {response}"
            )
        except pyvisa.Error as e:
            raise FlukeCommandError(
                "Failed to read primary value",
                pyvisa_error=e
            )

    @property
    def secondary_value(self) -> float:
        """
        Read current secondary display value without triggering.

        Returns the current value on the secondary display without triggering
        a new measurement. Fluke 45 only.

        Returns
        -------
        float
            Current secondary display value.

        Raises
        ------
        FlukeCommandError
            If read fails or response cannot be parsed.

        Examples
        --------
        >>> with Fluke45() as dmm:
        ...     dmm.secondary_function = Func2.FREQ
        ...     frequency = dmm.secondary_value
        ...     print(f"Frequency: {frequency} Hz")
        """
        self._ensure_connected()
        try:
            instrument = self._get_instrument()
            response = instrument.query('VAL2?')
            return float(response.strip())
        except ValueError:
            raise FlukeCommandError(
                f"Could not parse secondary value. Response: {response}"
            )
        except pyvisa.Error as e:
            raise FlukeCommandError(
                "Failed to read secondary value",
                pyvisa_error=e
            )

    @property
    def relative_mode(self) -> None:
        """
        Relative measurement mode status.

        Returns
        -------
        None
            Getter always returns None. Use setter to configure mode.

        Examples
        --------
        >>> with Fluke45() as dmm:
        ...     dmm.relative_mode = True
        """
        self._ensure_connected()
        return None

    @relative_mode.setter
    def relative_mode(self, value: bool) -> None:
        """
        Enable or disable relative measurement mode.

        In relative mode, measurements are displayed relative to a reference value.

        Parameters
        ----------
        value : bool
            True to enable relative mode, False to disable.

        Examples
        --------
        >>> with Fluke45() as dmm:
        ...     dmm.relative_mode = True
        ...     dmm.set_relative_offset(1.0)
        """
        self._ensure_connected()
        try:
            instrument = self._get_instrument()
            if value:
                instrument.write('REL')
            else:
                instrument.write('RELCLR')
            self._read_response()
        except pyvisa.Error as e:
            raise FlukeCommandError(
                f"Failed to set relative mode to {value}",
                pyvisa_error=e
            )

    def set_relative_offset(self, offset: float) -> None:
        """
        Set relative measurement offset value.

        Parameters
        ----------
        offset : float
            Offset value in current measurement units.

        Raises
        ------
        FlukeCommandError
            If command fails.

        Examples
        --------
        >>> with Fluke45() as dmm:
        ...     dmm.primary_function = Func.VDC
        ...     dmm.relative_mode = True
        ...     dmm.set_relative_offset(1.0)
        """
        self._ensure_connected()
        try:
            instrument = self._get_instrument()
            instrument.write(f'RELSET {offset}')
            self._read_response()
        except pyvisa.Error as e:
            raise FlukeCommandError(
                f"Failed to set relative offset to {offset}",
                pyvisa_error=e
            )

    @property
    def db_mode(self) -> None:
        """
        dB measurement mode status.

        Returns
        -------
        None
            Getter always returns None. Use setter to configure mode.

        Examples
        --------
        >>> with Fluke45() as dmm:
        ...     dmm.db_mode = True
        """
        self._ensure_connected()
        return None

    @db_mode.setter
    def db_mode(self, value: bool) -> None:
        """
        Enable or disable dB measurement mode.

        Parameters
        ----------
        value : bool
            True to enable dB mode, False to disable.

        Examples
        --------
        >>> with Fluke45() as dmm:
        ...     dmm.db_mode = True
        ...     dmm.set_db_reference(600)
        """
        self._ensure_connected()
        try:
            instrument = self._get_instrument()
            if value:
                instrument.write('DB')
            else:
                instrument.write('DBCLR')
            self._read_response()
        except pyvisa.Error as e:
            raise FlukeCommandError(
                f"Failed to set dB mode to {value}",
                pyvisa_error=e
            )

    def set_db_reference(self, impedance: int) -> None:
        """
        Set dB reference impedance.

        Parameters
        ----------
        impedance : int
            Reference impedance in ohms. Must be one of: 50, 75, 93, 110, 125,
            135, 150, 250, 300, 500, 600, 800, 900, 1000, 1200, 8000.

        Raises
        ------
        FlukeValidationError
            If impedance value is not supported.
        FlukeCommandError
            If command fails.

        Examples
        --------
        >>> with Fluke45() as dmm:
        ...     dmm.db_mode = True
        ...     dmm.set_db_reference(600)
        """
        self._ensure_connected()
        if impedance not in self.DB_REFERENCES:
            raise FlukeValidationError(
                f"dB reference impedance {impedance} Ω not supported.\n"
                f"Valid values: {self.DB_REFERENCES}"
            )
        try:
            instrument = self._get_instrument()
            instrument.write(f'DBREF {impedance}')
            self._read_response()
        except pyvisa.Error as e:
            raise FlukeCommandError(
                f"Failed to set dB reference to {impedance} Ω",
                pyvisa_error=e
            )

    @property
    def hold_mode(self) -> None:
        """
        Hold mode status.

        Returns
        -------
        None
            Getter always returns None. Use setter to configure mode.

        Examples
        --------
        >>> with Fluke45() as dmm:
        ...     dmm.hold_mode = True
        """
        self._ensure_connected()
        return None

    @hold_mode.setter
    def hold_mode(self, value: bool) -> None:
        """
        Enable or disable hold mode.

        In hold mode, the display freezes at the current measurement value.

        Parameters
        ----------
        value : bool
            True to enable hold mode, False to disable.

        Examples
        --------
        >>> with Fluke45() as dmm:
        ...     dmm.hold_mode = True
        """
        self._ensure_connected()
        try:
            instrument = self._get_instrument()
            if value:
                instrument.write('HOLD')
            else:
                instrument.write('HOLDCLR')
            self._read_response()
        except pyvisa.Error as e:
            raise FlukeCommandError(
                f"Failed to set hold mode to {value}",
                pyvisa_error=e
            )

    def min_max_mode(self, mode: str) -> None:
        """
        Set min/max measurement mode.

        Parameters
        ----------
        mode : str
            Mode string: 'MIN' for minimum tracking, 'MAX' for maximum tracking,
            'MMCLR' to clear min/max.

        Raises
        ------
        FlukeValidationError
            If mode is invalid.
        FlukeCommandError
            If command fails.

        Examples
        --------
        >>> with Fluke45() as dmm:
        ...     dmm.min_max_mode('MAX')
        ...     dmm.min_max_mode('MMCLR')
        """
        self._ensure_connected()
        valid_modes = ['MIN', 'MAX', 'MMCLR']
        if mode.upper() not in valid_modes:
            raise FlukeValidationError(
                f"Invalid min/max mode '{mode}'.\n"
                f"Valid modes: {', '.join(valid_modes)}"
            )
        try:
            instrument = self._get_instrument()
            instrument.write(mode.upper())
            self._read_response()
        except pyvisa.Error as e:
            raise FlukeCommandError(
                f"Failed to set min/max mode to {mode}",
                pyvisa_error=e
            )

    @property
    def compare_mode(self) -> None:
        """
        Compare mode status.

        Returns
        -------
        None
            Getter always returns None. Use setter to configure mode.

        Examples
        --------
        >>> with Fluke45() as dmm:
        ...     dmm.compare_mode = True
        """
        self._ensure_connected()
        return None

    @compare_mode.setter
    def compare_mode(self, value: bool) -> None:
        """
        Enable or disable compare mode.

        In compare mode, measurements are compared against high and low limits.

        Parameters
        ----------
        value : bool
            True to enable compare mode, False to disable.

        Examples
        --------
        >>> with Fluke45() as dmm:
        ...     dmm.compare_mode = True
        ...     dmm.compare_hi = 10.0
        ...     dmm.compare_lo = 5.0
        """
        self._ensure_connected()
        try:
            instrument = self._get_instrument()
            if value:
                instrument.write('COMP')
            else:
                instrument.write('COMP')
            self._read_response()
        except pyvisa.Error as e:
            raise FlukeCommandError(
                f"Failed to set compare mode to {value}",
                pyvisa_error=e
            )

    @property
    def compare_hi(self) -> None:
        """
        Compare high limit setting.

        Returns
        -------
        None
            Getter always returns None. Use setter to configure limit.

        Examples
        --------
        >>> with Fluke45() as dmm:
        ...     dmm.compare_hi = 10.0
        """
        self._ensure_connected()
        return None

    @compare_hi.setter
    def compare_hi(self, value: float) -> None:
        """
        Set compare high limit.

        Parameters
        ----------
        value : float
            High limit value in current measurement units.

        Examples
        --------
        >>> with Fluke45() as dmm:
        ...     dmm.compare_mode = True
        ...     dmm.compare_hi = 10.0
        """
        self._ensure_connected()
        try:
            instrument = self._get_instrument()
            instrument.write(f'COMPHI {value}')
            self._read_response()
        except pyvisa.Error as e:
            raise FlukeCommandError(
                f"Failed to set compare high limit to {value}",
                pyvisa_error=e
            )

    @property
    def compare_lo(self) -> None:
        """
        Compare low limit setting.

        Returns
        -------
        None
            Getter always returns None. Use setter to configure limit.

        Examples
        --------
        >>> with Fluke45() as dmm:
        ...     dmm.compare_lo = 5.0
        """
        self._ensure_connected()
        return None

    @compare_lo.setter
    def compare_lo(self, value: float) -> None:
        """
        Set compare low limit.

        Parameters
        ----------
        value : float
            Low limit value in current measurement units.

        Examples
        --------
        >>> with Fluke45() as dmm:
        ...     dmm.compare_mode = True
        ...     dmm.compare_lo = 5.0
        """
        self._ensure_connected()
        try:
            instrument = self._get_instrument()
            instrument.write(f'COMPLO {value}')
            self._read_response()
        except pyvisa.Error as e:
            raise FlukeCommandError(
                f"Failed to set compare low limit to {value}",
                pyvisa_error=e
            )

    @property
    def compare_result(self) -> str:
        """
        Compare mode result.

        Returns
        -------
        str
            Compare result: 'HI' if above high limit, 'LO' if below low limit,
            'PASS' if within limits.

        Raises
        ------
        FlukeCommandError
            If query fails or result is unexpected.

        Examples
        --------
        >>> with Fluke45() as dmm:
        ...     dmm.compare_mode = True
        ...     dmm.compare_hi = 10.0
        ...     dmm.compare_lo = 5.0
        ...     result = dmm.compare_result
        ...     print(f"Compare result: {result}")
        """
        self._ensure_connected()
        try:
            instrument = self._get_instrument()
            response = instrument.query('COMP?')
            result = response.strip()
            if result not in ['HI', 'LO', 'PASS']:
                raise FlukeCommandError(
                    f"Unexpected compare result: {result}"
                )
            return result
        except pyvisa.Error as e:
            raise FlukeCommandError(
                "Failed to read compare result",
                pyvisa_error=e
            )

    @property
    def trigger_mode(self) -> None:
        """
        Trigger mode setting.

        Returns
        -------
        None
            Getter always returns None. Use setter to configure mode.

        Examples
        --------
        >>> from inst_ctrl import TriggerMode
        >>> with Fluke45() as dmm:
        ...     dmm.trigger_mode = TriggerMode.EXTERNAL
        """
        self._ensure_connected()
        return None

    @trigger_mode.setter
    def trigger_mode(self, value: Union[TriggerMode, str, int]) -> None:
        """
        Set trigger mode.

        Parameters
        ----------
        value : TriggerMode or str or int
            Trigger mode. Can be TriggerMode enum, string, or integer code (1-5).

        Raises
        ------
        FlukeValidationError
            If mode is invalid.
        FlukeCommandError
            If command fails.

        Examples
        --------
        >>> from inst_ctrl import TriggerMode
        >>> with Fluke45() as dmm:
        ...     dmm.trigger_mode = TriggerMode.EXTERNAL
        ...     dmm.trigger_mode = 'internal'
        ...     dmm.trigger_mode = 1
        """
        self._ensure_connected()

        if isinstance(value, TriggerMode):
            mode_code = value.value
        elif isinstance(value, str):
            mode_str = value.lower()
            mode_map = {
                'internal': 1,
                'external': 4,
                'external_no_delay': 2,
                'external_delay': 3,
                'external_rear_no_delay': 4,
                'external_rear_delay': 5
            }
            if mode_str not in mode_map:
                raise FlukeValidationError(
                    f"Invalid trigger mode '{value}'.\n"
                    f"Valid modes: {', '.join(mode_map.keys())}\n"
                    f"Use TriggerMode enum or strings"
                )
            mode_code = mode_map[mode_str]
        elif isinstance(value, int):
            if not (1 <= value <= 5):
                raise FlukeValidationError(
                    f"Trigger mode code must be 1-5, got {value}"
                )
            mode_code = value
        else:
            raise FlukeValidationError(
                f"Trigger mode must be TriggerMode enum, string, or integer, got {type(value)}"
            )

        try:
            instrument = self._get_instrument()
            instrument.write(f'TRIGGER {mode_code}')
            self._read_response()
        except pyvisa.Error as e:
            raise FlukeCommandError(
                f"Failed to set trigger mode to {value}",
                pyvisa_error=e
            )

    def trigger(self) -> None:
        """
        Send trigger command to instrument.

        Triggers a measurement when in external trigger mode.

        Raises
        ------
        FlukeCommandError
            If trigger command fails.

        Examples
        --------
        >>> with Fluke45() as dmm:
        ...     dmm.trigger_mode = TriggerMode.EXTERNAL
        ...     dmm.trigger()
        """
        self._ensure_connected()
        try:
            instrument = self._get_instrument()
            instrument.write('*TRG')
            self._read_response()
        except pyvisa.Error as e:
            raise FlukeCommandError(
                "Failed to send trigger command",
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
        FlukeCommandError
            If communication fails.

        Examples
        --------
        >>> dmm = Fluke45()
        >>> dmm.connect()
        >>> if dmm.check_connection():
        ...     print("Instrument is responding")
        """
        self._ensure_connected()
        try:
            instrument = self._get_instrument()
            idn = instrument.query('*IDN?')
            print(f"Instrument responding: {idn.strip()}")
            return True
        except pyvisa.Error as e:
            raise FlukeCommandError(
                "Communication error during connection check",
                pyvisa_error=e
            )

    def reset(self) -> None:
        """
        Reset instrument to default state.

        Raises
        ------
        FlukeCommandError
            If reset command fails.

        Examples
        --------
        >>> with Fluke45() as dmm:
        ...     dmm.reset()
        """
        self._ensure_connected()
        try:
            instrument = self._get_instrument()
            instrument.write('*RST')
            self._read_response()
        except pyvisa.Error as e:
            raise FlukeCommandError(
                "Reset command failed",
                pyvisa_error=e
            )

    def clear_status(self) -> None:
        """
        Clear instrument status registers.

        Raises
        ------
        FlukeCommandError
            If clear command fails.

        Examples
        --------
        >>> with Fluke45() as dmm:
        ...     dmm.clear_status()
        """
        self._ensure_connected()
        try:
            instrument = self._get_instrument()
            instrument.write('*CLS')
            self._read_response()
        except pyvisa.Error as e:
            raise FlukeCommandError(
                "Clear status command failed",
                pyvisa_error=e
            )

    def self_test(self) -> bool:
        """
        Execute instrument self-test.

        Returns
        -------
        bool
            True if self-test passes, False if it fails.

        Raises
        ------
        FlukeCommandError
            If self-test command fails or response cannot be parsed.

        Examples
        --------
        >>> with Fluke45() as dmm:
        ...     if dmm.self_test():
        ...         print("Self-test passed")
        """
        self._ensure_connected()
        try:
            instrument = self._get_instrument()
            response = instrument.query('*TST?')
            result = int(response.strip())
            if result == 0:
                print("Self-test PASSED")
                return True
            else:
                print(f"Self-test FAILED with error code: {result}")
                return False
        except ValueError:
            raise FlukeCommandError(
                f"Could not parse self-test result. Response: {response}"
            )
        except pyvisa.Error as e:
            raise FlukeCommandError(
                "Self-test command failed",
                pyvisa_error=e
            )

    def read_status_byte(self) -> int:
        """
        Read instrument status byte.

        Returns
        -------
        int
            Status byte value.

        Raises
        ------
        FlukeCommandError
            If query fails or response cannot be parsed.

        Examples
        --------
        >>> with Fluke45() as dmm:
        ...     status = dmm.read_status_byte()
        ...     print(f"Status byte: {status:08b}")
        """
        self._ensure_connected()
        try:
            instrument = self._get_instrument()
            response = instrument.query('*STB?')
            return int(response.strip())
        except ValueError:
            raise FlukeCommandError(
                f"Could not parse status byte. Response: {response}"
            )
        except pyvisa.Error as e:
            raise FlukeCommandError(
                "Failed to read status byte",
                pyvisa_error=e
            )

    def read_event_status(self) -> int:
        """
        Read event status register.

        Returns
        -------
        int
            Event status register value.

        Raises
        ------
        FlukeCommandError
            If query fails or response cannot be parsed.

        Examples
        --------
        >>> with Fluke45() as dmm:
        ...     event_status = dmm.read_event_status()
        ...     print(f"Event status: {event_status:08b}")
        """
        self._ensure_connected()
        try:
            instrument = self._get_instrument()
            response = instrument.query('*ESR?')
            return int(response.strip())
        except ValueError:
            raise FlukeCommandError(
                f"Could not parse event status register. Response: {response}"
            )
        except pyvisa.Error as e:
            raise FlukeCommandError(
                "Failed to read event status register",
                pyvisa_error=e
            )


class Fluke88(Fluke45):
    """
    Interface for Fluke 8845A/8846A digital multimeter.

    Provides control over measurement functions, ranges, and rates using SCPI commands.
    Presents the same interface as Fluke45 for compatibility. Note that secondary
    display functions (Func2) are not available on 88xx series instruments.
    Supports GPIB, Ethernet, and RS-232 connections.

    Parameters
    ----------
    resource_name : str, optional
        Direct VISA resource name (e.g., 'GPIB0::1::INSTR').
    gpib_address : int, optional
        GPIB address for automatic connection.
    ip_address : str, optional
        IP address for Ethernet connection (e.g., '192.168.1.100').
    serial_port : str, optional
        Serial port name (e.g., 'COM1' on Windows, '/dev/ttyUSB0' on Linux).
    timeout : int, optional
        Communication timeout in milliseconds. Default is 5000.

    Examples
    --------
    Connect via Ethernet:
        >>> dmm = Fluke88(ip_address='192.168.1.100')
        >>> dmm.connect()
        >>> dmm.primary_function = Func.VDC
        >>> voltage = dmm.primary()

    Connect via GPIB:
        >>> with Fluke88(gpib_address=1) as dmm:
        ...     dmm.primary_function = Func.OHMS
        ...     resistance = dmm.primary()
    """

    # Function mapping from Func enum to SCPI commands
    _FUNCTION_MAP = {
        Func.VDC: 'VOLT:DC',
        Func.VAC: 'VOLT:AC',
        Func.ADC: 'CURR:DC',
        Func.AAC: 'CURR:AC',
        Func.OHMS: 'RES',
        Func.FREQ: 'FREQ',
        Func.DIODE: 'DIOD',
    }

    # Rate mapping to SCPI NPLC (Number of Power Line Cycles)
    _RATE_MAP = {
        Rate.FAST: 0.2,
        Rate.MEDIUM: 1,
        Rate.SLOW: 10
    }

    def __init__(
        self,
        resource_name: Optional[str] = None,
        gpib_address: Optional[int] = None,
        ip_address: Optional[str] = None,
        serial_port: Optional[str] = None,
        timeout: int = 5000
    ) -> None:
        super().__init__(resource_name, gpib_address, serial_port, timeout)
        self.ip_address = ip_address
        self._current_function: Optional[str] = None

    def connect(self) -> None:
        """
        Establish connection to Fluke 8845A/8846A multimeter.

        Attempts connection in order: IP address, GPIB address, resource name,
        then auto-discovery on GPIB or Ethernet.

        Raises
        ------
        FlukeConnectionError
            If connection fails or instrument is not a Fluke 8845A/8846A.

        Examples
        --------
        >>> dmm = Fluke88(ip_address='192.168.1.100')
        >>> dmm.connect()
        Connected to: FLUKE,8845A,12345678,1.0
        Resource: TCPIP0::192.168.1.100::inst0::INSTR
        """
        if self.ip_address:
            try:
                resource_string = f'TCPIP0::{self.ip_address}::inst0::INSTR'
                self.instrument = cast(MessageBasedResource, self.rm.open_resource(resource_string))
                self.instrument.timeout = self.timeout
                self.instrument.read_termination = '\n'
                self.instrument.write_termination = '\n'
                self._is_serial = False
                idn = self.instrument.query('*IDN?').strip()
                if 'FLUKE' in idn.upper() and ('8845' in idn or '8846' in idn):
                    self.resource_name = resource_string
                    print(f"Connected to: {idn}")
                    print(f"Resource: {self.resource_name}")
                    return
                else:
                    self.instrument.close()
                    raise FlukeConnectionError(
                        f"Device at {self.ip_address} is not a Fluke 8845A/8846A. Response: {idn}"
                    )
            except pyvisa.Error as e:
                raise FlukeConnectionError(
                    f"Could not connect to IP address {self.ip_address}. "
                    f"Check IP address and network connection.",
                    pyvisa_error=e
                )

        # Try GPIB if address provided
        if self.gpib_address is not None:
            try:
                resource_string = f'GPIB0::{self.gpib_address}::INSTR'
                self.instrument = cast(MessageBasedResource, self.rm.open_resource(resource_string))
                self.instrument.timeout = self.timeout
                self.instrument.read_termination = '\n'
                self.instrument.write_termination = '\n'
                self._is_serial = False
                idn = self.instrument.query('*IDN?').strip()
                if 'FLUKE' in idn.upper() and ('8845' in idn or '8846' in idn):
                    self.resource_name = resource_string
                    print(f"Connected to: {idn}")
                    print(f"Resource: {self.resource_name}")
                    return
                else:
                    self.instrument.close()
                    raise FlukeConnectionError(
                        f"Device at GPIB address {self.gpib_address} is not a Fluke 8845A/8846A. Response: {idn}"
                    )
            except pyvisa.Error as e:
                raise FlukeConnectionError(
                    f"Could not connect to GPIB address {self.gpib_address}. "
                    f"Check address and connections.",
                    pyvisa_error=e
                )

        # Try direct resource name
        if self.resource_name:
            try:
                self.instrument = cast(MessageBasedResource, self.rm.open_resource(self.resource_name))
                self.instrument.timeout = self.timeout
                self.instrument.read_termination = '\n'
                self.instrument.write_termination = '\n'
                self._is_serial = 'ASRL' in self.resource_name
                idn = self.instrument.query('*IDN?').strip()
                print(f"Connected to: {idn}")
                print(f"Resource: {self.resource_name}")
                return
            except pyvisa.Error as e:
                raise FlukeConnectionError(
                    f"Could not connect to {self.resource_name}. Check resource name and connections.",
                    pyvisa_error=e
                )

        # Auto-discovery
        try:
            resources = self.rm.list_resources()
        except pyvisa.Error as e:
            raise FlukeConnectionError(
                "Could not list VISA resources. Ensure NI-VISA is installed and instruments are connected.",
                pyvisa_error=e
            )

        for resource in resources:
            if 'GPIB' not in resource and 'TCPIP' not in resource:
                continue
            try:
                test_instr: MessageBasedResource = cast(MessageBasedResource, self.rm.open_resource(resource))
                test_instr.timeout = 2000
                test_instr.read_termination = '\n'
                test_instr.write_termination = '\n'
                idn = test_instr.query('*IDN?').strip()
                if 'FLUKE' in idn.upper() and ('8845' in idn or '8846' in idn):
                    self.instrument = test_instr
                    self.instrument.timeout = self.timeout
                    self.resource_name = resource
                    self._is_serial = False
                    print(f"Connected to: {idn}")
                    print(f"Resource: {resource}")
                    return
                else:
                    test_instr.close()
            except pyvisa.Error:
                continue

        raise FlukeConnectionError(
            "No Fluke 8845A/8846A instrument found. "
            "For LAN connection, specify ip_address parameter:\n"
            "  Fluke88(ip_address='192.168.1.100')\n"
            "For GPIB connection, specify gpib_address parameter:\n"
            "  Fluke88(gpib_address=1)"
        )

    @property
    def primary_function(self) -> None:
        """
        Primary display measurement function.

        Returns
        -------
        None
            Getter always returns None. Use setter to configure function.

        Examples
        --------
        >>> with Fluke88() as dmm:
        ...     dmm.primary_function = Func.VDC
        """
        return None

    @primary_function.setter
    def primary_function(self, value: Union[Func, str]) -> None:
        """
        Set primary display measurement function.

        Parameters
        ----------
        value : Func or str
            Measurement function. Can be Func enum or string.

        Raises
        ------
        FlukeValidationError
            If invalid or unsupported function specified.
        FlukeCommandError
            If command fails.

        Examples
        --------
        >>> with Fluke88() as dmm:
        ...     dmm.primary_function = Func.VDC
        ...     dmm.primary_function = 'OHMS'
        """
        self._ensure_connected()

        if isinstance(value, Func):
            func_enum = value
        elif isinstance(value, str):
            try:
                func_enum = Func[value.upper()]
            except KeyError:
                raise FlukeValidationError(
                    f"Invalid primary function '{value}'.\n"
                    f"Valid functions: {', '.join([f.name for f in Func])}"
                )
        else:
            raise FlukeValidationError(
                f"primary_function must be Func enum or string, got {type(value)}"
            )

        if func_enum not in self._FUNCTION_MAP:
            raise FlukeValidationError(
                f"Function {func_enum.name} not supported on Fluke 8845A/8846A.\n"
                f"Supported functions: {', '.join([f.name for f in self._FUNCTION_MAP.keys()])}"
            )

        scpi_function = self._FUNCTION_MAP[func_enum]
        self._current_function = scpi_function

        try:
            instrument = self._get_instrument()
            instrument.write(f'CONF:{scpi_function}')
        except pyvisa.Error as e:
            raise FlukeCommandError(
                f"Failed to configure {scpi_function}",
                pyvisa_error=e
            )

    @property
    def secondary_function(self) -> None:
        """
        Secondary display measurement function.

        Not supported on Fluke 8845A/8846A.

        Returns
        -------
        None

        Raises
        ------
        FlukeValidationError
            Always raised as secondary display is not supported.
        """
        return None

    @secondary_function.setter
    def secondary_function(self, value: Union[Func2, str]) -> None:
        """
        Set secondary display measurement function.

        Not supported on Fluke 8845A/8846A.

        Parameters
        ----------
        value : Func2 or str
            Not used.

        Raises
        ------
        FlukeValidationError
            Always raised as secondary display is not supported.
        """
        raise FlukeValidationError(
            "Fluke 8845A/8846A does not support secondary display.\n"
            "Use primary_function only."
        )

    @property
    def auto_range(self) -> None:
        """
        Auto range status.

        Returns
        -------
        None
            Getter always returns None. Use setter to configure.

        Examples
        --------
        >>> with Fluke88() as dmm:
        ...     dmm.primary_function = Func.VDC
        ...     dmm.auto_range = True
        """
        return None

    @auto_range.setter
    def auto_range(self, value: bool) -> None:
        """
        Enable or disable auto range.

        Parameters
        ----------
        value : bool
            True to enable auto range, False for manual range.

        Raises
        ------
        FlukeCommandError
            If primary_function not set or command fails.

        Examples
        --------
        >>> with Fluke88() as dmm:
        ...     dmm.primary_function = Func.VDC
        ...     dmm.auto_range = True
        """
        self._ensure_connected()
        if self._current_function is None:
            raise FlukeCommandError(
                "Must set primary_function before configuring auto_range"
            )

        try:
            instrument = self._get_instrument()
            if value:
                instrument.write(f'{self._current_function}:RANG:AUTO ON')
            else:
                instrument.write(f'{self._current_function}:RANG:AUTO OFF')
        except pyvisa.Error as e:
            raise FlukeCommandError(
                f"Failed to set auto range to {value}",
                pyvisa_error=e
            )

    @property
    def range(self) -> None:
        """
        Manual range setting.

        Returns
        -------
        None
            Getter always returns None. Use setter to configure.

        Examples
        --------
        >>> with Fluke88() as dmm:
        ...     dmm.primary_function = Func.VDC
        ...     dmm.auto_range = False
        ...     dmm.range = 10.0
        """
        return None

    @range.setter
    def range(self, value: float) -> None:
        """
        Set manual measurement range.

        Parameters
        ----------
        value : float
            Range value in current measurement units.

        Raises
        ------
        FlukeCommandError
            If primary_function not set or command fails.

        Examples
        --------
        >>> with Fluke88() as dmm:
        ...     dmm.primary_function = Func.VDC
        ...     dmm.auto_range = False
        ...     dmm.range = 10.0
        """
        self._ensure_connected()
        if self._current_function is None:
            raise FlukeCommandError(
                "Must set primary_function before configuring range"
            )

        try:
            instrument = self._get_instrument()
            instrument.write(f'{self._current_function}:RANG {value}')
        except pyvisa.Error as e:
            raise FlukeCommandError(
                f"Failed to set range to {value}",
                pyvisa_error=e
            )

    @property
    def rate(self) -> None:
        """
        Measurement rate setting.

        Returns
        -------
        None
            Getter always returns None. Use setter to configure.

        Examples
        --------
        >>> with Fluke88() as dmm:
        ...     dmm.primary_function = Func.VDC
        ...     dmm.rate = Rate.FAST
        """
        return None

    @rate.setter
    def rate(self, value: Union[Rate, str]) -> None:
        """
        Set measurement rate/speed.

        Parameters
        ----------
        value : Rate or str
            Measurement rate. Can be Rate enum or string.

        Raises
        ------
        FlukeCommandError
            If primary_function not set or command fails.
        FlukeValidationError
            If rate value is invalid.

        Examples
        --------
        >>> with Fluke88() as dmm:
        ...     dmm.primary_function = Func.VDC
        ...     dmm.rate = Rate.FAST
        """
        self._ensure_connected()
        if self._current_function is None:
            raise FlukeCommandError(
                "Must set primary_function before configuring rate"
            )

        if isinstance(value, Rate):
            rate_enum = value
        elif isinstance(value, str):
            try:
                rate_enum = Rate[value.upper()]
            except KeyError:
                raise FlukeValidationError(
                    f"Invalid rate '{value}'.\n"
                    f"Valid rates: SLOW, MEDIUM, FAST"
                )
        else:
            raise FlukeValidationError(
                f"rate must be Rate enum or string, got {type(value)}"
            )

        nplc = self._RATE_MAP[rate_enum]

        try:
            instrument = self._get_instrument()
            instrument.write(f'{self._current_function}:NPLC {nplc}')
        except pyvisa.Error as e:
            raise FlukeCommandError(
                f"Failed to set rate (NPLC={nplc})",
                pyvisa_error=e
            )

    def primary(self) -> float:
        """
        Trigger and read measurement.

        Triggers a new measurement and returns the value.

        Returns
        -------
        float
            Measurement value in current function units.

        Raises
        ------
        FlukeCommandError
            If measurement fails or response cannot be parsed.

        Examples
        --------
        >>> with Fluke88() as dmm:
        ...     dmm.primary_function = Func.VDC
        ...     voltage = dmm.primary()
        ...     print(f"Voltage: {voltage} V")
        """
        self._ensure_connected()
        try:
            instrument = self._get_instrument()
            response = instrument.query('READ?')
            return float(response.strip())
        except ValueError:
            raise FlukeCommandError(
                f"Could not parse measurement. Response: {response}"
            )
        except pyvisa.Error as e:
            raise FlukeCommandError(
                "Failed to read measurement",
                pyvisa_error=e
            )

    def secondary(self) -> float:
        """
        Trigger and read secondary display measurement.

        Not supported on Fluke 8845A/8846A.

        Returns
        -------
        float
            Not returned.

        Raises
        ------
        FlukeValidationError
            Always raised as secondary display is not supported.
        """
        raise FlukeValidationError(
            "Fluke 8845A/8846A does not support secondary display.\n"
            "Use primary() method only."
        )

    def both(self) -> Tuple[float, float]:
        """
        Trigger and read both displays.

        Not supported on Fluke 8845A/8846A.

        Returns
        -------
        tuple[float, float]
            Not returned.

        Raises
        ------
        FlukeValidationError
            Always raised as dual display is not supported.
        """
        raise FlukeValidationError(
            "Fluke 8845A/8846A does not support dual display.\n"
            "Use primary() method only."
        )

    @property
    def primary_value(self) -> float:
        """
        Read current value without triggering.

        Returns the current value without triggering a new measurement.

        Returns
        -------
        float
            Current measurement value.

        Raises
        ------
        FlukeCommandError
            If read fails or response cannot be parsed.

        Examples
        --------
        >>> with Fluke88() as dmm:
        ...     dmm.primary_function = Func.OHMS
        ...     resistance = dmm.primary_value
        ...     print(f"Resistance: {resistance} Ohms")
        """
        self._ensure_connected()
        try:
            instrument = self._get_instrument()
            response = instrument.query('FETCH?')
            return float(response.strip())
        except ValueError:
            raise FlukeCommandError(
                f"Could not parse value. Response: {response}"
            )
        except pyvisa.Error as e:
            raise FlukeCommandError(
                "Failed to fetch value",
                pyvisa_error=e
            )

    @property
    def secondary_value(self) -> float:
        """
        Read current secondary display value.

        Not supported on Fluke 8845A/8846A.

        Returns
        -------
        float
            Not returned.

        Raises
        ------
        FlukeValidationError
            Always raised as secondary display is not supported.
        """
        raise FlukeValidationError(
            "Fluke 8845A/8846A does not support secondary display."
        )

    def _read_response(self) -> None:
        """
        Read response from instrument.

        Fluke 88xx uses SCPI protocol which does not require reading prompts.
        """
        return
