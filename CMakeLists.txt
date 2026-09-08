cmake_minimum_required(VERSION 3.20)
project(x87trans VERSION 0.2.0 LANGUAGES C)
include(GNUInstallDirs)
include(CMakePackageConfigHelpers)
include(CheckCSourceCompiles)
check_c_source_compiles("int main(void) { unsigned __int128 x = 1; return (int)(x >> 64); }" X87TRANS_HAS_UINT128)
if(NOT X87TRANS_HAS_UINT128)
  message(FATAL_ERROR "x87trans currently requires unsigned __int128")
endif()
option(X87TRANS_BUILD_TOOLS "Build raw80 command-line clients" OFF)
option(X87TRANS_BUILD_EXAMPLES "Build example callers" OFF)
option(X87TRANS_BUILD_COMPAT "Build previous binary-family C API adapters" OFF)
option(X87TRANS_BUILD_TESTS "Build offline library tests" OFF)

add_library(x87trans
  src/context.c src/raw80.c
  src/fsin.c src/fcos.c src/fsincos.c src/fptan.c src/f2xm1.c
  src/fpatan.c src/fyl2x.c src/fyl2xp1.c
  src/arithmetic/soft_value.c src/arithmetic/wide.c src/arithmetic/finite.c
  src/trig/reduce.c src/trig/sin_cos.c src/trig/sincos.c
  src/trig/table.c src/trig/tiny.c
  src/log/logarithm.c src/constants/trig.c)
add_library(x87trans::x87trans ALIAS x87trans)
target_compile_features(x87trans PRIVATE c_std_11)
target_include_directories(x87trans
  PUBLIC $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
         $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>
  PRIVATE src)
set_target_properties(x87trans PROPERTIES
  C_VISIBILITY_PRESET hidden POSITION_INDEPENDENT_CODE ON
  VERSION ${PROJECT_VERSION} SOVERSION 0)
if(BUILD_SHARED_LIBS)
  target_compile_definitions(x87trans PUBLIC X87TRANS_SHARED PRIVATE X87TRANS_BUILDING)
endif()
if(CMAKE_C_COMPILER_ID MATCHES "Clang|GNU")
  target_compile_options(x87trans PRIVATE -Wall -Wextra -Werror)
endif()

if(X87TRANS_BUILD_TOOLS OR X87TRANS_BUILD_TESTS)
  add_executable(x87trans-cli tools/cli/main.c)
  target_link_libraries(x87trans-cli PRIVATE x87trans::x87trans)
  add_executable(x87trans-outcomes tools/cli/outcomes.c)
  target_link_libraries(x87trans-outcomes PRIVATE x87trans::x87trans)
endif()
if(X87TRANS_BUILD_TOOLS)
  add_executable(fsincos_skylake tools/cli/legacy_unary.c)
  add_executable(fpatan tools/cli/fpatan.c tools/cli/legacy_binary.c)
  add_executable(x87-log tools/cli/log.c tools/cli/legacy_binary.c)
  foreach(client fsincos_skylake fpatan x87-log)
    target_link_libraries(${client} PRIVATE x87trans::x87trans)
  endforeach()
endif()
if(X87TRANS_BUILD_COMPAT OR X87TRANS_BUILD_TESTS)
  add_library(fpatan-compat STATIC tools/compat/fpatan_library.c)
  add_library(log-compat STATIC tools/compat/log_library.c)
  foreach(adapter fpatan-compat log-compat)
    target_include_directories(${adapter} PUBLIC tools/compat)
    target_link_libraries(${adapter} PUBLIC x87trans::x87trans)
  endforeach()
endif()
if(X87TRANS_BUILD_EXAMPLES OR X87TRANS_BUILD_TESTS)
  add_executable(x87trans-example examples/evaluate.c)
  target_link_libraries(x87trans-example PRIVATE x87trans::x87trans)
endif()
if(X87TRANS_BUILD_TESTS)
  enable_testing()
  find_package(Python3 REQUIRED COMPONENTS Interpreter)
  find_package(Threads REQUIRED)
  # Compile the same private arithmetic into a test executable so shared builds
  # need not export internal functions just to exercise the independent oracle.
  add_executable(x87trans-finite-test tests/arithmetic/driver.c
    src/arithmetic/finite.c src/arithmetic/wide.c src/arithmetic/soft_value.c)
  target_compile_features(x87trans-finite-test PRIVATE c_std_11)
  target_include_directories(x87trans-finite-test PRIVATE src include)
  add_test(NAME finite-arithmetic COMMAND ${Python3_EXECUTABLE}
    ${CMAKE_CURRENT_SOURCE_DIR}/tests/arithmetic/check_finite.py $<TARGET_FILE:x87trans-finite-test>)
  add_executable(x87trans-api-test tests/api/test_api.c)
  target_link_libraries(x87trans-api-test PRIVATE x87trans::x87trans Threads::Threads)
  add_test(NAME api COMMAND x87trans-api-test)
  add_executable(fpatan-compat-test tests/api/test_fpatan_compat.c)
  target_link_libraries(fpatan-compat-test PRIVATE fpatan-compat)
  add_test(NAME fpatan-compat COMMAND fpatan-compat-test)
  add_executable(log-compat-test tests/api/test_log_compat.c)
  target_link_libraries(log-compat-test PRIVATE log-compat)
  add_test(NAME log-compat COMMAND log-compat-test)
  add_test(NAME example COMMAND x87trans-example)
  add_executable(x87trans-adapter-test tests/integration/test_adapter.c examples/emulator_adapter.c)
  target_include_directories(x87trans-adapter-test PRIVATE examples)
  target_link_libraries(x87trans-adapter-test PRIVATE x87trans::x87trans)
  add_test(NAME emulator-adapter COMMAND x87trans-adapter-test)
  add_test(NAME saved-witnesses COMMAND ${Python3_EXECUTABLE}
    ${CMAKE_CURRENT_SOURCE_DIR}/tests/regression/replay.py $<TARGET_FILE:x87trans-cli>)
  add_test(NAME witness-scorer-contract COMMAND ${Python3_EXECUTABLE}
    ${CMAKE_CURRENT_SOURCE_DIR}/tests/regression/test_replay.py)
  add_test(NAME saved-outcomes COMMAND ${Python3_EXECUTABLE}
    ${CMAKE_CURRENT_SOURCE_DIR}/tests/regression/outcomes.py $<TARGET_FILE:x87trans-outcomes>)
  add_test(NAME special-outcomes COMMAND ${Python3_EXECUTABLE}
    ${CMAKE_CURRENT_SOURCE_DIR}/tests/api/special_outcomes.py $<TARGET_FILE:x87trans-outcomes>)
  add_test(NAME captured-outcomes COMMAND ${Python3_EXECUTABLE}
    ${CMAKE_CURRENT_SOURCE_DIR}/tests/regression/outcomes.py $<TARGET_FILE:x87trans-outcomes>
    ${CMAKE_CURRENT_SOURCE_DIR}/tests/data/outcome-witnesses.json.gz)
  add_executable(x87trans-namespace-test tests/integration/test_namespace.c)
  target_link_libraries(x87trans-namespace-test PRIVATE x87trans::x87trans)
  add_test(NAME consumer-namespace COMMAND x87trans-namespace-test)
  add_test(NAME library-symbols COMMAND ${Python3_EXECUTABLE}
    ${CMAKE_CURRENT_SOURCE_DIR}/tests/integration/check_symbols.py
    ${CMAKE_NM} $<TARGET_FILE:x87trans>)
endif()

install(TARGETS x87trans EXPORT x87transTargets
  ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
  LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
  RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
install(DIRECTORY include/ DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
install(FILES LICENSE.md COPYING COPYING.LESSER
  DESTINATION ${CMAKE_INSTALL_DATADIR}/licenses/x87trans)
install(EXPORT x87transTargets NAMESPACE x87trans::
  DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/x87trans)
configure_package_config_file(cmake/x87transConfig.cmake.in
  ${CMAKE_CURRENT_BINARY_DIR}/x87transConfig.cmake
  INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/x87trans)
write_basic_package_version_file(${CMAKE_CURRENT_BINARY_DIR}/x87transConfigVersion.cmake
  VERSION ${PROJECT_VERSION} COMPATIBILITY SameMinorVersion)
# Derive relocation paths from the complete install layout, including multiarch
# lib directories. Explicit absolute install directories retain their meaning.
file(RELATIVE_PATH X87TRANS_PC_PREFIX_RELATIVE
  "${CMAKE_INSTALL_FULL_LIBDIR}/pkgconfig" "${CMAKE_INSTALL_PREFIX}")
foreach(directory LIBDIR INCLUDEDIR)
  if(IS_ABSOLUTE "${CMAKE_INSTALL_${directory}}")
    set(X87TRANS_PC_${directory} "${CMAKE_INSTALL_${directory}}")
  else()
    set(X87TRANS_PC_${directory} "\${prefix}/${CMAKE_INSTALL_${directory}}")
  endif()
endforeach()
configure_file(cmake/x87trans.pc.in ${CMAKE_CURRENT_BINARY_DIR}/x87trans.pc @ONLY)
install(FILES ${CMAKE_CURRENT_BINARY_DIR}/x87transConfig.cmake
  ${CMAKE_CURRENT_BINARY_DIR}/x87transConfigVersion.cmake
  DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/x87trans)
install(FILES ${CMAKE_CURRENT_BINARY_DIR}/x87trans.pc DESTINATION ${CMAKE_INSTALL_LIBDIR}/pkgconfig)
