"""
Instrument control for the Rigol DP800 series programmable power supplies.

This module provides Python interfaces for controlling Rigol DP800 series power supplies
via USB, Ethernet, GPIB, or RS-232 connections using PyVISA.

Examples
--------
Basic usage:
    >>> from inst_ctrl import RigolDP800, Channel
    >>> with RigolDP800(ip_address='192.168.1.100') as psu:
    ...     psu.channel = Channel.CH1
    ...     psu.voltage = 5.0
    ...     psu.current = 1.0
    ...     psu.output = True

Set voltage and current together:
    >>> with RigolDP800() as psu:
    ...     psu.apply(voltage=12.0, current=2.0, channel=Channel.CH1)
    ...     psu.output_on(Channel.CH1)

Measure output:
    >>> with RigolDP800() as psu:
    ...     psu.channel = Channel.CH1
    ...     voltage = psu.measured_voltage
    ...     current = psu.measured_current
    ...     power = psu.measured_power
    ...     print(f"V: {voltage}V, I: {current}A, P: {power}W")
"""

from __future__ import annotations

import pyvisa
from pyvisa.resources import MessageBasedResource
from enum import Enum
from typing import Optional, Union, Tuple, cast


class RigolError(Exception):
    """Base exception for all Rigol instrument errors."""
    pass


class RigolConnectionError(RigolError):
    """Raised when connection to instrument fails."""
    def __init__(self, message: str, pyvisa_error: Optional[Exception] = None) -> None:
        super().__init__(message)
        self.pyvisa_error = pyvisa_error


class RigolValidationError(RigolError):
    """Raised when invalid parameter values are provided."""
    def __init__(self, message: str, pyvisa_error: Optional[Exception] = None) -> None:
        super().__init__(message)
        self.pyvisa_error = pyvisa_error


class RigolCommandError(RigolError):
    """Raised when instrument command execution fails."""
    def __init__(self, message: str, pyvisa_error: Optional[Exception] = None) -> None:
        super().__init__(message)
        self.pyvisa_error = pyvisa_error


class Channel(Enum):
    """
    Power supply output channels.

    Attributes
    ----------
    CH1 : str
        Channel 1.
    CH2 : str
        Channel 2.
    CH3 : str
        Channel 3.

    Examples
    --------
    >>> from inst_ctrl import RigolDP800, Channel
    >>> with RigolDP800() as psu:
    ...     psu.channel = Channel.CH1
    ...     psu.voltage = 5.0
    """
    CH1 = 'CH1'
    CH2 = 'CH2'
    CH3 = 'CH3'


class RigolDP800:
    """
    Interface for Rigol DP800 series programmable power supplies.

    Provides control over voltage, current, output state, and protection settings
    for up to 3 channels. Supports USB, Ethernet, GPIB, and RS-232 connections.

    Parameters
    ----------
    resource_name : str, optional
        Direct VISA resource name (e.g., 'TCPIP0::192.168.1.100::INSTR').
    ip_address : str, optional
        IP address for Ethernet connection (e.g., '192.168.1.100').
    usb_serial : str, optional
        USB serial number for USB connection (e.g., 'DP8C12345678').
    gpib_address : int, optional
        GPIB address for GPIB connection.
    timeout : int, optional
        Communication timeout in milliseconds. Default is 5000.

    Attributes
    ----------
    Channel : Channel
        Channel enum for easy access.

    Examples
    --------
    Connect via Ethernet:
        >>> from inst_ctrl import RigolDP800, Channel
        >>> psu = RigolDP800(ip_address='192.168.1.100')
        >>> psu.connect()
        >>> psu.channel = Channel.CH1
        >>> psu.voltage = 5.0

    Use context manager:
        >>> with RigolDP800(ip_address='192.168.1.100') as psu:
        ...     psu.channel = Channel.CH1
        ...     psu.apply(voltage=12.0, current=2.0)
        ...     psu.output = True
    """

    Channel = Channel

    def __init__(
        self,
        resource_name: Optional[str] = None,
        ip_address: Optional[str] = None,
        usb_serial: Optional[str] = None,
        gpib_address: Optional[int] = None,
        timeout: int = 5000
    ) -> None:
        self.rm = pyvisa.ResourceManager()
        self.instrument: Optional[MessageBasedResource] = None
        self.resource_name = resource_name
        self.ip_address = ip_address
        self.usb_serial = usb_serial
        self.gpib_address = gpib_address
        self.timeout = timeout
        self._active_channel = Channel.CH1

    def __enter__(self) -> RigolDP800:
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type: Optional[type], exc_val: Optional[Exception], exc_tb: Optional[object]) -> None:
        """Context manager exit."""
        self.disconnect()

    def _ensure_connected(self) -> None:
        """Verify instrument is connected before operation."""
        if not self.instrument:
            raise RigolConnectionError(
                "Not connected to instrument. Use 'with RigolDP800() as psu:' "
                "or call psu.connect() before using."
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
        RigolConnectionError
            If instrument is not connected.
        """
        self._ensure_connected()
        return cast(MessageBasedResource, self.instrument)

    def _parse_channel(self, channel: Union[Channel, str, int]) -> str:
        """
        Convert channel parameter to string format.

        Parameters
        ----------
        channel : Channel or str or int
            Channel specification. Can be Channel enum, string ('CH1', 'CH2', 'CH3'),
            or integer (1, 2, 3).

        Returns
        -------
        str
            Channel string in format 'CH1', 'CH2', or 'CH3'.

        Raises
        ------
        RigolValidationError
            If channel is invalid.

        Examples
        --------
        >>> psu = RigolDP800()
        ...     ch = psu._parse_channel(Channel.CH1)
        ...     ch = psu._parse_channel('CH2')
        ...     ch = psu._parse_channel(3)
        """
        if isinstance(channel, Channel):
            return channel.value
        elif isinstance(channel, str):
            ch_upper = channel.upper()
            if ch_upper in ['CH1', 'CH2', 'CH3']:
                return ch_upper
            raise RigolValidationError(
                f"Invalid channel '{channel}'. Must be 'CH1', 'CH2', or 'CH3'"
            )
        elif isinstance(channel, int):
            if channel in [1, 2, 3]:
                return f'CH{channel}'
            raise RigolValidationError(
                f"Invalid channel number {channel}. Must be 1, 2, or 3"
            )
        else:
            raise RigolValidationError(
                f"Channel must be Channel enum, string, or int, got {type(channel)}"
            )

    def connect(self) -> None:
        """
        Establish connection to Rigol DP800 power supply.

        Attempts connection in order: USB serial, IP address, GPIB address,
        resource name, then auto-discovery on available interfaces.

        Raises
        ------
        RigolConnectionError
            If connection fails or instrument is not a Rigol DP800.

        Examples
        --------
        >>> psu = RigolDP800(ip_address='192.168.1.100')
        >>> psu.connect()
        Connected to: RIGOL TECHNOLOGIES,DP832,DP8C12345678,00.01.01.00.01
        Resource: TCPIP0::192.168.1.100::INSTR
        """
        if self.usb_serial:
            try:
                resource_string = f'USB0::0x1AB1::0x0E11::{self.usb_serial}::INSTR'
                usb_instrument: MessageBasedResource = cast(MessageBasedResource, self.rm.open_resource(resource_string))
                usb_instrument.timeout = self.timeout
                usb_instrument.read_termination = '\n'
                usb_instrument.write_termination = '\n'
                idn = usb_instrument.query('*IDN?').strip()
                if 'RIGOL' in idn.upper() and 'DP8' in idn.upper():
                    self.instrument = usb_instrument
                    self.resource_name = resource_string
                    print(f"Connected to: {idn}")
                    print(f"Resource: {self.resource_name}")
                    return
                else:
                    usb_instrument.close()
                    raise RigolConnectionError(
                        f"Device with serial {self.usb_serial} is not a Rigol DP800. Response: {idn}"
                    )
            except pyvisa.Error as e:
                raise RigolConnectionError(
                    f"Could not connect via USB with serial {self.usb_serial}. "
                    f"Check serial number and USB connection.",
                    pyvisa_error=e
                )

        if self.ip_address:
            try:
                resource_string = f'TCPIP0::{self.ip_address}::INSTR'
                ip_instrument: MessageBasedResource = cast(MessageBasedResource, self.rm.open_resource(resource_string))
                ip_instrument.timeout = self.timeout
                ip_instrument.read_termination = '\n'
                ip_instrument.write_termination = '\n'
                idn = ip_instrument.query('*IDN?').strip()
                if 'RIGOL' in idn.upper() and 'DP8' in idn.upper():
                    self.instrument = ip_instrument
                    self.resource_name = resource_string
                    print(f"Connected to: {idn}")
                    print(f"Resource: {self.resource_name}")
                    return
                else:
                    ip_instrument.close()
                    raise RigolConnectionError(
                        f"Device at {self.ip_address} is not a Rigol DP800. Response: {idn}"
                    )
            except pyvisa.Error as e:
                raise RigolConnectionError(
                    f"Could not connect to IP address {self.ip_address}. "
                    f"Check IP address and network connection.",
                    pyvisa_error=e
                )

        if self.gpib_address is not None:
            try:
                resource_string = f'GPIB0::{self.gpib_address}::INSTR'
                gpib_instrument: MessageBasedResource = cast(MessageBasedResource, self.rm.open_resource(resource_string))
                gpib_instrument.timeout = self.timeout
                gpib_instrument.read_termination = '\n'
                gpib_instrument.write_termination = '\n'
                idn = gpib_instrument.query('*IDN?').strip()
                if 'RIGOL' in idn.upper() and 'DP8' in idn.upper():
                    self.instrument = gpib_instrument
                    self.resource_name = resource_string
                    print(f"Connected to: {idn}")
                    print(f"Resource: {self.resource_name}")
                    return
                else:
                    gpib_instrument.close()
                    raise RigolConnectionError(
                        f"Device at GPIB address {self.gpib_address} is not a Rigol DP800. Response: {idn}"
                    )
            except pyvisa.Error as e:
                raise RigolConnectionError(
                    f"Could not connect to GPIB address {self.gpib_address}. "
                    f"Check address and connections.",
                    pyvisa_error=e
                )

        if self.resource_name:
            try:
                resource_instrument: MessageBasedResource = cast(MessageBasedResource, self.rm.open_resource(self.resource_name))
                resource_instrument.timeout = self.timeout
                resource_instrument.read_termination = '\n'
                resource_instrument.write_termination = '\n'
                idn = resource_instrument.query('*IDN?').strip()
                self.instrument = resource_instrument
                print(f"Connected to: {idn}")
                print(f"Resource: {self.resource_name}")
                return
            except pyvisa.Error as e:
                raise RigolConnectionError(
                    f"Could not connect to {self.resource_name}. Check resource name and connections.",
                    pyvisa_error=e
                )

        # Auto-discovery
        try:
            resources = self.rm.list_resources()
        except pyvisa.Error as e:
            raise RigolConnectionError(
                "Could not list VISA resources. Ensure NI-VISA is installed and instruments are connected.",
                pyvisa_error=e
            )

        for resource in resources:
            if 'USB' not in resource and 'TCPIP' not in resource and 'GPIB' not in resource:
                continue
            try:
                test_instr: MessageBasedResource = cast(MessageBasedResource, self.rm.open_resource(resource))
                test_instr.timeout = 2000
                test_instr.read_termination = '\n'
                test_instr.write_termination = '\n'
                idn = test_instr.query('*IDN?').strip()
                if 'RIGOL' in idn.upper() and 'DP8' in idn.upper():
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

        raise RigolConnectionError(
            "No Rigol DP800 series power supply found. "
            "For USB connection, specify usb_serial parameter:\n"
            "  RigolDP800(usb_serial='DP8C....')\n"
            "For LAN connection, specify ip_address parameter:\n"
            "  RigolDP800(ip_address='192.168.1.100')\n"
            "For GPIB connection, specify gpib_address parameter:\n"
            "  RigolDP800(gpib_address=5)"
        )

    def disconnect(self) -> None:
        """
        Close connection to instrument.

        Raises
        ------
        RigolConnectionError
            If closing connection fails.

        Examples
        --------
        >>> psu = RigolDP800()
        >>> psu.connect()
        >>> psu.disconnect()
        """
        if self.instrument:
            try:
                self.instrument.close()
            except pyvisa.Error as e:
                raise RigolConnectionError(
                    "Error closing instrument connection",
                    pyvisa_error=e
                )

    @property
    def channel(self) -> Channel:
        """
        Active channel for subsequent operations.

        Returns
        -------
        Channel
            Current active channel.

        Examples
        --------
        >>> with RigolDP800() as psu:
        ...     current_ch = psu.channel
        ...     print(f"Active channel: {current_ch}")
        """
        return self._active_channel

    @channel.setter
    def channel(self, value: Union[Channel, str, int]) -> None:
        """
        Set active channel for subsequent operations.

        Parameters
        ----------
        value : Channel or str or int
            Channel to activate. Can be Channel enum, string ('CH1', 'CH2', 'CH3'),
            or integer (1, 2, 3).

        Raises
        ------
        RigolValidationError
            If channel is invalid.

        Examples
        --------
        >>> with RigolDP800() as psu:
        ...     psu.channel = Channel.CH1
        ...     psu.channel = 'CH2'
        ...     psu.channel = 3
        """
        if isinstance(value, Channel):
            self._active_channel = value
        elif isinstance(value, str):
            ch_upper = value.upper()
            if ch_upper in ['CH1', 'CH2', 'CH3']:
                self._active_channel = Channel[ch_upper]
            else:
                raise RigolValidationError(
                    f"Invalid channel '{value}'. Must be 'CH1', 'CH2', or 'CH3'"
                )
        elif isinstance(value, int):
            if value in [1, 2, 3]:
                self._active_channel = Channel[f'CH{value}']
            else:
                raise RigolValidationError(
                    f"Invalid channel number {value}. Must be 1, 2, or 3"
                )
        else:
            raise RigolValidationError(
                f"Channel must be Channel enum, string, or int, got {type(value)}"
            )

    @property
    def voltage(self) -> float:
        """
        Voltage setting for active channel.

        Returns
        -------
        float
            Voltage setting in volts.

        Raises
        ------
        RigolCommandError
            If query fails or response cannot be parsed.

        Examples
        --------
        >>> with RigolDP800() as psu:
        ...     psu.channel = Channel.CH1
        ...     voltage = psu.voltage
        ...     print(f"Voltage setting: {voltage} V")
        """
        self._ensure_connected()
        ch = self._active_channel.value
        channel_num = int(ch[2])

        try:
            instrument = self._get_instrument()
            instrument.write(f':INSTrument:NSELect {channel_num}')
            response = instrument.query(':SOURce:VOLTage?')
            return float(response.strip())
        except ValueError:
            raise RigolCommandError(
                f"Could not parse voltage setting. Response: {response}"
            )
        except pyvisa.Error as e:
            raise RigolCommandError(
                f"Failed to query voltage on {ch}",
                pyvisa_error=e
            )

    @voltage.setter
    def voltage(self, value: Union[float, int]) -> None:
        """
        Set voltage for active channel.

        Parameters
        ----------
        value : float or int
            Voltage in volts.

        Raises
        ------
        RigolCommandError
            If command fails.

        Examples
        --------
        >>> with RigolDP800() as psu:
        ...     psu.channel = Channel.CH1
        ...     psu.voltage = 5.0
        ...     psu.voltage = 12
        """
        self._ensure_connected()
        ch = self._active_channel.value
        voltage = float(value)
        channel_num = int(ch[2])

        try:
            instrument = self._get_instrument()
            instrument.write(f':INSTrument:NSELect {channel_num}')
            instrument.write(f':SOURce:VOLTage {voltage}')
        except pyvisa.Error as e:
            raise RigolCommandError(
                f"Failed to set voltage to {voltage}V on {ch}",
                pyvisa_error=e
            )

    @property
    def current(self) -> float:
        """
        Current limit setting for active channel.

        Returns
        -------
        float
            Current limit in amperes.

        Raises
        ------
        RigolCommandError
            If query fails or response cannot be parsed.

        Examples
        --------
        >>> with RigolDP800() as psu:
        ...     psu.channel = Channel.CH1
        ...     current = psu.current
        ...     print(f"Current limit: {current} A")
        """
        self._ensure_connected()
        ch = self._active_channel.value
        channel_num = int(ch[2])

        try:
            instrument = self._get_instrument()
            instrument.write(f':INSTrument:NSELect {channel_num}')
            response = instrument.query(':SOURce:CURRent?')
            return float(response.strip())
        except ValueError:
            raise RigolCommandError(
                f"Could not parse current setting. Response: {response}"
            )
        except pyvisa.Error as e:
            raise RigolCommandError(
                f"Failed to query current on {ch}",
                pyvisa_error=e
            )

    @current.setter
    def current(self, value: Union[float, int]) -> None:
        """
        Set current limit for active channel.

        Parameters
        ----------
        value : float or int
            Current limit in amperes.

        Raises
        ------
        RigolCommandError
            If command fails.

        Examples
        --------
        >>> with RigolDP800() as psu:
        ...     psu.channel = Channel.CH1
        ...     psu.current = 1.0
        ...     psu.current = 2.5
        """
        self._ensure_connected()
        ch = self._active_channel.value
        current = float(value)
        channel_num = int(ch[2])

        try:
            instrument = self._get_instrument()
            instrument.write(f':INSTrument:NSELect {channel_num}')
            instrument.write(f':SOURce:CURRent {current}')
        except pyvisa.Error as e:
            raise RigolCommandError(
                f"Failed to set current to {current}A on {ch}",
                pyvisa_error=e
            )

    def apply(self, voltage: Union[float, int], current: Union[float, int], channel: Optional[Union[Channel, str, int]] = None) -> None:
        """
        Set both voltage and current for specified channel.

        Parameters
        ----------
        voltage : float or int
            Voltage in volts.
        current : float or int
            Current limit in amperes.
        channel : Channel or str or int, optional
            Channel to configure. If None, uses active channel.

        Raises
        ------
        RigolCommandError
            If command fails.

        Examples
        --------
        >>> with RigolDP800() as psu:
        ...     psu.apply(voltage=12.0, current=2.0, channel=Channel.CH1)
        ...     psu.apply(voltage=5.0, current=1.0)
        """
        self._ensure_connected()

        if channel is None:
            ch = self._active_channel.value
        else:
            ch = self._parse_channel(channel)

        voltage = float(voltage)
        current = float(current)

        try:
            instrument = self._get_instrument()
            instrument.write(f':APPLy {ch},{voltage},{current}')
        except pyvisa.Error as e:
            raise RigolCommandError(
                f"Failed to apply {voltage}V, {current}A to {ch}",
                pyvisa_error=e
            )

    def get_settings(self, channel: Optional[Union[Channel, str, int]] = None) -> Tuple[float, float]:
        """
        Query voltage and current settings for specified channel.

        Parameters
        ----------
        channel : Channel or str or int, optional
            Channel to query. If None, uses active channel.

        Returns
        -------
        tuple[float, float]
            Tuple of (voltage, current) in volts and amperes.

        Raises
        ------
        RigolCommandError
            If query fails or response cannot be parsed.

        Examples
        --------
        >>> with RigolDP800() as psu:
        ...     voltage, current = psu.get_settings(Channel.CH1)
        ...     print(f"CH1: {voltage}V, {current}A")
        """
        self._ensure_connected()

        if channel is None:
            ch = self._active_channel.value
        else:
            ch = self._parse_channel(channel)

        try:
            instrument = self._get_instrument()
            response = instrument.query(f':APPLy? {ch}')
            if ':' in response:
                response = response.split(':', 1)[1]

            response = response.replace('V', '').replace('A', '')
            values = response.strip().split(',')

            if len(values) >= 2:
                return float(values[0]), float(values[1])
            raise RigolCommandError(
                f"Unexpected response format: {response}"
            )
        except ValueError:
            raise RigolCommandError(
                f"Could not parse settings. Response: {response}"
            )
        except pyvisa.Error as e:
            raise RigolCommandError(
                f"Failed to query settings for {ch}",
                pyvisa_error=e
            )

    @property
    def measured_voltage(self) -> float:
        """
        Measure actual output voltage for active channel.

        Returns
        -------
        float
            Measured voltage in volts.

        Raises
        ------
        RigolCommandError
            If measurement fails or response cannot be parsed.

        Examples
        --------
        >>> with RigolDP800() as psu:
        ...     psu.channel = Channel.CH1
        ...     voltage = psu.measured_voltage
        ...     print(f"Measured voltage: {voltage} V")
        """
        self._ensure_connected()
        ch = self._active_channel.value

        try:
            instrument = self._get_instrument()
            response = instrument.query(f':MEASure:VOLTage? {ch}')
            return float(response.strip())
        except ValueError:
            raise RigolCommandError(
                f"Could not parse voltage measurement. Response: {response}"
            )
        except pyvisa.Error as e:
            raise RigolCommandError(
                f"Failed to measure voltage on {ch}",
                pyvisa_error=e
            )

    @property
    def measured_current(self) -> float:
        """
        Measure actual output current for active channel.

        Returns
        -------
        float
            Measured current in amperes.

        Raises
        ------
        RigolCommandError
            If measurement fails or response cannot be parsed.

        Examples
        --------
        >>> with RigolDP800() as psu:
        ...     psu.channel = Channel.CH1
        ...     current = psu.measured_current
        ...     print(f"Measured current: {current} A")
        """
        self._ensure_connected()
        ch = self._active_channel.value

        try:
            instrument = self._get_instrument()
            response = instrument.query(f':MEASure:CURRent? {ch}')
            return float(response.strip())
        except ValueError:
            raise RigolCommandError(
                f"Could not parse current measurement. Response: {response}"
            )
        except pyvisa.Error as e:
            raise RigolCommandError(
                f"Failed to measure current on {ch}",
                pyvisa_error=e
            )

    @property
    def measured_power(self) -> float:
        """
        Measure actual output power for active channel.

        Returns
        -------
        float
            Measured power in watts.

        Raises
        ------
        RigolCommandError
            If measurement fails or response cannot be parsed.

        Examples
        --------
        >>> with RigolDP800() as psu:
        ...     psu.channel = Channel.CH1
        ...     power = psu.measured_power
        ...     print(f"Measured power: {power} W")
        """
        self._ensure_connected()
        ch = self._active_channel.value

        try:
            instrument = self._get_instrument()
            response = instrument.query(f':MEASure:POWer? {ch}')
            return float(response.strip())
        except ValueError:
            raise RigolCommandError(
                f"Could not parse power measurement. Response: {response}"
            )
        except pyvisa.Error as e:
            raise RigolCommandError(
                f"Failed to measure power on {ch}",
                pyvisa_error=e
            )

    @property
    def power(self) -> float:
        """
        Convenience alias for measured_power.

        Returns
        -------
        float
            Measured power in watts.

        Examples
        --------
        >>> with RigolDP800() as psu:
        ...     psu.channel = Channel.CH1
        ...     power = psu.power
        """
        return self.measured_power

    def measure_all(self, channel: Optional[Union[Channel, str, int]] = None) -> Tuple[float, float, float]:
        """
        Measure voltage, current, and power for specified channel.

        Parameters
        ----------
        channel : Channel or str or int, optional
            Channel to measure. If None, uses active channel.

        Returns
        -------
        tuple[float, float, float]
            Tuple of (voltage, current, power) in volts, amperes, and watts.

        Raises
        ------
        RigolCommandError
            If measurement fails or response cannot be parsed.

        Examples
        --------
        >>> with RigolDP800() as psu:
        ...     voltage, current, power = psu.measure_all(Channel.CH1)
        ...     print(f"V: {voltage}V, I: {current}A, P: {power}W")
        """
        self._ensure_connected()

        if channel is None:
            ch = self._active_channel.value
        else:
            ch = self._parse_channel(channel)

        try:
            instrument = self._get_instrument()
            response = instrument.query(f':MEASure:ALL? {ch}')
            values = response.strip().split(',')
            if len(values) >= 3:
                return float(values[0]), float(values[1]), float(values[2])
            raise RigolCommandError(
                f"Unexpected response format: {response}"
            )
        except ValueError:
            raise RigolCommandError(
                f"Could not parse measurements. Response: {response}"
            )
        except pyvisa.Error as e:
            raise RigolCommandError(
                f"Failed to measure all on {ch}",
                pyvisa_error=e
            )

    @property
    def output(self) -> bool:
        """
        Output state for active channel.

        Returns
        -------
        bool
            True if output enabled, False if disabled.

        Raises
        ------
        RigolCommandError
            If query fails or response cannot be parsed.

        Examples
        --------
        >>> with RigolDP800() as psu:
        ...     psu.channel = Channel.CH1
        ...     is_on = psu.output
        ...     print(f"Output: {'ON' if is_on else 'OFF'}")
        """
        self._ensure_connected()
        ch = self._active_channel.value

        try:
            instrument = self._get_instrument()
            response = instrument.query(f':OUTPut:STATe? {ch}')
            return response.strip().upper() in ['ON', '1']
        except pyvisa.Error as e:
            raise RigolCommandError(
                f"Failed to query output state on {ch}",
                pyvisa_error=e
            )

    @output.setter
    def output(self, value: Union[bool, str, int]) -> None:
        """
        Set output state for active channel.

        Parameters
        ----------
        value : bool or str or int
            Output state. Can be True/False, 'ON'/'OFF', or 1/0.

        Raises
        ------
        RigolValidationError
            If output state is invalid.
        RigolCommandError
            If command fails.

        Examples
        --------
        >>> with RigolDP800() as psu:
        ...     psu.channel = Channel.CH1
        ...     psu.output = True
        ...     psu.output = 'OFF'
        """
        self._ensure_connected()
        ch = self._active_channel.value

        if value in [True, 'ON', 'on', 1]:
            state_str = 'ON'
        elif value in [False, 'OFF', 'off', 0]:
            state_str = 'OFF'
        else:
            raise RigolValidationError(
                f"Invalid output state '{value}'. Must be True/False or 'ON'/'OFF'"
            )

        try:
            instrument = self._get_instrument()
            instrument.write(f':OUTPut {ch},{state_str}')
        except pyvisa.Error as e:
            raise RigolCommandError(
                f"Failed to set output to {state_str} on {ch}",
                pyvisa_error=e
            )

    def output_on(self, channel: Optional[Union[Channel, str, int]] = None) -> None:
        """
        Enable output for specified channel.

        Parameters
        ----------
        channel : Channel or str or int, optional
            Channel to enable. If None, enables active channel.

        Examples
        --------
        >>> with RigolDP800() as psu:
        ...     psu.output_on(Channel.CH1)
        ...     psu.output_on()
        """
        if channel is not None:
            old_channel = self._active_channel
            self.channel = channel
            self.output = True
            self._active_channel = old_channel
        else:
            self.output = True

    def output_off(self, channel: Optional[Union[Channel, str, int]] = None) -> None:
        """
        Disable output for specified channel.

        Parameters
        ----------
        channel : Channel or str or int, optional
            Channel to disable. If None, disables active channel.

        Examples
        --------
        >>> with RigolDP800() as psu:
        ...     psu.output_off(Channel.CH1)
        ...     psu.output_off()
        """
        if channel is not None:
            old_channel = self._active_channel
            self.channel = channel
            self.output = False
            self._active_channel = old_channel
        else:
            self.output = False

    def set_ovp(self, value: Union[float, int], channel: Optional[Union[Channel, str, int]] = None) -> None:
        """
        Set over-voltage protection level.

        Parameters
        ----------
        value : float or int
            Over-voltage protection level in volts.
        channel : Channel or str or int, optional
            Channel to configure. If None, uses active channel.

        Raises
        ------
        RigolCommandError
            If command fails.

        Examples
        --------
        >>> with RigolDP800() as psu:
        ...     psu.set_ovp(15.0, channel=Channel.CH1)
        ...     psu.set_ovp(6.0)
        """
        self._ensure_connected()

        if channel is None:
            ch = self._active_channel.value
        else:
            ch = self._parse_channel(channel)

        value = float(value)

        try:
            instrument = self._get_instrument()
            instrument.write(f':OUTPut:OVP:VALue {ch},{value}')
        except pyvisa.Error as e:
            raise RigolCommandError(
                f"Failed to set OVP to {value}V on {ch}",
                pyvisa_error=e
            )

    def set_ocp(self, value: Union[float, int], channel: Optional[Union[Channel, str, int]] = None) -> None:
        """
        Set over-current protection level.

        Parameters
        ----------
        value : float or int
            Over-current protection level in amperes.
        channel : Channel or str or int, optional
            Channel to configure. If None, uses active channel.

        Raises
        ------
        RigolCommandError
            If command fails.

        Examples
        --------
        >>> with RigolDP800() as psu:
        ...     psu.set_ocp(2.5, channel=Channel.CH1)
        ...     psu.set_ocp(1.2)
        """
        self._ensure_connected()

        if channel is None:
            ch = self._active_channel.value
        else:
            ch = self._parse_channel(channel)

        value = float(value)

        try:
            instrument = self._get_instrument()
            instrument.write(f':OUTPut:OCP:VALue {ch},{value}')
        except pyvisa.Error as e:
            raise RigolCommandError(
                f"Failed to set OCP to {value}A on {ch}",
                pyvisa_error=e
            )

    def enable_ovp(self, state: bool = True, channel: Optional[Union[Channel, str, int]] = None) -> None:
        """
        Enable or disable over-voltage protection.

        Parameters
        ----------
        state : bool, optional
            True to enable, False to disable. Default is True.
        channel : Channel or str or int, optional
            Channel to configure. If None, uses active channel.

        Raises
        ------
        RigolCommandError
            If command fails.

        Examples
        --------
        >>> with RigolDP800() as psu:
        ...     psu.enable_ovp(True, channel=Channel.CH1)
        ...     psu.enable_ovp(False)
        """
        self._ensure_connected()

        if channel is None:
            ch = self._active_channel.value
        else:
            ch = self._parse_channel(channel)

        state_str = 'ON' if state else 'OFF'

        try:
            instrument = self._get_instrument()
            instrument.write(f':OUTPut:OVP {ch},{state_str}')
        except pyvisa.Error as e:
            raise RigolCommandError(
                f"Failed to set OVP state to {state_str} on {ch}",
                pyvisa_error=e
            )

    def enable_ocp(self, state: bool = True, channel: Optional[Union[Channel, str, int]] = None) -> None:
        """
        Enable or disable over-current protection.

        Parameters
        ----------
        state : bool, optional
            True to enable, False to disable. Default is True.
        channel : Channel or str or int, optional
            Channel to configure. If None, uses active channel.

        Raises
        ------
        RigolCommandError
            If command fails.

        Examples
        --------
        >>> with RigolDP800() as psu:
        ...     psu.enable_ocp(True, channel=Channel.CH1)
        ...     psu.enable_ocp(False)
        """
        self._ensure_connected()

        if channel is None:
            ch = self._active_channel.value
        else:
            ch = self._parse_channel(channel)

        state_str = 'ON' if state else 'OFF'

        try:
            instrument = self._get_instrument()
            instrument.write(f':OUTPut:OCP {ch},{state_str}')
        except pyvisa.Error as e:
            raise RigolCommandError(
                f"Failed to set OCP state to {state_str} on {ch}",
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
        RigolCommandError
            If communication fails.

        Examples
        --------
        >>> psu = RigolDP800()
        >>> psu.connect()
        >>> if psu.check_connection():
        ...     print("Instrument is responding")
        """
        self._ensure_connected()
        try:
            instrument = self._get_instrument()
            idn = instrument.query('*IDN?')
            print(f"Instrument responding: {idn.strip()}")
            return True
        except pyvisa.Error as e:
            raise RigolCommandError(
                "Communication error during connection check",
                pyvisa_error=e
            )

    def reset(self) -> None:
        """
        Reset instrument to factory defaults.

        Raises
        ------
        RigolCommandError
            If reset command fails.

        Examples
        --------
        >>> with RigolDP800() as psu:
        ...     psu.reset()
        """
        self._ensure_connected()
        try:
            instrument = self._get_instrument()
            instrument.write('*RST')
        except pyvisa.Error as e:
            raise RigolCommandError(
                "Reset command failed",
                pyvisa_error=e
            )

    def clear_status(self) -> None:
        """
        Clear status registers.

        Raises
        ------
        RigolCommandError
            If clear command fails.

        Examples
        --------
        >>> with RigolDP800() as psu:
        ...     psu.clear_status()
        """
        self._ensure_connected()
        try:
            instrument = self._get_instrument()
            instrument.write('*CLS')
        except pyvisa.Error as e:
            raise RigolCommandError(
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
        RigolCommandError
            If self-test command fails or response cannot be parsed.

        Examples
        --------
        >>> with RigolDP800() as psu:
        ...     if psu.self_test():
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
            raise RigolCommandError(
                f"Could not parse self-test result. Response: {response}"
            )
        except pyvisa.Error as e:
            raise RigolCommandError(
                "Self-test command failed",
                pyvisa_error=e
            )
