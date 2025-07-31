"""
Setup script for building NanoMQ Python bindings.

This script builds the NanoSDK C library and creates Python bindings
for MQTT client functionality.
"""

import os
import sys
import subprocess
import platform
from pathlib import Path
from setuptools import setup, Extension
from pybind11.setup_helpers import Pybind11Extension, build_ext
from pybind11 import get_cmake_dir
import pybind11


def build_nanosdk():
    """Build NanoSDK using CMake."""
    build_dir = Path("build")
    build_dir.mkdir(exist_ok=True)
    
    cmake_args = [
        f"-DCMAKE_BUILD_TYPE=Release",
        f"-DBUILD_SHARED_LIBS=OFF",
        f"-DNNG_ENABLE_MQTT=ON",
        f"-DNNG_ENABLE_QUIC=OFF",
        f"-DNNG_TESTS=OFF",
        f"-DNNG_TOOLS=OFF",
    ]
    
    # Platform-specific settings
    if platform.system() == "Darwin":
        cmake_args.append("-DCMAKE_OSX_DEPLOYMENT_TARGET=10.14")
    
    # Configure
    subprocess.check_call([
        "cmake", "-S", ".", "-B", "build"
    ] + cmake_args)
    
    # Build
    subprocess.check_call([
        "cmake", "--build", "build", "--config", "Release", "--parallel"
    ])
    
    return build_dir


class CustomBuildExt(build_ext):
    """Custom build extension that builds NanoSDK first."""
    
    def run(self):
        """Run the build process."""
        # Build NanoSDK first
        build_dir = build_nanosdk()
        
        # Update library paths for linking
        for ext in self.extensions:
            ext.library_dirs.append(str(build_dir / "lib"))
            ext.library_dirs.append(str(build_dir / "external" / "nanosdk"))
        
        super().run()


# Define the extension module
ext_modules = [
    Pybind11Extension(
        "nanomq_bindings",
        sources=[
            "mqtt_clients/nanomq_bindings.cpp",
        ],
        include_dirs=[
            "external/nanosdk/include",
            "external/nanosdk/src/core",
            pybind11.get_include(),
        ],
        libraries=["nng"],
        library_dirs=[
            "build/lib",
            "build/external/nanosdk",
        ],
        language="c++",
        cxx_std=17,
    ),
]

setup(
    name="synergy-screen-monitor",
    version="1.0.0",
    author="Synergy Screen Monitor Team",
    description="MQTT monitoring system for Synergy with NanoMQ support",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    ext_modules=ext_modules,
    cmdclass={"build_ext": CustomBuildExt},
    python_requires=">=3.8",
    install_requires=[
        "paho-mqtt>=2.0.0",
        "python-dotenv>=1.0.0",
    ],
    extras_require={
        "build": [
            "pybind11>=2.10.0",
            "cmake>=3.16.0",
        ],
        "dev": [
            "pytest>=8.0.0",
            "pytest-mock>=3.12.0",
            "pytest-cov>=4.1.0",
        ],
    },
    zip_safe=False,
)