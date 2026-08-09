def encode_bits(data: str) -> str:
    """Codifica una cadena de bits usando Hamming (7,4)."""
    if len(data) % 4 != 0:
        data = data + "0" * (4 - (len(data) % 4))

    encoded = []
    for i in range(0, len(data), 4):
        chunk = data[i:i+4]
        d1, d2, d3, d4 = map(int, chunk)
        p1 = d1 ^ d2 ^ d4
        p2 = d1 ^ d3 ^ d4
        p3 = d2 ^ d3 ^ d4
        encoded.append(''.join(map(str, [p1, p2, d1, p3, d2, d3, d4])))
    return ''.join(encoded)


def decode_bits(bits: str) -> str:
    """Decodifica bits Hamming (7,4) y corrige un error simple."""
    if len(bits) % 7 != 0:
        raise ValueError("La longitud de los bits debe ser múltiplo de 7")

    output = []
    for i in range(0, len(bits), 7):
        chunk = bits[i:i+7]
        b = [int(c) for c in chunk]
        p1, p2, d1, p3, d2, d3, d4 = b
        s1 = p1 ^ d1 ^ d2 ^ d4
        s2 = p2 ^ d1 ^ d3 ^ d4
        s3 = p3 ^ d2 ^ d3 ^ d4
        error = s1 + 2*s2 + 4*s3
        if error:
            b[error-1] ^= 1
        data = ''.join(str(x) for x in [b[2], b[4], b[5], b[6]])
        output.append(data)
    return ''.join(output)
