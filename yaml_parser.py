#!/usr/bin/env python3
"""
Embedded Peripheral Configuration Parser - YAML Edition
Clean, simple, and MCU-friendly YAML based configuration parsing

Author: Embedded Config System
Description: Parses YAML configuration files for embedded peripheral setup
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple
from dataclasses import dataclass, asdict, field
import yaml
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint
import jsonschema

# Console for rich output
console = Console()

@dataclass
class GPIOConfig:
    """GPIO pin configuration"""
    pin: str
    direction: str  # "input" or "output"
    pull: str = "none"  # "none", "up", "down"
    speed: str = "medium"  # "low", "medium", "high", "very-high"
    initial_state: str = "low"  # "low", "high"
    description: str = ""
    
    def __post_init__(self):
        """Validate GPIO configuration after initialization"""
        valid_directions = ["input", "output"]
        valid_pulls = ["none", "up", "down"]
        valid_speeds = ["low", "medium", "high", "very-high"]
        valid_states = ["low", "high"]
        
        if self.direction not in valid_directions:
            raise ValueError(f"Invalid direction '{self.direction}'. Must be one of: {valid_directions}")
        if self.pull not in valid_pulls:
            raise ValueError(f"Invalid pull '{self.pull}'. Must be one of: {valid_pulls}")
        if self.speed not in valid_speeds:
            raise ValueError(f"Invalid speed '{self.speed}'. Must be one of: {valid_speeds}")
        if self.initial_state not in valid_states:
            raise ValueError(f"Invalid initial_state '{self.initial_state}'. Must be one of: {valid_states}")

@dataclass
class UARTConfig:
    """UART peripheral configuration"""
    name: str
    enabled: bool
    baudrate: int
    data_bits: int = 8
    stop_bits: int = 1
    parity: str = "none"  # "none", "even", "odd"
    flow_control: str = "none"  # "none", "rts-cts", "xon-xoff"
    tx_pin: str = ""
    rx_pin: str = ""
    description: str = ""
    
    def __post_init__(self):
        """Validate UART configuration"""
        valid_baudrates = [9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600]
        valid_data_bits = [7, 8, 9]
        valid_stop_bits = [1, 2]
        valid_parity = ["none", "even", "odd"]
        valid_flow_control = ["none", "rts-cts", "xon-xoff"]
        
        if self.baudrate not in valid_baudrates:
            console.print(f"[yellow]Warning: Non-standard baudrate {self.baudrate}[/yellow]")
        if self.data_bits not in valid_data_bits:
            raise ValueError(f"Invalid data_bits '{self.data_bits}'. Must be one of: {valid_data_bits}")
        if self.stop_bits not in valid_stop_bits:
            raise ValueError(f"Invalid stop_bits '{self.stop_bits}'. Must be one of: {valid_stop_bits}")
        if self.parity not in valid_parity:
            raise ValueError(f"Invalid parity '{self.parity}'. Must be one of: {valid_parity}")
        if self.flow_control not in valid_flow_control:
            raise ValueError(f"Invalid flow_control '{self.flow_control}'. Must be one of: {valid_flow_control}")

@dataclass
class I2CDevice:
    """I2C device configuration"""
    name: str
    address: int
    device_type: str
    description: str = ""
    
    def __post_init__(self):
        """Validate I2C device configuration"""
        if not (8 <= self.address <= 119):  # 0x08 to 0x77 in decimal
            raise ValueError(f"Invalid I2C address {self.address}. Must be between 8 and 119 (0x08-0x77)")

@dataclass
class I2CConfig:
    """I2C peripheral configuration"""
    name: str
    enabled: bool
    speed: int  # Hz
    scl_pin: str
    sda_pin: str
    pull_up: bool = True
    description: str = ""
    devices: List[I2CDevice] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate I2C configuration"""
        valid_speeds = [100000, 400000, 1000000, 3400000]  # Standard, Fast, Fast+, High-speed
        if self.speed not in valid_speeds:
            console.print(f"[yellow]Warning: Non-standard I2C speed {self.speed} Hz[/yellow]")

@dataclass
class TimerConfig:
    """Timer peripheral configuration"""
    name: str
    enabled: bool
    prescaler: int
    period: int
    mode: str = "periodic"  # "periodic", "pwm", "input-capture"
    auto_reload: bool = True
    channel: Optional[int] = None
    duty_cycle: Optional[int] = None  # For PWM mode (0-100%)
    output_pin: Optional[str] = None  # For PWM mode
    description: str = ""
    
    def __post_init__(self):
        """Validate timer configuration"""
        valid_modes = ["periodic", "pwm", "input-capture"]
        if self.mode not in valid_modes:
            raise ValueError(f"Invalid mode '{self.mode}'. Must be one of: {valid_modes}")
        
        if self.mode == "pwm":
            if self.duty_cycle is None or not (0 <= self.duty_cycle <= 100):
                raise ValueError("PWM mode requires duty_cycle between 0 and 100")
            if not self.output_pin:
                raise ValueError("PWM mode requires output_pin")

@dataclass
class SPIConfig:
    """SPI peripheral configuration"""
    name: str
    enabled: bool
    mode: int  # 0, 1, 2, 3
    speed: int  # Hz
    data_bits: int = 8
    bit_order: str = "msb"  # "msb", "lsb"
    sck_pin: str = ""
    miso_pin: str = ""
    mosi_pin: str = ""
    cs_pins: List[str] = field(default_factory=list)
    description: str = ""
    
    def __post_init__(self):
        """Validate SPI configuration"""
        valid_modes = [0, 1, 2, 3]
        valid_data_bits = [8, 16]
        valid_bit_orders = ["msb", "lsb"]
        
        if self.mode not in valid_modes:
            raise ValueError(f"Invalid mode '{self.mode}'. Must be one of: {valid_modes}")
        if self.data_bits not in valid_data_bits:
            raise ValueError(f"Invalid data_bits '{self.data_bits}'. Must be one of: {valid_data_bits}")
        if self.bit_order not in valid_bit_orders:
            raise ValueError(f"Invalid bit_order '{self.bit_order}'. Must be one of: {valid_bit_orders}")

@dataclass
class BoardConfig:
    """Board configuration"""
    name: str
    mcu: str
    clock_frequency: int
    voltage: float = 3.3
    description: str = ""
    
    def __post_init__(self):
        """Validate board configuration"""
        if self.clock_frequency <= 0:
            raise ValueError("Clock frequency must be positive")
        if not (1.8 <= self.voltage <= 5.5):
            raise ValueError("Voltage must be between 1.8V and 5.5V")

@dataclass
class EmbeddedConfig:
    """Complete embedded system configuration"""
    board: BoardConfig
    gpio: List[GPIOConfig] = field(default_factory=list)
    uart: Dict[str, UARTConfig] = field(default_factory=dict)
    i2c: Dict[str, I2CConfig] = field(default_factory=dict)
    timers: Dict[str, TimerConfig] = field(default_factory=dict)
    spi: Dict[str, SPIConfig] = field(default_factory=dict)

class ConfigurationError(Exception):
    """Custom exception for configuration errors"""
    pass

class YAMLConfigParser:
    """YAML-based embedded peripheral configuration parser"""
    
    def __init__(self):
        self.config: Optional[EmbeddedConfig] = None
        self.validation_errors: List[str] = []
        self.validation_warnings: List[str] = []
    
    def load_config(self, config_file: Union[str, Path]) -> EmbeddedConfig:
        """Load and parse YAML configuration file"""
        try:
            with open(config_file, 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file)
                return self._parse_config_data(data)
        except FileNotFoundError:
            raise ConfigurationError(f"Configuration file not found: {config_file}")
        except yaml.YAMLError as e:
            raise ConfigurationError(f"YAML parsing error: {e}")
        except Exception as e:
            raise ConfigurationError(f"Error loading configuration: {e}")
    
    def _parse_config_data(self, data: Dict[str, Any]) -> EmbeddedConfig:
        """Parse configuration data into structured objects"""
        try:
            # Parse board configuration
            if 'board' not in data:
                raise ConfigurationError("Board configuration is required")
            
            board_data = data['board']
            board = BoardConfig(
                name=board_data.get('name', ''),
                mcu=board_data.get('mcu', ''),
                clock_frequency=board_data.get('clock_frequency', 0),
                voltage=board_data.get('voltage', 3.3),
                description=board_data.get('description', '')
            )
            
            # Parse GPIO configurations
            gpio_configs = []
            for gpio_data in data.get('gpio', []):
                gpio = GPIOConfig(
                    pin=gpio_data.get('pin', ''),
                    direction=gpio_data.get('direction', ''),
                    pull=gpio_data.get('pull', 'none'),
                    speed=gpio_data.get('speed', 'medium'),
                    initial_state=gpio_data.get('initial_state', 'low'),
                    description=gpio_data.get('description', '')
                )
                gpio_configs.append(gpio)
            
            # Parse UART configurations
            uart_configs = {}
            for uart_name, uart_data in data.get('uart', {}).items():
                uart = UARTConfig(
                    name=uart_name,
                    enabled=uart_data.get('enabled', False),
                    baudrate=uart_data.get('baudrate', 115200),
                    data_bits=uart_data.get('data_bits', 8),
                    stop_bits=uart_data.get('stop_bits', 1),
                    parity=uart_data.get('parity', 'none'),
                    flow_control=uart_data.get('flow_control', 'none'),
                    tx_pin=uart_data.get('tx_pin', ''),
                    rx_pin=uart_data.get('rx_pin', ''),
                    description=uart_data.get('description', '')
                )
                uart_configs[uart_name] = uart
            
            # Parse I2C configurations
            i2c_configs = {}
            for i2c_name, i2c_data in data.get('i2c', {}).items():
                # Parse devices
                devices = []
                for device_data in i2c_data.get('devices', []):
                    device = I2CDevice(
                        name=device_data.get('name', ''),
                        address=device_data.get('address', 0),
                        device_type=device_data.get('type', ''),  # YAML uses 'type', class uses 'device_type'
                        description=device_data.get('description', '')
                    )
                    devices.append(device)
                
                i2c = I2CConfig(
                    name=i2c_name,
                    enabled=i2c_data.get('enabled', False),
                    speed=i2c_data.get('speed', 100000),
                    scl_pin=i2c_data.get('scl_pin', ''),
                    sda_pin=i2c_data.get('sda_pin', ''),
                    pull_up=i2c_data.get('pull_up', True),
                    description=i2c_data.get('description', ''),
                    devices=devices
                )
                i2c_configs[i2c_name] = i2c
            
            # Parse Timer configurations
            timer_configs = {}
            for timer_name, timer_data in data.get('timers', {}).items():
                timer = TimerConfig(
                    name=timer_name,
                    enabled=timer_data.get('enabled', False),
                    prescaler=timer_data.get('prescaler', 1),
                    period=timer_data.get('period', 1000),
                    mode=timer_data.get('mode', 'periodic'),
                    auto_reload=timer_data.get('auto_reload', True),
                    channel=timer_data.get('channel'),
                    duty_cycle=timer_data.get('duty_cycle'),
                    output_pin=timer_data.get('output_pin'),
                    description=timer_data.get('description', '')
                )
                timer_configs[timer_name] = timer
            
            # Parse SPI configurations
            spi_configs = {}
            for spi_name, spi_data in data.get('spi', {}).items():
                spi = SPIConfig(
                    name=spi_name,
                    enabled=spi_data.get('enabled', False),
                    mode=spi_data.get('mode', 0),
                    speed=spi_data.get('speed', 1000000),
                    data_bits=spi_data.get('data_bits', 8),
                    bit_order=spi_data.get('bit_order', 'msb'),
                    sck_pin=spi_data.get('sck_pin', ''),
                    miso_pin=spi_data.get('miso_pin', ''),
                    mosi_pin=spi_data.get('mosi_pin', ''),
                    cs_pins=spi_data.get('cs_pins', []),
                    description=spi_data.get('description', '')
                )
                spi_configs[spi_name] = spi
            
            # Create final configuration
            self.config = EmbeddedConfig(
                board=board,
                gpio=gpio_configs,
                uart=uart_configs,
                i2c=i2c_configs,
                timers=timer_configs,
                spi=spi_configs
            )
            
            return self.config
            
        except Exception as e:
            raise ConfigurationError(f"Error parsing configuration data: {e}")
    
    def validate_pin_format(self, pin: str) -> bool:
        """Validate pin format (e.g., PA0, PB15)"""
        import re
        pattern = r'^P[A-Z]\d{1,2}$'
        return bool(re.match(pattern, pin))
    
    def validate_with_schemas(self, config_data: Dict[str, Any]) -> List[str]:
        """Validate configuration using JSON schemas"""
        errors = []
        
        # Get MCU type
        mcu_type = config_data.get('board', {}).get('mcu', '').lower()
        
        # MCU-specific validation
        if mcu_type:
            mcu_errors = self._validate_mcu_schema(config_data, mcu_type)
            errors.extend(mcu_errors)
        
        # Peripheral validation
        peripheral_errors = self._validate_peripheral_schemas(config_data)
        errors.extend(peripheral_errors)
        
        return errors
    
    def _validate_mcu_schema(self, config_data: Dict[str, Any], mcu_type: str) -> List[str]:
        """Validate against MCU-specific schema"""
        schema_file = Path("schemas/mcu") / f"{mcu_type}.json"
        
        if not schema_file.exists():
            # Try to match by family (e.g., stm32f407vgt6 -> stm32f4)
            family_name = self._extract_mcu_family(mcu_type)
            schema_file = Path("schemas/mcu") / f"{family_name}.json"
        
        if schema_file.exists():
            try:
                with open(schema_file) as f:
                    schema = json.load(f)
                
                jsonschema.validate(config_data, schema)
                return []
                
            except jsonschema.ValidationError as e:
                # More detailed error reporting
                error_path = " -> ".join(str(p) for p in e.absolute_path) if e.absolute_path else "root"
                return [f"MCU validation ({mcu_type}) at '{error_path}': {e.message}"]
            except Exception as e:
                return [f"Schema loading error for {mcu_type}: {e}"]
        
        return []  # No schema found, skip MCU-specific validation
    
    def _validate_peripheral_schemas(self, config_data: Dict[str, Any]) -> List[str]:
        """Validate I2C devices against peripheral schemas"""
        errors = []
        
        for i2c_name, i2c_config in config_data.get('i2c', {}).items():
            if not i2c_config.get('enabled', False):
                continue
                
            for device in i2c_config.get('devices', []):
                device_type = device.get('type', '').lower()  # YAML'da 'type' field'ı kullanılıyor
                if device_type:
                    device_errors = self._validate_device_schema(device, device_type)
                    errors.extend(device_errors)
        
        return errors
    
    def _validate_device_schema(self, device: Dict[str, Any], device_type: str) -> List[str]:
        """Validate device against peripheral schema"""
        schema_file = Path("schemas/peripherals") / f"{device_type}.json"
        
        if schema_file.exists():
            try:
                with open(schema_file) as f:
                    schema = json.load(f)
                
                jsonschema.validate(device, schema)
                return []
                
            except jsonschema.ValidationError as e:
                return [f"Peripheral validation ({device_type}): {e.message}"]
            except Exception as e:
                return [f"Schema loading error for {device_type}: {e}"]
        
        return []  # No schema found, skip validation
    
    def _extract_mcu_family(self, mcu_type: str) -> str:
        """Extract MCU family from full part number"""
        # STM32F407VGT6 -> stm32f4
        # STM32F103C8T6 -> stm32f1
        # ATMEGA328P -> atmega
        
        mcu_lower = mcu_type.lower()
        
        if mcu_lower.startswith('stm32f4'):
            return 'stm32f4'
        elif mcu_lower.startswith('stm32f1'):
            return 'stm32f1'
        elif mcu_lower.startswith('stm32f0'):
            return 'stm32f0'
        elif mcu_lower.startswith('atmega'):
            return 'atmega'
        elif mcu_lower.startswith('esp32'):
            return 'esp32'
        
        return mcu_lower  # Return as-is if no family match
    
    def validate_configuration(self) -> Tuple[List[str], List[str]]:
        """Validate the complete configuration"""
        if not self.config:
            return ["No configuration loaded"], []
        
        errors = []
        warnings = []
        
        # First: JSON Schema validation
        # Transform config for schema validation (device_type -> type)
        config_dict = asdict(self.config)
        
        # Transform I2C devices for schema validation
        for i2c_name, i2c_config in config_dict.get('i2c', {}).items():
            for device in i2c_config.get('devices', []):
                if 'device_type' in device:
                    device['type'] = device.pop('device_type')  # Rename device_type to type for schema
        
        schema_errors = self.validate_with_schemas(config_dict)
        errors.extend(schema_errors)
        
        # Second: Custom Python validation
        used_pins = set()
        
        # Validate GPIO pins
        for gpio in self.config.gpio:
            if not self.validate_pin_format(gpio.pin):
                errors.append(f"Invalid GPIO pin format: {gpio.pin}")
            elif gpio.pin in used_pins:
                errors.append(f"Pin conflict: {gpio.pin} used multiple times")
            else:
                used_pins.add(gpio.pin)
        
        # Validate UART pins
        for uart_name, uart in self.config.uart.items():
            if uart.enabled:
                if uart.tx_pin:
                    if not self.validate_pin_format(uart.tx_pin):
                        errors.append(f"Invalid UART {uart_name} TX pin: {uart.tx_pin}")
                    elif uart.tx_pin in used_pins:
                        errors.append(f"Pin conflict: {uart.tx_pin} used by both GPIO and UART {uart_name}")
                    else:
                        used_pins.add(uart.tx_pin)
                
                if uart.rx_pin:
                    if not self.validate_pin_format(uart.rx_pin):
                        errors.append(f"Invalid UART {uart_name} RX pin: {uart.rx_pin}")
                    elif uart.rx_pin in used_pins:
                        errors.append(f"Pin conflict: {uart.rx_pin} used by both GPIO and UART {uart_name}")
                    else:
                        used_pins.add(uart.rx_pin)
        
        # Validate I2C pins
        for i2c_name, i2c in self.config.i2c.items():
            if i2c.enabled:
                if not self.validate_pin_format(i2c.scl_pin):
                    errors.append(f"Invalid I2C {i2c_name} SCL pin: {i2c.scl_pin}")
                elif i2c.scl_pin in used_pins:
                    errors.append(f"Pin conflict: {i2c.scl_pin} used by I2C {i2c_name} SCL")
                else:
                    used_pins.add(i2c.scl_pin)
                
                if not self.validate_pin_format(i2c.sda_pin):
                    errors.append(f"Invalid I2C {i2c_name} SDA pin: {i2c.sda_pin}")
                elif i2c.sda_pin in used_pins:
                    errors.append(f"Pin conflict: {i2c.sda_pin} used by I2C {i2c_name} SDA")
                else:
                    used_pins.add(i2c.sda_pin)
        
        # Validate SPI pins
        for spi_name, spi in self.config.spi.items():
            if spi.enabled:
                spi_pins = [spi.sck_pin, spi.miso_pin, spi.mosi_pin] + spi.cs_pins
                for pin in spi_pins:
                    if pin:
                        if not self.validate_pin_format(pin):
                            errors.append(f"Invalid SPI {spi_name} pin: {pin}")
                        elif pin in used_pins:
                            errors.append(f"Pin conflict: {pin} used by SPI {spi_name}")
                        else:
                            used_pins.add(pin)
        
        # Validate timer PWM pins
        for timer_name, timer in self.config.timers.items():
            if timer.enabled and timer.mode == "pwm" and timer.output_pin:
                if not self.validate_pin_format(timer.output_pin):
                    errors.append(f"Invalid Timer {timer_name} PWM pin: {timer.output_pin}")
                elif timer.output_pin in used_pins:
                    errors.append(f"Pin conflict: {timer.output_pin} used by Timer {timer_name} PWM")
                else:
                    used_pins.add(timer.output_pin)
        
        # Check clock frequency sanity
        clock_freq = self.config.board.clock_frequency
        if clock_freq > 200_000_000:  # 200 MHz - reasonable upper limit for MCUs
            warnings.append(f"Very high clock frequency: {clock_freq:,} Hz")
        elif clock_freq < 1_000_000:  # 1 MHz - reasonable lower limit
            warnings.append(f"Very low clock frequency: {clock_freq:,} Hz")
        
        self.validation_errors = errors
        self.validation_warnings = warnings
        
        return errors, warnings
    
    def generate_summary_report(self) -> None:
        """Generate a comprehensive summary report"""
        if not self.config:
            console.print("[red]No configuration loaded[/red]")
            return
        
        # Board information
        board_table = Table(title="📋 Board Configuration", show_header=False)
        board_table.add_column("Property", style="cyan")
        board_table.add_column("Value", style="yellow")
        
        board_table.add_row("Name", self.config.board.name)
        board_table.add_row("MCU", self.config.board.mcu)
        board_table.add_row("Clock", f"{self.config.board.clock_frequency:,} Hz")
        board_table.add_row("Voltage", f"{self.config.board.voltage}V")
        if self.config.board.description:
            board_table.add_row("Description", self.config.board.description)
        
        console.print(board_table)
        
        # GPIO summary
        if self.config.gpio:
            gpio_table = Table(title=f"🔌 GPIO Configuration ({len(self.config.gpio)} pins)")
            gpio_table.add_column("Pin", style="cyan")
            gpio_table.add_column("Direction", style="green")
            gpio_table.add_column("Pull", style="blue")
            gpio_table.add_column("Speed", style="magenta")
            gpio_table.add_column("Description", style="yellow")
            
            for gpio in self.config.gpio:
                gpio_table.add_row(
                    gpio.pin,
                    gpio.direction,
                    gpio.pull,
                    gpio.speed,
                    gpio.description
                )
            console.print(gpio_table)
        
        # UART summary
        enabled_uart = [(name, uart) for name, uart in self.config.uart.items() if uart.enabled]
        if enabled_uart:
            uart_table = Table(title=f"📡 UART Configuration ({len(enabled_uart)} enabled)")
            uart_table.add_column("Interface", style="cyan")
            uart_table.add_column("Baudrate", style="green")
            uart_table.add_column("TX Pin", style="blue")
            uart_table.add_column("RX Pin", style="blue")
            uart_table.add_column("Description", style="yellow")
            
            for name, uart in enabled_uart:
                uart_table.add_row(
                    name,
                    f"{uart.baudrate:,}",
                    uart.tx_pin,
                    uart.rx_pin,
                    uart.description
                )
            console.print(uart_table)
        
        # I2C summary
        enabled_i2c = [(name, i2c) for name, i2c in self.config.i2c.items() if i2c.enabled]
        if enabled_i2c:
            i2c_table = Table(title=f"🔗 I2C Configuration ({len(enabled_i2c)} buses)")
            i2c_table.add_column("Bus", style="cyan")
            i2c_table.add_column("Speed", style="green")
            i2c_table.add_column("SCL Pin", style="blue")
            i2c_table.add_column("SDA Pin", style="blue")
            i2c_table.add_column("Devices", style="magenta")
            i2c_table.add_column("Description", style="yellow")
            
            for name, i2c in enabled_i2c:
                device_count = len(i2c.devices)
                device_list = ", ".join([f"{d.name}@0x{d.address:02X}" for d in i2c.devices[:2]])
                if device_count > 2:
                    device_list += f" (+{device_count-2} more)"
                
                i2c_table.add_row(
                    name,
                    f"{i2c.speed:,} Hz",
                    i2c.scl_pin,
                    i2c.sda_pin,
                    device_list,
                    i2c.description
                )
            console.print(i2c_table)
        
        # Timer summary
        enabled_timers = [(name, timer) for name, timer in self.config.timers.items() if timer.enabled]
        if enabled_timers:
            timer_table = Table(title=f"⏱️  Timer Configuration ({len(enabled_timers)} enabled)")
            timer_table.add_column("Timer", style="cyan")
            timer_table.add_column("Mode", style="green")
            timer_table.add_column("Prescaler", style="blue")
            timer_table.add_column("Period", style="magenta")
            timer_table.add_column("Output", style="yellow")
            
            for name, timer in enabled_timers:
                output_info = ""
                if timer.mode == "pwm" and timer.output_pin:
                    output_info = f"{timer.output_pin} ({timer.duty_cycle}%)"
                
                timer_table.add_row(
                    name,
                    timer.mode,
                    str(timer.prescaler),
                    str(timer.period),
                    output_info
                )
            console.print(timer_table)
        
        # SPI summary
        enabled_spi = [(name, spi) for name, spi in self.config.spi.items() if spi.enabled]
        if enabled_spi:
            spi_table = Table(title=f"🔄 SPI Configuration ({len(enabled_spi)} enabled)")
            spi_table.add_column("Interface", style="cyan")
            spi_table.add_column("Mode", style="green")
            spi_table.add_column("Speed", style="blue")
            spi_table.add_column("Pins", style="magenta")
            spi_table.add_column("Description", style="yellow")
            
            for name, spi in enabled_spi:
                pins_info = f"SCK:{spi.sck_pin} MISO:{spi.miso_pin} MOSI:{spi.mosi_pin}"
                if spi.cs_pins:
                    pins_info += f" CS:{','.join(spi.cs_pins)}"
                
                spi_table.add_row(
                    name,
                    f"Mode {spi.mode}",
                    f"{spi.speed:,} Hz",
                    pins_info,
                    spi.description
                )
            console.print(spi_table)
    
    def export_to_json(self, output_file: Union[str, Path]) -> None:
        """Export configuration to JSON file"""
        if not self.config:
            raise ConfigurationError("No configuration loaded")
        
        # Convert to dictionary
        config_dict = asdict(self.config)
        
        # Save to file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, indent=2, ensure_ascii=False)
        
        console.print(f"[green]Configuration exported to: {output_file}[/green]")


@click.command()
@click.argument('config_file', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), help='Output JSON file path')
@click.option('--validate', '-v', is_flag=True, help='Validate configuration')
@click.option('--summary', '-s', is_flag=True, help='Show configuration summary')
@click.option('--verbose', is_flag=True, help='Verbose output')
def main(config_file: str, output: str, validate: bool, summary: bool, verbose: bool):
    """
    Parse YAML configuration file for embedded peripheral setup.
    
    CONFIG_FILE: Path to the YAML configuration file
    """
    console.print(Panel.fit(
        "[bold blue]Embedded Peripheral Configuration Parser[/bold blue]\n"
        "[dim]Clean YAML-based configuration parser for embedded peripherals[/dim]",
        border_style="blue"
    ))
    
    console.print(f"\n[yellow]📁 Loading configuration:[/yellow] [cyan]{config_file}[/cyan]")
    
    try:
        parser = YAMLConfigParser()
        
        # Load and parse configuration
        config = parser.load_config(config_file)
        console.print("[green]✓ Configuration loaded successfully[/green]")
        
        # Validation
        if validate:
            console.print("\n[yellow]🔍 Validating configuration...[/yellow]")
            errors, warnings = parser.validate_configuration()
            
            if errors:
                console.print("\n[red]❌ Validation Errors:[/red]")
                for error in errors:
                    console.print(f"  [red]•[/red] {error}")
                
                console.print(f"\n[red]❌ Validation failed with {len(errors)} error(s)[/red]")
                console.print("[red]🛑 Stopping execution due to validation errors[/red]")
                console.print("[dim]Fix the errors above and try again[/dim]")
                sys.exit(1)  # Exit with error code
                
            if warnings:
                console.print("\n[yellow]⚠️  Validation Warnings:[/yellow]")
                for warning in warnings:
                    console.print(f"  [yellow]•[/yellow] {warning}")
                console.print("[yellow]✓ Validation passed with warnings[/yellow]")
            else:
                console.print("[green]✓ All validation checks passed[/green]")
        
        # Summary report
        if summary or verbose:
            console.print("\n" + "="*60)
            parser.generate_summary_report()
            console.print("="*60)
        
        # Pin usage summary
        if verbose:
            used_pins = set()
            # Collect all used pins
            for gpio in config.gpio:
                used_pins.add(gpio.pin)
            for uart in config.uart.values():
                if uart.enabled and uart.tx_pin:
                    used_pins.add(uart.tx_pin)
                if uart.enabled and uart.rx_pin:
                    used_pins.add(uart.rx_pin)
            for i2c in config.i2c.values():
                if i2c.enabled:
                    used_pins.add(i2c.scl_pin)
                    used_pins.add(i2c.sda_pin)
            for timer in config.timers.values():
                if timer.enabled and timer.output_pin:
                    used_pins.add(timer.output_pin)
            for spi in config.spi.values():
                if spi.enabled:
                    used_pins.update([spi.sck_pin, spi.miso_pin, spi.mosi_pin] + spi.cs_pins)
            
            # Remove empty pins
            used_pins = {pin for pin in used_pins if pin}
            
            console.print(f"\n[bold cyan]📌 Pin Usage Summary:[/bold cyan]")
            console.print(f"Total pins used: [yellow]{len(used_pins)}[/yellow]")
            if used_pins:
                sorted_pins = sorted(used_pins)
                console.print(f"Pins: [cyan]{', '.join(sorted_pins)}[/cyan]")
        
        # Export to JSON
        if output:
            parser.export_to_json(output)
        
        # Default JSON output if no other output specified
        if not summary and not verbose and not output:
            config_dict = asdict(config)
            print(json.dumps(config_dict, indent=2))
        
        console.print("\n[green]🎉 Processing completed successfully![/green]")
        
    except ConfigurationError as e:
        console.print(f"\n[red]❌ Configuration Error:[/red] {e}")
        if verbose:
            import traceback
            console.print(f"\n[red]Traceback:[/red]\n{traceback.format_exc()}")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red]❌ Unexpected Error:[/red] {e}")
        if verbose:
            import traceback
            console.print(f"\n[red]Traceback:[/red]\n{traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    main()