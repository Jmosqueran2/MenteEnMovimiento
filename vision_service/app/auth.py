import jwt


def usuario_del_token(token, secreto):
    """Valida un token de acceso emitido por el backend Django (SimpleJWT, HS256).

    Devuelve el id del usuario, o None si el token falta, venció o es inválido.
    """
    if not token:
        return None
    try:
        datos = jwt.decode(token, secreto, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    if datos.get("token_type") != "access":
        return None
    return datos.get("user_id")
