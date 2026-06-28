import sys
from pathlib import Path

# Agregar raíz al path
root_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root_dir))

from src.storage.database import DatabaseManager

def probar():
    db = DatabaseManager()
    print("Inicializando DatabaseManager y ejecutando migración...")
    print("Usuarios actuales:")
    session = db.SessionLocal()
    from src.storage.database import UsuarioDB
    users = session.query(UsuarioDB).all()
    for u in users:
        print(f"- {u.username}: email={u.email}, recibir={getattr(u, 'recibir_alertas', 'N/A')}")
    session.close()

    print("\nIntentando actualizar preferencias de 'admin'...")
    exito = db.actualizar_preferencias_alertas("admin", True, "*", "*")
    print(f"Resultado de la actualización: {exito}")

if __name__ == "__main__":
    probar()
