"""Generate frozen block-level SHA-1 vectors from the pinned NIST SHAVS files."""

from __future__ import annotations

import argparse
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

DOMAIN_DIR = Path(__file__).resolve().parent
NIST_DIR = DOMAIN_DIR / "benchmarks" / "nist_shavs"


@dataclass(frozen=True, slots=True)
class Sha1Case:
    """One byte-oriented SHAVS message and expected digest."""

    source: str
    length_bits: int
    message: bytes
    digest_hex: str


def parse_response_file(path: Path) -> list[Sha1Case]:
    """Parse byte-oriented ShortMsg or LongMsg response records."""
    text = path.read_text(encoding="ascii")
    records = re.findall(
        r"Len\s*=\s*(\d+)\s*\nMsg\s*=\s*([0-9a-fA-F]+)\s*\nMD\s*=\s*([0-9a-fA-F]{40})",
        text,
    )
    cases: list[Sha1Case] = []
    for length_raw, message_hex, digest_hex in records:
        length_bits = int(length_raw)
        if length_bits % 8:
            raise ValueError(
                f"{path.name} contains non-byte-oriented Len={length_bits}"
            )
        message = bytes.fromhex(message_hex)[: length_bits // 8]
        if len(message) * 8 != length_bits:
            raise ValueError(f"{path.name} record Len={length_bits} is truncated")
        actual = hashlib.sha1(message, usedforsecurity=False).hexdigest()
        if actual != digest_hex.lower():
            raise ValueError(f"{path.name} host oracle mismatch for Len={length_bits}")
        cases.append(Sha1Case(path.stem, length_bits, message, digest_hex.lower()))
    if not cases:
        raise ValueError(f"no SHA-1 records found in {path}")
    return cases


def padded_blocks(message: bytes) -> tuple[bytes, ...]:
    """Return FIPS 180-4 SHA-1 padding split into 512-bit blocks."""
    bit_length = len(message) * 8
    padded = bytearray(message)
    padded.append(0x80)
    while len(padded) % 64 != 56:
        padded.append(0)
    padded.extend(bit_length.to_bytes(8, "big"))
    return tuple(
        bytes(padded[index : index + 64]) for index in range(0, len(padded), 64)
    )


def write_block_corpus(cases: list[Sha1Case], output: Path) -> None:
    """Write a compact text corpus consumed by the frozen Verilator testbench."""
    lines = [f"SHA1_BLOCK_CORPUS_V1 {len(cases)}"]
    for case in cases:
        blocks = padded_blocks(case.message)
        lines.append(
            f"{case.source} {case.length_bits} {len(blocks)} {case.digest_hex}"
        )
        lines.extend(block.hex() for block in blocks)
    output.write_text("\n".join(lines) + "\n", encoding="ascii")


def monte_carlo_cases(path: Path) -> list[Sha1Case]:
    """Expand the complete 100x1000 SHA-1 SHAVS Monte Carlo sequence."""
    text = path.read_text(encoding="ascii")
    seed_match = re.search(r"Seed\s*=\s*([0-9a-fA-F]{40})", text)
    expected = [
        value.lower()
        for value in re.findall(r"^MD\s*=\s*([0-9a-fA-F]{40})", text, re.MULTILINE)
    ]
    if seed_match is None or len(expected) != 100:
        raise ValueError("invalid SHA1Monte.rsp structure")
    seed = bytes.fromhex(seed_match.group(1))
    cases: list[Sha1Case] = []
    for outer_index, expected_digest in enumerate(expected):
        digests = [seed, seed, seed]
        for inner_index in range(1000):
            message = digests[-3] + digests[-2] + digests[-1]
            digest = hashlib.sha1(message, usedforsecurity=False).digest()
            digests.append(digest)
            cases.append(
                Sha1Case(
                    f"SHA1Monte_{outer_index}_{inner_index}",
                    len(message) * 8,
                    message,
                    digest.hex(),
                )
            )
        if digests[-1].hex() != expected_digest:
            raise ValueError(f"SHA1Monte host oracle mismatch at COUNT={outer_index}")
        seed = digests[-1]
    return cases


def main() -> int:
    """Generate and independently validate the pinned short/long corpus."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--message-hex")
    parser.add_argument("--monte", action="store_true")
    args = parser.parse_args()
    if args.monte:
        if args.message_hex is not None:
            raise ValueError("--monte and --message-hex are mutually exclusive")
        cases = monte_carlo_cases(NIST_DIR / "SHA1Monte.rsp")
    elif args.message_hex is not None:
        message = bytes.fromhex(args.message_hex)
        cases = [
            Sha1Case(
                "direct",
                len(message) * 8,
                message,
                hashlib.sha1(message, usedforsecurity=False).hexdigest(),
            )
        ]
    else:
        cases = parse_response_file(NIST_DIR / "SHA1ShortMsg.rsp")
        cases.extend(parse_response_file(NIST_DIR / "SHA1LongMsg.rsp"))
    if args.start < 0:
        raise ValueError("--start must be non-negative")
    cases = cases[args.start :]
    if args.limit is not None:
        if args.limit <= 0:
            raise ValueError("--limit must be positive")
        cases = cases[: args.limit]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_block_corpus(cases, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
