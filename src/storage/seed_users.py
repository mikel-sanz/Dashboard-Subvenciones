import sqlite3
import os
import sys

# Añadir el directorio src al path para importar correctamente
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.storage.auth_service import hash_password

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "processed", "subvenciones.db"))

users_to_seed = [
    ("MIKEL", "jeVnmq54H86jspj", "mikel@moriarty.local", "user"),
    ("ANA", "ana123*QP", "ana@moriarty.local", "user"),
    ("BRENDA", "brenda123*PM", "brenda@moriarty.local", "user"),
    ("ADMIN", "Admin_Moriarty#2026!", "admin@moriarty.local", "admin"),
    ("INVITADO", "Invitado1234", "invitado@moriarty.local", "guest")
]

def seed_db():
    print(f"Conectando a SQLite en: {DB_PATH}")
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Asegurar que la tabla existe basándonos en la estructura típica de un ORM
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            email TEXT,
            role TEXT DEFAULT 'user'
        )
    ''')
    
    for username, plain_pass, email, role in users_to_seed:
        hashed = hash_password(plain_pass)
        try:
            cursor.execute('''
                INSERT INTO users (username, hashed_password, email, role)
                VALUES (?, ?, ?, ?)
            ''', (username, hashed, email, role))
            print(f"Usuario {username} insertado correctamente.")
        except sqlite3.IntegrityError:
            print(f"Usuario {username} ya existe, actualizando contraseña...")
            cursor.execute('''
                UPDATE users SET hashed_password = ?, email = ?, role = ? WHERE username = ?
            ''', (hashed, email, role, username))
            print(f"Usuario {username} actualizado.")
            
    conn.commit()
    conn.close()
    print("Seeding finalizado con éxito.")

if __name__ == "__main__":
    seed_db()
