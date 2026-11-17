"""Command line entry point. argparse, thin. Parses at the boundary, calls Store or Worker.

    saasx2x migrate
    saasx2x target add example.com [--interval 300]
    saasx2x target remove example.com
    saasx2x target list
    saasx2x worker
"""
from __future__ import annotations


def main(argv: list[str] | None = None) -> int:
    raise NotImplementedError
