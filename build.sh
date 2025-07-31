#!/bin/bash

# Synergy Screen Monitor - NanoMQ Build Script
# Automates the building of NanoSDK and Python bindings

set -e  # Exit on any error

echo "=== Synergy Screen Monitor - NanoMQ Build Script ==="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check for required tools
check_dependencies() {
    print_status "Checking build dependencies..."
    
    local missing_deps=()
    
    if ! command -v cmake &> /dev/null; then
        missing_deps+=("cmake")
    fi
    
    if ! command -v python3 &> /dev/null; then
        missing_deps+=("python3")
    fi
    
    if ! command -v pip3 &> /dev/null; then
        missing_deps+=("pip3")
    fi
    
    # Check for C++ compiler
    if ! command -v g++ &> /dev/null && ! command -v clang++ &> /dev/null; then
        missing_deps+=("g++ or clang++")
    fi
    
    if [ ${#missing_deps[@]} -ne 0 ]; then
        print_error "Missing required dependencies: ${missing_deps[*]}"
        echo ""
        echo "Please install the missing dependencies:"
        echo "  macOS: brew install cmake"
        echo "  Ubuntu/Debian: sudo apt-get install cmake build-essential python3-dev"
        echo "  CentOS/RHEL: sudo yum install cmake gcc-c++ python3-devel"
        exit 1
    fi
    
    print_status "All build dependencies are available"
}

# Initialize and update git submodules
init_submodules() {
    print_status "Initializing git submodules..."
    
    if [ ! -e "external/nanosdk/.git" ]; then
        print_error "NanoSDK submodule not found. Please run: git submodule update --init --recursive"
        exit 1
    fi
    
    # Update submodules to latest (skip failed ones)
    if ! git submodule update --recursive; then
        print_warning "Some submodules failed to update, continuing with available modules"
        # Try to update just the main NanoSDK without recursive
        git submodule update external/nanosdk || true
    fi
    print_status "Git submodules updated"
}

# Build NanoSDK using CMake
build_nanosdk() {
    print_status "Building NanoSDK..."
    
    # Create build directory
    mkdir -p build
    cd build
    
    # Configure CMake (disable QUIC to avoid problematic dependencies)
    cmake .. \
        -DCMAKE_BUILD_TYPE=Release \
        -DBUILD_SHARED_LIBS=OFF \
        -DNNG_ENABLE_MQTT=ON \
        -DNNG_ENABLE_QUIC=OFF \
        -DNNG_TESTS=OFF \
        -DNNG_TOOLS=OFF \
        -DCMAKE_POSITION_INDEPENDENT_CODE=ON
    
    # Build with portable CPU detection
    CPU_COUNT=$(python3 -c "import os; print(os.cpu_count() or 4)" 2>/dev/null || echo 4)
    cmake --build . --config Release --parallel $CPU_COUNT
    
    cd ..
    print_status "NanoSDK build completed"
}

# Install Python build dependencies
install_python_deps() {
    print_status "Installing Python build dependencies..."
    
    # Install build requirements
    pip3 install --upgrade pip
    pip3 install -r requirements.txt
    pip3 install pybind11 cmake
    
    print_status "Python dependencies installed"
}

# Build Python extension
build_python_extension() {
    print_status "Building Python extension..."
    
    # Try setuptools first, fall back to manual compilation
    if python3 setup.py build_ext --inplace 2>/dev/null; then
        print_status "Python extension built successfully"
        return 0
    fi
    
    print_warning "setuptools build failed, trying manual compilation..."
    
    # Manual compilation as fallback
    python3_config=$(which python3-config)
    if [ -z "$python3_config" ]; then
        print_error "python3-config not found. Please install python3-dev package"
        exit 1
    fi
    
    # Get Python include and library paths
    PYTHON_INCLUDE=$(python3 -c "import sysconfig; print(sysconfig.get_path('include'))")
    PYBIND11_INCLUDE=$(python3 -c "import pybind11; print(pybind11.get_include())")
    
    # Get Python library path
    PYTHON_LIB_DIR=$(python3 -c "import sysconfig; print(sysconfig.get_config_var('LIBDIR'))")
    PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    
    # Platform-specific linking
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS: link against Python framework
        PYTHON_LINK_FLAGS="-undefined dynamic_lookup"
    else
        # Linux: link against Python library
        PYTHON_LINK_FLAGS="-L$PYTHON_LIB_DIR -lpython$PYTHON_VERSION"
    fi
    
    # Compile the extension manually
    g++ -O3 -Wall -shared -std=c++17 -fPIC \
        -I"$PYTHON_INCLUDE" \
        -I"$PYBIND11_INCLUDE" \
        -Iexternal/nanosdk/include \
        -Iexternal/nanosdk/src/core \
        mqtt_clients/nanomq_bindings.cpp \
        -Lbuild -Lbuild/external/nanosdk \
        -lnng \
        $PYTHON_LINK_FLAGS \
        -o nanomq_bindings$(python3-config --extension-suffix)
    
    if [ $? -eq 0 ]; then
        print_status "Python extension built manually"
    else
        print_error "Manual compilation failed"
        exit 1
    fi
}

# Test the build
test_build() {
    print_status "Testing the build..."
    
    # Test importing the extension
    python3 -c "
import sys
sys.path.insert(0, '.')
try:
    import nanomq_bindings
    print('✓ NanoMQ bindings imported successfully')
except ImportError as e:
    print(f'✗ Failed to import NanoMQ bindings: {e}')
    sys.exit(1)

try:
    from mqtt_clients.nanomq_client import NanoMQTTPublisher, NanoMQTTSubscriber
    print('✓ NanoMQ client classes imported successfully')
except ImportError as e:
    print(f'✗ Failed to import NanoMQ client classes: {e}')
    sys.exit(1)

try:
    from mqtt_clients.factory import MQTTClientFactory
    clients = MQTTClientFactory.get_supported_clients()
    if 'nanomq' in clients:
        print('✓ NanoMQ client type is supported in factory')
    else:
        print(f'✗ NanoMQ client type not found in supported clients: {clients}')
        sys.exit(1)
except Exception as e:
    print(f'✗ Factory test failed: {e}')
    sys.exit(1)

print('All build tests passed!')
"
    
    print_status "Build test completed successfully"
}

# Clean build artifacts
clean_build() {
    print_status "Cleaning build artifacts..."
    
    rm -rf build/
    rm -rf *.egg-info/
    find . -name "*.so" -delete
    find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    find . -name "*.pyc" -delete
    
    print_status "Build artifacts cleaned"
}

# Main build process
main() {
    local clean_first=false
    local skip_tests=false
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --clean)
                clean_first=true
                shift
                ;;
            --skip-tests)
                skip_tests=true
                shift
                ;;
            --help)
                echo "Usage: $0 [options]"
                echo ""
                echo "Options:"
                echo "  --clean        Clean build artifacts before building"
                echo "  --skip-tests   Skip build verification tests"
                echo "  --help         Show this help message"
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done
    
    # Clean if requested
    if [ "$clean_first" = true ]; then
        clean_build
    fi
    
    # Execute build steps
    check_dependencies
    init_submodules
    build_nanosdk
    install_python_deps
    build_python_extension
    
    # Test if not skipped
    if [ "$skip_tests" = false ]; then
        test_build
    fi
    
    echo ""
    print_status "Build completed successfully!"
    echo ""
    echo "You can now use NanoMQ client with:"
    echo "  python3 waldo.py --client-type nanomq"
    echo "  python3 found-him.py desktop_name --client-type nanomq"
    echo ""
}

# Run main function
main "$@"