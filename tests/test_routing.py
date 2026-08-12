import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from apps.atm_client import ATMClient
from apps.bank_server import BankServer
from common.framing import decode_packet, encode_packet
from common.hamming import decode_bits, encode_bits
from routers.router import LinkStateRouter, compute_shortest_paths


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

    def test_framing_encode_decode(self):
        packet = {
            "nodo_origen": "ATM1",
            "nodo_destino": "BANK1",
            "mensaje": {"action": "withdraw", "data": {"amount": 100}},
        }
        wire_data = encode_packet(packet)
        # Quitar el encabezado de 4 bytes de longitud para decodificar la carga útil directamente
        payload_bytes = wire_data[4:]
        decoded = decode_packet(payload_bytes)
        self.assertEqual(decoded, packet)

    def test_socket_end_to_end_banking_flow(self):
        node_addresses = {
            "R1": ("127.0.0.1", 16001),
            "R2": ("127.0.0.1", 16002),
            "BANK1": ("127.0.0.1", 16010),
            "ATM1": ("127.0.0.1", 16020),
        }

        r1 = LinkStateRouter(
            "R1",
            neighbors={"R2": 1, "ATM1": 1},
            host="127.0.0.1",
            port=16001,
            node_addresses=node_addresses,
            hello_interval=0.5,
            lsa_interval=1.5,
        )
        r2 = LinkStateRouter(
            "R2",
            neighbors={"R1": 1, "BANK1": 1},
            host="127.0.0.1",
            port=16002,
            node_addresses=node_addresses,
            hello_interval=0.5,
            lsa_interval=1.5,
        )
        bank = BankServer("BANK1", host="127.0.0.1", port=16010, gateway_addr=node_addresses["R2"])
        atm = ATMClient("ATM1", bank_id="BANK1", host="127.0.0.1", port=16020, gateway_addr=node_addresses["R1"])

        try:
            r1.start()
            r2.start()
            bank.start()
            atm.start()

            # Dar tiempo para estabilizar el intercambio LSA
            time.sleep(2.5)

            # 1. Login
            login_res = atm.login("4111111111111111", "1234", timeout=5.0)
            self.assertIsNotNone(login_res)
            self.assertEqual(login_res.get("action"), "login_ok")

            # 2. Withdraw
            withdraw_res = atm.withdraw(150.0, timeout=5.0)
            self.assertIsNotNone(withdraw_res)
            self.assertEqual(withdraw_res.get("action"), "withdraw_ok")
            self.assertEqual(withdraw_res.get("data", {}).get("balance"), 350.0)

            # 3. Logout
            logout_res = atm.logout(timeout=5.0)
            self.assertIsNotNone(logout_res)
            self.assertEqual(logout_res.get("action"), "logout_ok")

        finally:
            atm.stop()
            bank.stop()
            r2.stop()
            r1.stop()


if __name__ == "__main__":
    unittest.main()
