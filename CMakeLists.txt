cmake_minimum_required(VERSION 3.16)
project(SynergyScreenMonitor LANGUAGES C CXX)

set(CMAKE_C_STANDARD 99)
set(CMAKE_CXX_STANDARD 17)

# Set build type to Release if not specified
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

# Options for NanoSDK build
option(NNG_ENABLE_MQTT "Enable MQTT protocol support" ON)
option(NNG_ENABLE_QUIC "Enable QUIC transport support" ON)
option(BUILD_SHARED_LIBS "Build shared libraries" OFF)

# Platform-specific settings
if(APPLE)
    set(CMAKE_OSX_DEPLOYMENT_TARGET "10.14")
endif()

# Add NanoSDK subdirectory
add_subdirectory(external/nanosdk)

# Create a target for the Python extension dependencies
add_library(nanomq_client_deps INTERFACE)

# Link NanoSDK libraries to our interface target
target_link_libraries(nanomq_client_deps INTERFACE nng)

# Include directories for Python extension
target_include_directories(nanomq_client_deps INTERFACE
    ${CMAKE_CURRENT_SOURCE_DIR}/external/nanosdk/include
    ${CMAKE_CURRENT_SOURCE_DIR}/external/nanosdk/src/core
)

# Export compile commands for development tools
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Installation rules
install(TARGETS nng
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
    RUNTIME DESTINATION bin
)

# Install headers
install(DIRECTORY external/nanosdk/include/
    DESTINATION include
    FILES_MATCHING PATTERN "*.h"
)