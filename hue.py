# hue.py
import os
import json
import uuid
import socket
import ssl
import requests
from dotenv import load_dotenv

load_dotenv()

CA_BUNDLE = "huebridge_cacert_bundle.pem"
ENV_FILE = ".env"


class HueBridge:
    def __init__(self):
        self.bridge_ip = os.getenv("HUE_BRIDGE_IP")
        self.bridge_id = os.getenv("HUE_BRIDGE_ID")
        self.username = os.getenv("HUE_BRIDGE_USERNAME")
        self.clientkey = os.getenv("HUE_BRIDGE_CLIENTKEY")
        self.target_device_name = os.getenv("HUE_BRIDGE_FLASK_DEVICE_NAME")
        self.service_id = os.getenv("HUE_BRIDGE_FLASK_SERVICE_ID")

        if not self.bridge_ip or not self.bridge_id:
            raise ValueError("HUE_BRIDGE_IP and HUE_BRIDGE_ID must be set in .env")

        # requests session (we will target the IP address in URLs)
        self.session = requests.Session()

        # internal on/off tracking
        self.state_on = False

        # validate the bridge certificate and CN (SNI) once at startup
        self._validate_bridge_certificate()

        # if no username -> register
        if not self.username:
            self._register_app()

        # if no service id -> discover devices
        if not self.service_id:
            self._discover_service_id()

    # -------------------------
    # TLS / Certificate helpers
    # -------------------------
    def _validate_bridge_certificate(self):
        """
        Open an SSL socket to the bridge IP while specifying server_hostname=self.bridge_id.
        This performs certificate chain validation and hostname (CN/SAN) validation using the CA bundle.
        Raises exception if validation fails.
        """
        ctx = ssl.create_default_context(cafile=CA_BUNDLE)
        # ctx.check_hostname = True  # default True, rely on server_hostname parameter in wrap_socket
        ctx.verify_mode = ssl.CERT_REQUIRED

        addr = (self.bridge_ip, 443)
        sock = socket.create_connection(addr, timeout=5)
        try:
            # Wrap the socket with SNI = bridge_id so server presents correct cert and hostname is checked.
            ss = ctx.wrap_socket(sock, server_hostname=self.bridge_id)
            # If wrap_socket returns without Exception, the cert chain and hostname are valid.
            # Close the SSL socket immediately; subsequent HTTP requests will use requests.
            ss.close()
        except Exception as e:
            # ensure socket closed
            try:
                sock.close()
            except Exception:
                pass
            raise RuntimeError(f"TLS validation to Hue Bridge failed: {e}")

    # -------------------------
    # .env helper
    # -------------------------
    def _update_env(self, key, value):
        os.environ[key] = value
        # append to .env if not present, otherwise replace existing line
        # simple replace: read file, update or append, write back
        try:
            if os.path.exists(ENV_FILE):
                with open(ENV_FILE, "r", encoding="utf-8") as f:
                    lines = f.readlines()
            else:
                lines = []

            found = False
            new_lines = []
            for ln in lines:
                if ln.strip().startswith(f"{key}="):
                    new_lines.append(f"{key}={value}\n")
                    found = True
                else:
                    new_lines.append(ln)
            if not found:
                new_lines.append(f"{key}={value}\n")

            with open(ENV_FILE, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
        except Exception:
            # fallback: append
            with open(ENV_FILE, "a", encoding="utf-8") as f:
                f.write(f"\n{key}={value}\n")

    # -------------------------
    # Registration (POST /api)
    # -------------------------
    def _register_app(self):
        """
        Register application and generate username + clientkey.
        Must press the Hue link button on the bridge before calling this.
        """
        url = f"https://{self.bridge_ip}/api"
        instance = str(uuid.uuid4())[:8]
        payload = {"devicetype": f"FlaskCookbook#{instance}", "generateclientkey": True}

        # pre-flight TLS check already done in __init__, so we now call requests->IP and include Host header.
        headers = {"Host": self.bridge_id}

        r = self.session.post(url, json=payload, headers=headers, verify=False, timeout=10)
        try:
            data = r.json()
        except Exception:
            raise RuntimeError(f"Unexpected response registering app: {r.status_code} {r.text}")

        # Hue returns a list with either error or success
        if isinstance(data, list) and len(data) > 0 and "error" in data[0]:
            raise RuntimeError(f"Hue registration error: {data[0]['error']}")
        if isinstance(data, list) and len(data) > 0 and "success" in data[0]:
            success = data[0]["success"]
            self.username = success.get("username")
            self.clientkey = success.get("clientkey")
            if self.username:
                self._update_env("HUE_BRIDGE_USERNAME", self.username)
            if self.clientkey:
                self._update_env("HUE_BRIDGE_CLIENTKEY", self.clientkey)
            return

        raise RuntimeError(f"Unexpected registration response: {data}")

    # -------------------------
    # Devices (GET clip/v2/resource/device)
    # -------------------------
    def _get_devices(self):
        url = f"https://{self.bridge_ip}/clip/v2/resource/device"
        headers = {
            "hue-application-key": self.username,
            "Host": self.bridge_id
        }

        r = self.session.get(url, headers=headers, verify=False, timeout=10)

        if r.status_code == 403:
            # maybe username expired or not authorized; re-register then retry
            self._register_app()
            headers["hue-application-key"] = self.username
            r = self.session.get(url, headers=headers, verify=False, timeout=10)

        try:
            return r.json()
        except Exception:
            raise RuntimeError(f"Failed to parse devices JSON: {r.status_code} {r.text}")

    def _discover_service_id(self):
        if not self.target_device_name:
            raise ValueError("HUE_BRIDGE_FLASK_DEVICE_NAME must be set in .env")

        devices = self._get_devices()
        for dev in devices.get("data", []):
            name = dev.get("metadata", {}).get("name", "")
            if name == self.target_device_name:
                for svc in dev.get("services", []):
                    if svc.get("rtype") == "light":
                        rid = svc.get("rid")
                        if rid:
                            self.service_id = rid
                            self._update_env("HUE_BRIDGE_FLASK_SERVICE_ID", rid)
                            return
        raise RuntimeError(f"Device '{self.target_device_name}' with a 'light' service not found")

    # -------------------------
    # Turn on / off
    # -------------------------
    def _set_state(self, new_state: bool):
        if not self.service_id:
            raise ValueError("Service ID missing; cannot set light state")

        url = f"https://{self.bridge_ip}/clip/v2/resource/light/{self.service_id}"
        headers = {
            "hue-application-key": self.username,
            "Host": self.bridge_id,
            "Content-Type": "application/json"
        }
        payload = {"on": {"on": bool(new_state)}}

        r = self.session.put(url, headers=headers, json=payload, verify=False, timeout=10)
        # Accept 200 or 207 depending on bridge behaviour
        if r.status_code not in (200, 207):
            raise RuntimeError(f"Failed to set state: {r.status_code} {r.text}")

    def turn_on(self):
        if self.state_on:
            return
        self._set_state(True)
        self.state_on = True

    def turn_off(self):
        if not self.state_on:
            return
        self._set_state(False)
        self.state_on = False

