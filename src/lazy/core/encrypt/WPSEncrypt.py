import base64
import json
import secrets
import string

from cryptography.hazmat.primitives import padding as aes_padding
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding as rsa_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

ALPHABET = string.ascii_letters + string.digits

def _json_bytes(value: object) -> bytes:
    """紧凑的JSON格式"""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class WPSEncryptToolKit:
    def __init__(
        self,
        rsa_pem: str,
        key: str|None = None,
        iv: str|None = None
    ):
        # AES-256
        self.key = key if key else (
            "".join(
                secrets.choice(ALPHABET) for _ in range(32)
            ).encode("ascii")
        )

        self.iv = iv if iv else (
            "".join(
                secrets.choice(ALPHABET) for _ in range(16)
            ).encode("ascii")
        )

        self.rsa_pem = rsa_pem
        self.rsa_pubkey = serialization.load_pem_public_key(self.rsa_pem)

        # 初始化时候顺带把 AES KEY IV 的 RSA 加密做了
        self._encrypt_aes_key_iv()

    def _encrypt_aes_key_iv(self):
        key_parameters = {
            "private_key": self.key.decode("ascii"),
            "iv": self.iv.decode("ascii"),
        }

        wrapped_key = self.rsa_pubkey.encrypt(
            _json_bytes(key_parameters),
            rsa_padding.PKCS1v15(),
        )

        self.encryption_parameters = base64.b64encode(wrapped_key).decode("ascii")

    def aes_encrypt(
        self,
        data: object
    )->str:
        # 如果传进来的是 JSON 对象，则紧凑为bytes
        # 如果传进来的字符串，转换为bytes
        if isinstance(data, str):
            data = data.encode("utf-8")
        elif not isinstance(data, bytes):
            data = _json_bytes(data)

        padder = aes_padding.PKCS7(128).padder()
        padded = padder.update(data) + padder.finalize()

        encryptor = Cipher(
            algorithms.AES(self.key),
            modes.CBC(self.iv),
        ).encryptor()

        ciphertext = encryptor.update(padded) + encryptor.finalize()
        return base64.b64encode(ciphertext).decode("ascii")

    def aes_decrypt(
        self,    
        text: str
    ) -> str:
        ciphertext = base64.b64decode(text.strip())

        decryptor = Cipher(
            algorithms.AES(self.key),
            modes.CBC(self.iv),
        ).decryptor()

        padded = decryptor.update(ciphertext) + decryptor.finalize()

        unpadder = aes_padding.PKCS7(128).unpadder()
        plaintext = unpadder.update(padded) + unpadder.finalize()

        return plaintext.decode("utf-8")