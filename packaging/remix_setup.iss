; Inno Setup 6 — 社媒视频混剪 / 鲸点混剪部门版
; 编译：ISCC packaging\remix_setup.iss（需先 PyInstaller 产出 dist\社媒视频混剪）

#define MyAppName "社媒视频混剪"
#define MyAppNameAlt "鲸点混剪部门版"
#define MyAppVersion "0.3.4"
#define MyAppPublisher "鲸点"
#define MyAppExeName "社媒视频混剪.exe"

[Setup]
AppId={{A7C3E9F1-8B42-4D6E-9F21-B3C8D0E1F2A3}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}（{#MyAppNameAlt}）
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\JingDian\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\deliver_win
OutputBaseFilename=社媒视频混剪_Setup_v{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
; ChineseSimplified.isl is not shipped with every Inno Setup install.
; build_windows.ps1 downloads it next to this script when it can.
; English is always available so a missing translation does not block Setup.exe,
; and Setup.exe itself never blocks the portable folder.
#ifexist "ChineseSimplified.isl"
Name: "chinesesimplified"; MessagesFile: "ChineseSimplified.isl"
#endif
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加图标:"; Flags: unchecked

[Files]
Source: "..\dist\社媒视频混剪\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "启动 {#MyAppName}"; Flags: nowait postinstall skipifsilent
