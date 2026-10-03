; mdook-setup.iss - Inno Setup Script for Mdook
; Builds a 1-click Windows installer with desktop shortcut and PATH registration.

#define MyAppName "Mdook"
#define MyAppVersion "2.0.1"
#define MyAppPublisher "Mdook Contributors"
#define MyAppURL "https://github.com/nijuna/Mdook"
#define MyAppExeName "Mdook.exe"
#define MyCliExeName "mdook-cli.exe"

[Setup]
AppId={{E68F1F35-081B-4C61-B9BE-D6104F5E6B7A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=..\..\dist\installer
OutputBaseFilename=Mdook-Setup-x64
SetupIconFile=..\..\assets\icons\mdook.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "addtopath"; Description: "Add Mdook to user PATH environment variable"; GroupDescription: "System Integration:"; Flags: unchecked

[Files]
Source: "..\..\dist\Mdook.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\dist\mdook-cli.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\dist\mdook.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\assets\icons\mdook.ico"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "..\..\README.md"; DestDir: "{app}"; Flags: ignoreversion isreadme

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\mdook.ico"
Name: "{group}\Mdook CLI"; Filename: "{cmd}"; Parameters: "/K ""{app}\{#MyCliExeName}"" --help"; IconFilename: "{app}\assets\mdook.ico"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\mdook.ico"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; Tasks: addtopath; Check: NeedsAddPath(ExpandConstant('{app}'))

[Code]
function NeedsAddPath(Param: string): boolean;
var
  OrigPath: string;
begin
  if not RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', OrigPath)
  then begin
    Result := True;
    exit;
  end;
  Result := Pos(';' + UpperCase(Param) + ';', ';' + UpperCase(OrigPath) + ';') = 0;
end;

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
