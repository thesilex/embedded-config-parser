#!/usr/bin/env python3
"""
Installation script for Embedded Peripheral Configuration Parser
This script sets up the development environment and installs dependencies.
"""

import sys
import subprocess
import platform
from pathlib import Path

def run_command(command, description, ignore_errors=False):
    """Run a command and handle errors"""
    print(f"[INFO] {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, 
                              capture_output=True, text=True)
        if result.stdout:
            print(f"[SUCCESS] {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        if ignore_errors:
            print(f"[WARNING] {description} failed (continuing anyway)")
            if e.stderr:
                print(f"[ERROR] {e.stderr.strip()}")
            return False
        else:
            print(f"[ERROR] {description} failed!")
            if e.stderr:
                print(f"[ERROR] {e.stderr.strip()}")
            return False

def check_python_version():
    """Check if Python version is compatible"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("[ERROR] Python 3.8 or higher is required!")
        print(f"[ERROR] Current version: {version.major}.{version.minor}.{version.micro}")
        return False
    
    print(f"[OK] Python version: {version.major}.{version.minor}.{version.micro}")
    return True

def setup_virtual_environment():
    """Create virtual environment if it doesn't exist"""
    venv_path = Path("venv")
    
    if venv_path.exists():
        print("[INFO] Virtual environment already exists")
        return True
    
    print("[INFO] Creating virtual environment...")
    success = run_command(f"{sys.executable} -m venv venv", 
                         "Creating virtual environment")
    
    if not success:
        print("[ERROR] Failed to create virtual environment")
        return False
    
    print("[OK] Virtual environment created successfully")
    return True

def get_pip_command():
    """Get the correct pip command for the platform"""
    system = platform.system().lower()
    if system == "windows":
        return "venv\\Scripts\\pip"
    else:
        return "venv/bin/pip"

def get_python_command():
    """Get the correct python command for the platform"""
    system = platform.system().lower()
    if system == "windows":
        return "venv\\Scripts\\python"
    else:
        return "venv/bin/python"

def install_python_dependencies():
    """Install Python package dependencies"""
    pip_cmd = get_pip_command()
    
    # Upgrade pip first
    print("[INFO] Upgrading pip...")
    run_command(f"{pip_cmd} install --upgrade pip", "Upgrading pip")
    
    # Install requirements
    if Path("requirements.txt").exists():
        print("[INFO] Installing dependencies from requirements.txt...")
        success = run_command(f"{pip_cmd} install -r requirements.txt", 
                             "Installing Python dependencies")
        if not success:
            return False
    else:
        print("[ERROR] requirements.txt not found!")
        print("[INFO] Please ensure requirements.txt exists in the current directory")
        return False
    
    return True

def test_installation():
    """Test if installation was successful"""
    print("[INFO] Testing installation...")
    
    python_cmd = get_python_command()
    
    # Test critical imports
    test_imports = [
        ("yaml", "PyYAML"),
        ("click", "Click"),
        ("rich", "Rich"),
        ("jsonschema", "JSONSchema")
    ]
    
    all_passed = True
    for module, name in test_imports:
        success = run_command(f'{python_cmd} -c "import {module}; print(\'{name}: OK\')"', 
                             f"Testing {name} import", 
                             ignore_errors=True)
        if not success:
            print(f"[ERROR] {name} import failed")
            all_passed = False
    
    return all_passed

def main():
    """Main installation function"""
    print("=" * 50)
    print("🔧 YAML Parser Installation")
    print("=" * 50)
    print("Installing dependencies only...")
    print()
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Setup virtual environment
    if not setup_virtual_environment():
        sys.exit(1)
    
    # Install Python dependencies
    if not install_python_dependencies():
        print("\n[ERROR] Failed to install dependencies!")
        sys.exit(1)
    
    # Test installation
    if not test_installation():
        print("\n[WARNING] Some tests failed, but installation may still work")
    
    print("\n" + "=" * 50)
    print("✅ Installation completed!")
    print("=" * 50)
    
    # Show activation instructions
    system = platform.system().lower()
    print("\nTo activate the virtual environment:")
    if system == "windows":
        print("   venv\\Scripts\\activate")
    else:
        print("   source venv/bin/activate")
    
    print("\nTo test the parser:")
    print("   python app.py --help")
    
    print("\n🎉 Ready to parse YAML configurations!")

if __name__ == "__main__":
    main()