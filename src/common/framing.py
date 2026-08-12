from __future__ import annotations

import json
import socket
import struct
from typing import Any, Dict, Optional

from common.hamming import decode_bits, encode_bits


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


def encode_packet(packet: Dict[str, Any]) -> bytes:
    """Codifica un paquete JSON usando Hamming (7,4) y devuelve los bytes formateados."""
    payload_bits = json_to_bits(packet)
    encoded_bits = encode_bits(payload_bits)
    ascii_bytes = encoded_bits.encode("ascii")
    length_prefix = struct.pack("!I", len(ascii_bytes))
    return length_prefix + ascii_bytes


def decode_packet(data_bytes: bytes) -> Dict[str, Any]:
    """Decodifica bytes recibidos con Hamming (7,4) a diccionario JSON."""
    ascii_bits = data_bytes.decode("ascii")
    decoded_bits = decode_bits(ascii_bits)
    return bits_to_json(decoded_bits)


def recv_exact(sock: socket.socket, num_bytes: int) -> Optional[bytes]:
    """Lee exactamente num_bytes de un socket. Retorna None si el socket se cierra."""
    buf = bytearray()
    while len(buf) < num_bytes:
        try:
            chunk = sock.recv(num_bytes - len(buf))
            if not chunk:
                return None
            buf.extend(chunk)
        except (socket.error, ConnectionResetError):
            return None
    return bytes(buf)


def send_packet(sock: socket.socket, packet: Dict[str, Any]) -> None:
    """Envía un paquete codificado por el socket."""
    wire_data = encode_packet(packet)
    sock.sendall(wire_data)


def recv_packet(sock: socket.socket) -> Optional[Dict[str, Any]]:
    """Lee un paquete enmarcado del socket y lo decodifica."""
    header = recv_exact(sock, 4)
    if not header:
        return None
    (length,) = struct.unpack("!I", header)
    payload_bytes = recv_exact(sock, length)
    if not payload_bytes:
        return None
    return decode_packet(payload_bytes)
