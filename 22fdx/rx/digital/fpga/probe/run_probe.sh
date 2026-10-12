#!/bin/bash
# Run the Vivado probes of fpga/probe in batch mode. Each probe writes into fpga/work/<probe>/
# (gitignored): vivado.log, stdout.txt and probe.txt (the "PROBE" result lines).
#   fpga/probe/run_probe.sh                     # all light probes
#   fpga/probe/run_probe.sh csi2_rx_no_phy      # one probe
#   fpga/probe/run_probe.sh impl_tiny           # a heavy probe: only by name, when the machine is idle
# VIVADO overrides the Vivado binary (default: Vivado 2025.2 of this machine).
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(dirname "$HERE")
VIVADO=${VIVADO:-/opt/xilinx/2025.2/Vivado/bin/vivado}
known=(csi2_rx_no_phy dphy_rx_versal iowiz_mipi_rx synth_tiny)
heavy=(impl_tiny dphy_exdes_sim)
probes=("$@")
[ ${#probes[@]} -eq 0 ] && probes=("${known[@]}")
status=0
for p in "${probes[@]}"; do
  if [[ ! " ${known[*]} ${heavy[*]} " == *" $p "* ]]; then
    echo "$p: unknown probe (light: ${known[*]}; heavy: ${heavy[*]})"
    status=1
    continue
  fi
  w="$ROOT/work/$p"
  mkdir -p "$w"
  if (cd "$w" && "$VIVADO" -mode batch -nojournal -log vivado.log -source "$HERE/$p.tcl" -tclargs "$w" \
        > stdout.txt 2>&1); then
    grep '^PROBE' "$w/stdout.txt" > "$w/probe.txt"
    if grep -q '^PROBE done' "$w/probe.txt"; then
      echo "$p: PASS ($(wc -l < "$w/probe.txt") lines in work/$p/probe.txt)"
      continue
    fi
  fi
  echo "$p: FAIL (see work/$p/vivado.log)"
  status=1
done
exit $status
