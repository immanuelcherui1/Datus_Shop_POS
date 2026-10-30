Unicode true
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "x64.nsh"
!ifndef VERSION
!define VERSION "0.3.1"
!endif
!ifndef BUNDLE
!error "Supply /DBUNDLE=absolute path to the PyInstaller DATUS folder"
!endif
!ifndef OUTPUT
!error "Supply /DOUTPUT=absolute installer output file"
!endif

Name "DATUS Retail & Wholesale"
OutFile "${OUTPUT}"
InstallDir "$LOCALAPPDATA\Programs\DATUS"
RequestExecutionLevel user
SetCompressor /SOLID lzma
VIProductVersion "${VERSION}.0"
VIAddVersionKey "ProductName" "DATUS Retail & Wholesale"
VIAddVersionKey "FileDescription" "DATUS Windows Installer"
VIAddVersionKey "FileVersion" "${VERSION}"
VIAddVersionKey "ProductVersion" "${VERSION}"
VIAddVersionKey "LegalCopyright" "DATUS contributors"

!define MUI_ICON "${BUNDLE}\_internal\frontend\dist\branding\datus.ico"
!define MUI_UNICON "${BUNDLE}\_internal\frontend\dist\branding\datus.ico"
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TEXT "Install DATUS for this Windows account.$\r$\n$\r$\nPython, the shop interface and a private PostgreSQL database engine are included. No developer tools or internet connection are needed to run the installed application.$\r$\n$\r$\nOn first launch, create your shop owner account. Your business data is stored separately and kept when DATUS is uninstalled."
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\DATUS.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Open DATUS and set up my shop"
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "DATUS requires 64-bit Windows 11."
    Abort
  ${EndIf}
  System::Call 'kernel32::OpenMutexW(i 0x100000, i 0, w "Local\DATUS-Desktop") p.r0'
  ${If} $0 != 0
    System::Call 'kernel32::CloseHandle(p r0)'
    MessageBox MB_ICONSTOP "Close the DATUS desktop window before installing or updating. Business data will be kept."
    Abort
  ${EndIf}
FunctionEnd

Section "DATUS application (required)" SEC_APP
  SectionIn RO
  SetShellVarContext current
  SetOutPath "$INSTDIR"
  File /r "${BUNDLE}\*.*"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateDirectory "$SMPROGRAMS\DATUS"
  CreateShortcut "$SMPROGRAMS\DATUS\DATUS.lnk" "$INSTDIR\DATUS.exe"
  CreateShortcut "$SMPROGRAMS\DATUS\Uninstall DATUS.lnk" "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DATUS" "DisplayName" "DATUS Retail & Wholesale"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DATUS" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DATUS" "UninstallString" '$\"$INSTDIR\Uninstall.exe$\"'
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DATUS" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DATUS" "DisplayIcon" "$INSTDIR\DATUS.exe,0"
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DATUS" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DATUS" "NoRepair" 1
SectionEnd

Section "Desktop shortcut" SEC_DESKTOP
  CreateShortcut "$DESKTOP\DATUS.lnk" "$INSTDIR\DATUS.exe"
SectionEnd

Section /o "Open DATUS when I sign in" SEC_STARTUP
  CreateShortcut "$SMSTARTUP\DATUS.lnk" "$INSTDIR\DATUS.exe"
SectionEnd

Function un.onInit
  System::Call 'kernel32::OpenMutexW(i 0x100000, i 0, w "Local\DATUS-Desktop") p.r0'
  ${If} $0 != 0
    System::Call 'kernel32::CloseHandle(p r0)'
    MessageBox MB_ICONSTOP "Close DATUS before uninstalling. Your database and backups will be kept."
    Abort
  ${EndIf}
FunctionEnd

Section "Uninstall"
  SetShellVarContext current
  Delete "$DESKTOP\DATUS.lnk"
  Delete "$SMSTARTUP\DATUS.lnk"
  Delete "$SMPROGRAMS\DATUS\DATUS.lnk"
  Delete "$SMPROGRAMS\DATUS\Uninstall DATUS.lnk"
  RMDir "$SMPROGRAMS\DATUS"
  Delete "$INSTDIR\DATUS.exe"
  RMDir /r "$INSTDIR\_internal"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DATUS"
  ; Never remove $LOCALAPPDATA\DATUS: it contains the user's database, credentials and backups.
SectionEnd
