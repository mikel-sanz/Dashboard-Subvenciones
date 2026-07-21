import bcrypt

def hash_password(plain_text: str) -> str:
    """Hashea una contraseña en texto plano utilizando bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain_text.encode('utf-8'), salt).decode('utf-8')

def verify_password(plain_text: str, hashed_pass: str) -> bool:
    """Verifica si una contraseña en texto plano coincide con su hash."""
    try:
        return bcrypt.checkpw(plain_text.encode('utf-8'), hashed_pass.encode('utf-8'))
    except ValueError:
        return False
