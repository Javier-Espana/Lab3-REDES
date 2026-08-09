import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from common.hamming import encode_bits, decode_bits
from routers.router import compute_shortest_paths


class RoutingTests(unittest.TestCase):
    def test_hamming_round_trip(self):
        original = "101010101010"
        encoded = encode_bits(original)
        decoded = decode_bits(encoded)
        self.assertEqual(decoded, original)

    def test_dijkstra_shortest_paths(self):
        graph = {
            "R1": {"R2": 1, "R3": 4},
            "R2": {"R1": 1, "R3": 2},
            "R3": {"R1": 4, "R2": 2, "BANK1": 1},
            "BANK1": {"R3": 1},
        }
        paths = compute_shortest_paths(graph, "R1")
        self.assertEqual(paths["R2"], ("R2", 1))
        self.assertEqual(paths["BANK1"], ("R2", 4))


if __name__ == "__main__":
    unittest.main()
