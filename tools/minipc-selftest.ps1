# MINI-PC local read-only self-test
# Purpose: collect machine-local evidence without changing configuration.
# Safe to re-run. Writes only a timestamped report under %USERPROFILE%\Trading\Logs.

$ErrorActionPreference = "Continue"
$ts = Get-Date -Format "yyyyMMdd-HHmmss"
$logDir = Join-Path $env:USERPROFILE "Trading\Logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$report = Join-Path $logDir "minipc-selftest-$ts.txt"

function Section([string]$name) {
    $line = "`n=== $name ==="
    $line | Tee-Object -FilePath $report -Append
}
function Line([string]$text) {
    $text | Tee-Object -FilePath $report -Append
}
function Run([string]$label, [scriptblock]$cmd) {
    Line "-- $label"
    try {
        (& $cmd 2>&1 | Out-String).TrimEnd() | Tee-Object -FilePath $report -Append
    } catch {
        Line ("ERROR: " + $_.Exception.Message)
    }
}

Section "IDENTITY"
Line ("Timestamp: " + (Get-Date -Format "o"))
Line ("ComputerName: " + $env:COMPUTERNAME)
Line ("UserProfile: " + $env:USERPROFILE)
Run "Windows version" { Get-ComputerInfo | Select-Object WindowsProductName,WindowsVersion,OsBuildNumber,OsArchitecture }
Run "Windows OS via CIM" {
    Get-CimInstance Win32_OperatingSystem |
      Select-Object Caption,Version,BuildNumber,OSArchitecture,LastBootUpTime
}

Section "POWER"
Run "Active power scheme" { powercfg /getactivescheme }
Run "Available sleep states" { powercfg /a }

Section "SECURITY"
Run "Defender service" { Get-Service WinDefend | Select-Object Status,StartType,Name }
Run "Firewall profiles" { Get-NetFirewallProfile | Select-Object Name,Enabled,DefaultInboundAction,DefaultOutboundAction }

Section "NETWORK"
Run "IPv4 addresses" { Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -notlike "127.*"} | Select-Object InterfaceAlias,IPAddress,PrefixLength }
Run "DNS resolution api.kraken.com" { Resolve-DnsName api.kraken.com | Select-Object -First 5 Name,Type,IPAddress }
Run "TCP 443 api.kraken.com" { Test-NetConnection api.kraken.com -Port 443 | Select-Object ComputerName,RemoteAddress,RemotePort,TcpTestSucceeded }
Run "PowerShell HTTPS Kraken AssetPairs" {
    $r = Invoke-WebRequest -UseBasicParsing -Uri "https://api.kraken.com/0/public/AssetPairs?pair=XBTEUR" -TimeoutSec 20
    "HTTP " + [int]$r.StatusCode + " bytes=" + $r.RawContentLength
}

Section "LOCAL PROJECT"
$repo = Join-Path $env:USERPROFILE "Trading\Repos\kraken-eur-scanner"
$venvPy = Join-Path $env:USERPROFILE "Trading\Runtime\kraken-eur-scanner-venv\Scripts\python.exe"
Line ("RepoPathExists: " + (Test-Path $repo))
Line ("VenvPythonExists: " + (Test-Path $venvPy))
if (Test-Path $repo) {
    Push-Location $repo
    Run "Git version" { git --version }
    Run "Git branch" { git branch --show-current }
    Run "Git remote" { git remote -v }
    Run "Git status" { git status --short --branch }
    Run "Git HEAD" { git log -1 --oneline }
    Pop-Location
}
if (Test-Path $venvPy) {
    Run "Venv Python version" { & $venvPy --version }
    Run "Venv pip version" { & $venvPy -m pip --version }
    Run "Python TLS defaults" { & $venvPy -c "import ssl; print(ssl.OPENSSL_VERSION); print(ssl.get_default_verify_paths())" }
    Run "Python HTTPS Kraken AssetPairs" {
        & $venvPy -c "import urllib.request; u='https://api.kraken.com/0/public/AssetPairs?pair=XBTEUR'; r=urllib.request.urlopen(u, timeout=20); print('HTTP', r.status, 'bytes', len(r.read()))"
    }
}

Section "DISK"
Run "C drive capacity" {
    Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'" |
      Select-Object DeviceID,@{n='SizeGB';e={[math]::Round($_.Size/1GB,1)}},@{n='FreeGB';e={[math]::Round($_.FreeSpace/1GB,1)}}
}

Section "STORAGE HEALTH"
Run "Physical disk health" {
    Get-PhysicalDisk -ErrorAction SilentlyContinue |
      Select-Object FriendlyName,MediaType,HealthStatus,OperationalStatus,
        @{n='SizeGB';e={[math]::Round($_.Size/1GB,1)}}
}
Run "Reliability counters (if supported)" {
    Get-PhysicalDisk -ErrorAction SilentlyContinue | ForEach-Object {
        $disk = $_
        try {
            $r = $disk | Get-StorageReliabilityCounter -ErrorAction Stop
            [PSCustomObject]@{
                FriendlyName = $disk.FriendlyName
                Temperature = $r.Temperature
                Wear = $r.Wear
                PowerOnHours = $r.PowerOnHours
                ReadErrorsTotal = $r.ReadErrorsTotal
                WriteErrorsTotal = $r.WriteErrorsTotal
            }
        } catch {
            [PSCustomObject]@{ FriendlyName=$disk.FriendlyName; Detail="Reliability counters unsupported/unavailable" }
        }
    }
}

Section "BASE LOAD"
Run "CPU / RAM snapshot" {
    $os = Get-CimInstance Win32_OperatingSystem
    $cpu = Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average
    [PSCustomObject]@{
        CpuLoadPct = [math]::Round([double]$cpu.Average,1)
        TotalRamGB = [math]::Round($os.TotalVisibleMemorySize/1MB,1)
        FreeRamGB = [math]::Round($os.FreePhysicalMemory/1MB,1)
        UsedRamPct = [math]::Round((1-($os.FreePhysicalMemory/$os.TotalVisibleMemorySize))*100,1)
    }
}

Section "LOCAL TASKS"
Run "Crypto MINI-PC scheduled tasks" {
    Get-ScheduledTask -TaskName "CryptoMiniPC-*" -ErrorAction SilentlyContinue |
      ForEach-Object {
        $info = $_ | Get-ScheduledTaskInfo
        [PSCustomObject]@{
            TaskName = $_.TaskName
            State = $_.State
            LastRunTime = $info.LastRunTime
            LastTaskResult = $info.LastTaskResult
            NextRunTime = $info.NextRunTime
        }
      }
}
Run "Latest backup" {
    $backupDir = Join-Path $env:USERPROFILE "Trading\Backup"
    $latest = Get-ChildItem $backupDir -File -Filter "minipc-state-*.zip" -ErrorAction SilentlyContinue |
      Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($latest) {
        [PSCustomObject]@{
            Name=$latest.Name
            LastWriteTime=$latest.LastWriteTime
            SizeKB=[math]::Round($latest.Length/1KB,1)
            AgeHours=[math]::Round(((Get-Date)-$latest.LastWriteTime).TotalHours,2)
        }
    } else {
        "No MINI-PC state backup found"
    }
}

Section "RECENT SYSTEM ERRORS"
Run "Critical/Error events last 24h (max 20)" {
    Get-WinEvent -FilterHashtable @{LogName='System'; Level=1,2; StartTime=(Get-Date).AddHours(-24)} -ErrorAction SilentlyContinue |
      Select-Object -First 20 TimeCreated,Id,ProviderName,LevelDisplayName,Message
}

Section "RESULT"
Line ("Report: " + $report)
Write-Host "`nSelf-test complete. Report: $report"
