# Add design-specific lint waivers here.
# Each waiver names the rtl_rule item, the RTL decision (doc/rtl_notes.md) and the REQs behind it.

# rtl_rule K2 (4), rtl_notes D-19, REQ-343, REQ-364 (HAS §4.1, §4.3): in the clock structure of
# Block No. 1 the output of the reset synchronizer of the byte-clock enable is, by design, both the
# reset of the divider and the load phase and the enable of the clock gate of rxbyteclkhs.
waive -du "m_ftel_dphy_rx_byte_clk" -rule "STARC05-1.3.1.3" -comment "rtl_rule K2(4), rtl_notes D-19, REQ-343, REQ-364: the gate-enable reset synchronizer also resets the divider"
