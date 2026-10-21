# DPHY — MIPI D-PHY Receiver

Local repository for designing a MIPI D-PHY receiver controller (D-PHY lanes → PPI)
that interoperates with a MIPI CSI-2 v1.3 transmitter.

## Layout

```
DPHY/
├── README.md                 ← this file
├── .gitignore                ← tool output (VCS, Verdi, Design Compiler, SpyGlass)
├── .claude/commands/         ← flow commands: /dphy_autoflow, /dphy_spec_parse
├── hw/                       ← same layout as the FX1 ip-dev repository
│   ├── utils/req_flow/       ← deterministic requirement tooling of the flow (see its README)
│   └── rtl/ip/
│       └── ftel_dphy_rx/     ← D-PHY Rx controller IP — see hw/rtl/ip/ftel_dphy_rx/README.md
└── ref/                      ← reference material, not design sources
    ├── spec/                 ← MIPI CSI-2 v1.3 and MIPI D-PHY v1.1 specifications (PDF)
    └── mipi_tx_dphy_model/   ← third-party example Tx behavioural model (illustrative only)
```

## Ground rules

- **Source of truth for transmitter behaviour is MIPI CSI-2 v1.3** (`ref/spec/`). The real
  transmitter is developed by a partner team against that specification.
- `ref/mipi_tx_dphy_model/` is an example stimulus only. Where it deviates from the
  specification, the specification wins; the Rx design must not depend on the model's quirks.
- Day-to-day work happens on branch `dev`.
