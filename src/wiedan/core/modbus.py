"""Modbus-TCP-Client für Holdingregister, Discrete Inputs und Coil-Schreibzugriffe. Ohne GUI."""
import itertools
import socket
import struct
import threading

READ_DISCRETE_INPUTS = 0x02
READ_HOLDING_REGISTERS = 0x03
WRITE_SINGLE_COIL = 0x05
WRITE_SINGLE_REGISTER = 0x06
WRITE_MULTIPLE_COILS = 0x0F
WRITE_MULTIPLE_REGISTERS = 0x10
MAX_READ_QUANTITY = 125
MAX_WRITE_QUANTITY = 123
MAX_READ_INPUTS = 2000
MAX_WRITE_COILS = 1968
_MBAP_HEADER_SIZE = 7  # Transaktions-ID, Protokoll-ID, Länge, Unit-ID


class ModbusError(Exception):
    """Verbindung oder Antwort ist fehlgeschlagen."""


class ModbusTcpClient:
    def __init__(self, host: str, port: int = 502, unit_id: int = 0, timeout: float = 1.0):
        self.host = host
        self.port = port
        self.unit_id = unit_id
        self.timeout = timeout
        self._sock: socket.socket | None = None
        self._transaction_ids = itertools.count(1)
        self._lock = threading.Lock()  # Anfragen von mehreren Threads nacheinander

    @property
    def connected(self) -> bool:
        return self._sock is not None

    def connect(self):
        self.close()
        try:
            self._sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        except OSError as exc:
            raise ModbusError(
                f"Verbindung zu {self.host}:{self.port} fehlgeschlagen: {exc}"
            ) from exc

    def close(self):
        if self._sock is not None:
            self._sock.close()
            self._sock = None

    def read_holding_registers(self, address: int, quantity: int = 1) -> list[int]:
        _check_request(address, quantity, MAX_READ_QUANTITY)
        data = self._request(READ_HOLDING_REGISTERS, struct.pack(">HH", address, quantity))
        if len(data) != 1 + 2 * quantity or data[0] != 2 * quantity:
            raise ModbusError("Ungültige Antwort")
        return list(struct.unpack(f">{quantity}H", data[1:]))

    def read_discrete_inputs(self, address: int, quantity: int = 1) -> list[int]:
        """Liest Eingänge als 0/1 in aufsteigender Adressfolge (FC02)."""
        _check_request(address, quantity, MAX_READ_INPUTS)
        data = self._request(READ_DISCRETE_INPUTS, struct.pack(">HH", address, quantity))
        byte_count = (quantity + 7) // 8
        if len(data) != 1 + byte_count or data[0] != byte_count:
            raise ModbusError("Ungültige Antwort")
        return [(data[1 + index // 8] >> (index % 8)) & 1 for index in range(quantity)]

    def write_single_register(self, address: int, value: int):
        _check_request(address, 1, 1, value)
        request = struct.pack(">HH", address, value)
        if self._request(WRITE_SINGLE_REGISTER, request) != request:
            raise ModbusError("Ungültige Antwort")

    def write_multiple_registers(self, address: int, values: list[int]):
        count = len(values)
        _check_request(address, count, MAX_WRITE_QUANTITY, *values)
        payload = struct.pack(f">HHB{count}H", address, count, 2 * count, *values)
        if self._request(WRITE_MULTIPLE_REGISTERS, payload) != struct.pack(">HH", address, count):
            raise ModbusError("Ungültige Antwort")

    def write_single_coil(self, address: int, value: int):
        """Schreibt einen Coil mit FC05; die SPS muss Adresse und Wert bestätigen."""
        _check_request(address, 1, 1)
        if value not in (0, 1):
            raise ValueError("Coil-Wert muss 0 oder 1 sein")
        request = struct.pack(">HH", address, 0xFF00 if value else 0x0000)
        if self._request(WRITE_SINGLE_COIL, request) != request:
            raise ModbusError("Ungültige Antwort")

    def write_multiple_coils(self, address: int, values: list[int]):
        """Schreibt 0/1-Werte ab address in aufsteigender Adressfolge (FC15 / 0x0F)."""
        count = len(values)
        _check_request(address, count, MAX_WRITE_COILS)
        if any(value not in (0, 1) for value in values):
            raise ValueError("Coil-Werte müssen 0 oder 1 sein")
        packed = bytearray((count + 7) // 8)
        for index, value in enumerate(values):
            packed[index // 8] |= value << (index % 8)
        payload = struct.pack(">HHB", address, count, len(packed)) + bytes(packed)
        if self._request(WRITE_MULTIPLE_COILS, payload) != struct.pack(">HH", address, count):
            raise ModbusError("Ungültige Antwort")

    def _request(self, function: int, payload: bytes) -> bytes:
        """Sendet eine Anfrage und liefert die Antwortdaten ohne Funktionscode."""
        with self._lock:
            sock = self._sock
            if sock is None:
                raise ModbusError("Nicht verbunden")
            transaction_id = next(self._transaction_ids) & 0xFFFF
            pdu = bytes([function]) + payload
            request = struct.pack(">HHHB", transaction_id, 0, 1 + len(pdu), self.unit_id) + pdu
            phase = "Senden der Anfrage"
            try:
                sock.sendall(request)
                phase = "Empfangen des Antwort-Headers"
                header = _recv_exact(sock, _MBAP_HEADER_SIZE)
                response_id, _protocol, length, _unit = struct.unpack(">HHHB", header)
                phase = "Empfangen der Antwortdaten"
                response = _recv_exact(sock, length - 1)
            except socket.timeout as exc:
                self.close()
                raise ModbusError(
                    f"Timeout ({self.timeout:g} s) beim {phase} "
                    f"für FC{function:02d}, Unit-ID {self.unit_id}."
                ) from exc
            except OSError as exc:
                self.close()
                raise ModbusError(
                    f"Fehler beim {phase} für FC{function:02d}, Unit-ID {self.unit_id}: {exc}"
                ) from exc

        if response_id != transaction_id:
            raise ModbusError("Antwort passt nicht zur Anfrage")
        if len(response) < 2:
            raise ModbusError("Ungültige Antwort")
        if response[0] == function | 0x80:
            raise ModbusError(f"Gerät meldet Fehler, Modbus-Exceptioncode {response[1]}")
        if response[0] != function:
            raise ModbusError("Ungültige Antwort")
        return response[1:]


def combine_registers(registers: list[int], high_first: bool = True) -> int:
    """Setzt ein oder zwei Register zu einem Wert zusammen."""
    if len(registers) == 1:
        return registers[0]
    first, second = registers
    high, low = (first, second) if high_first else (second, first)
    return (high << 16) | low


def split_value(value: int, quantity: int, high_first: bool = True) -> list[int]:
    """Zerlegt einen Wert in ein oder zwei Register (negative Werte als Zweierkomplement)."""
    if quantity == 1:
        return [value & 0xFFFF]
    high, low = (value >> 16) & 0xFFFF, value & 0xFFFF
    return [high, low] if high_first else [low, high]


def _check_request(address: int, quantity: int, max_quantity: int, *values: int):
    if not 0 <= address <= 0xFFFF:
        raise ValueError("Adresse muss zwischen 0 und 65535 liegen")
    if not 1 <= quantity <= max_quantity:
        raise ValueError(f"Anzahl muss zwischen 1 und {max_quantity} liegen")
    if address + quantity > 0x10000:
        raise ValueError("Adressbereich darf nicht über 65535 hinausgehen")
    if any(not 0 <= value <= 0xFFFF for value in values):
        raise ValueError("Registerwert muss zwischen 0 und 65535 liegen")


def _recv_exact(sock: socket.socket, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise ConnectionError("Gerät hat die Verbindung geschlossen")
        data.extend(chunk)
    return bytes(data)
