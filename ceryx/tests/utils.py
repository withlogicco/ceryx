import os
import stat
import subprocess


CERTIFICATE_ROOT = "/usr/local/share/certificates"
EVERYBODY_CAN_READ = stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH


def create_certificates_for_host(host):
    base_path = f"{CERTIFICATE_ROOT}/{host}"
    certificate_path = f"{base_path}.crt"
    key_path = f"{base_path}.key"

    command = [
        "openssl",
        "req", "-x509",
        "-newkey", "rsa:4096",
        "-keyout", key_path,
        "-out", certificate_path,
        "-days", "1",
        "-subj", f"/C=GR/ST=Attica/L=Athens/O=SourceLair/OU=Org/CN={host}",
        "-nodes",
    ]
    subprocess.run(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
    )
    os.chmod(certificate_path, EVERYBODY_CAN_READ)
    os.chmod(key_path, EVERYBODY_CAN_READ)

    return certificate_path, key_path
