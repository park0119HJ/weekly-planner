# generate_vapid.py
import json
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from base64 import urlsafe_b64encode

# 1) ECDSA 키 쌍 생성 (P-256)
private_key = ec.generate_private_key(ec.SECP256R1())
public_key  = private_key.public_key()

# 2) DER 포맷 바이트로 직렬화
private_bytes = private_key.private_bytes(
    encoding=serialization.Encoding.DER,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
)
public_bytes = public_key.public_bytes(
    encoding=serialization.Encoding.DER,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
)

# 3) URL-safe Base64 인코딩 (패딩 제거)
priv = urlsafe_b64encode(private_bytes).rstrip(b'=').decode('utf-8')
pub  = urlsafe_b64encode(public_bytes).rstrip(b'=').decode('utf-8')

# 4) 출력
print("==== VAPID 키 페어 ====")
print("Public Key:\n", pub)
print("Private Key:\n", priv)
