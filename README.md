# inst-ctrl

Python interfaces for controlling Fluke digital multimeters and Siglent arbitrary waveform generators via PyVISA.

## Overview

This package provides high-level Python interfaces for instrument control:

- **Fluke 45** and **Fluke 8845A/8846A** digital multimeters
- **Siglent SDG2042X** arbitrary waveform generator

All instruments support multiple connection methods (GPIB, USB, Ethernet, RS-232) and provide type-safe, well-documented APIs with comprehensive error handling.

## Installation

### Requirements

- Python >= 3.13
- NI-VISA or PyVISA-py backend
- uv package manager (recommended)

### Install with uv

```bash
uv pip install -e .
```

### Install with pip

```bash
pip install -e .
```

### Optional Dependencies

For pint unit support with Siglent instruments:

```bash
uv pip install -e ".[units]"
```

## Quick Start

### Fluke 45 Digital Multimeter

```python
from inst_ctrl import Fluke45, Func, Rate

# Connect via GPIB
with Fluke45(gpib_address=3) as dmm:
    dmm.primary_function = Func.VDC
    dmm.rate = Rate.FAST
    voltage = dmm.primary()
    print(f"Voltage: {voltage} V")
```

### Fluke 8845A/8846A Digital Multimeter

```python
from inst_ctrl import Fluke88, Func

# Connect via Ethernet
with Fluke88(ip_address='192.168.1.100') as dmm:
    dmm.primary_function = Func.OHMS
    resistance = dmm.primary()
    print(f"Resistance: {resistance} Ohms")
```

### Siglent SDG2042X Waveform Generator

```python
from inst_ctrl import SiglentSDG2042X

# Auto-discover and connect
with SiglentSDG2042X() as sig_gen:
    sig_gen.channel = 1
    sig_gen.waveform_type = 'SINE'
    sig_gen.frequency = 1000
    sig_gen.amplitude = 1.0
    sig_gen.output_state = True
```

## Connection Methods

### Fluke Instruments

**GPIB Connection:**
```python
dmm = Fluke45(gpib_address=3)
dmm.connect()
```

**Ethernet Connection (Fluke 88xx only):**
```python
dmm = Fluke88(ip_address='192.168.1.100')
dmm.connect()
```

**Serial Connection:**
```python
# Windows
dmm = Fluke45(serial_port='COM1')

# Linux/Mac
dmm = Fluke45(serial_port='/dev/ttyUSB0')
dmm.connect()
```

**Direct Resource Name:**
```python
dmm = Fluke45(resource_name='GPIB0::3::INSTR')
dmm.connect()
```

**Auto-Discovery:**
```python
# Automatically finds first Fluke instrument on GPIB bus
dmm = Fluke45()
dmm.connect()
```

### Siglent Instruments

**Auto-Discovery:**
```python
# Automatically finds first Siglent SDG instrument
sig_gen = SiglentSDG2042X()
sig_gen.connect()
```

**Direct Resource Name:**
```python
sig_gen = SiglentSDG2042X(resource_name='USB0::0x0483::0x7540::SDG2042X12345678::INSTR')
sig_gen.connect()
```

## Fluke 45 Examples

### Basic Voltage Measurement

```python
from inst_ctrl import Fluke45, Func

with Fluke45(gpib_address=3) as dmm:
    dmm.primary_function = Func.VDC
    dmm.auto_range = True
    voltage = dmm.primary()
    print(f"DC Voltage: {voltage} V")
```

### Dual Display Measurement

```python
from inst_ctrl import Fluke45, Func, Func2

with Fluke45() as dmm:
    dmm.primary_function = Func.VDC
    dmm.secondary_function = Func2.FREQ
    voltage, frequency = dmm.both()
    print(f"Voltage: {voltage} V, Frequency: {frequency} Hz")
```

### Manual Range and Rate Control

```python
from inst_ctrl import Fluke45, Func, Rate

with Fluke45() as dmm:
    dmm.primary_function = Func.OHMS
    dmm.auto_range = False
    dmm.range = 3
    dmm.rate = Rate.SLOW
    resistance = dmm.primary()
    print(f"Resistance: {resistance} Ohms")
```

### Relative Measurement Mode

```python
with Fluke45() as dmm:
    dmm.primary_function = Func.VDC
    dmm.relative_mode = True
    dmm.set_relative_offset(1.0)
    relative_voltage = dmm.primary()
    print(f"Relative to 1.0V: {relative_voltage} V")
```

### Compare Mode

```python
with Fluke45() as dmm:
    dmm.primary_function = Func.VDC
    dmm.compare_mode = True
    dmm.compare_hi = 10.0
    dmm.compare_lo = 5.0
    result = dmm.compare_result
    print(f"Compare result: {result}")  # 'HI', 'LO', or 'PASS'
```

### Trigger Control

```python
from inst_ctrl import Fluke45, TriggerMode

with Fluke45() as dmm:
    dmm.trigger_mode = TriggerMode.EXTERNAL
    dmm.trigger()
    measurement = dmm.primary()
```

## Fluke 8845A/8846A Examples

### Basic Measurement

```python
from inst_ctrl import Fluke88, Func

with Fluke88(ip_address='192.168.1.100') as dmm:
    dmm.primary_function = Func.VDC
    dmm.auto_range = True
    voltage = dmm.primary()
    print(f"Voltage: {voltage} V")
```

### Measurement Rate Control

```python
from inst_ctrl import Fluke88, Func, Rate

with Fluke88(gpib_address=1) as dmm:
    dmm.primary_function = Func.OHMS
    dmm.rate = Rate.FAST
    resistance = dmm.primary()
```

## Siglent SDG2042X Examples

### Basic Sine Wave Generation

```python
from inst_ctrl import SiglentSDG2042X

with SiglentSDG2042X() as sig_gen:
    sig_gen.channel = 1
    sig_gen.waveform_type = 'SINE'
    sig_gen.frequency = 1000
    sig_gen.amplitude = 2.0
    sig_gen.offset = 0.5
    sig_gen.output_state = True
```

### Configure Waveform with All Parameters

```python
with SiglentSDG2042X() as sig_gen:
    sig_gen.channel = 1
    sig_gen.configure_waveform(
        waveform_type='SINE',
        frequency=1000,
        amplitude=2.0,
        offset=0.5,
        phase=45
    )
    sig_gen.output_state = True
```

### Square Wave with Duty Cycle

```python
with SiglentSDG2042X() as sig_gen:
    sig_gen.channel = 1
    sig_gen.waveform_type = 'SQUARE'
    sig_gen.frequency = 10000
    sig_gen.amplitude = 3.3
    sig_gen.set_duty_cycle(25.0)
    sig_gen.output_state = True
```

### Pulse Waveform

```python
with SiglentSDG2042X() as sig_gen:
    sig_gen.channel = 1
    sig_gen.waveform_type = 'PULSE'
    sig_gen.frequency = 1000
    sig_gen.amplitude = 5.0
    sig_gen.set_pulse_width(1e-3)
    sig_gen.set_rise_time(1e-6)
    sig_gen.set_fall_time(1e-6)
    sig_gen.output_state = True
```

### Ramp Waveform with Symmetry

```python
with SiglentSDG2042X() as sig_gen:
    sig_gen.channel = 1
    sig_gen.waveform_type = 'RAMP'
    sig_gen.frequency = 500
    sig_gen.amplitude = 2.0
    sig_gen.set_symmetry(75.0)
    sig_gen.output_state = True
```

### Using Pint Units

```python
from inst_ctrl import SiglentSDG2042X

sig_gen = SiglentSDG2042X(unit_mode='pint')
sig_gen.connect()
sig_gen.channel = 1
sig_gen.frequency = 1000

freq = sig_gen.frequency
print(f"Frequency: {freq}")  # Prints as pint Quantity
```

### Load Impedance Configuration

```python
with SiglentSDG2042X() as sig_gen:
    sig_gen.channel = 1
    sig_gen.load_impedance = 'HiZ'
    sig_gen.load_impedance = 50
```

### Arbitrary Waveform Selection

```python
with SiglentSDG2042X() as sig_gen:
    waveforms = sig_gen.list_waveforms()
    for wv in waveforms:
        print(f"Index {wv['index']}: {wv['name']}")

    sig_gen.channel = 1
    sig_gen.waveform_type = 'ARB'
    sig_gen.select_arbitrary_waveform(index=1)
```

## API Reference

### Fluke 45

#### Connection

- `Fluke45(gpib_address=None, serial_port=None, resource_name=None, timeout=5000)`
- `connect()` - Establish connection
- `disconnect()` - Close connection
- `check_connection()` - Verify communication

#### Measurement Functions

- `primary_function` - Set/get primary measurement function (Func enum)
- `secondary_function` - Set/get secondary measurement function (Func2 enum, Fluke 45 only)
- `primary()` - Trigger and read primary measurement
- `secondary()` - Trigger and read secondary measurement (Fluke 45 only)
- `both()` - Trigger and read both displays (Fluke 45 only)
- `primary_value` - Read current primary value without triggering
- `secondary_value` - Read current secondary value without triggering

#### Configuration

- `auto_range` - Enable/disable auto range
- `range` - Set manual range (1-7)
- `rate` - Set measurement rate (Rate enum: SLOW, MEDIUM, FAST)
- `trigger_mode` - Set trigger mode (TriggerMode enum)
- `trigger()` - Send trigger command

#### Special Modes

- `relative_mode` - Enable/disable relative measurement
- `set_relative_offset(offset)` - Set relative offset value
- `db_mode` - Enable/disable dB measurement
- `set_db_reference(impedance)` - Set dB reference impedance
- `hold_mode` - Enable/disable hold mode
- `min_max_mode(mode)` - Set min/max tracking mode
- `compare_mode` - Enable/disable compare mode
- `compare_hi` - Set compare high limit
- `compare_lo` - Set compare low limit
- `compare_result` - Get compare result

#### System Commands

- `reset()` - Reset instrument to defaults
- `clear_status()` - Clear status registers
- `self_test()` - Execute self-test
- `read_status_byte()` - Read status byte
- `read_event_status()` - Read event status register

### Fluke 8845A/8846A

Fluke88 inherits from Fluke45 and provides the same interface. Key differences:

- Supports Ethernet connections via `ip_address` parameter
- Uses SCPI commands internally
- Does not support secondary display (Func2)
- `secondary()` and `both()` methods raise exceptions

### Siglent SDG2042X

#### Connection

- `SiglentSDG2042X(resource_name=None, timeout=5000, unit_mode='tuple')`
- `connect()` - Establish connection
- `disconnect()` - Close connection
- `check_connection()` - Verify communication

#### Channel Control

- `channel` - Set active channel (1 or 2)

#### Waveform Parameters

- `waveform_type` - Set/get waveform type ('SINE', 'SQUARE', 'RAMP', 'PULSE', 'NOISE', 'ARB', 'DC', 'PRBS', 'IQ')
- `frequency` - Set/get frequency
- `amplitude` - Set/get amplitude
- `offset` - Set/get DC offset
- `phase` - Set/get phase

#### Waveform-Specific Parameters

- `get_duty_cycle()` / `set_duty_cycle(duty)` - For SQUARE/PULSE waveforms
- `get_symmetry()` / `set_symmetry(symmetry)` - For RAMP waveforms
- `get_pulse_width()` / `set_pulse_width(width)` - For PULSE waveforms
- `get_rise_time()` / `set_rise_time(rise_time)` - For PULSE waveforms
- `get_fall_time()` / `set_fall_time(fall_time)` - For PULSE waveforms

#### Output Control

- `output_state` - Enable/disable output
- `load_impedance` - Set/get load impedance ('HiZ' or numeric value)

#### Convenience Methods

- `configure_waveform(waveform_type, frequency, amplitude, offset=0, phase=0)` - Configure all parameters at once
- `list_waveforms()` - List available arbitrary waveforms
- `select_arbitrary_waveform(index=None, name=None)` - Select arbitrary waveform
- `get_all_parameters()` - Get raw parameter string

#### Parameter Limits

- `limits` - ParameterLimits object for validation
  - `limits.freq_min`, `limits.freq_max`
  - `limits.amp_min`, `limits.amp_max`
  - `limits.offset_min`, `limits.offset_max`
  - `limits.phase_min`, `limits.phase_max`
  - `limits.reset_to_defaults()`

## Enums and Constants

### Fluke Enums

- `Func` - Primary measurement functions: VDC, VAC, VACDC, ADC, AAC, OHMS, FREQ, DIODE
- `Func2` - Secondary measurement functions (Fluke 45 only): VDC, VAC, ADC, AAC, OHMS, FREQ, DIODE, CLEAR
- `Rate` - Measurement rates: SLOW, MEDIUM, FAST
- `TriggerMode` - Trigger modes: INTERNAL, EXTERNAL, EXTERNAL_NO_DELAY, EXTERNAL_DELAY, EXTERNAL_REAR_NO_DELAY, EXTERNAL_REAR_DELAY

### Siglent Waveform Types

- 'SINE', 'SQUARE', 'RAMP', 'PULSE', 'NOISE', 'ARB', 'DC', 'PRBS', 'IQ'

## Error Handling

All instruments raise specific exception types:

### Fluke Exceptions

- `FlukeError` - Base exception
- `FlukeConnectionError` - Connection failures
- `FlukeValidationError` - Invalid parameter values
- `FlukeCommandError` - Command execution failures

### Siglent Exceptions

- `SiglentError` - Base exception
- `SiglentConnectionError` - Connection failures
- `SiglentValidationError` - Invalid parameter values
- `SiglentCommandError` - Command execution failures

### Example Error Handling

```python
from inst_ctrl import Fluke45, FlukeConnectionError, FlukeValidationError

try:
    dmm = Fluke45(gpib_address=3)
    dmm.connect()
    dmm.primary_function = 'INVALID'
except FlukeConnectionError as e:
    print(f"Connection failed: {e}")
except FlukeValidationError as e:
    print(f"Invalid parameter: {e}")
```

## Context Manager Usage

All instruments support context manager syntax for automatic connection management:

```python
from inst_ctrl import Fluke45, SiglentSDG2042X

# Automatically connects on entry, disconnects on exit
with Fluke45(gpib_address=3) as dmm:
    voltage = dmm.primary()

with SiglentSDG2042X() as sig_gen:
    sig_gen.frequency = 1000
    sig_gen.output_state = True
```

## Type Safety

All functions are fully typed with type hints. The package uses strict typing practices:

- Functions must have complete type annotations
- Variables are typed only when ambiguous
- Type narrowing ensures safe instrument access after connection verification

## Requirements

- Python >= 3.13
- pyvisa >= 1.16.1
- NI-VISA or PyVISA-py backend
- pint >= 0.25.2 (optional, for unit support)

## Development

### Project Structure

```
inst_ctrl/
├── src/
│   └── inst_ctrl/
│       ├── __init__.py
│       ├── fluke.py      # Fluke 45 and 8845A/8846A interfaces
│       └── siglent.py    # Siglent SDG2042X interface
├── pyproject.toml
└── README.md
```

### Building

```bash
uv build
```

## License

[Add your license information here]

## Contributing

[Add contribution guidelines here]
