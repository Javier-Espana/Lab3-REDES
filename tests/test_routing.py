import os
import sys
import time
import unittest

# Añadir src/ al path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_PROJECT_ROOT, "src"))

from apps.atm_client import ATMClient
from apps.bank_server import BankServer
from common.framing import decode_packet, encode_packet
from common.hamming import (
    decode_bits,
    decode_hamming_frame,
    encode_bits,
    encode_hamming_frame,
)
from routers.router import LinkStateRouter, compute_shortest_paths


class RoutingTests(unittest.TestCase):
    def test_hamming_round_trip(self):
        original = "101010101010"
        encoded = encode_bits(original)
        decoded = decode_bits(encoded)
        self.assertEqual(decoded, original)

    def test_hamming_frame_with_header(self):
        data_bits = "0100000101000010"  # 'AB' en binario ASCII
        frame = encode_hamming_frame(data_bits)
        decoded = decode_hamming_frame(frame)
        self.assertEqual(decoded, data_bits)

    def test_dijkstra_shortest_paths(self):
        graph = {
            "R1": {"R2": 1, "R3": 4},
            "R2": {"R1": 1, "R3": 2},
            "R3": {"R1": 4, "R2": 2, "BANK1": 1},
            "BANK1": {"R3": 1},
        }
        paths = compute_shortest_paths(graph, "R1")
        self.assertEqual(paths["R2"][:2], ("R2", 1))
        self.assertEqual(paths["BANK1"][:2], ("R2", 4))

    def test_framing_encode_decode(self):
        packet = {
            "nodo_origen": "ATM1",
            "nodo_destino": "BANK1",
            "mensaje": {"action": "withdraw", "data": {"amount": 100}},
        }
        wire_data = encode_packet(packet)
        self.assertTrue(wire_data.startswith(b"hamming|"))
        self.assertTrue(wire_data.endswith(b"\n"))
        decoded = decode_packet(wire_data)
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

    def test_interoperability_with_classmates_repo(self):
        """Prueba que un Router de src/ e interactúe con un Router del grupo clonado (Lab3-Redes/)."""
        classmates_dir = os.path.join(_PROJECT_ROOT, "Lab3-Redes")
        if not os.path.exists(classmates_dir):
            self.skipTest("Directorio Lab3-Redes no encontrado")

        sys.path.insert(0, classmates_dir)
        try:
            from data_plane import Forwarder
            from linkstate import LinkState
        except ImportError:
            self.skipTest("No se pudieron importar módulos de Lab3-Redes")

        node_addresses = {
            "R1": ("127.0.0.1", 17001),
            "R2": ("127.0.0.1", 17002),
            "BANK1": ("127.0.0.1", 17010),
            "ATM1": ("127.0.0.1", 17020),
        }

        # Router 1 en nuestro proyecto (src/)
        r1 = LinkStateRouter(
            "R1",
            neighbors={"R2": 1, "ATM1": 1},
            host="127.0.0.1",
            port=17001,
            node_addresses=node_addresses,
            hello_interval=0.5,
            lsa_interval=1.5,
        )

        # Router 2 en el proyecto de los compañeros (Lab3-Redes/)
        r2_neighbors = [{"node_id": "R1", "ip": "127.0.0.1", "port": 17001, "cost": 1}]
        r2_end_hosts = [{"node_id": "BANK1", "ip": "127.0.0.1", "port": 17010, "cost": 1}]
        peer_addr = {
            "R1": ("127.0.0.1", 17001),
            "BANK1": ("127.0.0.1", 17010),
        }
        r2_linkstate = LinkState("R2", r2_neighbors, r2_end_hosts, peer_addr)
        r2_forwarder = Forwarder("R2", "127.0.0.1", 17002, r2_linkstate)

        # Servidor de Banco en nuestro proyecto (src/)
        bank = BankServer("BANK1", host="127.0.0.1", port=17010, gateway_addr=node_addresses["R2"])
        # Cliente ATM en nuestro proyecto (src/)
        atm = ATMClient("ATM1", bank_id="BANK1", host="127.0.0.1", port=17020, gateway_addr=node_addresses["R1"])

        try:
            r1.start()
            r2_forwarder.start()
            r2_linkstate.start()
            bank.start()
            atm.start()

            # Esperar convergencia de LSA en ambos routers (R1 y R2)
            for _ in range(25):
                with r2_linkstate.rt_lock:
                    r2_ready = "BANK1" in r2_linkstate.routing_table
                if "BANK1" in r1.routing_table and r2_ready:
                    break
                time.sleep(0.5)

            # Prueba de comunicación entre cliente ATM (src) -> R1 (src) -> R2 (Lab3-Redes) -> Banco (src)
            login_res = atm.login("4111111111111111", "1234", timeout=5.0)
            self.assertIsNotNone(login_res, "Fallo al autenticar inter-grupo")
            self.assertEqual(login_res.get("action"), "login_ok")

            withdraw_res = atm.withdraw(100.0, timeout=5.0)
            self.assertIsNotNone(withdraw_res, "Fallo en retiro inter-grupo")
            self.assertEqual(withdraw_res.get("action"), "withdraw_ok")

        finally:
            atm.stop()
            bank.stop()
            r1.stop()


if __name__ == "__main__":
    unittest.main()

