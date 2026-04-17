#!/usr/bin/env python3
"""
ft_client.py - Secure File Transfer Client

Usage:
    python3 ft_client.py <server_host> <filename> [output_file]
    python3 ft_client.py localhost secret.txt
    python3 ft_client.py 192.168.1.10 report.pdf downloaded_report.pdf

Protocol (mirrors server):
1. Receive server RSA public key
2. Send ECDHE public key + cipher suite encrypted with RSA
3. Receive server ECDHE public key + confirmed cipher suite
4. Derive shared AES-256-GCM session key via ECDHE
5. Send encrypted filename request
6. Receive encrypted file data, decrypt and save
"""

import socket
import struct
import json
import os
import sys


from cryptography.hazmat.primitives.asymmetric import padding, ec
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.serialization import load_pem_public_key

PORT = 9999
PREFERRED_SUITE = 'ECDHE-RSA-AES256-GCM-SHA256'
OUTPUT_DIR = './received_files'


def send_msg(sock, data: bytes):
    sock.sendall(struct.pack('>I', len(data)) + data)


def recv_msg(sock) -> bytes:
    raw_len = recvall(sock, 4)
    msg_len = struct.unpack('>I', raw_len)[0]
    return recvall(sock, msg_len)


def recvall(sock, n: int) -> bytes:
    data = b''
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("Socket closed unexpectedly")
        data += chunk
    return data


def derive_session_key(shared_secret: bytes) -> bytes:
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b'ft-session-key',
    )
    return hkdf.derive(shared_secret)


def aes_encrypt(key: bytes, plaintext: bytes) -> bytes:
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ct = aesgcm.encrypt(nonce, plaintext, None)
    return nonce + ct


def aes_decrypt(key: bytes, data: bytes) -> bytes:
    nonce, ct = data[:12], data[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ct, None)


def download_file(host: str, filename: str, output_path: str = None):
    print(f"[*] Connecting to {host}:{PORT}...")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((host, PORT))

        # Step 1: Receive server RSA public key
        rsa_pub_pem = recv_msg(s)
        server_rsa_public_key = load_pem_public_key(rsa_pub_pem)
        print("[*] Received server RSA public key.")

        # Step 2: Generate client ECDHE keypair, send hello encrypted with RSA
        client_ecdhe_private = ec.generate_private_key(ec.SECP256R1())
        client_ecdhe_public = client_ecdhe_private.public_key()
        client_ecdhe_pub_bytes = client_ecdhe_public.public_bytes(
            serialization.Encoding.X962,
            serialization.PublicFormat.UncompressedPoint
        )

        hello = {
            'cipher_suite': PREFERRED_SUITE,
            'ecdhe_public_key': client_ecdhe_pub_bytes.hex()
        }
        hello_bytes = json.dumps(hello).encode()

        encrypted_hello = server_rsa_public_key.encrypt(
            hello_bytes,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        send_msg(s, encrypted_hello)
        print(f"[*] Sent cipher suite proposal ({PREFERRED_SUITE}) encrypted with RSA.")

        # Step 3: Receive server hello (cipher suite confirmation + server ECDHE key)
        server_hello_raw = recv_msg(s)
        server_hello = json.loads(server_hello_raw)

        if server_hello.get('status') != 'ok':
            print(f"[-] Server rejected cipher suite: {server_hello.get('msg')}")
            return False

        confirmed_suite = server_hello['cipher_suite']
        server_ecdhe_pub_bytes = bytes.fromhex(server_hello['ecdhe_public_key'])
        print(f"[*] Server confirmed cipher suite: {confirmed_suite}")

        # Step 4: Derive shared session key
        server_ecdhe_public = ec.EllipticCurvePublicKey.from_encoded_point(
            ec.SECP256R1(), server_ecdhe_pub_bytes
        )
        shared_secret = client_ecdhe_private.exchange(ec.ECDH(), server_ecdhe_public)
        session_key = derive_session_key(shared_secret)
        print("[*] Session key derived via ECDHE.")

        # Step 5: Send encrypted filename request
        enc_request = aes_encrypt(session_key, filename.encode())
        send_msg(s, enc_request)
        print(f"[*] Requested file: {filename!r}")

        # Step 6: Receive header
        enc_header = recv_msg(s)
        header = json.loads(aes_decrypt(session_key, enc_header))

        if header.get('status') != 'ok':
            print(f"[-] Server error: {header.get('msg')}")
            return False

        file_size = header['size']
        remote_name = header['filename']
        print(f"[*] File info: {remote_name!r}, {file_size} bytes")

        # Receive encrypted file data
        enc_file = recv_msg(s)
        file_data = aes_decrypt(session_key, enc_file)

        if len(file_data) != file_size:
            print(f"[-] Size mismatch: expected {file_size}, got {len(file_data)}")
            return False

        # Save file
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        if output_path is None:
            output_path = os.path.join(OUTPUT_DIR, os.path.basename(remote_name))

        with open(output_path, 'wb') as f:
            f.write(file_data)

        print(f"[+] File saved to: {output_path} ({len(file_data)} bytes)")
        return True


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 ft_client.py <server_host> <filename> [output_path]")
        print("Example: python3 ft_client.py localhost secret.txt")
        sys.exit(1)

    host = sys.argv[1]
    filename = sys.argv[2]
    output_path = sys.argv[3] if len(sys.argv) > 3 else None

    success = download_file(host, filename, output_path)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
