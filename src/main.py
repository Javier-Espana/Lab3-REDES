from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from routers.router import LinkStateRouter
from common.hamming import encode_bits, decode_bits


def main() -> None:
    print("Simulación del laboratorio 3")
    router_a = LinkStateRouter("R1", {"R2": 1, "R3": 4})
    router_b = LinkStateRouter("R2", {"R1": 1, "R3": 2})
    router_c = LinkStateRouter("R3", {"R1": 4, "R2": 2, "BANK1": 1})
    router_bank = LinkStateRouter("BANK1", {"R3": 1})

    lsa_a = router_a.build_lsa()
    lsa_b = router_b.build_lsa()
    lsa_c = router_c.build_lsa()
    lsa_bank = router_bank.build_lsa()

    for router, lsa in [(router_a, lsa_a), (router_b, lsa_b), (router_c, lsa_c), (router_bank, lsa_bank)]:
        router.process_lsa(lsa)

    packet = {
        "nodo_origen": "ATM1",
        "nodo_destino": "BANK1",
        "mensaje": {"action": "withdraw", "data": {"amount": 100}},
    }

    payload_bits = ''.join(format(ord(ch), '08b') for ch in json.dumps(packet))
    encoded_bits = encode_bits(payload_bits)
    decoded_bits = decode_bits(encoded_bits)
    print("Bits de datos originales:", payload_bits[:80])
    print("Bits decodificados:", decoded_bits[:80])

    print("Tabla de enrutamiento generada para R1:")
    with open(os.path.join(os.getcwd(), "R1_tabla_enrutamiento.csv"), "r", encoding="utf-8") as handle:
        print(handle.read())


if __name__ == "__main__":
    main()
