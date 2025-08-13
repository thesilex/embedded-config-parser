#!/usr/bin/env python3
"""
Configuration Models and YAML Parser
Contains all configuration data classes and YAML parsing logic
"""

import json
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, asdict, field
from rich.console import Console
from rich.table import Table

# Console for rich output
console = Console()

# ============================================================================
# CONFIGURATION MODEL CLASSES
# ============================================================================

@dataclass
class GPIOConfig:
    """GPIO pin configuration"""
    pin: str
    direction: str  # "input" or "output"
    pull: str = "none"  # "none", "up", "down"
    speed: str = "medium"  # "low", "medium", "high", "very-high"
    initial_state: str = "low"  # "low", "high"
    description: str = ""

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

@dataclass
class I2CDevice:
    """I2C device configuration"""
    name: str
    address: int
    device_type: str
    description: str = ""

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

@dataclass
class BoardConfig:
    """Board configuration"""
    name: str
    mcu: str
    clock_frequency: int
    voltage: float = 3.3
    description: str = ""

@dataclass
class EmbeddedConfig:
    """Complete embedded system configuration"""
    board: BoardConfig
    gpio: List[GPIOConfig] = field(default_factory=list)
    uart: Dict[str, UARTConfig] = field(default_factory=dict)
    i2c: Dict[str, I2CConfig] = field(default_factory=dict)
    timers: Dict[str, TimerConfig] = field(default_factory=dict)
    spi: Dict[str, SPIConfig] = field(default_factory=dict)
    
    def get_all_used_pins(self) -> List[str]:
        """Get all pins used in configuration"""
        pins = []
        
        # GPIO pins
        pins.extend([gpio.pin for gpio in self.gpio])
        
        # UART pins
        for uart in self.uart.values():
            if uart.enabled:
                if uart.tx_pin:
                    pins.append(uart.tx_pin)
                if uart.rx_pin:
                    pins.append(uart.rx_pin)
        
        # I2C pins
        for i2c in self.i2c.values():
            if i2c.enabled:
                pins.extend([i2c.scl_pin, i2c.sda_pin])
        
        # SPI pins
        for spi in self.spi.values():
            if spi.enabled:
                pins.extend([spi.sck_pin, spi.miso_pin, spi.mosi_pin])
                pins.extend(spi.cs_pins)
        
        # Timer pins
        for timer in self.timers.values():
            if timer.enabled and timer.output_pin:
                pins.append(timer.output_pin)
        
        # Remove empty strings and duplicates
        return list(set([pin for pin in pins if pin]))
    
    def get_enabled_peripheral_count(self) -> Dict[str, int]:
        """Get count of enabled peripherals by type"""
        return {
            "uart": len([u for u in self.uart.values() if u.enabled]),
            "i2c": len([i for i in self.i2c.values() if i.enabled]),
            "spi": len([s for s in self.spi.values() if s.enabled]),
            "timers": len([t for t in self.timers.values() if t.enabled]),
            "gpio": len(self.gpio)
        }

# ============================================================================
# EXCEPTION CLASSES
# ============================================================================

class ConfigurationError(Exception):
    """Custom exception for configuration errors"""
    pass

# ============================================================================
# YAML CONFIGURATION PARSER
# ============================================================================

class YAMLConfigParser:
    """YAML-based embedded peripheral configuration parser"""
    
    def __init__(self):
        self.config: Optional[EmbeddedConfig] = None
    
    def load_config(self, config_file: Union[str, Path]) -> EmbeddedConfig:
        """Load and parse YAML configuration file"""
        try:
            with open(config_file, 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file)
                self.config = self._parse_config_data(data)
                return self.config
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
                        device_type=device_data.get('device_type', device_data.get('type', '')),
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
            return EmbeddedConfig(
                board=board,
                gpio=gpio_configs,
                uart=uart_configs,
                i2c=i2c_configs,
                timers=timer_configs,
                spi=spi_configs
            )
            
        except Exception as e:
            raise ConfigurationError(f"Error parsing configuration data: {e}")
    
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