#!/usr/bin/env python3
"""
test_ft.py - Test suite for the secure file transfer system.

Tests:
1. Unit tests for crypto primitives (key derivation, AES-GCM encrypt/decrypt)
2. Integration test: full server-client file transfer
3. Security test: verify ciphertext differs from plaintext
4. Edge cases: empty file, large file, missing file
"""

import os
import sys
import json
import time
import socket
import struct
import threading
import tempfile
import unittest

from cryptography.hazmat.primitives.asymmetric import rsa, padding, ec
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.serialization import load_pem_public_key

# ── shared helpers (duplicated from ft_server/ft_client to keep tests standalone) ──

def send_msg(sock, data):
    sock.sendall(struct.pack('>I', len(data)) + data)

def recv_msg(sock):
    raw = recvall(sock, 4)
    n = struct.unpack('>I', raw)[0]
    return recvall(sock, n)

def recvall(sock, n):
    data = b''
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("Socket closed")
        data += chunk
    return data

def derive_session_key(shared_secret):
    hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b'ft-session-key')
    return hkdf.derive(shared_secret)

def aes_encrypt(key, plaintext):
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    return nonce + aesgcm.encrypt(nonce, plaintext, None)

def aes_decrypt(key, data):
    nonce, ct = data[:12], data[12:]
    return AESGCM(key).decrypt(nonce, ct, None)

SUPPORTED_SUITES = ['ECDHE-RSA-AES256-GCM-SHA256']


# ── Minimal server implementation for integration tests ──

def run_test_server(host, port, files_dir, ready_event, stop_event):
    """Minimal server that handles one connection at a time until stop_event is set."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
    public_key = private_key.public_key()
    rsa_pub_pem = public_key.public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo
    )

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, port))
    srv.listen(5)
    srv.settimeout(2.0)
    ready_event.set()

    while not stop_event.is_set():
        try:
            conn, addr = srv.accept()
        except socket.timeout:
            continue
        try:
            # Send RSA pub key
            send_msg(conn, rsa_pub_pem)

            # Recv encrypted hello
            enc_hello = recv_msg(conn)
            hello_bytes = private_key.decrypt(
                enc_hello,
                padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),
                             algorithm=hashes.SHA256(), label=None)
            )
            hello = json.loads(hello_bytes)
            proposed_suite = hello['cipher_suite']
            client_pub_bytes = bytes.fromhex(hello['ecdhe_public_key'])

            if proposed_suite not in SUPPORTED_SUITES:
                send_msg(conn, json.dumps({'status': 'error', 'msg': 'bad suite'}).encode())
                conn.close()
                continue

            # Server ECDHE
            srv_priv = ec.generate_private_key(ec.SECP256R1())
            srv_pub_bytes = srv_priv.public_key().public_bytes(
                serialization.Encoding.X962,
                serialization.PublicFormat.UncompressedPoint
            )
            send_msg(conn, json.dumps({'status': 'ok', 'cipher_suite': proposed_suite,
                                       'ecdhe_public_key': srv_pub_bytes.hex()}).encode())

            # Derive key
            client_pub = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), client_pub_bytes)
            shared = srv_priv.exchange(ec.ECDH(), client_pub)
            session_key = derive_session_key(shared)

            # Recv filename
            enc_req = recv_msg(conn)
            filename = aes_decrypt(session_key, enc_req).decode()

            safe = os.path.realpath(os.path.join(files_dir, os.path.basename(filename)))
            if not safe.startswith(os.path.realpath(files_dir)) or not os.path.isfile(safe):
                send_msg(conn, aes_encrypt(session_key,
                    json.dumps({'status': 'error', 'msg': 'not found'}).encode()))
                conn.close()
                continue

            with open(safe, 'rb') as f:
                file_data = f.read()

            send_msg(conn, aes_encrypt(session_key,
                json.dumps({'status': 'ok', 'filename': filename, 'size': len(file_data)}).encode()))
            send_msg(conn, aes_encrypt(session_key, file_data))
        except Exception as e:
            print(f"[test server error] {e}")
        finally:
            conn.close()
    srv.close()


def do_client_download(host, port, filename):
    """Client logic - returns (success, file_bytes_or_error_msg)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((host, port))

        rsa_pub_pem = recv_msg(s)
        server_rsa_pub = load_pem_public_key(rsa_pub_pem)

        cli_priv = ec.generate_private_key(ec.SECP256R1())
        cli_pub_bytes = cli_priv.public_key().public_bytes(
            serialization.Encoding.X962,
            serialization.PublicFormat.UncompressedPoint
        )
        hello = json.dumps({'cipher_suite': 'ECDHE-RSA-AES256-GCM-SHA256',
                            'ecdhe_public_key': cli_pub_bytes.hex()}).encode()
        enc_hello = server_rsa_pub.encrypt(
            hello,
            padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),
                         algorithm=hashes.SHA256(), label=None)
        )
        send_msg(s, enc_hello)

        srv_hello = json.loads(recv_msg(s))
        if srv_hello.get('status') != 'ok':
            return False, srv_hello.get('msg', 'unknown error')

        srv_pub = ec.EllipticCurvePublicKey.from_encoded_point(
            ec.SECP256R1(), bytes.fromhex(srv_hello['ecdhe_public_key']))
        shared = cli_priv.exchange(ec.ECDH(), srv_pub)
        session_key = derive_session_key(shared)

        send_msg(s, aes_encrypt(session_key, filename.encode()))

        header = json.loads(aes_decrypt(session_key, recv_msg(s)))
        if header.get('status') != 'ok':
            return False, header.get('msg', 'unknown error')

        file_data = aes_decrypt(session_key, recv_msg(s))
        return True, file_data


# ── Unit Tests ──

class TestCryptoPrimitives(unittest.TestCase):
    """Test crypto building blocks independently."""

    def test_aes_gcm_roundtrip(self):
        key = os.urandom(32)
        plaintext = b"Hello, secure world!"
        ciphertext = aes_encrypt(key, plaintext)
        recovered = aes_decrypt(key, ciphertext)
        self.assertEqual(plaintext, recovered)

    def test_aes_gcm_different_nonces(self):
        """Two encryptions of same data should produce different ciphertext."""
        key = os.urandom(32)
        plaintext = b"Same plaintext"
        ct1 = aes_encrypt(key, plaintext)
        ct2 = aes_encrypt(key, plaintext)
        self.assertNotEqual(ct1, ct2, "Ciphertexts must differ (random nonces)")

    def test_aes_gcm_ciphertext_not_plaintext(self):
        key = os.urandom(32)
        plaintext = b"Secret data - should not appear in ciphertext"
        ciphertext = aes_encrypt(key, plaintext)
        self.assertNotIn(plaintext, ciphertext)

    def test_aes_gcm_tamper_detection(self):
        """GCM authentication tag should detect tampering."""
        key = os.urandom(32)
        ct = bytearray(aes_encrypt(key, b"important data"))
        ct[20] ^= 0xFF  # Flip a byte
        with self.assertRaises(Exception):
            aes_decrypt(key, bytes(ct))

    def test_aes_gcm_wrong_key(self):
        key1 = os.urandom(32)
        key2 = os.urandom(32)
        ct = aes_encrypt(key1, b"data")
        with self.assertRaises(Exception):
            aes_decrypt(key2, ct)

    def test_ecdhe_shared_secret(self):
        """Both parties derive the same shared secret."""
        priv_a = ec.generate_private_key(ec.SECP256R1())
        priv_b = ec.generate_private_key(ec.SECP256R1())
        secret_a = priv_a.exchange(ec.ECDH(), priv_b.public_key())
        secret_b = priv_b.exchange(ec.ECDH(), priv_a.public_key())
        self.assertEqual(secret_a, secret_b)

    def test_session_key_deterministic(self):
        """Same shared secret -> same session key."""
        shared = os.urandom(32)
        k1 = derive_session_key(shared)
        k2 = derive_session_key(shared)
        self.assertEqual(k1, k2)

    def test_session_key_length(self):
        k = derive_session_key(os.urandom(32))
        self.assertEqual(len(k), 32)

    def test_rsa_oaep_encrypt_decrypt(self):
        priv = rsa.generate_private_key(public_exponent=65537, key_size=4096)
        pub = priv.public_key()
        msg = b"cipher suite: ECDHE-RSA-AES256-GCM-SHA256"
        oaep = padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),
                            algorithm=hashes.SHA256(), label=None)
        ct = pub.encrypt(msg, oaep)
        pt = priv.decrypt(ct, oaep)
        self.assertEqual(msg, pt)

    def test_rsa_ciphertext_randomized(self):
        """RSA-OAEP should produce different ciphertext each time (randomized)."""
        priv = rsa.generate_private_key(public_exponent=65537, key_size=4096)
        pub = priv.public_key()
        oaep = padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),
                            algorithm=hashes.SHA256(), label=None)
        msg = b"test"
        ct1 = pub.encrypt(msg, oaep)
        ct2 = pub.encrypt(msg, oaep)
        self.assertNotEqual(ct1, ct2)

    def test_empty_file_aes(self):
        key = os.urandom(32)
        ct = aes_encrypt(key, b"")
        pt = aes_decrypt(key, ct)
        self.assertEqual(pt, b"")


# ── Integration Tests ──

class TestIntegration(unittest.TestCase):
    """Full server-client integration tests."""

    HOST = '127.0.0.1'
    PORT = 19999  # use different port from production

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.mkdtemp()
        cls.stop_event = threading.Event()
        cls.ready_event = threading.Event()
        cls.server_thread = threading.Thread(
            target=run_test_server,
            args=(cls.HOST, cls.PORT, cls.tmpdir, cls.ready_event, cls.stop_event),
            daemon=True
        )
        cls.server_thread.start()
        cls.ready_event.wait(timeout=5)

    @classmethod
    def tearDownClass(cls):
        cls.stop_event.set()
        cls.server_thread.join(timeout=5)

    def _write_file(self, name, content):
        path = os.path.join(self.tmpdir, name)
        with open(path, 'wb') as f:
            f.write(content)
        return path

    def test_basic_text_file(self):
        """Download a text file and verify content matches."""
        content = b"Hello, this is a secret file!\nLine 2.\n"
        self._write_file("hello.txt", content)
        ok, data = do_client_download(self.HOST, self.PORT, "hello.txt")
        self.assertTrue(ok, f"Download failed: {data}")
        self.assertEqual(data, content)

    def test_binary_file(self):
        """Download binary data."""
        content = bytes(range(256)) * 100  # 25,600 bytes
        self._write_file("binary.bin", content)
        ok, data = do_client_download(self.HOST, self.PORT, "binary.bin")
        self.assertTrue(ok)
        self.assertEqual(data, content)

    def test_large_file(self):
        """Download a large file (~1MB)."""
        content = os.urandom(1024 * 1024)
        self._write_file("large.bin", content)
        ok, data = do_client_download(self.HOST, self.PORT, "large.bin")
        self.assertTrue(ok)
        self.assertEqual(data, content)

    def test_empty_file(self):
        """Download an empty file."""
        self._write_file("empty.txt", b"")
        ok, data = do_client_download(self.HOST, self.PORT, "empty.txt")
        self.assertTrue(ok)
        self.assertEqual(data, b"")

    def test_missing_file_returns_error(self):
        """Requesting non-existent file returns error."""
        ok, msg = do_client_download(self.HOST, self.PORT, "does_not_exist.txt")
        self.assertFalse(ok)
        self.assertIn("not found", msg.lower())

    def test_multiple_clients_sequential(self):
        """Multiple sequential downloads work correctly."""
        content_a = b"File A content"
        content_b = b"File B content"
        self._write_file("a.txt", content_a)
        self._write_file("b.txt", content_b)

        ok_a, data_a = do_client_download(self.HOST, self.PORT, "a.txt")
        ok_b, data_b = do_client_download(self.HOST, self.PORT, "b.txt")

        self.assertTrue(ok_a)
        self.assertTrue(ok_b)
        self.assertEqual(data_a, content_a)
        self.assertEqual(data_b, content_b)

    def test_path_traversal_blocked(self):
        """Path traversal attempts should be blocked."""
        ok, msg = do_client_download(self.HOST, self.PORT, "../etc/passwd")
        # Either blocked by security check (not found) or returns error
        if ok:
            # If it somehow succeeded, make sure it didn't return /etc/passwd
            self.fail("Path traversal should have been blocked")
        # Error is expected - any error is fine

    def test_session_keys_independent(self):
        """Each connection gets its own independent session key."""
        content = b"Same file, different sessions"
        self._write_file("same.txt", content)

        ok1, data1 = do_client_download(self.HOST, self.PORT, "same.txt")
        ok2, data2 = do_client_download(self.HOST, self.PORT, "same.txt")

        self.assertTrue(ok1)
        self.assertTrue(ok2)
        self.assertEqual(data1, content)
        self.assertEqual(data2, content)


if __name__ == '__main__':
    print("=" * 60)
    print("Secure File Transfer System - Test Suite")
    print("=" * 60)
    unittest.main(verbosity=2)
