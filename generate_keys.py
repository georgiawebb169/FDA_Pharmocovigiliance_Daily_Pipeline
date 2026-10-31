from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

# Generate private key
print("Generating 2048-bit RSA private key...")
private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048
)

# Save private key (PKCS#8, unencrypted, matching rsa_key.p8)
pem_private = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
)
with open("rsa_key.p8", "wb") as f:
    f.write(pem_private)

# Save public key (matching rsa_key.pub)
pem_public = private_key.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
)
with open("rsa_key.pub", "wb") as f:
    f.write(pem_public)

print("Success! rsa_key.p8 and rsa_key.pub have been created in your project folder.")