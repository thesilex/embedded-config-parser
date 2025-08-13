#!/usr/bin/env python3
"""
Configuration Validation System using JSON Schemas
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from rich.console import Console
import jsonschema

# Console for rich output
console = Console()

# ============================================================================
# VALIDATION RESULT CLASSES
# ============================================================================

class ValidationLevel(Enum):
    """Validation message severity levels"""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

@dataclass
class ValidationMessage:
    """Single validation message"""
    level: ValidationLevel
    message: str
    location: str = ""
    category: str = ""
    suggestion: str = ""
    
    def __str__(self) -> str:
        prefix = "❌" if self.level == ValidationLevel.ERROR else "⚠️" if self.level == ValidationLevel.WARNING else "ℹ️"
        location_str = f"{self.location}: " if self.location else ""
        return f"{prefix} {location_str}{self.message}"

@dataclass
class ValidationResult:
    """Complete validation result"""
    is_valid: bool = True
    messages: List[ValidationMessage] = field(default_factory=list)
    
    @property
    def errors(self) -> List[ValidationMessage]:
        return [msg for msg in self.messages if msg.level == ValidationLevel.ERROR]
    
    @property
    def warnings(self) -> List[ValidationMessage]:
        return [msg for msg in self.messages if msg.level == ValidationLevel.WARNING]
    
    @property
    def info_messages(self) -> List[ValidationMessage]:
        return [msg for msg in self.messages if msg.level == ValidationLevel.INFO]
    
    def add_error(self, message: str, location: str = "", category: str = "", suggestion: str = ""):
        """Add validation error"""
        self.messages.append(ValidationMessage(
            level=ValidationLevel.ERROR,
            message=message,
            location=location,
            category=category,
            suggestion=suggestion
        ))
        self.is_valid = False
    
    def add_warning(self, message: str, location: str = "", category: str = "", suggestion: str = ""):
        """Add validation warning"""
        self.messages.append(ValidationMessage(
            level=ValidationLevel.WARNING,
            message=message,
            location=location,
            category=category,
            suggestion=suggestion
        ))
    
    def add_info(self, message: str, location: str = "", category: str = "", suggestion: str = ""):
        """Add validation info"""
        self.messages.append(ValidationMessage(
            level=ValidationLevel.INFO,
            message=message,
            location=location,
            category=category,
            suggestion=suggestion
        ))
    
    def merge(self, other: 'ValidationResult'):
        """Merge another validation result"""
        self.messages.extend(other.messages)
        if not other.is_valid:
            self.is_valid = False
    
    def has_errors(self) -> bool:
        return len(self.errors) > 0
    
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

# ============================================================================
# PIN MAPPING AND CONFLICT DETECTION
# ============================================================================

@dataclass
class PinMapping:
    """Pin usage mapping for conflict detection"""
    pin: str
    usage_type: str  # "GPIO", "UART", "I2C", "SPI", "Timer"
    peripheral: str  # "uart1_tx", "i2c1_scl", "gpio_output"
    description: str = ""
    config_location: str = ""

class PinConflictDetector:
    """Efficient pin conflict detection"""
    
    def __init__(self):
        self.pin_mappings: Dict[str, PinMapping] = {}
        self.conflicts: List[Tuple[PinMapping, PinMapping]] = []
    
    def add_pin_usage(self, mapping: PinMapping) -> bool:
        """Add pin usage, return True if conflict detected"""
        if mapping.pin in self.pin_mappings:
            existing = self.pin_mappings[mapping.pin]
            self.conflicts.append((existing, mapping))
            return True
        
        self.pin_mappings[mapping.pin] = mapping
        return False
    
    def get_conflicts(self) -> List[Tuple[PinMapping, PinMapping]]:
        """Get all detected conflicts"""
        return self.conflicts
    
    def clear(self):
        """Clear all mappings and conflicts"""
        self.pin_mappings.clear()
        self.conflicts.clear()

# ============================================================================
# SCHEMA-DRIVEN MCU SPECS LOADER
# ============================================================================

class SchemaBasedMCUDatabase:
    """Load MCU specifications from schema files"""
    
    def __init__(self, schema_dir: Path = Path("schemas")):
        self.schema_dir = schema_dir
        self.mcu_specs_cache = {}
        self._load_all_schemas()
    
    def _load_all_schemas(self):
        """Load all MCU schema files at initialization"""
        mcu_schema_dir = self.schema_dir / "mcu"
        
        if not mcu_schema_dir.exists():
            console.print(f"Warning: MCU schema directory not found: {mcu_schema_dir}")
            return
        
        for schema_file in mcu_schema_dir.glob("*.json"):
            try:
                with open(schema_file) as f:
                    schema = json.load(f)
                
                # Extract schema name and MCU patterns
                schema_name = schema_file.stem  # e.g., "STM32F407Vxxx"
                mcu_patterns = schema.get('mcu_patterns', [])
                
                # Extract specs from schema
                specs = self._extract_specs_from_schema(schema)
                specs['schema_file'] = schema_name
                
                # Store specs with patterns as keys
                for pattern in mcu_patterns:
                    self.mcu_specs_cache[pattern.lower()] = specs
                
                console.print(f"Loaded MCU specs for {schema_name}: {len(mcu_patterns)} patterns")
                
            except Exception as e:
                console.print(f"Warning: Could not load schema {schema_file}: {e}")
    
    def _extract_specs_from_schema(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Extract MCU specifications from JSON schema"""
        specs = {}
        
        try:
            # Get package constraints
            package_constraints = schema.get('package_constraints', {})
            
            # Extract GPIO port information
            gpio_ports = package_constraints.get('gpio_ports', {})
            specs['gpio_ports'] = list(gpio_ports.keys())
            specs['max_pins_per_port'] = {
                port: info.get('max', 15) + 1  # max+1 for pin count
                for port, info in gpio_ports.items()
            }
            
            # Extract peripheral limits
            peripheral_limits = package_constraints.get('peripheral_limits', {})
            specs['uart_count'] = peripheral_limits.get('uart_count', 6)
            specs['i2c_count'] = peripheral_limits.get('i2c_count', 3)
            specs['spi_count'] = peripheral_limits.get('spi_count', 6)
            specs['timer_count'] = peripheral_limits.get('timer_count', 14)
            
            # Extract clock and voltage limits from board properties
            board_props = schema.get('properties', {}).get('board', {}).get('properties', {})
            
            clock_props = board_props.get('clock_frequency', {})
            specs['max_clock'] = clock_props.get('maximum', 200_000_000)
            
            voltage_props = board_props.get('voltage', {})
            specs['min_voltage'] = voltage_props.get('minimum', 1.8)
            specs['max_voltage'] = voltage_props.get('maximum', 5.5)
            
            # Get package info
            package_info = schema.get('package_info', {})
            specs['package_type'] = package_info.get('package_type', 'Unknown')
            specs['pin_count'] = package_info.get('pin_count', 0)
            
        except Exception as e:
            console.print(f"Warning: Error extracting specs from schema: {e}")
            # Return minimal fallback specs
            specs = {
                'max_clock': 200_000_000,
                'min_voltage': 1.8,
                'max_voltage': 5.5,
                'gpio_ports': ['A', 'B', 'C', 'D', 'E'],
                'max_pins_per_port': {port: 16 for port in ['A', 'B', 'C', 'D', 'E']},
                'uart_count': 6,
                'i2c_count': 3,
                'spi_count': 6,
                'timer_count': 14,
                'package_type': 'Unknown',
                'pin_count': 0
            }
        
        return specs
    
    def find_mcu_specs(self, mcu_type: str) -> Optional[Dict[str, Any]]:
        """Find MCU specs by matching against patterns"""
        mcu_lower = mcu_type.lower()
        
        # Direct pattern matching
        for pattern, specs in self.mcu_specs_cache.items():
            if self._match_pattern(mcu_lower, pattern):
                return specs
        
        return None
    
    def _match_pattern(self, mcu_type: str, pattern: str) -> bool:
        """Match MCU type against pattern (supports wildcards)"""
        # Convert simple wildcards to regex
        regex_pattern = pattern.replace('*', '.*').replace('?', '.')
        return bool(re.match(f"^{regex_pattern}$", mcu_type))

# ============================================================================
# SCHEMA-DRIVEN VALIDATORS
# ============================================================================

class SchemaBasedPinValidator:
    """Schema-driven pin validation"""
    
    def __init__(self, mcu_database: SchemaBasedMCUDatabase):
        self.mcu_database = mcu_database
        self.conflict_detector = PinConflictDetector()
    
    def validate(self, config) -> ValidationResult:
        """Validate pin configuration using schema-derived specs"""
        result = ValidationResult()
        self.conflict_detector.clear()
        
        # Get MCU specs from schema
        mcu_specs = self.mcu_database.find_mcu_specs(config.board.mcu)
        if not mcu_specs:
            result.add_error(
                f"No schema found for MCU: {config.board.mcu}",
                location="board.mcu",
                category="schema_missing",
                suggestion="Add appropriate schema file for this MCU"
            )
            return result
        
        # Collect all pin usages
        self._collect_gpio_pins(config, result, mcu_specs)
        self._collect_uart_pins(config, result, mcu_specs)
        self._collect_i2c_pins(config, result, mcu_specs)
        self._collect_spi_pins(config, result, mcu_specs)
        self._collect_timer_pins(config, result, mcu_specs)
        
        # Report conflicts
        conflicts = self.conflict_detector.get_conflicts()
        for existing, new in conflicts:
            result.add_error(
                f"Pin {existing.pin} used by both {existing.peripheral} and {new.peripheral}",
                location="pin_conflicts",
                category="pin_conflict",
                suggestion=f"Use different pins for {existing.peripheral} and {new.peripheral}"
            )
        
        return result
    
    def _validate_pin_against_schema(self, pin: str, mcu_specs: Dict[str, Any]) -> bool:
        """Validate pin against schema-derived constraints"""
        if len(pin) < 2 or pin[0] != 'P':
            return False
        
        port = pin[1]
        try:
            pin_num = int(pin[2:])
        except ValueError:
            return False
        
        # Check if port exists
        if port not in mcu_specs.get('gpio_ports', []):
            return False
        
        # Check if pin number is valid for this port
        max_pins_per_port = mcu_specs.get('max_pins_per_port', {})
        max_pin = max_pins_per_port.get(port, 16)
        
        return 0 <= pin_num < max_pin
    
    def _collect_gpio_pins(self, config, result: ValidationResult, mcu_specs: Dict[str, Any]):
        """Collect GPIO pin mappings with schema validation"""
        for i, gpio in enumerate(config.gpio):
            if not self._validate_pin_against_schema(gpio.pin, mcu_specs):
                available_ports = ', '.join(mcu_specs.get('gpio_ports', []))
                result.add_error(
                    f"Invalid GPIO pin: {gpio.pin}",
                    location=f"gpio[{i}]",
                    category="pin_format",
                    suggestion=f"Use pins from available ports: {available_ports}"
                )
                continue
            
            mapping = PinMapping(
                pin=gpio.pin,
                usage_type="GPIO",
                peripheral=f"GPIO ({gpio.direction})",
                description=gpio.description,
                config_location=f"gpio[{i}]"
            )
            self.conflict_detector.add_pin_usage(mapping)
    
    def _collect_uart_pins(self, config, result: ValidationResult, mcu_specs: Dict[str, Any]):
        """Collect UART pin mappings with schema validation"""
        for uart_name, uart in config.uart.items():
            if not uart.enabled:
                continue
            
            for pin_type, pin in [("TX", uart.tx_pin), ("RX", uart.rx_pin)]:
                if not pin:
                    continue
                
                if not self._validate_pin_against_schema(pin, mcu_specs):
                    available_ports = ', '.join(mcu_specs.get('gpio_ports', []))
                    result.add_error(
                        f"Invalid UART {uart_name} {pin_type} pin: {pin}",
                        location=f"uart.{uart_name}",
                        category="pin_format",
                        suggestion=f"Use pins from available ports: {available_ports}"
                    )
                    continue
                
                mapping = PinMapping(
                    pin=pin,
                    usage_type="UART",
                    peripheral=f"UART {uart_name} {pin_type}",
                    description=uart.description,
                    config_location=f"uart.{uart_name}"
                )
                self.conflict_detector.add_pin_usage(mapping)
    
    def _collect_i2c_pins(self, config, result: ValidationResult, mcu_specs: Dict[str, Any]):
        """Collect I2C pin mappings with schema validation"""
        for i2c_name, i2c in config.i2c.items():
            if not i2c.enabled:
                continue
            
            for pin_type, pin in [("SCL", i2c.scl_pin), ("SDA", i2c.sda_pin)]:
                if not self._validate_pin_against_schema(pin, mcu_specs):
                    available_ports = ', '.join(mcu_specs.get('gpio_ports', []))
                    result.add_error(
                        f"Invalid I2C {i2c_name} {pin_type} pin: {pin}",
                        location=f"i2c.{i2c_name}",
                        category="pin_format",
                        suggestion=f"Use pins from available ports: {available_ports}"
                    )
                    continue
                
                mapping = PinMapping(
                    pin=pin,
                    usage_type="I2C",
                    peripheral=f"I2C {i2c_name} {pin_type}",
                    description=i2c.description,
                    config_location=f"i2c.{i2c_name}"
                )
                self.conflict_detector.add_pin_usage(mapping)
    
    def _collect_spi_pins(self, config, result: ValidationResult, mcu_specs: Dict[str, Any]):
        """Collect SPI pin mappings with schema validation"""
        for spi_name, spi in config.spi.items():
            if not spi.enabled:
                continue
            
            spi_pins = [
                ("SCK", spi.sck_pin),
                ("MISO", spi.miso_pin),
                ("MOSI", spi.mosi_pin)
            ]
            
            # Add CS pins
            for i, cs_pin in enumerate(spi.cs_pins):
                spi_pins.append((f"CS{i}", cs_pin))
            
            for pin_type, pin in spi_pins:
                if not pin:
                    continue
                
                if not self._validate_pin_against_schema(pin, mcu_specs):
                    available_ports = ', '.join(mcu_specs.get('gpio_ports', []))
                    result.add_error(
                        f"Invalid SPI {spi_name} {pin_type} pin: {pin}",
                        location=f"spi.{spi_name}",
                        category="pin_format",
                        suggestion=f"Use pins from available ports: {available_ports}"
                    )
                    continue
                
                mapping = PinMapping(
                    pin=pin,
                    usage_type="SPI",
                    peripheral=f"SPI {spi_name} {pin_type}",
                    description=spi.description,
                    config_location=f"spi.{spi_name}"
                )
                self.conflict_detector.add_pin_usage(mapping)
    
    def _collect_timer_pins(self, config, result: ValidationResult, mcu_specs: Dict[str, Any]):
        """Collect Timer pin mappings with schema validation"""
        for timer_name, timer in config.timers.items():
            if not timer.enabled or timer.mode != "pwm" or not timer.output_pin:
                continue
            
            pin = timer.output_pin
            if not self._validate_pin_against_schema(pin, mcu_specs):
                available_ports = ', '.join(mcu_specs.get('gpio_ports', []))
                result.add_error(
                    f"Invalid Timer {timer_name} PWM pin: {pin}",
                    location=f"timers.{timer_name}",
                    category="pin_format",
                    suggestion=f"Use pins from available ports: {available_ports}"
                )
                continue
            
            mapping = PinMapping(
                pin=pin,
                usage_type="Timer PWM",
                peripheral=f"Timer {timer_name} PWM",
                description=timer.description,
                config_location=f"timers.{timer_name}"
            )
            self.conflict_detector.add_pin_usage(mapping)

class SchemaBasedMCUValidator:
    """Schema-driven MCU validation"""
    
    def __init__(self, mcu_database: SchemaBasedMCUDatabase):
        self.mcu_database = mcu_database
    
    def validate(self, config) -> ValidationResult:
        """Validate MCU-specific constraints using schema"""
        result = ValidationResult()
        
        # Get MCU specs from schema
        mcu_specs = self.mcu_database.find_mcu_specs(config.board.mcu)
        
        if not mcu_specs:
            result.add_warning(
                f"No schema found for MCU: {config.board.mcu}",
                location="board.mcu",
                category="schema_missing",
                suggestion="Add appropriate schema file for this MCU"
            )
            return result
        
        # Validate clock frequency
        max_clock = mcu_specs.get('max_clock', 200_000_000)
        if config.board.clock_frequency > max_clock:
            result.add_error(
                f"Clock frequency {config.board.clock_frequency:,}Hz exceeds maximum {max_clock:,}Hz",
                location="board.clock_frequency",
                category="mcu_limits",
                suggestion=f"Reduce clock frequency to max {max_clock:,}Hz"
            )
        
        # Validate voltage range
        min_voltage = mcu_specs.get('min_voltage', 1.8)
        max_voltage = mcu_specs.get('max_voltage', 5.5)
        if not (min_voltage <= config.board.voltage <= max_voltage):
            result.add_error(
                f"Voltage {config.board.voltage}V outside valid range {min_voltage}-{max_voltage}V",
                location="board.voltage",
                category="mcu_limits"
            )
        
        # Validate peripheral counts
        peripheral_counts = config.get_enabled_peripheral_count()
        
        uart_limit = mcu_specs.get('uart_count', 6)
        if peripheral_counts['uart'] > uart_limit:
            result.add_error(
                f"Too many UART peripherals enabled: {peripheral_counts['uart']} > {uart_limit}",
                location="uart",
                category="mcu_limits"
            )
        
        i2c_limit = mcu_specs.get('i2c_count', 3)
        if peripheral_counts['i2c'] > i2c_limit:
            result.add_error(
                f"Too many I2C peripherals enabled: {peripheral_counts['i2c']} > {i2c_limit}",
                location="i2c",
                category="mcu_limits"
            )
        
        spi_limit = mcu_specs.get('spi_count', 6)
        if peripheral_counts['spi'] > spi_limit:
            result.add_error(
                f"Too many SPI peripherals enabled: {peripheral_counts['spi']} > {spi_limit}",
                location="spi",
                category="mcu_limits"
            )
        
        # Add info about detected MCU
        package_type = mcu_specs.get('package_type', 'Unknown')
        pin_count = mcu_specs.get('pin_count', 0)
        result.add_info(
            f"Detected MCU package: {package_type} ({pin_count} pins)",
            category="mcu_detection"
        )
        
        return result

class PeripheralValidator:
    """Peripheral-specific business logic validation"""
    
    def validate(self, config) -> ValidationResult:
        """Validate peripheral configurations"""
        result = ValidationResult()
        
        # I2C address conflicts
        self._validate_i2c_addresses(config, result)
        
        # Timer configuration validation
        self._validate_timer_configs(config, result)
        
        # SPI configuration validation
        self._validate_spi_configs(config, result)
        
        # UART configuration validation
        self._validate_uart_configs(config, result)
        
        return result
    
    def _validate_i2c_addresses(self, config, result: ValidationResult):
        """Check for I2C address conflicts"""
        for i2c_name, i2c in config.i2c.items():
            if not i2c.enabled:
                continue
            
            addresses = set()
            for device in i2c.devices:
                if device.address in addresses:
                    result.add_error(
                        f"I2C address conflict on {i2c_name}: 0x{device.address:02X} used multiple times",
                        location=f"i2c.{i2c_name}",
                        category="i2c_conflict",
                        suggestion="Use unique I2C addresses for each device"
                    )
                addresses.add(device.address)
                
                # Check reserved addresses
                if device.address < 0x08 or device.address > 0x77:
                    result.add_error(
                        f"Invalid I2C address on {i2c_name}: 0x{device.address:02X} (must be 0x08-0x77)",
                        location=f"i2c.{i2c_name}.{device.name}",
                        category="i2c_address"
                    )
    
    def _validate_timer_configs(self, config, result: ValidationResult):
        """Validate timer configurations"""
        for timer_name, timer in config.timers.items():
            if not timer.enabled:
                continue
            
            # PWM specific validation
            if timer.mode == "pwm":
                if timer.duty_cycle is None or not (0 <= timer.duty_cycle <= 100):
                    result.add_error(
                        f"Timer {timer_name}: PWM mode requires duty_cycle between 0-100",
                        location=f"timers.{timer_name}",
                        category="timer_config"
                    )
                
                if not timer.output_pin:
                    result.add_error(
                        f"Timer {timer_name}: PWM mode requires output_pin",
                        location=f"timers.{timer_name}",
                        category="timer_config"
                    )
                
                if timer.channel is None or not (1 <= timer.channel <= 4):
                    result.add_error(
                        f"Timer {timer_name}: Invalid PWM channel (must be 1-4)",
                        location=f"timers.{timer_name}",
                        category="timer_config"
                    )
            
            # Check prescaler and period values
            if timer.prescaler <= 0 or timer.prescaler > 65536:
                result.add_error(
                    f"Timer {timer_name}: Invalid prescaler value {timer.prescaler} (1-65536)",
                    location=f"timers.{timer_name}",
                    category="timer_config"
                )
            
            if timer.period <= 0 or timer.period > 65536:
                result.add_error(
                    f"Timer {timer_name}: Invalid period value {timer.period} (1-65536)",
                    location=f"timers.{timer_name}",
                    category="timer_config"
                )
    
    def _validate_spi_configs(self, config, result: ValidationResult):
        """Validate SPI configurations"""
        for spi_name, spi in config.spi.items():
            if not spi.enabled:
                continue
            
            # Required pins check
            if not spi.sck_pin:
                result.add_error(
                    f"SPI {spi_name}: SCK pin is required",
                    location=f"spi.{spi_name}",
                    category="spi_config"
                )
            
            if not spi.mosi_pin:
                result.add_error(
                    f"SPI {spi_name}: MOSI pin is required",
                    location=f"spi.{spi_name}",
                    category="spi_config"
                )
            
            # CS pins validation
            if not spi.cs_pins:
                result.add_warning(
                    f"SPI {spi_name}: No CS pins configured",
                    location=f"spi.{spi_name}",
                    category="spi_config",
                    suggestion="Add CS pins for device selection"
                )
    
    def _validate_uart_configs(self, config, result: ValidationResult):
        """Validate UART configurations"""
        for uart_name, uart in config.uart.items():
            if not uart.enabled:
                continue
            
            # Pin validation
            if not uart.tx_pin and not uart.rx_pin:
                result.add_warning(
                    f"UART {uart_name}: No TX or RX pins configured",
                    location=f"uart.{uart_name}",
                    category="uart_config",
                    suggestion="Configure at least TX or RX pin"
                )

class SchemaValidator:
    """JSON Schema validation with schema-based MCU discovery"""
    
    def __init__(self, mcu_database: SchemaBasedMCUDatabase):
        self.mcu_database = mcu_database
    
    def validate(self, config) -> ValidationResult:
        """Validate using JSON schemas"""
        result = ValidationResult()
        
        # Convert config to dict for schema validation
        from dataclasses import asdict
        config_dict = asdict(config)
        
        # Transform device_type to type for schema compatibility
        for i2c_name, i2c_config in config_dict.get('i2c', {}).items():
            for device in i2c_config.get('devices', []):
                if 'device_type' in device:
                    device['type'] = device.pop('device_type')
        
        # MCU schema validation
        mcu_result = self._validate_mcu_schema(config_dict, config.board.mcu)
        result.merge(mcu_result)
        
        # Peripheral schema validation
        peripheral_result = self._validate_peripheral_schemas(config_dict)
        result.merge(peripheral_result)
        
        return result
    
    def _validate_mcu_schema(self, config_data: Dict[str, Any], mcu_type: str) -> ValidationResult:
        """Validate against MCU-specific schema"""
        result = ValidationResult()
        
        # Find schema using MCU database
        mcu_specs = self.mcu_database.find_mcu_specs(mcu_type)
        if not mcu_specs:
            result.add_info(
                f"No schema found for MCU: {mcu_type}",
                category="schema_availability"
            )
            return result
        
        schema_file_name = mcu_specs.get('schema_file')
        schema_file = self.mcu_database.schema_dir / "mcu" / f"{schema_file_name}.json"
        
        try:
            with open(schema_file) as f:
                schema = json.load(f)
            
            jsonschema.validate(config_data, schema)
            result.add_info(f"MCU schema validation passed for {schema_file_name}", category="schema_validation")
            
        except jsonschema.ValidationError as e:
            error_path = " -> ".join(str(p) for p in e.absolute_path) if e.absolute_path else "root"
            result.add_error(
                f"MCU schema validation at '{error_path}': {e.message}",
                location=error_path,
                category="schema_validation"
            )
        except Exception as e:
            result.add_warning(
                f"Schema loading error for {schema_file_name}: {e}",
                category="schema_error"
            )
        
        return result
    
    def _validate_peripheral_schemas(self, config_data: Dict[str, Any]) -> ValidationResult:
        """Validate peripheral schemas"""
        result = ValidationResult()
        
        for i2c_name, i2c_config in config_data.get('i2c', {}).items():
            if not i2c_config.get('enabled', False):
                continue
            
            for device in i2c_config.get('devices', []):
                device_type = device.get('type', '').lower()
                if device_type:
                    device_result = self._validate_device_schema(device, device_type)
                    result.merge(device_result)
        
        return result
    
    def _validate_device_schema(self, device: Dict[str, Any], device_type: str) -> ValidationResult:
        """Validate device against peripheral schema"""
        result = ValidationResult()
        
        schema_file = self.mcu_database.schema_dir / "peripherals" / f"{device_type}.json"
        
        if not schema_file.exists():
            result.add_info(
                f"No schema found for device type: {device_type}",
                category="schema_availability"
            )
            return result
        
        try:
            with open(schema_file) as f:
                schema = json.load(f)
            
            jsonschema.validate(device, schema)
            result.add_info(f"Device schema validation passed for {device_type}", category="schema_validation")
            
        except jsonschema.ValidationError as e:
            result.add_error(
                f"Device schema validation ({device_type}): {e.message}",
                category="schema_validation"
            )
        except Exception as e:
            result.add_warning(
                f"Schema loading error for {device_type}: {e}",
                category="schema_error"
            )
        
        return result

# ============================================================================
# MAIN CONFIGURATION VALIDATOR - SCHEMA DRIVEN
# ============================================================================

class ConfigValidator:
    """Schema-driven configuration validator orchestrator"""
    
    def __init__(self, schema_dir: Optional[Path] = None):
        self.schema_dir = schema_dir or Path("schemas")
        
        # Initialize schema-based MCU database
        self.mcu_database = SchemaBasedMCUDatabase(self.schema_dir)
        
        # Initialize schema-driven validators
        self.pin_validator = SchemaBasedPinValidator(self.mcu_database)
        self.mcu_validator = SchemaBasedMCUValidator(self.mcu_database)
        self.peripheral_validator = PeripheralValidator()
        self.schema_validator = SchemaValidator(self.mcu_database)
    
    def validate(self, config) -> ValidationResult:
        """Run all validations and return combined result"""
        final_result = ValidationResult()
        
        # Run all validators
        validators = [
            ("Schema-Based Pin Validation", self.pin_validator),
            ("Schema-Based MCU Validation", self.mcu_validator), 
            ("Peripheral Validation", self.peripheral_validator),
            ("JSON Schema Validation", self.schema_validator)
        ]
        
        for validator_name, validator in validators:
            try:
                result = validator.validate(config)
                final_result.merge(result)
            except Exception as e:
                final_result.add_error(
                    f"Validation error in {validator_name}: {e}",
                    category="validator_error"
                )
        
        return final_result
