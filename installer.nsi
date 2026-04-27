; NSIS installer script for Bitdam
; Build:   makensis.exe installer.nsi
; Output:  installer_output\Bitdam-Setup-1.0.0.exe
;
; User-level install (no admin required):
;   - files to %LOCALAPPDATA%\Bitdam
;   - registry to HKCU so Windows "Apps & Features" shows it
;     without elevation
;
; Uninstall via standard Windows "Apps & Features" UI.

Unicode True

!define APPNAME         "Bitdam"
!define COMPANYNAME     "KyoungSeok Ko (artmouse)"
!define DESCRIPTION     "Screen capture to GIF / MP4"
!define VERSIONMAJOR    1
!define VERSIONMINOR    5
!define VERSIONBUILD    0
!define VERSIONSTR      "${VERSIONMAJOR}.${VERSIONMINOR}.${VERSIONBUILD}"
!define HELPURL         "https://github.com/kuoungseok/bitdam"
!define UPDATEURL       "https://github.com/kuoungseok/bitdam/releases"
!define ABOUTURL        "https://github.com/kuoungseok/bitdam"
!define INSTALLSIZE     352000         ; KB, rough; Windows shows this
!define UNINSTKEY       "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}"

RequestExecutionLevel   user
InstallDir              "$LOCALAPPDATA\${APPNAME}"
InstallDirRegKey        HKCU "Software\${APPNAME}" "InstallLocation"
Name                    "${APPNAME}"
OutFile                 "installer_output\${APPNAME}-Setup-${VERSIONSTR}.exe"
BrandingText            "${COMPANYNAME}"
Icon                    "resources\bitdam.ico"
UninstallIcon           "resources\bitdam.ico"
VIProductVersion        "${VERSIONMAJOR}.${VERSIONMINOR}.${VERSIONBUILD}.0"
VIAddVersionKey         "ProductName"       "${APPNAME}"
VIAddVersionKey         "FileDescription"   "${DESCRIPTION}"
VIAddVersionKey         "CompanyName"       "${COMPANYNAME}"
VIAddVersionKey         "FileVersion"       "${VERSIONSTR}"
VIAddVersionKey         "ProductVersion"    "${VERSIONSTR}"
VIAddVersionKey         "LegalCopyright"    "(C) ${COMPANYNAME}"

!include "MUI2.nsh"
!include "LogicLib.nsh"

!define MUI_ICON        "resources\bitdam.ico"
!define MUI_UNICON      "resources\bitdam.ico"
!define MUI_ABORTWARNING
!define MUI_FINISHPAGE_RUN "$INSTDIR\Bitdam.exe"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

!insertmacro MUI_LANGUAGE "Korean"
!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "Japanese"
!insertmacro MUI_LANGUAGE "German"

Function .onInit
    ; Pick installer UI language from system locale
    !insertmacro MUI_LANGDLL_DISPLAY
FunctionEnd

Section "Install"
    SetOutPath "$INSTDIR"

    ; Copy packaged app tree (must match PyInstaller's dist\Bitdam output)
    File /r "dist\Bitdam\*.*"

    ; Start Menu
    CreateDirectory "$SMPROGRAMS\${APPNAME}"
    CreateShortCut  "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk"       "$INSTDIR\Bitdam.exe" "" "$INSTDIR\Bitdam.exe"
    CreateShortCut  "$SMPROGRAMS\${APPNAME}\Uninstall ${APPNAME}.lnk" "$INSTDIR\uninstall.exe" "" "$INSTDIR\uninstall.exe"

    ; Desktop shortcut
    CreateShortCut  "$DESKTOP\${APPNAME}.lnk" "$INSTDIR\Bitdam.exe" "" "$INSTDIR\Bitdam.exe"

    ; Uninstaller
    WriteUninstaller "$INSTDIR\uninstall.exe"

    ; App registry
    WriteRegStr   HKCU "Software\${APPNAME}" "InstallLocation" "$INSTDIR"
    WriteRegStr   HKCU "Software\${APPNAME}" "Version"         "${VERSIONSTR}"

    ; Apps & Features entry (HKCU avoids admin elevation)
    WriteRegStr   HKCU "${UNINSTKEY}" "DisplayName"          "${APPNAME}"
    WriteRegStr   HKCU "${UNINSTKEY}" "DisplayVersion"       "${VERSIONSTR}"
    WriteRegStr   HKCU "${UNINSTKEY}" "DisplayIcon"          "$\"$INSTDIR\Bitdam.exe$\""
    WriteRegStr   HKCU "${UNINSTKEY}" "Publisher"            "${COMPANYNAME}"
    WriteRegStr   HKCU "${UNINSTKEY}" "InstallLocation"      "$\"$INSTDIR$\""
    WriteRegStr   HKCU "${UNINSTKEY}" "UninstallString"      "$\"$INSTDIR\uninstall.exe$\""
    WriteRegStr   HKCU "${UNINSTKEY}" "QuietUninstallString" "$\"$INSTDIR\uninstall.exe$\" /S"
    WriteRegStr   HKCU "${UNINSTKEY}" "HelpLink"             "${HELPURL}"
    WriteRegStr   HKCU "${UNINSTKEY}" "URLInfoAbout"         "${ABOUTURL}"
    WriteRegStr   HKCU "${UNINSTKEY}" "URLUpdateInfo"        "${UPDATEURL}"
    WriteRegDWORD HKCU "${UNINSTKEY}" "VersionMajor"         ${VERSIONMAJOR}
    WriteRegDWORD HKCU "${UNINSTKEY}" "VersionMinor"         ${VERSIONMINOR}
    WriteRegDWORD HKCU "${UNINSTKEY}" "NoModify"             1
    WriteRegDWORD HKCU "${UNINSTKEY}" "NoRepair"             1
    WriteRegDWORD HKCU "${UNINSTKEY}" "EstimatedSize"        ${INSTALLSIZE}
SectionEnd

Section "Uninstall"
    ; Remove shortcuts
    Delete "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk"
    Delete "$SMPROGRAMS\${APPNAME}\Uninstall ${APPNAME}.lnk"
    RMDir  "$SMPROGRAMS\${APPNAME}"
    Delete "$DESKTOP\${APPNAME}.lnk"

    ; Remove install tree (keeps user data in %USERPROFILE%\Videos\Bitdam)
    RMDir /r "$INSTDIR"

    ; Clean registry
    DeleteRegKey HKCU "${UNINSTKEY}"
    DeleteRegKey HKCU "Software\${APPNAME}"
    ; Keep user language preference at HKCU\Software\Bitdam\Bitdam so future
    ; install reuses it; remove explicitly if user wants a clean slate:
    ; DeleteRegKey HKCU "Software\Bitdam"
SectionEnd
