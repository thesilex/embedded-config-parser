# Embedded Peripheral Configuration Parser

Clean, simple YAML-based configuration parser for embedded peripherals.

## Features

- 🔧 **YAML-based configuration** - Clean, readable peripheral setup
- 📋 **Schema validation** - MCU-specific constraint checking  
- 🔍 **Pin conflict detection** - Automatic pin usage analysis
- 📊 **Rich reporting** - Beautiful terminal output with tables
- 🎯 **Type safety** - Full Python type hints and dataclass support
- 🚀 **Extensible** - Easy to add new MCU families and peripherals

## Installation

```bash
python install.py
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate     # Windows
```

## Quick Start

```bash
# Parse and validate configuration
python app.py .\examples\advanced_board.yaml

# Show detailed summary
python app.py .\examples\advanced_board.yaml --summary

# Validation only
python app.py .\examples\advanced_board.yaml --validate

# Export to JSON
python app.py .\examples\advanced_board.yaml --output config.json

# Verbose output with pin usage
python app.py .\examples\advanced_board.yaml --verbose
```

## Example Configuration

Here's what a typical board config looks like:

```yaml
board:
  name: "Custom STM32F4 Board"
  mcu: "STM32F407VGT6"
  clock_frequency: 168000000
  voltage: 3.3

gpio:
  - pin: "PD12"
    direction: "output"
    speed: "high"
    description: "Status LED Green"
    
  - pin: "PA0"
    direction: "input"
    pull: "down"
    description: "User Button"

uart:
  uart1:
    enabled: true
    baudrate: 115200
    tx_pin: "PA9"
    rx_pin: "PA10"
    description: "Debug Console"

i2c:
  i2c1:
    enabled: true
    speed: 400000
    scl_pin: "PB6"
    sda_pin: "PB7"
    devices:
      - name: "temp_sensor"
        address: 0x48
        device_type: "LM75"
        
spi:
  spi1:
    enabled: true
    mode: 0
    speed: 10000000
    sck_pin: "PA5"
    miso_pin: "PA6"
    mosi_pin: "PA7"
    cs_pins: ["PA4"]

timers:
  timer2:
    enabled: true
    mode: "pwm"
    prescaler: 84
    period: 20000
    duty_cycle: 75
    output_pin: "PA8"
```

## Command Line Options

```bash
python app.py <config_file> [OPTIONS]

Options:
  --validate     Validate configuration only
  --parse        Parse and validate (explicit, same as default)
  --output, -o   Export to JSON file
  --summary, -s  Show configuration summary
  --verbose      Verbose output with detailed information
  --help         Show help message
```

## What gets validated

### Pin conflicts
The tool automatically catches when you accidentally use the same pin twice:

```
❌ Pin PA9 used by both UART uart1 TX and GPIO (output)
⚠️  SPI spi1: No CS pins configured
ℹ️  Detected MCU package: LQFP100 (100 pins)
```

### Schema based validation
- Pin availability for your specific MCU package
- Peripheral count limits (can't use more UARTs than the chip has)
- Clock frequency ranges
- I2C address conflicts

## Architecture

```
├── app.py          # Main CLI interface
├── parser.py       # YAML parsing and data models
├── validator.py    # Schema-driven validation system
├── examples/       # Example YAML files for MCU based boards
|   └── advanced_board.yaml
|   └── simple_board.yaml
|   └── test_invalid_syntax.yaml
|   └── test_pin_conflict.yaml
└── schemas/        # JSON schemas for MCU families and peripherals
    └── mcu/
        └── STM32F407Vxxx.json
    └── peripherals/
        └── lm75.json
        └── mma8451q.json
```

## Supported MCU Families

- **STM32F407V series** (VGT6, VET6, VCT6) - 100-pin LQFP package
- The schema system makes it straightforward to add other MCU families.

## Adding New MCU Support

1. Create JSON schema in `schemas/mcu/`
2. Define package constraints and peripheral limits
3. Add MCU patterns for automatic detection

Example schema structure:
```json
{
  "mcu_patterns": ["STM32F407V.*"],
  "package_constraints": {
    "gpio_ports": {"A": {"max": 15}, "B": {"max": 15}},
    "peripheral_limits": {"uart_count": 6, "i2c_count": 3}
  }
}
```

## Output Formats

### JSON Export

Converts your YAML config to JSON for integration with other tools:

```json
{
  "board": {
    "name": "Custom STM32F4 Board",
    "mcu": "STM32F407VGT6",
    "clock_frequency": 168000000
  },
  "gpio": [{"pin": "PD12", "direction": "output"}]
}
```

### Rich Terminal Tables
- Board configuration overview
- GPIO pin assignments  
- UART/I2C/SPI peripheral summary
- Timer configurations with PWM details
- Pin usage summary with conflict detection

## Requirements

- Python 3.8+
- PyYAML
- Rich (terminal formatting)
- JSONSchema (validation)
- Click (CLI interface)

## Design Decisions & Extensibility

### Why YAML + JSON Schema?

I went with YAML + JSON Schema because:

**YAML makes sense for config files** - it's readable, supports comments, and handles the hierarchical nature of peripheral configs well. Much better than trying to maintain C header files by hand.

**JSON Schema handles validation declaratively** - rather than hardcoding validation rules, they're defined in data files. This makes it easy to add new MCU families without touching the Python code.

## Extending the system

The architecture is designed to be extensible:

### New peripheral types
Add a dataclass and corresponding schema:

```python
@dataclass
class CANConfig:
    name: str
    enabled: bool
    bitrate: int = 500000
    tx_pin: str = ""
    rx_pin: str = ""
```

### Smart defaults
JSON schemas can define reasonable defaults:

```json
{
  "properties": {
    "baudrate": {
      "type": "integer",
      "default": 115200,
      "enum": [9600, 19200, 38400, 57600, 115200]
    }
  }
}
```

### Configuration templates
YAML supports inheritance for reusable configs:

```yaml
# Base template
uart: &debug_uart
  uart1:
    enabled: true
    baudrate: 115200
    description: "Debug Console"

# Specific board inherits it
uart:
  <<: *debug_uart
```

The parsed configuration can also drive **code generation** - generate C headers, device tree files, or whatever format your toolchain needs.

## Future improvements

- Support for more MCU families (ESP32, Nordic, etc.)
- Code generation for different embedded frameworks
- Configuration templates and inheritance
- Better error messages with fix suggestions
- Integration with popular embedded IDEs
- Testing suite - This needs proper unit tests and integration tests. Right now I've been testing manually with the example configs