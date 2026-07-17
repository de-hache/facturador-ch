from app.backup import crear_backup_sqlite


if __name__ == "__main__":
    ruta = crear_backup_sqlite()

    print(
        f"Backup creado correctamente: {ruta}"
    )