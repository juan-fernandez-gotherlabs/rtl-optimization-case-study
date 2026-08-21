# Third-party notices and case licensing

The repository-level MIT License covers original portfolio presentation,
verification and packaging work unless a case or source file states otherwise.

## SHA-1 case

The SHA-1 RTL descends from the OpenCores core redistributed by the
Verilog-to-Routing project at pinned commit
`95f5c6de9e158371ba7185bf97c07a84153735d6`. Its source headers retain the
original copyright, redistribution condition and disclaimer. The VTR
architecture and technology files are referenced by identity and remain under
their upstream terms.

## INT8 MatVec case

The baseline and optimized INT8 MatVec RTL are original work copyright 2026
Juan José Fernández, authored for this Evolther/Göther Labs case study and
licensed under Apache License 2.0. A copy of that license is included at
`cases/int8-matvec/LICENSE`. The frozen evidence-bound source files retain the
original “Evolther contributors” header; for this case that designation refers
to Juan José Fernández. The files are kept byte-exact so their published
certificate and raw evidence remain verifiable.

The INT8 implementation results use the open Verilog-to-Routing toolchain and
academic VTR/PTM architecture models. Tool names identify the measurement
environment and do not imply vendor endorsement.

## ML-KEM CBD case

The CBD RTL baseline descends from `rtl/cbd.v` in the HWSec-CSIC HOPE-MLKEM
repository at pinned commit `72a90d80484d45d0bed1e0f9903bd0fb78cceb47`.
The evaluated baseline adds provenance comments only. The baseline and optimized
RTL retain the upstream MIT terms, a copy of which is included at
`cases/mlkem-cbd/LICENSE`.

NIST FIPS 203 is cited to identify the standardized ML-KEM algorithm. This case
does not imply NIST, HWSec-CSIC, VTR or any tool-provider endorsement. The VTR
architecture and PTM technology model remain under their respective upstream
terms.
