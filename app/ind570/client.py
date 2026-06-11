import socket
import time
import random
from dataclasses import dataclass


@dataclass
class WeightReading:
    weight: float
    unit: str
    stable: bool
    error: str | None


class IND570Client:

    def __init__(self, host, port=1701, simulate=False):
        self.host = host
        self.port = port
        self.simulate = simulate
        self._socket = None
        self._connected = False
        self._sim_weight = 0.0
        self._sim_up = True

    @property
    def connected(self):
        return self._connected

    def connect(self):
        if self.simulate:
            self._connected = True
            return True

        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(5.0)
            self._socket.connect((self.host, self.port))

            resp = self._send("user anonymous")
            if resp and resp.startswith("9"):
                raise ConnectionError(f"Login rejected: {resp}")

            self._connected = True
            return True

        except Exception as e:
            self._connected = False
            if self._socket:
                try:
                    self._socket.close()
                except Exception:
                    pass
            self._socket = None
            msg = str(e).replace("[Errno 111] ", "")
            raise ConnectionError(f"IND570 @ {self.host}:{self.port} – {msg}")

    def _send(self, command, timeout=1.0):
        self._socket.sendall(f"{command}\r\n".encode())
        self._socket.settimeout(timeout)
        data = b""
        try:
            while b"\n" not in data and b"\r" not in data:
                chunk = self._socket.recv(1024)
                if not chunk:
                    break
                data += chunk
        except socket.timeout:
            pass
        return data.decode(errors="replace").strip()

    def disconnect(self):
        if self._socket:
            try:
                self._send("quit", timeout=0.5)
            except Exception:
                pass
            try:
                self._socket.close()
            except Exception:
                pass
        self._socket = None
        self._connected = False

    def read_weight(self) -> WeightReading:
        if self.simulate:
            return self._simulate_read()

        if not self._connected or not self._socket:
            return WeightReading(0.0, "", False, "Not connected")

        try:
            response = self._send("read wt0101 wt0103")

            if not response:
                self._connected = False
                return WeightReading(0.0, "", False, "No response from scale")

            return self._parse_response(response)

        except socket.timeout:
            self._connected = False
            return WeightReading(0.0, "", False, "Connection timeout")
        except OSError as e:
            self._connected = False
            return WeightReading(0.0, "", False, f"Connection error: {e}")
        except Exception as e:
            self._connected = False
            return WeightReading(0.0, "", False, str(e))

    def _parse_response(self, response):
        # Format: 00R453~14780~kg~S
        #   00          = status code (00 = success, 99 = fail)
        #   R           = operation type (R=read, W=write, C=callback)
        #   453         = identifier
        #   ~14780~     = weight value
        #   ~kg~        = unit
        #   ~S          = status flag (S=stable, D=dynamic, ''=standstill)

        fields = response.split("~")

        if len(fields) < 3:
            return WeightReading(0.0, "", False, f"Invalid response: {response}")

        header = fields[0]

        if len(header) < 3:
            return WeightReading(0.0, "", False, f"Invalid header: {header}")

        status = header[:2]
        if status == "99":
            return WeightReading(0.0, "", False, f"Scale error: {response}")

        weight_str = fields[1]
        unit = fields[2] if len(fields) > 2 else ""

        try:
            weight = float(weight_str)
        except ValueError:
            return WeightReading(0.0, unit, False, f"Invalid weight: {weight_str}")

        status_flag = fields[3] if len(fields) > 3 else ""
        stable = status_flag in ("S", "")

        return WeightReading(weight, unit, stable, None)

    def _simulate_read(self):
        step = random.uniform(10, 200)
        if self._sim_up:
            self._sim_weight += step
            if self._sim_weight > 30000:
                self._sim_up = False
        else:
            self._sim_weight -= step
            if self._sim_weight < 0:
                self._sim_weight = 0
                time.sleep(3)
                self._sim_up = True

        stable = random.random() > 0.1
        return WeightReading(round(self._sim_weight, 1), "kg", stable, None)
