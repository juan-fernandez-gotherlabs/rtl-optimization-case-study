# Third-party provenance and notices

This repository combines original case-study material with redistributed or invoked third-party components. The exact source identities are frozen in [`contract/sha_vtr_manifest.json`](contract/sha_vtr_manifest.json).

## Benchmark RTL

The SHA-1 source descends from the OpenCores SHA core by `marsgod`, redistributed through the Verilog-to-Routing benchmark suite. Its original copyright notice and disclaimer are preserved at the top of both RTL files. The VTR source commit is `95f5c6de9e158371ba7185bf97c07a84153735d6`; the original upstream file hash, conformance patch and corrected-reference hash are recorded in the manifest.

## Verilog-to-Routing

VTR, VPR, ACE, Odin II, ABC/Parmys integration, academic architecture descriptions and technology files are obtained from the [Verilog-to-Routing project](https://github.com/verilog-to-routing/vtr-verilog-to-routing). Their licenses remain authoritative. The full image build exports the applicable VTR and dependency license texts into each evidence directory.

## Yosys, EQY and MCY

The flow uses Yosys and pinned snapshots of:

- [EQY](https://github.com/YosysHQ/eqy), commit `6734d8c2df366be50ea9e734c6cb10609b5f32c2`.
- [MCY](https://github.com/YosysHQ/mcy), commit `686c816ceaae60003d51a863e0aefe221003185c`.

Both projects' source archive hashes and the reviewed EQY compatibility patch are in the manifest. Their upstream license files are copied into full evidence runs.

## NIST vectors

The functional corpus is derived from NIST CAVP SHA byte-oriented response files. Source URL, archive SHA-256 and per-file hashes are recorded in the manifest. NIST states that these vectors can be used to informally verify implementation correctness and that their use does not replace formal CAVP validation: [NIST Secure Hashing validation resources](https://csrc.nist.gov/projects/cryptographic-algorithm-validation-program/secure-hashing).

## Container packages

The measurement image starts from a digest-pinned Ubuntu 24.04 image and a dated Ubuntu package snapshot. Each full evidence run exports `dpkg-manifest.tsv`, a Python package manifest, a CycloneDX SBOM and Debian copyright records.

## Original material

The report, figures, compact evidence tooling and standalone packaging written for this repository are Copyright (c) 2026 Juan José Fernández and licensed under the MIT License. This notice is an engineering provenance index, not legal advice; downstream users remain responsible for reviewing the actual third-party licenses.
