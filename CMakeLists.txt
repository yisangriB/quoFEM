cmake_minimum_required(VERSION 3.21)

project(quoFEM VERSION 1.0.0 LANGUAGES C CXX)

# ---- C++17 ----
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ---- Qt ----
find_package(Qt6 REQUIRED COMPONENTS
  Core Gui Widgets
  Charts Concurrent Network PrintSupport
  3DCore 3DRender 3DExtras
  WebEngineWidgets WebEngineCore
)

set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTOUIC ON)
set(CMAKE_AUTORCC ON)

# ---- Conan Packages -----
find_package(jansson REQUIRED)
find_package(ZLIB REQUIRED)
find_package(CURL REQUIRED)

# ---- Resources, Forms, and Icons ----
set(RESOURCES styles.qrc)
set(FORMS mainwindow.ui)

if(APPLE)
    set(MACOSX_BUNDLE_ICON_FILE NHERI-quoFEM-Icon.icns)
    set(APP_ICON icons/NHERI-quoFEM-Icon.icns)
    set_source_files_properties(${APP_ICON} PROPERTIES MACOSX_PACKAGE_LOCATION Resources)
elseif(WIN32)
    set(APP_ICON icons/NHERI-quoFEM-Icon.ico)
endif()


# ---- Sources and Headers ----

set(SOURCES
    main.cpp
    WorkflowApp_quoFEM.cpp
    main.cpp
    WorkflowApp_quoFEM.cpp
    RunWidget.cpp
    EDP/quoEDP.cpp
    EDP/InputWidgetEDP.cpp
    FEM/FEM_Selection.cpp
    FEM/OpenSeesFEM.cpp
    FEM/OpenSeesPyFEM.cpp
    FEM/FEAPpvFEM.cpp
    FEM/FEAPpvParser.cpp
    FEM/OpenSeesPyParser.cpp
    FEM/surrogateGpFEM.cpp
    FEM/surrogateGpParser.cpp
    FEM/CustomFEM.cpp
)

set(HEADERS
  WorkflowApp_quoFEM.h
  RunWidget.h
  EDP/InputWidgetEDP.h
  EDP/quoEDP.h
  FEM/FEM_Selection.h
  FEM/OpenSeesFEM.h
  FEM/OpenSeesPyFEM.h
  FEM/FEAPpvFEM.h
  FEM/FEAPpvParser.h
  FEM/OpenSeesPyParser.h
  FEM/surrogateGpFEM.h
  FEM/surrogateGpParser.h
  FEM/CustomFEM.h
)	

# ---- Define Target and add ----
set(TARGET_NAME quoFEM)

add_executable(${TARGET_NAME}
    ${APP_ICON}
    ${RESOURCES}
    ${FORMS}
    ${SOURCES}
    ${HEADERS}
)

# ---- Compiler Options -----
target_compile_definitions(${TARGET_NAME} PRIVATE
    APP_VERSION="${PROJECT_VERSION}"
    _GRAPHICS_Qt3D
)

if(WIN32)
    target_compile_definitions(${TARGET_NAME} PRIVATE USE_SIMCENTER_PYTHON)
    target_link_libraries(${TARGET_NAME} PRIVATE Advapi32)
elseif(APPLE)
    set_target_properties(${TARGET_NAME} PROPERTIES
        MACOSX_BUNDLE TRUE
        MACOSX_BUNDLE_INFO_PLIST ${CMAKE_CURRENT_SOURCE_DIR}/Info.plist
    )
elseif(UNIX AND NOT APPLE)
    target_link_libraries(${TARGET_NAME} PRIVATE glut GLU GL)
endif()


# ---- Include paths (from .pro) ----
target_include_directories(${PROJECT_NAME} PRIVATE
  ${CMAKE_CURRENT_LIST_DIR}/FEM
  ${CMAKE_CURRENT_LIST_DIR}/EDP
  ${CMAKE_CURRENT_LIST_DIR}/../SimCenterCommon/RandomVariables
  ${CMAKE_CURRENT_LIST_DIR}/../SimCenterCommon/Workflow/WORKFLOW
)


# =============================================================================
# Source-in modules (replacing .pri includes)
# =============================================================================

# Common (also pulls in ZipUtils via include + simcenter_add_ziputils)
include(${CMAKE_CURRENT_LIST_DIR}/../SimCenterCommon/Common/Common.cmake)
simcenter_add_common(${PROJECT_NAME})

# RandomVariables
include(${CMAKE_CURRENT_LIST_DIR}/../SimCenterCommon/RandomVariables/RandomVariables.cmake)
simcenter_add_randomvariables(${PROJECT_NAME})

# InputSheetBM
include(${CMAKE_CURRENT_LIST_DIR}/../SimCenterCommon/InputSheetBM/InputSheet.cmake)
simcenter_add_inputsheet(${PROJECT_NAME})

# Workflow
include(${CMAKE_CURRENT_LIST_DIR}/../SimCenterCommon/Workflow/Workflow.cmake)
simcenter_add_workflow(${PROJECT_NAME})

# ---- Link libreraies ----
target_link_libraries(${TARGET_NAME} PRIVATE
  Qt6::Core Qt6::Gui Qt6::Widgets
  Qt6::Charts Qt6::Concurrent Qt6::Network Qt6::PrintSupport
  Qt6::3DCore Qt6::3DRender Qt6::3DExtras
  Qt6::WebEngineWidgets Qt6::WebEngineCore
  jansson::jansson
  ZLIB::ZLIB
  CURL::libcurl
)

# ---- Platform-specific libs ----
if(WIN32)
  target_link_libraries(${PROJECT_NAME} PRIVATE Advapi32)
  set_target_properties(${PROJECT_NAME} PROPERTIES WIN32_EXECUTABLE TRUE)  
endif()

if(UNIX AND NOT APPLE)
  # Mirrors qmake: -lglut -lGLU -lGL
  find_package(OpenGL REQUIRED)
  find_package(GLUT)
  if(GLUT_FOUND)
    target_link_libraries(${PROJECT_NAME} PRIVATE OpenGL::GL OpenGL::GLU GLUT::GLUT)
  else()
    target_link_libraries(${PROJECT_NAME} PRIVATE OpenGL::GL OpenGL::GLU)
  endif()
endif()

# ---- macOS bundle bits (icon + Info.plist) ----
if(APPLE)
  set_target_properties(${PROJECT_NAME} PROPERTIES
    MACOSX_BUNDLE TRUE
    MACOSX_BUNDLE_INFO_PLIST "${CMAKE_CURRENT_LIST_DIR}/Info.plist"
  )

  set(MAC_ICON "${CMAKE_CURRENT_LIST_DIR}/icons/NHERI-quoFEM-Icon.icns")
  target_sources(${PROJECT_NAME} PRIVATE "${MAC_ICON}")
  set_source_files_properties("${MAC_ICON}" PROPERTIES MACOSX_PACKAGE_LOCATION "Resources")
endif()

# ---- Windows icon (recommended approach) ----
# qmake: RC_ICONS = icons/NHERI-quoFEM-Icon.ico
# In CMake, you normally add a .rc file. Example:
#   appicon.rc:  IDI_ICON1 ICON "icons/NHERI-${PROJECT_NAME}-Icon.ico"
if(WIN32)
  if(EXISTS "${CMAKE_CURRENT_LIST_DIR}/icons/appicon.rc")
    target_sources({PROJECT_NAME} PRIVATE "${CMAKE_CURRENT_LIST_DIR}/icons/appicon.rc")
  endif()
endif()



