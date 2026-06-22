from django.core.management.base import BaseCommand

from frontend.qz_signing import generate_qz_certificate, get_qz_cert_path, get_qz_key_path


class Command(BaseCommand):
    help = "Genera certificado y clave privada para QZ Tray (impresión sin cartel de confianza)."

    def handle(self, *args, **options):
        cert_path, key_path = generate_qz_certificate()
        self.stdout.write(self.style.SUCCESS("Certificados QZ generados:"))
        self.stdout.write(f"  Público:  {cert_path}")
        self.stdout.write(f"  Privado:  {key_path}")
        self.stdout.write("")
        self.stdout.write("Instalá el certificado público en QZ Tray (una vez por PC):")
        self.stdout.write("  Mac: copiá digital-certificate.txt a")
        self.stdout.write("       /Applications/QZ Tray.app/Contents/Resources/override.crt")
        self.stdout.write("  Windows: copiá a C:\\Program Files\\QZ Tray\\override.crt")
        self.stdout.write("")
        self.stdout.write("Reiniciá QZ Tray después de copiar el archivo.")
