cmake_minimum_required(VERSION 3.28)
project(chext_template)

add_compile_definitions(SC_DISABLE_API_VERSION_CHECK)
add_compile_definitions(SC_ALLOW_DEPRECATED_IEEE_API)

cmake_policy(SET CMP0167 OLD)

find_package(Boost 1.80 REQUIRED COMPONENTS endian program_options)
find_package(SystemCLanguage REQUIRED)
find_package(verilator REQUIRED)
find_package(fmt REQUIRED)

find_package(hdlscw REQUIRED)
find_package(chext_test REQUIRED)

include(CMakeParseArguments)

file(
    GLOB_RECURSE
    COMMON_SRCS
    CONFIGURE_DEPENDS
    "${CMAKE_SOURCE_DIR}/_common/src/*.c"
    "${CMAKE_SOURCE_DIR}/_common/src/*.cc"
    "${CMAKE_SOURCE_DIR}/_common/src/*.cpp"
)

function(generate_tb)
    set(options "")
    set(oneValueArgs TARGET_NAME HDL_DIR)
    set(multiValueArgs CPP_SOURCES HDL_MODULES VERILATOR_ARGS CPP_DEFS)
    cmake_parse_arguments(GEN_TB "${options}" "${oneValueArgs}" "${multiValueArgs}" ${ARGN})

    if(NOT GEN_TB_HDL_DIR)
        set(GEN_TB_HDL_DIR hdl)
    endif()

    add_executable(${GEN_TB_TARGET_NAME})
    set_target_properties(${GEN_TB_TARGET_NAME} PROPERTIES OUTPUT_NAME ${GEN_TB_TARGET_NAME})
    target_compile_definitions(${GEN_TB_TARGET_NAME} PUBLIC ${GEN_TB_CPP_DEFS})

    foreach(SOURCE_FILE IN LISTS GEN_TB_CPP_SOURCES)
        target_sources(
            ${GEN_TB_TARGET_NAME}
            PUBLIC
            ${CMAKE_CURRENT_SOURCE_DIR}/${SOURCE_FILE}
        )
    endforeach()

    foreach(SOURCE_FILE IN LISTS COMMON_SRCS)
        target_sources(
            ${GEN_TB_TARGET_NAME}
            PUBLIC
            ${SOURCE_FILE}
        )
    endforeach()

    target_include_directories(${GEN_TB_TARGET_NAME} PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
    target_include_directories(${GEN_TB_TARGET_NAME} PUBLIC ${CMAKE_SOURCE_DIR}/_common/include)

    target_link_libraries(
        ${GEN_TB_TARGET_NAME}
        PUBLIC
        SystemC::systemc
        fmt::fmt
        Boost::boost
        Boost::endian
        Boost::program_options
        hdlscw::hdlscw
        chext::chext_test
    )

    foreach(MODULE IN LISTS GEN_TB_HDL_MODULES)
        verilate(
            ${GEN_TB_TARGET_NAME}
            SYSTEMC
            SOURCES
                "${CMAKE_CURRENT_SOURCE_DIR}/${GEN_TB_HDL_DIR}/${MODULE}.sv"
            VERILATOR_ARGS
                "-I${CMAKE_SOURCE_DIR}/_common/verilog/"
                "-I${CMAKE_CURRENT_SOURCE_DIR}/${GEN_TB_HDL_DIR}/${MODULE}_include/"
                "${GEN_TB_VERILATOR_ARGS}"
        )

        hdlscw(
            TARGET ${GEN_TB_TARGET_NAME}
            HDLINFO
                "${CMAKE_CURRENT_SOURCE_DIR}/${GEN_TB_HDL_DIR}/${MODULE}.hdlinfo.json"
            ARGS
                "-r" "${CMAKE_SOURCE_DIR}/protocols.py"
        )
    endforeach()
endfunction()

# BEGIN MANAGED PACKAGES
add_subdirectory(chext_template)
# END MANAGED PACKAGES
