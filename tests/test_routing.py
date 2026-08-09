import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from common.hamming import encode_bits, decode_bits
from routers.router import compute_shortest_paths


def test_hamming_round_trip():
    original = "101010101010"
    encoded = encode_bits(original)
    decoded = decode_bits(encoded)
    assert decoded == original


def test_dijkstra_shortest_paths():
    graph = {
        "R1": {"R2": 1, "R3": 4},
        "R2": {"R1": 1, "R3": 2},
        "R3": {"R1": 4, "R2": 2, "BANK1": 1},
        "BANK1": {"R3": 1},
    }
    paths = compute_shortest_paths(graph, "R1")
    assert paths["R2"] == ("R2", 1)
    assert paths["BANK1"] == ("R3", 3)
