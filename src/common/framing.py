from __future__ import annotations

import json
import socket
from typing import Any, Dict, Optional

from common.hamming import (
    decode_bits,
    decode_hamming_frame,
    encode_bits,
    encode_hamming_frame,
)


def json_to_bits(data: Dict[str, Any]) -> str:
    """Convierte un diccionario JSON en una cadena de bits ASCII."""
    raw_str = json.dumps(data)
    return "".join(format(ord(ch), "08b") for ch in raw_str)


def bits_to_json(bits: str) -> Dict[str, Any]:
    """Convierte una cadena de bits ASCII de múltiplos de 8 en un diccionario JSON."""
    if len(bits) % 8 != 0:
        bits = bits[: len(bits) - (len(bits) % 8)]
    chars = []
    for i in range(0, len(bits), 8):
        byte_bits = bits[i : i + 8]
        chars.append(chr(int(byte_bits, 2)))
    raw_str = "".join(chars)
    return json.loads(raw_str)


def encode_packet(packet: Dict[str, Any], algorithm: Optional[str] = None) -> bytes:
    """
    Serializa un paquete JSON al formato del socket:
    <algorithm>|<bit_string>\n
    """
    if algorithm is None:
        p_type = packet.get("type")
        algorithm = "none" if p_type in ("HELLO", "LSA") else "hamming"

    raw_bits = json_to_bits(packet)
    if algorithm == "none":
        frame_bits = raw_bits
    elif algorithm == "hamming":
        frame_bits = encode_hamming_frame(raw_bits)
    else:
        frame_bits = raw_bits

    line = f"{algorithm}|{frame_bits}\n"
    return line.encode("utf-8")


def decode_packet(data_bytes: bytes) -> Optional[Dict[str, Any]]:
    """Decodifica una línea del socket en formato <algorithm>|<bit_string>."""
    try:
        line = data_bytes.decode("utf-8").strip()
        if "|" not in line:
            return None
        algorithm, bit_string = line.split("|", 1)
        algorithm = algorithm.strip().lower()

        if algorithm == "none":
            data_bits = bit_string
        elif algorithm == "hamming":
            data_bits = decode_hamming_frame(bit_string)
        else:
            data_bits = bit_string

        return bits_to_json(data_bits)
    except Exception:
        return None


def recv_line(sock: socket.socket) -> Optional[bytes]:
    """Lee una línea terminada por \\n de un socket."""
    buf = bytearray()
    while True:
        try:
            chunk = sock.recv(65536)
            if not chunk:
                if buf:
                    return bytes(buf)
                return None
            buf.extend(chunk)
            if b"\n" in buf:
                # Extraer hasta el primer \n
                pos = buf.index(b"\n")
                line = buf[: pos + 1]
                return bytes(line)
        except (socket.error, ConnectionResetError, TimeoutError):
            if buf:
                return bytes(buf)
            return None


def send_packet(sock: socket.socket, packet: Dict[str, Any], algorithm: Optional[str] = None) -> None:
    """Envía un paquete codificado por el socket."""
    wire_data = encode_packet(packet, algorithm=algorithm)
    sock.sendall(wire_data)


def recv_packet(sock: socket.socket) -> Optional[Dict[str, Any]]:
    """Lee un paquete enmarcado del socket y lo decodifica."""
    line_bytes = recv_line(sock)
    if not line_bytes:
        return None
    return decode_packet(line_bytes)

