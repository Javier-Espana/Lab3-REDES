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
    routers = {
        "R1": LinkStateRouter("R1", {"R2": 1, "R3": 4}),
        "R2": LinkStateRouter("R2", {"R1": 1, "R3": 2}),
        "R3": LinkStateRouter("R3", {"R1": 4, "R2": 2, "BANK1": 1}),
        "BANK1": LinkStateRouter("BANK1", {"R3": 1}),
    }

    for router_id, router in routers.items():
        hello = router.build_hello()
        router.process_hello(hello)
        lsa = router.build_lsa()
        for neighbor_id, _ in router.neighbors.items():
            routers[neighbor_id].process_lsa(lsa, sender=router_id)

    for router_id, router in routers.items():
        for neighbor_id in list(router.neighbors):
            routers[neighbor_id].process_hello(router.build_hello())

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
    with open(os.path.join(os.getcwd(), "output", "R1_nodo_tabla_enrutamiento.csv"), "r", encoding="utf-8") as handle:
        print(handle.read())


if __name__ == "__main__":
    main()
