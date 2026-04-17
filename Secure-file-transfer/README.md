# Secure File Transfer

A simple encrypted file transfer system implemented in Python using the cipher suite `ECDHE-RSA-AES256-GCM-SHA256`. Files are stored in plaintext on disk and encrypted only during transfer.

## Files

| File | Description |
|---|---|
| `ft_server.py` | Server — serves files from `./server_files/` |
| `ft_client.py` | Client — downloads a file and saves it to `./received_files/` |
| `test_ft.py` | Test suite (18 tests) |
| `benchmark.py` | Performance benchmark for the crypto operations |

## Requirements

Python 3.10+ and the `cryptography` package:

```
pip install cryptography
```

## Usage

**Start the server:**
```
python3 ft_server.py
```
The server generates an RSA-4096 keypair on startup (takes 1–3 seconds), then listens on port 9999. Place files you want to serve in `./server_files/`.

**Download a file:**
```
python3 ft_client.py <host> <filename>
python3 ft_client.py <host> <filename> <output_path>
```

Examples:
```
python3 ft_client.py localhost secret.txt
python3 ft_client.py 192.168.1.10 report.pdf ~/downloads/report.pdf
```

Downloaded files are saved to `./received_files/` unless an output path is given.

## Running the Tests

```
python3 test_ft.py
```

The test suite starts its own server thread internally, so `ft_server.py` does not need to be running. All 18 tests should pass in a few seconds (RSA key generation adds some startup time).

## Running the Benchmark

```
python3 benchmark.py
```

Measures the latency of each cryptographic operation in isolation. No network is involved. Results will vary between machines.

## How It Works

The protocol has six steps:

1. Server sends its RSA-4096 public key to the client.
2. Client sends its ECDHE public key, encrypted with the server's RSA key.
3. Server sends its ECDHE public key in plaintext.
4. Both sides independently compute the same session key: `HKDF(ECDH(priv, pub_other))`.
5. Client sends the requested filename, encrypted with AES-256-GCM.
6. Server sends the file contents, encrypted with AES-256-GCM.

All messages use a 4-byte length prefix for framing. The server returns an empty encrypted message if the file is not found or the path is invalid.

## Security Notes

- **Protects against:** passive eavesdropping. File contents, filenames, and past sessions are kept confidential. Forward secrecy means past sessions cannot be decrypted even if the server's RSA key is later compromised.
- **Does not protect against:** active man-in-the-middle attacks. The server's RSA key is sent without any proof of identity, so an attacker who can intercept and modify traffic could impersonate the server.
- The server handles one connection at a time (single-threaded).
- Files are loaded fully into memory before sending, so very large files may cause issues.
