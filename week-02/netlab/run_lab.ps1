$ErrorActionPreference = "Stop"
$labRoot = $PSScriptRoot

Write-Host "Starting the Week 2 Mininet container from $labRoot"
docker run -it --rm --privileged -v "${labRoot}:/lab" -w /lab `
    firdaussahran/netlab-mininet:1.0 `
    python3 build_topo.py topology.yaml

if ($LASTEXITCODE -ne 0) {
    throw "The Week 2 Mininet container exited with code $LASTEXITCODE."
}
