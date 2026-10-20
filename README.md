# FU3 D-PHY

MIPI D-PHY receiver design repository for FU3 using the 22FDX-EXT PDK.

## Directory structure

```text
22fdx/
`-- rx/
    |-- analog/
    |-- digital/
    |-- top/
    `-- verification/
```

The receiver is divided into the following design areas:

- `analog/`: supporting analog circuits, such as bias, reference, clock, and calibration circuits.
- `digital/`: receiver control, lane-state logic, deserialization, and digital interfaces.
- `top/`: integration of the complete D-PHY receiver.
- `verification/`: shared testbenches, models, and verification environments.

## Technology and design environment

This project targets the GlobalFoundries 22FDX-EXT PDK.

The 22FDX-EXT PDK is proprietary and must not be committed to this
repository. Each designer must configure the PDK and EDA Tools
environment locally according to the project setup instructions.

## Required code header

All contributors must include the standard FTEL signature header in
every source code file. Copy the template from
[FTEL_signature.md](FTEL_signature.md), then replace all placeholders
with the correct author, email, date, and module information.
