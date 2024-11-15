import os
import requests
import gzip
import zipfile
import shutil
import random
import string
import subprocess
import tarfile
from urllib.parse import urlparse
import pwd
import grp

# Chemins des fichiers et dossiers
URLS_FILE = "/var/lib/transmission/.config/transmission-daemon/url.txt"
TMP_DIR = "/var/tmp/transmission/"
DEST_DIR = "/var/lib/transmission/.config/transmission-daemon/blocklists/"
SERVICE_NAME = "transmission-daemon"

# Création des dossiers si nécessaires
os.makedirs(TMP_DIR, exist_ok=True)
os.makedirs(DEST_DIR, exist_ok=True)

# Générer un nom aléatoire
def generate_random_name(original_name):
    random_part = ''.join(random.choices(string.ascii_letters + string.digits, k=4))  # 4 caractères alphanumériques
    return f"{random_part}-{original_name}"

# Téléchargement des fichiers
def download_files():
    print("Début du téléchargement des fichiers...")
    with open(URLS_FILE, 'r') as f:
        urls = f.readlines()

    for url in urls:
        url = url.strip()
        if not url:
            continue

        # Suivi des redirections d'URL
        try:
            print(f"Téléchargement de {url}...")
            response = requests.get(url, stream=True, allow_redirects=True)
            response.raise_for_status()  # Vérifier si la requête a réussi

            # Extraire le nom du fichier de l'URL après redirection
            parsed_url = urlparse(response.url)
            file_name = os.path.basename(parsed_url.path)

            # Vérifier si l'URL mène à un fichier
            if not file_name:
                print(f"Erreur: L'URL {url} ne mène pas directement à un fichier.")
                continue

            # Créer un chemin complet pour le fichier
            file_path = os.path.join(TMP_DIR, file_name)

            # Si le chemin est un répertoire, on saute
            if os.path.isdir(file_path):
                print(f"Erreur: {file_path} est un répertoire, et non un fichier.")
                continue

            # Sauvegarder le fichier téléchargé
            with open(file_path, 'wb') as f:
                f.write(response.content)
            print(f"Fichier téléchargé sous {file_path}")

        except requests.exceptions.RequestException as e:
            print(f"Erreur lors du téléchargement de {url}: {e}")
        except Exception as e:
            print(f"Erreur inattendue: {e}")

# Suppression du contenu du répertoire blocklists
def clean_blocklists():
    print(f"Suppression du contenu de {DEST_DIR}...")
    try:
        for file in os.listdir(DEST_DIR):
            file_path = os.path.join(DEST_DIR, file)
            if os.path.isdir(file_path):
                shutil.rmtree(file_path)
            else:
                os.remove(file_path)
        print("Contenu de blocklists supprimé.")
    except Exception as e:
        print(f"Erreur lors de la suppression du contenu de {DEST_DIR}: {e}")

# Extraction des archives .gz, .zip, .tar.gz
def extract_files():
    print(f"Début de l'extraction des fichiers dans {TMP_DIR}...")
    for file_name in os.listdir(TMP_DIR):
        file_path = os.path.join(TMP_DIR, file_name)

        if file_name.endswith('.gz'):
            try:
                print(f"Extraction de {file_name} (gzip)...")
                with gzip.open(file_path, 'rb') as gz_file:
                    # Identifier le nom du fichier interne (ou utiliser le nom de fichier original)
                    original_name = os.path.basename(file_name).replace('.gz', '')
                    new_name = generate_random_name(original_name)  # Pas d'extension .gz ici
                    dest_file_path = os.path.join(DEST_DIR, new_name)

                    # Extraire le fichier avec le nouveau nom
                    with open(dest_file_path, 'wb') as extracted_file:
                        shutil.copyfileobj(gz_file, extracted_file)  # Décompression et copie
                print(f"Fichier extrait sous {new_name}")
            except Exception as e:
                print(f"Erreur lors de l'extraction de {file_name}: {e}")
        elif file_name.endswith('.zip'):
            try:
                print(f"Extraction de {file_name} (zip)...")
                with zipfile.ZipFile(file_path, 'r') as zip_file:
                    for member in zip_file.namelist():
                        original_name = os.path.basename(member)
                        new_name = generate_random_name(original_name)
                        dest_file_path = os.path.join(DEST_DIR, new_name)
                        with open(dest_file_path, 'wb') as extracted_file:
                            extracted_file.write(zip_file.read(member))
                print(f"Fichier {file_name} extrait.")
            except Exception as e:
                print(f"Erreur lors de l'extraction de {file_name}: {e}")
        elif file_name.endswith('.tar.gz'):
            try:
                print(f"Extraction de {file_name} (tar.gz)...")
                with tarfile.open(file_path, 'r:gz') as tar_file:
                    tar_file.extractall(path=DEST_DIR)
                print(f"Fichier {file_name} extrait.")
            except Exception as e:
                print(f"Erreur lors de l'extraction de {file_name}: {e}")

# Modification des permissions des fichiers extraits
def change_permissions():
    print(f"Modification des permissions des fichiers dans {DEST_DIR}...")
    # Utiliser les modules pwd et grp pour obtenir les UID et GID
    try:
        transmission_uid = pwd.getpwnam('transmission').pw_uid
        hdd_gid = grp.getgrnam('hdd').gr_gid
    except KeyError as e:
        print(f"Erreur lors de la récupération des informations utilisateur/groupe : {e}")
        return

    for file_name in os.listdir(DEST_DIR):
        file_path = os.path.join(DEST_DIR, file_name)
        try:
            print(f"Changement de l'utilisateur et du groupe pour {file_path}")
            os.chown(file_path, transmission_uid, hdd_gid)
            print(f"Permissions modifiées pour {file_name}")
        except Exception as e:
            print(f"Erreur lors de la modification des permissions de {file_path}: {e}")

# Redémarrer le service
def restart_service():
    print(f"Redémarrage du service {SERVICE_NAME}...")
    try:
        subprocess.run(["systemctl", "restart", f"{SERVICE_NAME}.service"], check=True)
        print(f"Service {SERVICE_NAME} redémarré avec succès.")
    except Exception as e:
        print(f"Erreur lors du redémarrage du service: {e}")

# Supprimer le contenu de /var/tmp/transmission/
def clean_tmp_dir():
    print(f"Suppression des fichiers dans {TMP_DIR}...")
    try:
        shutil.rmtree(TMP_DIR)
        os.makedirs(TMP_DIR, exist_ok=True)
        print(f"Dossier {TMP_DIR} nettoyé.")
    except Exception as e:
        print(f"Erreur lors de la suppression du contenu de {TMP_DIR}: {e}")

# Exécution des étapes
if __name__ == "__main__":
    print("Début du programme...\n")
    download_files()
    clean_blocklists()
    extract_files()
    change_permissions()
    restart_service()
    clean_tmp_dir()
    print("Fin du programme.")
