#!/usr/bin/env bash
# ============================================================================
# Key numbers of each run in syn/output/: WNS and TNS per clock group, cells, the Block No. 1
# paths of doc/rtl_notes.md §6, violators and area per block (lanes summed). Times in the unit of
# the library (ps for [target library]), area in um2.
# ============================================================================
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
slack() { grep -m1 -E "slack \((MET|VIOLATED)" "$1" 2>/dev/null | awk '{print $NF}'; }
for r in "$HERE"/output/*/; do
  r=${r%/}
  [[ -f "$r/qor.rpt" ]] || continue
  echo "== ${r##*/}"
  awk '/Timing Path Group/ {g = $4}
       /Critical Path Slack:/ {s = $4}
       /Total Negative Slack:/ {printf "   %-12s WNS %9s   TNS %s\n", g, s, $4}' "$r/qor.rpt"
  grep -E "Leaf Cell Count|Sequential Cell Count|Cell Area:" "$r/qor.rpt" | sed 's/^ */   /'
  printf "   %-30s %s\n" \
    "samplers"                  "$(slack "$r/b1_samplers.rpt")" \
    "half period load->load_fall" "$(slack "$r/b1_half_period.rpt")" \
    "parallel->byte, setup"     "$(slack "$r/b1_par2byte_setup.rpt")" \
    "parallel->byte, hold"      "$(slack "$r/b1_par2byte_hold.rpt")" \
    "clock gate enable"         "$(slack "$r/b1_icg_enable.rpt")" \
    "divider reset recovery"    "$(slack "$r/b1_div_recovery.rpt")"
  echo "   violators: $(grep -c 'VIOLATED' "$r/violators.rpt")"
  awk '$1 ~ /^u_dphy_rx_0\// && $2 ~ /^[0-9.]+$/ {
         k = $1; gsub(/g_(lane|phy)\[[0-9]+\]\./, "", k); n = split(k, a, "/")
         if (n == 2 || (n == 3 && (a[3] == "u_eot_0" || a[3] == "u_sync_search_0" || a[2] == "u_afe_adapter_0")))
           s[k] += $2 }
       END { for (k in s) printf "   area %-50s %9.1f\n", k, s[k] }' "$r/area_hier.rpt" | sort
done
