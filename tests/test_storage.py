"""
Pruebas Unitarias para la Capa de Persistencia (SQLite).

Este módulo valida la correcta inserción en la base de datos local SQLite,
la prevención efectiva de duplicados lógicos y la lectura a DataFrames de Pandas.
"""

import datetime

from src.processing.schemas import SubvencionSchema
from src.storage.database import DatabaseManager
from src.storage.models import SubvencionDB, UsuarioDB
from src.storage.db_session import DBSession


def test_insertar_y_cargar_dataframe(db_manager_in_memory: DatabaseManager) -> None:
    """
    ARRANGE: Configurar una base de datos en memoria vacía y crear dos registros
             de subvenciones normalizados.
    ACT: Insertar los registros en lote y cargar el DataFrame resultante.
    ASSERT: Validar que se insertaron 2 registros, que el DataFrame cargado no
            está vacío y que contiene las columnas con los tipos correctos.
    """
    db = db_manager_in_memory

    subvenciones = [
        SubvencionSchema(
            Tipo_Subvencion="Ayudas Kit Digital",
            Cuantia=150000.0,
            Fecha_Vigencia=datetime.date(2026, 12, 31),
            Entidad_Convocante="Ministerio de Economía",
            Ambito_Territorial="España",
            Actividad_Relacionada="Digitalización/Robótica",
            Es_Simulado=True,
        ),
        SubvencionSchema(
            Tipo_Subvencion="Subvenciones LIFE Green",
            Cuantia=2500000.0,
            Fecha_Vigencia=datetime.date(2026, 9, 30),
            Entidad_Convocante="Comisión Europea",
            Ambito_Territorial="Europa",
            Actividad_Relacionada="Transición Verde/Sostenibilidad",
            Es_Simulado=False,
        ),
    ]

    # Inserción
    insertados_cnt = db.bulk_insert(subvenciones)
    assert insertados_cnt == 2

    # Carga de DataFrame
    df = db.load_as_dataframe()

    assert df.shape[0] == 2
    assert "Tipo_Subvencion" in df.columns
    assert "Cuantia" in df.columns
    assert "Fecha_Vigencia" in df.columns
    assert "Es_Simulado" in df.columns

    # Validar tipos de datos
    assert df["Cuantia"].iloc[0] == 150000.0
    assert df["Ambito_Territorial"].iloc[1] == "Europa"
    assert bool(df["Es_Simulado"].iloc[0]) is True
    assert bool(df["Es_Simulado"].iloc[1]) is False
    assert isinstance(df["Fecha_Vigencia"].iloc[0], datetime.date)


def test_prevencion_duplicados_deterministica(
    db_manager_in_memory: DatabaseManager,
) -> None:
    """
    ARRANGE: Configurar DB en memoria y crear un registro único.
    ACT: Insertar el mismo registro dos veces.
    ASSERT: Validar que la segunda inserción reporta 0 y evita duplicados.
    """
    db = db_manager_in_memory

    sub = SubvencionSchema(
        Tipo_Subvencion="Ayuda Duplicable",
        Cuantia=12000.0,
        Fecha_Vigencia=datetime.date(2026, 10, 15),
        Entidad_Convocante="Gobierno de Navarra",
        Ambito_Territorial="Navarra",
        Actividad_Relacionada="Educación/Social",
        Es_Simulado=True,
    )

    # Primera inserción
    res1 = db.bulk_insert([sub])
    assert res1 == 1

    # Segunda inserción (del mismo registro exacto)
    res2 = db.bulk_insert([sub])
    assert res2 == 0

    # Comprobación física en base de datos
    session = DBSession.get_session()
    en_bd = session.query(SubvencionDB).count()
    session.close()

    assert en_bd == 1


def test_alta_usuario_y_validar_credenciales(
    db_manager_in_memory: DatabaseManager,
) -> None:
    """
    ARRANGE: Configurar base de datos y preparar datos de usuario de prueba.
    ACT: Crear el usuario y validar sus credenciales correctas e incorrectas.
    ASSERT: Verificar que la creación es exitosa, no admite duplicados y
            la autenticación valida hashes bcrypt de forma correcta.
    """
    db = db_manager_in_memory

    username = "OPERADOR"
    email = "operador@moriarty.local"
    password = "seguraPassword123"

    # Act - Registro
    exito_alta = db.crear_usuario(username, email, password)
    assert exito_alta is True

    # Act - Intento de duplicado
    exito_duplicado = db.crear_usuario(username, email, password)
    assert exito_duplicado is False

    # Act & Assert - Validar credenciales correctas e incorrectas
    assert db.validar_credenciales(username, password) is True
    assert db.validar_credenciales(username, "incorrecta") is False
    assert db.validar_credenciales("inexistente", password) is False


def test_baja_usuario_y_obtener_lista(
    db_manager_in_memory: DatabaseManager,
) -> None:
    """
    ARRANGE: Crear un usuario de prueba en la base de datos.
    ACT: Obtener lista de usuarios, dar de baja al usuario y re-obtener lista.
    ASSERT: Verificar que el usuario aparece en la lista, luego se elimina
            correctamente y ya no se encuentra registrado en el sistema.
    """
    db = db_manager_in_memory

    username = "TEMPORAL_USER"
    email = "temporal@moriarty.local"
    password = "tempPassword"

    # Registro
    db.crear_usuario(username, email, password)

    # Act - Obtener lista inicial (incluye admin por defecto sembrado)
    usuarios_iniciales = db.obtener_usuarios()
    nombres_usuarios_iniciales = [u.username for u in usuarios_iniciales]
    assert username in nombres_usuarios_iniciales

    # Act - Dar de baja
    exito_baja = db.eliminar_usuario(username)
    assert exito_baja is True

    # Act - Comprobación final
    usuarios_finales = db.obtener_usuarios()
    nombres_usuarios_finales = [u.username for u in usuarios_finales]
    assert username not in nombres_usuarios_finales

    # Dar de baja a un usuario inexistente
    exito_inexistente = db.eliminar_usuario("usuario_fantasma")
    assert exito_inexistente is False


def test_actualizar_contrasena(db_manager_in_memory: DatabaseManager) -> None:
    """
    ARRANGE: Registrar un usuario con contraseña inicial.
    ACT: Modificar la contraseña del usuario y validar con la nueva y la vieja.
    ASSERT: Verificar que la contraseña cambia con éxito, autentica con la nueva
            y falla con la antigua.
    """
    db = db_manager_in_memory

    username = "USER_TEST_PWD"
    email = "testpwd@moriarty.local"
    password_vieja = "vieja123"
    password_nueva = "nueva456"

    db.crear_usuario(username, email, password_vieja)

    # Act - Actualizar contraseña
    exito_cambio = db.actualizar_contrasena(username, password_nueva)
    assert exito_cambio is True

    # Assert - Comprobar autenticación con ambas
    assert db.validar_credenciales(username, password_nueva) is True
    assert db.validar_credenciales(username, password_vieja) is False

    # Act & Assert - Intentar cambiar contraseña de un usuario que no existe
    exito_fantasma = db.actualizar_contrasena("fantasma", password_nueva)
    assert exito_fantasma is False


def test_actualizar_preferencias_alertas(db_manager_in_memory) -> None:
    """
    ARRANGE: Registrar un usuario.
    ACT: Actualizar sus preferencias de alertas.
    ASSERT: Verificar que la actualización devuelve éxito y se persiste.
    """
    db = db_manager_in_memory
    username = "USER_ALERTS_PREF"
    email = "testalerts@moriarty.local"

    db.crear_usuario(username, email, "pass123")

    # Act
    exito, err_msg = db.actualizar_preferencias_alertas(
        username=username,
        recibir=True,
        sectores="Agroalimentario,Educación/Social",
        ambitos="Europa,Navarra"
    )

    # Assert
    assert exito is True
    assert err_msg == ""

    # Validar persistencia real en la sesión de base de datos
    session = DBSession.get_session()
    user_db = session.query(UsuarioDB).filter(
        UsuarioDB.username == username.upper()
    ).first()
    assert user_db.recibir_alertas is True
    assert user_db.sectores_interes == "Agroalimentario,Educación/Social"
    assert user_db.ambitos_interes == "Europa,Navarra"
    session.close()


def test_usuarios_semilla_default(db_manager_in_memory: DatabaseManager) -> None:
    """
    ARRANGE: Inicializar base de datos en memoria (sembrado por defecto).
    ACT: Validar credenciales de los usuarios semilla.
    ASSERT: Confirmar que ADMIN, MIKEL, ANA y BRENDA están registrados
            y sus contraseñas respectivas se validan de forma correcta.
    """
    db = db_manager_in_memory

    # Validar que los usuarios se validan con sus claves
    assert db.validar_credenciales("ADMIN", "admin123") is True
    assert db.validar_credenciales("MIKEL", "jeVnmq54H86jspj") is True
    assert db.validar_credenciales("ANA", "ana123*QP") is True
    assert db.validar_credenciales("BRENDA", "brenda123*PM") is True

    # Validar que fallan con credenciales incorrectas
    assert db.validar_credenciales("MIKEL", "clave_erronea") is False



