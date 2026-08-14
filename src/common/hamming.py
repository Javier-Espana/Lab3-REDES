from __future__ import annotations

from typing import Tuple


def encode_block(chunk: str) -> str:
    """Codifica un bloque de 4 bits de datos en un código Hamming (7,4) de 7 bits."""
    if len(chunk) < 4:
        chunk = chunk.ljust(4, "0")
    d1, d2, d3, d4 = map(int, chunk)
    p1 = d1 ^ d2 ^ d4
    p2 = d1 ^ d3 ^ d4
    p3 = d2 ^ d3 ^ d4
    return "".join(map(str, [p1, p2, d1, p3, d2, d3, d4]))


def decode_block(chunk: str) -> Tuple[str, bool]:
    """Decodifica un bloque Hamming de 7 bits y corrige un error simple de 1 bit."""
    b = [int(c) for c in chunk]
    p1, p2, d1, p3, d2, d3, d4 = b
    s1 = p1 ^ d1 ^ d2 ^ d4
    s2 = p2 ^ d1 ^ d3 ^ d4
    s3 = p3 ^ d2 ^ d3 ^ d4
    error_pos = s1 + 2 * s2 + 4 * s3
    error_detected = error_pos != 0
    if error_detected and 1 <= error_pos <= 7:
        b[error_pos - 1] ^= 1

    data_bits = "".join(str(x) for x in [b[2], b[4], b[5], b[6]])
    return data_bits, error_detected


def encode_bits(data: str) -> str:
    """Codifica una cadena de bits en bloques Hamming (7,4)."""
    remainder = len(data) % 4
    if remainder != 0:
        data = data + "0" * (4 - remainder)

    encoded = []
    for i in range(0, len(data), 4):
        encoded.append(encode_block(data[i : i + 4]))
    return "".join(encoded)


def decode_bits(bits: str) -> str:
    """Decodifica bits Hamming (7,4) sin encabezado."""
    if len(bits) % 7 != 0:
        raise ValueError("La longitud de los bits debe ser múltiplo de 7")

    output = []
    for i in range(0, len(bits), 7):
        data, _ = decode_block(bits[i : i + 7])
        output.append(data)
    return "".join(output)


def encode_hamming_frame(data_bits: str) -> str:
    """
    Construye una trama Hamming completa según el estándar inter-grupo:
    - Encabezado de 16 bits con el número de bloques.
    - Bloques de 4 bits codificados a 7 bits con Hamming(7,4).
    """
    remainder = len(data_bits) % 4
    if remainder != 0:
        data_bits = data_bits + "0" * (4 - remainder)

    num_blocks = len(data_bits) // 4
    header = format(num_blocks, "016b")

    blocks_encoded = []
    for i in range(0, len(data_bits), 4):
        blocks_encoded.append(encode_block(data_bits[i : i + 4]))

    return header + "".join(blocks_encoded)


def decode_hamming_frame(frame_bits: str) -> str:
    """
    Decodifica una trama Hamming con encabezado de 16 bits.
    Retorna la cadena de bits de datos original.
    """
    if len(frame_bits) < 16:
        return ""

    num_blocks = int(frame_bits[:16], 2)
    encoded_blocks_bits = frame_bits[16:]

    block_len = 7
    expected_len = num_blocks * block_len
    if len(encoded_blocks_bits) < expected_len:
        encoded_blocks_bits = encoded_blocks_bits.ljust(expected_len, "0")

    decoded_bits = []
    for i in range(num_blocks):
        block = encoded_blocks_bits[i * block_len : (i + 1) * block_len]
        data, _ = decode_block(block)
        decoded_bits.append(data)

    return "".join(decoded_bits)

