"""Generate deterministic 5,000-cycle ACE input vectors for the SHA-1 core."""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

VECTOR_CYCLES = 5_000
RESET_CYCLES = 3
BLOCK_PERIOD_CYCLES = 83
WORDS_PER_BLOCK = 16


def canonical_blif_sha256(path: Path) -> str:
    """Hash a BLIF while excluding only ABC's nondeterministic timestamp header."""
    lines = path.read_bytes().splitlines(keepends=True)
    if (
        lines
        and lines[0].startswith(b'# Benchmark "')
        and b" written by ABC on " in lines[0]
    ):
        lines = lines[1:]
    return hashlib.sha256(b"".join(lines)).hexdigest()


def parse_blif_inputs(path: Path) -> tuple[str, ...]:
    """Return flattened primary-input names in ABC BLIF order."""
    text = path.read_text(encoding="utf-8", errors="replace")
    match = re.search(
        r"^\.inputs\s+(.*?)(?=\n\s*\n?\.outputs)", text, re.MULTILINE | re.DOTALL
    )
    if match is None:
        raise ValueError(f"cannot locate .inputs in {path}")
    names = tuple(match.group(1).replace("\\\n", " ").split())
    required = {"clk_i", "rst_i", "cmd_w_i", *(f"cmd_i~{index}" for index in range(3))}
    required.update(f"text_i~{index}" for index in range(32))
    if set(names) != required:
        raise ValueError(f"unexpected BLIF primary inputs: {names}")
    return names


def _lfsr_next(value: int) -> int:
    feedback = ((value >> 31) ^ (value >> 21) ^ (value >> 1) ^ value) & 1
    return ((value << 1) & 0xFFFFFFFF) | feedback


def activity_blocks(count: int) -> tuple[tuple[int, ...], ...]:
    """Create diverse deterministic compression blocks."""
    state = 0x1BADC0DE
    blocks: list[tuple[int, ...]] = []
    for block_index in range(count):
        words: list[int] = []
        state ^= block_index
        for _ in range(WORDS_PER_BLOCK):
            state = _lfsr_next(state)
            words.append(state)
        blocks.append(tuple(words))
    return tuple(blocks)


def profile_values(profile: str) -> tuple[dict[str, int], ...]:
    """Return one legal primary-input assignment per abstract clock cycle."""
    available_cycles = VECTOR_CYCLES - RESET_CYCLES
    complete_block_slots = available_cycles // BLOCK_PERIOD_CYCLES
    blocks = activity_blocks(complete_block_slots)
    rows: list[dict[str, int]] = []
    for cycle in range(VECTOR_CYCLES):
        values = {
            "clk_i": 0,
            "rst_i": int(cycle < RESET_CYCLES),
            "cmd_w_i": 0,
            "cmd_i": 0,
            "text_i": 0,
        }
        if profile == "active" and cycle >= RESET_CYCLES:
            active_cycle = cycle - RESET_CYCLES
            block_index, phase = divmod(active_cycle, BLOCK_PERIOD_CYCLES)
            # Do not start a 61st block that cannot finish inside the frozen
            # 5,000-cycle observation window.  This keeps the energy divisor
            # equal to the exact number of blocks represented by the trace.
            if block_index >= complete_block_slots:
                pass
            elif phase == 0:
                values["cmd_w_i"] = 1
                values["cmd_i"] = 0b010 if block_index % 4 == 0 else 0b110
                values["text_i"] = blocks[block_index][0]
            elif phase == 1:
                values["text_i"] = blocks[block_index][0]
            elif 2 <= phase <= 16:
                values["text_i"] = blocks[block_index][phase - 1]
        rows.append(values)
    return tuple(rows)


def _bit_value(name: str, values: dict[str, int]) -> int:
    if "~" not in name:
        return int(values[name])
    base, index_raw = name.rsplit("~", 1)
    return (int(values[base]) >> int(index_raw)) & 1


def write_vectors(blif: Path, profile: str, output: Path) -> int:
    """Write vectors and return the number of complete active blocks."""
    if profile not in {"active", "idle"}:
        raise ValueError("profile must be active or idle")
    inputs = parse_blif_inputs(blif)
    rows = profile_values(profile)
    lines = [
        "".join(str(_bit_value(name, values)) for name in inputs) for values in rows
    ]
    if len(lines) != VECTOR_CYCLES or any(len(line) != len(inputs) for line in lines):
        raise AssertionError("invalid ACE vector dimensions")
    output.write_text("\n".join(lines) + "\n", encoding="ascii")
    return (
        (VECTOR_CYCLES - RESET_CYCLES) // BLOCK_PERIOD_CYCLES
        if profile == "active"
        else 0
    )


def main() -> int:
    """Generate one activity profile from a synthesized BLIF."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--blif", required=True, type=Path)
    parser.add_argument("--profile", required=True, choices=("active", "idle"))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    blocks = write_vectors(args.blif, args.profile, args.output)
    print(
        f"ACE_VECTOR_PROFILE_PASS profile={args.profile} cycles={VECTOR_CYCLES} blocks={blocks}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
