"""Native regression check; set DOMAIN_GATEWAY_NGINX_IMAGE to an installed image."""

import json
import os
from pathlib import Path
import socket
import ssl
import subprocess
import tempfile
import time
import unittest
import uuid

from render import render


@unittest.skipUnless(os.environ.get("DOMAIN_GATEWAY_NGINX_IMAGE"), "native Nginx image not selected")
class RedirectTests(unittest.TestCase):
    def test_domain_redirect_uses_public_origin_and_legacy_listener_keeps_its_port(self):
        image = os.environ["DOMAIN_GATEWAY_NGINX_IMAGE"]
        with tempfile.TemporaryDirectory(prefix="gateway-redirect-test-") as temporary:
            root = Path(temporary)
            for name in ("sites", "policies", "certs", "webroot"):
                (root / name).mkdir()
            subprocess.run([
                "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                "-subj", "/CN=app.example.invalid",
                "-addext", "subjectAltName=DNS:app.example.invalid,DNS:legacy.example.invalid",
                "-keyout", str(root / "certs/privkey.pem"),
                "-out", str(root / "certs/fullchain.pem"),
            ], check=True, capture_output=True)
            values = {
                "WEB_DOMAINS": ["app.example.invalid"], "WEB_DOMAIN": "app.example.invalid",
                "HTTP_PORT": 80, "HTTPS_PORT": 443, "TLS_PORT": 8443, "RAW_PORT": 8444,
                "DOCKER_DNS_IP": "127.0.0.11", "RAW_BACKEND": "127.0.0.1:9",
                "HTTP_POLICY_GLOB": "/etc/nginx/policies/*.conf",
                "HTTP_VHOSTS_GLOB": "/etc/nginx/sites/*.conf",
                "PRIVATE_LOCATIONS_INCLUDE": "/etc/nginx/policies/app.inc",
            }
            (root / "nginx.conf").write_text(render("public-nginx.conf.template", values))
            (root / "sites/app.conf").write_text(render("public-vhost.conf.template", values))
            (root / "policies/app.inc").write_text("location / { return 302 /landing; }\n")
            (root / "policies/legacy.conf").write_text("""
server {
    listen 9443 ssl;
    server_name legacy.example.invalid;
    ssl_certificate /etc/nginx/domain-certs/fullchain.pem;
    ssl_certificate_key /etc/nginx/domain-certs/privkey.pem;
    location / { return 302 /landing; }
}
""")
            name = "gateway-redirect-test-" + uuid.uuid4().hex
            args = ["docker", "run", "--detach", "--rm", "--pull=never", "--name", name,
                    "-p", "127.0.0.1::443", "-p", "127.0.0.1::9443"]
            for source, target in (("nginx.conf", "/etc/nginx/nginx.conf"),
                                   ("sites", "/etc/nginx/sites"),
                                   ("policies", "/etc/nginx/policies"),
                                   ("certs", "/etc/nginx/domain-certs"),
                                   ("webroot", "/var/www/acme")):
                args += ["-v", f"{root / source}:{target}:ro"]
            subprocess.run([*args, image], check=True, capture_output=True)
            try:
                info = json.loads(subprocess.check_output(["docker", "inspect", name]))[0]
                ports = info["NetworkSettings"]["Ports"]
                context = ssl.create_default_context(cafile=str(root / "certs/fullchain.pem"))

                def location(host, port_key):
                    port = int(ports[port_key][0]["HostPort"])
                    for attempt in range(30):
                        connection = None
                        try:
                            connection = socket.create_connection(("127.0.0.1", port), timeout=3)
                            tls = context.wrap_socket(connection, server_hostname=host)
                            break
                        except ssl.SSLCertVerificationError:
                            raise
                        except OSError:
                            if connection is not None:
                                connection.close()
                            if attempt == 29:
                                raise
                            time.sleep(0.1)
                    with tls:
                        tls.sendall(f"GET /entry HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n".encode())
                        data = b""
                        while b"\r\n\r\n" not in data:
                            block = tls.recv(8192)
                            self.assertTrue(block, "response ended before headers")
                            data += block
                    lines = data.split(b"\r\n\r\n", 1)[0].decode().split("\r\n")
                    self.assertIn(" 302 ", lines[0])
                    headers = dict(line.split(": ", 1) for line in lines[1:])
                    return {key.lower(): value for key, value in headers.items()}["location"]

                self.assertEqual(location("app.example.invalid", "443/tcp"),
                                 "https://app.example.invalid/landing")
                self.assertEqual(location("legacy.example.invalid", "9443/tcp"),
                                 "https://legacy.example.invalid:9443/landing")
            finally:
                subprocess.run(["docker", "rm", "--force", name], check=True, capture_output=True)


if __name__ == "__main__":
    unittest.main()
