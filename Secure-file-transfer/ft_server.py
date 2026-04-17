#!/usr/bin/env python3
"""
ft_server.py - Secure File Transfer Server

Protocol:
1. Server sends RSA public key to client
2. Client sends ECDHE public key encrypted with RSA
3. Server sends its ECDHE public key (plaintext, RSA already established trust)
4. Both derive shared secret via ECDHE -> AES-256-GCM session key
5. Client sends requested filename (AES-GCM encrypted)
6. Server sends file data (AES-GCM encrypted), or error

Cipher suite negotiation: client proposes, server confirms (both use AES-256-GCM + ECDHE-P256 + RSA-2048)
"""

import socket
import struct
import json
import os
import sys

from cryptography.hazmat.primitives.asymmetric import rsa, padding, ec
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

HOST = '0.0.0.0'
PORT = 9999
FILES_DIR = './server_files'

# Supported cipher suites
SUPPORTED_SUITES = ['ECDHE-RSA-AES256-GCM-SHA256']


def send_msg(sock, data: bytes):
    """Send length-prefixed message."""
    sock.sendall(struct.pack('>I', len(data)) + data)


def recv_msg(sock) -> bytes:
    """Receive length-prefixed message."""
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


def generate_rsa_keypair():
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=4096,
    )
    return private_key, private_key.public_key()


def derive_session_key(shared_secret: bytes) -> bytes:
    """Derive 32-byte AES key from ECDHE shared secret using HKDF-SHA256."""
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b'ft-session-key',
    )
    return hkdf.derive(shared_secret)


def aes_encrypt(key: bytes, plaintext: bytes) -> bytes:
    """Encrypt with AES-256-GCM. Returns nonce+ciphertext."""
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ct = aesgcm.encrypt(nonce, plaintext, None)
    return nonce + ct


def aes_decrypt(key: bytes, data: bytes) -> bytes:
    """Decrypt AES-256-GCM. Expects nonce+ciphertext."""
    nonce, ct = data[:12], data[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ct, None)


def handle_client(conn, addr, rsa_private_key, rsa_public_key):
    print(f"[+] Connection from {addr}")
    try:
        # Step 1: Send RSA public key
        rsa_pub_pem = rsa_public_key.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo
        )
        send_msg(conn, rsa_pub_pem)

        # Step 2: Receive cipher suite proposal + client ECDHE public key (RSA-encrypted)
        encrypted_hello = recv_msg(conn)
        hello_json_bytes = rsa_private_key.decrypt(
            encrypted_hello,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        hello = json.loads(hello_json_bytes)
        proposed_suite = hello['cipher_suite']
        client_ecdhe_pub_bytes = bytes.fromhex(hello['ecdhe_public_key'])

        # Validate cipher suite
        if proposed_suite not in SUPPORTED_SUITES:
            send_msg(conn, json.dumps({'status': 'error', 'msg': 'Unsupported cipher suite'}).encode())
            return

        # Step 3: Generate server ECDHE key pair, send confirmation + server ECDHE public key
        server_ecdhe_private = ec.generate_private_key(ec.SECP256R1())
        server_ecdhe_public = server_ecdhe_private.public_key()
        server_ecdhe_pub_bytes = server_ecdhe_public.public_bytes(
            serialization.Encoding.X962,
            serialization.PublicFormat.UncompressedPoint
        )
        server_hello = {
            'status': 'ok',
            'cipher_suite': proposed_suite,
            'ecdhe_public_key': server_ecdhe_pub_bytes.hex()
        }
        send_msg(conn, json.dumps(server_hello).encode())

        # Step 4: Derive shared session key
        client_ecdhe_public = ec.EllipticCurvePublicKey.from_encoded_point(
            ec.SECP256R1(), client_ecdhe_pub_bytes
        )
        shared_secret = server_ecdhe_private.exchange(ec.ECDH(), client_ecdhe_public)
        session_key = derive_session_key(shared_secret)
        print(f"[+] Session key established with {addr}")

        # Step 5: Receive encrypted filename request
        enc_request = recv_msg(conn)
        filename = aes_decrypt(session_key, enc_request).decode()
        print(f"[+] Client requests file: {filename!r}")

        # Security: prevent path traversal
        safe_path = os.path.realpath(os.path.join(FILES_DIR, os.path.basename(filename)))
        if not safe_path.startswith(os.path.realpath(FILES_DIR)):
            response = {'status': 'error', 'msg': 'Invalid filename'}
            send_msg(conn, aes_encrypt(session_key, json.dumps(response).encode()))
            return

        if not os.path.isfile(safe_path):
            response = {'status': 'error', 'msg': f'File not found: {filename}'}
            send_msg(conn, aes_encrypt(session_key, json.dumps(response).encode()))
            return

        # Step 6: Send encrypted file
        with open(safe_path, 'rb') as f:
            file_data = f.read()

        header = json.dumps({'status': 'ok', 'filename': filename, 'size': len(file_data)}).encode()
        send_msg(conn, aes_encrypt(session_key, header))

        # Send encrypted file data
        send_msg(conn, aes_encrypt(session_key, file_data))
        print(f"[+] Sent {len(file_data)} bytes of {filename!r} to {addr}")

    except Exception as e:
        print(f"[-] Error handling {addr}: {e}")
    finally:
        conn.close()
        print(f"[-] Connection closed: {addr}")


def main():
    os.makedirs(FILES_DIR, exist_ok=True)

    # Generate RSA keypair (could also load from disk)
    print("[*] Generating RSA-2048 keypair...")
    rsa_private_key, rsa_public_key = generate_rsa_keypair()
    print("[*] RSA keypair ready.")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen(5)
        print(f"[*] Server listening on {HOST}:{PORT}")
        print(f"[*] Serving files from: {os.path.abspath(FILES_DIR)}")

        while True:
            conn, addr = s.accept()
            # For simplicity, handle sequentially. For production, use threading.
            handle_client(conn, addr, rsa_private_key, rsa_public_key)


if __name__ == '__main__':
    main()
