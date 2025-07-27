import os
import base64
import secrets
import string

salt = os.urandom(16)
salt_b64 = base64.b64encode(salt).decode('utf-8')

print(f"Сгенерированная соль (base64): {salt_b64}")

alphabet = string.ascii_letters + string.digits + string.punctuation
master_password = ''.join(secrets.choice(alphabet) for _ in range(32))

print(f"Сгенерированный мастер-пароль: {master_password}")