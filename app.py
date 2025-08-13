#!/usr/bin/env python3
"""
Embedded Peripheral Configuration Parser - CLI Interface
Main entry point for YAML configuration parsing and validation

Usage:
    app.py config.yaml                    # Parse + validate + display
    app.py config.yaml --summary          # Visualize configuration summary
    app.py config.yaml --validate         # Validate only
    app.py config.yaml --parse            # Parse + validate (explicit)
    app.py config.yaml --output config.json
"""

import sys
from pathlib import Path
import click
from rich.console import Console
from rich.panel import Panel

from parser import YAMLConfigParser, ConfigurationError
from validator import ConfigValidator

# Console for rich output
console = Console()

@click.command()
@click.argument('config_file', type=click.Path(exists=True))
@click.option('--validate', is_flag=True, help='Validate configuration only')
@click.option('--parse', is_flag=True, help='Parse and validate configuration (explicit)')
@click.option('--output', '-o', type=click.Path(), help='Output JSON file path')
@click.option('--summary', '-s', is_flag=True, help='Show configuration summary')
@click.option('--verbose', is_flag=True, help='Verbose output')
def main(config_file: str, validate: bool, parse: bool, output: str, summary: bool, verbose: bool):
    """
    Parse YAML configuration file for embedded peripheral setup.
    
    CONFIG_FILE: Path to the YAML configuration file
    
    Examples:
        app.py .\examples\advanced_board.yaml                      # Default: parse + validate + display
        app.py .\examples\advanced_board.yaml --summary            # Show detailed summary
        app.py .\examples\advanced_board.yaml --validate           # Validate only
        app.py .\examples\advanced_board.yaml --output config.json # Export to JSON
        app.py .\examples\advanced_board.yaml --verbose            # Verbose output with pin usage
    """
    
    # Print header
    console.print(Panel.fit(
        "[bold blue]Embedded Peripheral Configuration Parser[/bold blue]\n"
        "[dim]Clean YAML-based configuration parser for embedded peripherals[/dim]",
        border_style="blue"
    ))
    
    console.print(f"\n[yellow]📁 Loading configuration:[/yellow] [cyan]{config_file}[/cyan]")
    
    try:
        # Initialize parser and validator
        parser = YAMLConfigParser()
        validator = ConfigValidator()
        
        # Load configuration
        config = parser.load_config(config_file)
        console.print("[green]✓ Configuration loaded successfully[/green]")
        
        # Determine operation mode
        if validate:
            validate_only(config, validator, verbose)
        else:
            # As default parse and validate
            parse_and_display(config, parser, validator, output, summary, verbose)
    
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

def validate_only(config, validator, verbose: bool):
    """Validate configuration only and show results"""
    console.print("\n[yellow]🔍 Validating configuration...[/yellow]")
    
    # Run validation
    validation_result = validator.validate(config)
    
    # Display results
    if validation_result.has_errors():
        console.print("\n[red]❌ Validation Errors:[/red]")
        for error in validation_result.errors:
            console.print(f"  [red]•[/red] {error}")
        
        console.print(f"\n[red]❌ Validation failed with {len(validation_result.errors)} error(s)[/red]")
        console.print("[red]🛑 Fix the errors above and try again[/red]")
        sys.exit(1)
    
    if validation_result.has_warnings():
        console.print("\n[yellow]⚠️  Validation Warnings:[/yellow]")
        for warning in validation_result.warnings:
            console.print(f"  [yellow]•[/yellow] {warning}")
        console.print("[yellow]✓ Validation passed with warnings[/yellow]")
    else:
        console.print("[green]✓ All validation checks passed[/green]")
    
    # Show validation details in verbose mode
    if verbose and validation_result.info_messages:
        console.print("\n[blue]ℹ️  Validation Info:[/blue]")
        for info in validation_result.info_messages:
            console.print(f"  [blue]•[/blue] {info}")
    
    console.print("\n[green]🎉 Validation completed successfully![/green]")

def parse_and_display(config, parser, validator, output: str, summary: bool, verbose: bool):
    """Parse, validate, and display configuration"""
    
    # Always validate first
    console.print("\n[yellow]🔍 Validating configuration...[/yellow]")
    validation_result = validator.validate(config)
    
    # Check for validation errors
    if validation_result.has_errors():
        console.print("\n[red]❌ Validation Errors:[/red]")
        for error in validation_result.errors:
            console.print(f"  [red]•[/red] {error}")
        
        console.print(f"\n[red]❌ Validation failed with {len(validation_result.errors)} error(s)[/red]")
        console.print("[red]🛑 Stopping execution due to validation errors[/red]")
        console.print("[dim]Fix the errors above and try again[/dim]")
        sys.exit(1)
    
    # Show validation warnings
    if validation_result.has_warnings():
        console.print("\n[yellow]⚠️  Validation Warnings:[/yellow]")
        for warning in validation_result.warnings:
            console.print(f"  [yellow]•[/yellow] {warning}")
        console.print("[yellow]✓ Validation passed with warnings[/yellow]")
    else:
        console.print("[green]✓ All validation checks passed[/green]")
    
    # Summary report
    if summary or verbose:
        console.print("\n" + "="*60)
        parser.generate_summary_report()
        console.print("="*60)
    
    # Verbose pin usage summary
    if verbose:
        show_pin_usage_summary(config)
    
    # Export to JSON if requested
    if output:
        parser.export_to_json(output)
    
    # Default JSON output if no other output specified
    if not summary and not verbose and not output:
        import json
        from dataclasses import asdict
        config_dict = asdict(config)

        # Cleanup nulls
        cleaned_config = remove_nulls(config_dict)

        print(json.dumps(cleaned_config, indent=2))
    
    console.print("\n[green]🎉 Processing completed successfully![/green]")

def remove_nulls(obj):
    """Null cleaner"""

    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            cleaned_v = remove_nulls(v)
            # Add if not null, empty string or empty list
            if cleaned_v is not None and cleaned_v != "" and cleaned_v != []:
                result[k] = cleaned_v
        return result
    elif isinstance(obj, list):
        return [remove_nulls(item) for item in obj if item is not None]
    else:
        return obj

def show_pin_usage_summary(config):
    """Show detailed pin usage summary"""
    used_pins = set(config.get_all_used_pins())
    
    console.print(f"\n[bold cyan]📌 Pin Usage Summary:[/bold cyan]")
    console.print(f"Total pins used: [yellow]{len(used_pins)}[/yellow]")
    if used_pins:
        sorted_pins = sorted(used_pins)
        console.print(f"Pins: [cyan]{', '.join(sorted_pins)}[/cyan]")

if __name__ == "__main__":
    main()