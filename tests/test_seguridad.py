import subprocess
from pathlib import Path


RAIZ_PROYECTO = Path(__file__).resolve().parent.parent


EXTENSIONES_PROHIBIDAS = {
    ".crt",
    ".key",
    ".pem",
    ".csr",
    ".pfx",
    ".p12",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".csv"
}


NOMBRES_PROHIBIDOS = {
    ".env",
    "certificado.crt",
    "privada.key",
    "facturador.db"
}


def archivos_versionados():
    resultado = subprocess.run(
        [
            "git",
            "ls-files"
        ],
        cwd=RAIZ_PROYECTO,
        capture_output=True,
        text=True,
        check=True
    )

    return [
        linea.strip()
        for linea in resultado.stdout.splitlines()
        if linea.strip()
    ]


def test_env_real_no_esta_versionado():
    archivos = archivos_versionados()

    assert ".env" not in archivos


def test_no_hay_archivos_con_nombres_sensibles():
    archivos = archivos_versionados()

    encontrados = [
        archivo
        for archivo in archivos
        if Path(archivo).name in NOMBRES_PROHIBIDOS
    ]

    assert encontrados == []


def test_no_hay_extensiones_sensibles_versionadas():
    archivos = archivos_versionados()

    encontrados = [
        archivo
        for archivo in archivos
        if Path(archivo).suffix.lower() in EXTENSIONES_PROHIBIDAS
    ]

    assert encontrados == []


def test_env_example_si_esta_versionado():
    archivos = archivos_versionados()

    assert ".env.example" in archivos


def test_archivos_principales_estan_versionados():
    archivos = archivos_versionados()

    obligatorios = {
        "app/main.py",
        "app/database.py",
        "procesar_lote.py",
        "requirements.txt",
        ".gitignore"
    }

    faltantes = obligatorios.difference(archivos)

    assert faltantes == set()