from sqlalchemy.orm import Session

from app.models.user import User


def get_user_by_email(database: Session, email: str):
    """
    Busca un usuario por correo electrónico.
    Se utiliza para validar correo único (RF_01) y para autenticación (RF_02).
    """
    return database.query(User).filter(User.email == email).first()


def get_user_by_id(database: Session, user_id: int):
    """
    Busca un usuario por su ID.
    Se utiliza para obtener el usuario actual a partir del token JWT.
    """
    return database.query(User).filter(User.id == user_id).first()


def create_user(database: Session, email: str, password_hash: str, name: str):
    """
    Crea un nuevo usuario en la base de datos (CU_01, paso 14).
    La contraseña ya debe estar hasheada antes de llegar aquí (RNF_01).
    Rol por defecto: 'user' (según reservent-db.sql).
    """
    new_user = User(
        email=email,
        password_hash=password_hash,
        name=name,
        role="user"
    )

    database.add(new_user)
    database.commit()
    database.refresh(new_user)

    return new_user
