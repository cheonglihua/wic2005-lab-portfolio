$ErrorActionPreference = "Stop"

$labRoot = Split-Path -Parent $PSScriptRoot
$resultsPath = Join-Path $PSScriptRoot "results.txt"
$previousLocation = Get-Location

$commands = @(
    "nodes",
    "net",
    "dump",
    "h1 ip neigh",
    "sh brctl showmacs s1",
    "h1 ping -c 3 h2",
    "h1 ip neigh",
    "sh brctl showmacs s1",
    "pingall",
    "link s1 h3 down",
    "pingall",
    "link s1 h3 up",
    "pingall",
    "h2 python3 -m http.server 80 --directory /lab/week-01/web &",
    "sh sleep 1",
    "h1 curl -sS h2",
    "exit"
)

$dockerArgs = @(
    "run", "--rm", "-i", "--privileged",
    "-v", "${labRoot}:/lab",
    "-w", "/lab",
    "firdaussahran/netlab-mininet:1.0",
    "mn", "--topo", "single,3", "--mac", "--switch", "lxbr",
    "--controller", "none"
)

Write-Host "Running Week 1 Mininet lab..."
try {
    Set-Location $labRoot
    $commands -join "`n" | docker @dockerArgs 2>&1 | Tee-Object -FilePath $resultsPath
    if ($LASTEXITCODE -ne 0) {
        throw "The Mininet container exited with code $LASTEXITCODE."
    }
}
finally {
    Set-Location $previousLocation
}

Write-Host "Saved transcript to $resultsPath"
