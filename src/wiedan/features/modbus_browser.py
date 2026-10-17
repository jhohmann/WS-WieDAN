"""Modbus-Browser: Holdingregister, Discrete Inputs und Coil-Schreibzugriffe. Ohne Projektbezug."""
from dataclasses import dataclass

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wiedan.core.modbus import (
    MAX_WRITE_COILS,
    READ_DISCRETE_INPUTS,
    READ_HOLDING_REGISTERS,
    WRITE_MULTIPLE_COILS,
    WRITE_MULTIPLE_REGISTERS,
    WRITE_SINGLE_REGISTER,
    ModbusError,
    ModbusTcpClient,
    combine_registers,
    split_value,
)

UNIT_ID = 0  # Unit-ID bei direkter Modbus-TCP-Verbindung; Gateways können abweichen
WORD_BITS = 16
MAX_BITS = 32
COLUMNS = (
    "Name", "Dezimal", "Hex", "Binär", "Adresse", "Offset", "Bitlänge", "Wortfolge", "Funktion",
)
VALUE_COLUMNS = (1, 2, 3)
NO_VALUE = "–"
WORD_ORDERS = ("Hi-Lo (Standard)", "Lo-Hi")  # Reihenfolge der zwei Register bei 32 Bit
WRITE_WIDTHS = (WORD_BITS, MAX_BITS)


@dataclass(frozen=True)
class Query:
    name: str
    address: int  # 0-basierte Registeradresse
    offset: int  # Bitposition im Wert, 0 = niederwertigstes Bit
    length: int  # Anzahl Bits
    high_first: bool = True  # Bei zwei Registern: höherwertiges Wort zuerst
    function: int = READ_HOLDING_REGISTERS

    @property
    def quantity(self) -> int:
        """Anzahl der Eingänge (FC02) bzw. Register (FC03)."""
        if self.function == READ_DISCRETE_INPUTS:
            return self.length
        return 1 if self.offset + self.length <= WORD_BITS else 2

    @property
    def key(self) -> tuple[int, int, int]:
        return self.function, self.address, self.quantity

    def extract(self, registers: list[int], high_first: bool) -> int:
        if self.function == READ_DISCRETE_INPUTS:
            return sum(bit << index for index, bit in enumerate(registers))
        value = combine_registers(registers, high_first)
        return (value >> self.offset) & ((1 << self.length) - 1)


class _PollSignals(QObject):
    finished = Signal(object, object, object)  # Client, {(Funktion, Adresse, Anzahl): Werte}, Fehler


class _PollTask(QRunnable):
    """Verbindet bei Bedarf und liest alle Bereiche nacheinander, außerhalb des GUI-Threads."""

    def __init__(self, client: ModbusTcpClient, reads: list[tuple[int, int, int]]):
        super().__init__()
        self.client = client
        self.reads = reads
        self.signals = _PollSignals()

    def run(self):
        try:
            if not self.client.connected:
                self.client.connect()
            registers = {}
            for function, address, quantity in self.reads:
                if function == READ_DISCRETE_INPUTS:
                    values = self.client.read_discrete_inputs(address, quantity)
                elif function == READ_HOLDING_REGISTERS:
                    values = self.client.read_holding_registers(address, quantity)
                else:
                    raise ValueError("Nicht unterstützte Lesefunktion")
                registers[function, address, quantity] = values
        except (ModbusError, ValueError) as exc:
            self.signals.finished.emit(self.client, None, str(exc))
        else:
            self.signals.finished.emit(self.client, registers, None)


@dataclass(frozen=True)
class WriteRequest:
    function: int
    address: int
    values: list[int]
    description: str  # Bestätigung bezieht sich auf den abgesendeten Auftrag


class _WriteSignals(QObject):
    finished = Signal(object, object, object)  # Client, Auftrag, Fehlertext oder None bei Erfolg


class _WriteTask(QRunnable):
    """Schreibt Register oder Coils außerhalb des GUI-Threads."""

    def __init__(self, client: ModbusTcpClient, request: WriteRequest):
        super().__init__()
        self.client = client
        self.request = request
        self.signals = _WriteSignals()

    def run(self):
        try:
            request = self.request
            if request.function == WRITE_MULTIPLE_COILS:
                self.client.write_multiple_coils(request.address, request.values)
            elif request.function == WRITE_SINGLE_REGISTER:
                self.client.write_single_register(request.address, request.values[0])
            elif request.function == WRITE_MULTIPLE_REGISTERS:
                self.client.write_multiple_registers(request.address, request.values)
            else:
                raise ValueError("Nicht unterstützte Schreibfunktion")
        except (ModbusError, ValueError) as exc:
            self.signals.finished.emit(self.client, self.request, str(exc))
        else:
            self.signals.finished.emit(self.client, self.request, None)


def _parse_write_value(text: str, bits: int) -> int:
    """Liest Dezimal- oder 0x-Hex-Eingabe und liefert den vorzeichenlosen Wert mit der Breite bits."""
    text = text.strip()
    try:
        value = int(text, 16) if text.lower().startswith("0x") else int(text, 10)
    except ValueError:
        raise ValueError("Wert nicht lesbar: Dezimal oder 0x-Hex eingeben") from None
    low, high = -(1 << (bits - 1)), (1 << bits) - 1
    if not low <= value <= high:
        raise ValueError(f"Wert muss zwischen {low} und {high} liegen")
    return value & high


def _parse_coils(text: str) -> list[int]:
    digits = "".join(text.split())
    if not digits or any(digit not in "01" for digit in digits):
        raise ValueError("Coils als 0/1-Folge eingeben, z. B. 1 0 1 1 (aufsteigende Adressen).")
    if len(digits) > MAX_WRITE_COILS:
        raise ValueError(f"Höchstens {MAX_WRITE_COILS} Coils pro Schreibauftrag.")
    return [int(digit) for digit in digits]


class ModbusBrowser(QWidget):
    message = Signal(str)

    def __init__(self):
        super().__init__()
        self._client: ModbusTcpClient | None = None
        self._busy = False
        self._writing = False
        self._pending_write: WriteRequest | None = None
        self._task: _PollTask | _WriteTask | None = None
        self._queries: list[Query] = []
        self._registers: dict[tuple[int, int, int], list[int]] = {}
        self._last_poll_error: str | None = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)

        self._ip = QLineEdit()
        self._ip.setPlaceholderText("IP-Adresse, z. B. 192.168.196.22")
        self._ip.setMinimumWidth(200)
        self._ip.textChanged.connect(lambda: self._set_invalid(self._ip, False))
        self._port = QSpinBox()
        self._port.setRange(1, 65535)
        self._port.setValue(502)
        self._interval = QSpinBox()
        self._interval.setRange(100, 10000)
        self._interval.setSingleStep(100)
        self._interval.setValue(500)
        self._interval.setSuffix(" ms")
        self._interval.valueChanged.connect(self._timer.setInterval)
        self._connect_button = QPushButton("Verbinden")
        self._connect_button.setObjectName("modbusConnectButton")
        self._connect_button.ensurePolished()
        self._connect_button.setFixedWidth(self._connect_button.sizeHint().width())
        self._connect_button.clicked.connect(self._toggle_connection)
        self._status = QLabel("Getrennt")

        connection_row = QHBoxLayout()
        connection_row.addWidget(QLabel("IP"))
        connection_row.addWidget(self._ip, 1)
        connection_row.addWidget(QLabel("Port"))
        connection_row.addWidget(self._port)
        connection_row.addWidget(QLabel("Aktualisierung"))
        connection_row.addWidget(self._interval)
        connection_row.addWidget(self._connect_button)

        self._name = QLineEdit()
        self._name.setPlaceholderText("Name")
        self._read_function = QComboBox()
        self._read_function.addItem("Holdingregister (FC03)", READ_HOLDING_REGISTERS)
        self._read_function.addItem("Discrete Inputs (FC02)", READ_DISCRETE_INPUTS)
        self._address = QSpinBox()
        self._address.setRange(0, 65535)
        self._address.setToolTip("0-basierte Registeradresse")
        self._offset = QSpinBox()
        self._offset.setRange(0, MAX_BITS - 1)
        self._offset.setToolTip("Bitposition, 0 = niederwertigstes Bit")
        self._length = QSpinBox()
        self._length.setRange(1, MAX_BITS)
        self._length.setValue(WORD_BITS)
        self._read_order = QComboBox()
        self._read_order.addItems(WORD_ORDERS)
        self._read_order.setEnabled(False)
        self._read_order.setToolTip("Reihenfolge der beiden 16-Bit-Register")
        self._offset.valueChanged.connect(self._on_query_bits_changed)
        self._length.valueChanged.connect(self._on_query_bits_changed)
        self._add_button = QPushButton("Abfrage hinzufügen")
        self._add_button.setEnabled(False)
        self._add_button.clicked.connect(self._add_query)
        self._name.textChanged.connect(
            lambda text: self._add_button.setEnabled(bool(text.strip()))
        )
        remove_button = QPushButton("Entfernen")
        remove_button.clicked.connect(self._remove_query)

        query_row = QHBoxLayout()
        for label, widget in (
            ("Name", self._name), ("Adresse", self._address),
        ):
            query_row.addWidget(QLabel(label))
            query_row.addWidget(widget, 1 if widget is self._name else 0)
        query_row.addWidget(self._add_button)
        query_row.addWidget(remove_button)
        query_bits_row = QHBoxLayout()
        query_bits_row.addWidget(QLabel("Funktion"))
        query_bits_row.addWidget(self._read_function)
        self._length_label = QLabel("Bitlänge")
        for label, widget in (
            (QLabel("Offset"), self._offset), (self._length_label, self._length),
            (QLabel("Wortfolge"), self._read_order),
        ):
            query_bits_row.addWidget(label)
            query_bits_row.addWidget(widget)
        query_bits_row.addStretch(1)
        self._read_function.currentIndexChanged.connect(self._on_read_function_changed)

        self._table = QTableWidget(0, len(COLUMNS))
        self._table.setObjectName("modbusTable")
        self._table.setHorizontalHeaderLabels(COLUMNS)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(42)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)

        self._write_group = QGroupBox("Vollständige Register schreiben")
        self._write_function = QComboBox()
        self._write_function.addItem("Holdingregister (FC06 / FC16)", 0)
        self._write_function.addItem("Coils (FC15 / 0x0F)", WRITE_MULTIPLE_COILS)
        self._write_address = QSpinBox()
        self._write_address.setRange(0, 65535)
        self._write_address.setToolTip("0-basierte Registeradresse")
        self._write_width = QComboBox()
        self._write_width.addItems(("16 Bit · 1 Register", "32 Bit · 2 Register"))
        self._write_order = QComboBox()
        self._write_order.addItems(WORD_ORDERS)
        self._write_order.setEnabled(False)
        self._write_width.currentIndexChanged.connect(self._on_write_width_changed)
        self._write_value = QLineEdit()
        self._write_value.setPlaceholderText("Neuer Wert, z. B. 123 oder 0x7B")
        self._write_value.setClearButtonEnabled(True)
        self._write_value.textChanged.connect(
            lambda: self._set_invalid(self._write_value, False)
        )
        self._write_button = QPushButton("Wert schreiben")
        self._write_button.setObjectName("modbusWriteButton")
        self._write_button.clicked.connect(self._request_write)
        self._write_address.valueChanged.connect(self._on_write_target_changed)
        self._write_width.currentIndexChanged.connect(self._on_write_target_changed)
        self._write_order.currentIndexChanged.connect(self._on_write_target_changed)
        self._write_group.setToolTip(
            "Schreibt vollständige Register. Offset und Bitlänge der Abfrage gelten hier nicht."
        )
        write_row = QHBoxLayout()
        write_row.addWidget(QLabel("Funktion"))
        write_row.addWidget(self._write_function, 1)
        write_row.addWidget(QLabel("Adresse"))
        write_row.addWidget(self._write_address)
        self._write_register_options = QWidget()
        register_row = QHBoxLayout(self._write_register_options)
        register_row.setContentsMargins(0, 0, 0, 0)
        for label, widget in (
            ("Breite", self._write_width), ("Wortfolge", self._write_order),
        ):
            register_row.addWidget(QLabel(label))
            register_row.addWidget(widget)
        register_row.addStretch(1)
        value_row = QHBoxLayout()
        self._write_value_label = QLabel("Neuer Wert")
        value_row.addWidget(self._write_value_label)
        value_row.addWidget(self._write_value, 1)
        value_row.addWidget(self._write_button)
        write_layout = QVBoxLayout(self._write_group)
        write_layout.addLayout(write_row)
        write_layout.addWidget(self._write_register_options)
        write_layout.addLayout(value_row)
        self._write_function.currentIndexChanged.connect(self._on_write_function_changed)
        self._table.itemSelectionChanged.connect(self._on_query_selected)
        self._on_write_target_changed()
        self._update_write_ui()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 8)
        layout.addLayout(connection_row)
        layout.addWidget(self._status)
        layout.addLayout(query_row)
        layout.addLayout(query_bits_row)
        layout.addWidget(self._table, 1)
        layout.addWidget(self._write_group)

    def _toggle_connection(self):
        if self._client is None:
            self._start()
        else:
            self._stop()

    def _start(self):
        ip = self._ip.text().strip()
        if not ip:
            self._set_invalid(self._ip, True)
            self._ip.setFocus()
            self._notify("Bitte IP-Adresse eingeben.")
            return
        self._last_poll_error = None
        self._set_invalid(self._ip, False)
        self._client = ModbusTcpClient(ip, self._port.value(), UNIT_ID)
        self._set_connected_ui(True)
        self._status.setText("Verbinde …")
        self._notify(f"Verbindung zu {ip}:{self._port.value()} wird aufgebaut.")
        self._timer.start(self._interval.value())
        self._on_tick()

    def _stop(self):
        self._timer.stop()
        client, self._client = self._client, None
        if client is not None and not self._busy:
            client.close()  # läuft gerade ein Abruf, schließt _on_poll_finished die Verbindung
        self._registers = {}
        self._last_poll_error = None
        self._set_invalid(self._connect_button, False)
        self._set_connected_ui(False)
        self._status.setText("Getrennt")
        self._notify("Verbindung getrennt.")
        self._update_values()

    def _set_connected_ui(self, connected: bool):
        self._connect_button.setText("Trennen" if connected else "Verbinden")
        self._ip.setEnabled(not connected)
        self._port.setEnabled(not connected)
        self._update_write_ui()

    def _on_tick(self):
        if self._busy or self._client is None:
            return
        if self._pending_write is not None:
            request = self._pending_write
            self._pending_write = None
            self._writing = True
            self._busy = True
            task = _WriteTask(self._client, request)
            task.signals.finished.connect(self._on_write_finished)
            self._task = task
            self._update_write_ui()
            QThreadPool.globalInstance().start(task)
            return
        self._busy = True
        reads = sorted({query.key for query in self._queries})
        task = _PollTask(self._client, reads)
        task.signals.finished.connect(self._on_poll_finished)
        self._task = task
        QThreadPool.globalInstance().start(task)

    @Slot(object, object, object)
    def _on_poll_finished(self, client, registers, error):
        self._busy = False
        if client is not self._client:
            client.close()  # Verbindung wurde während des Abrufs getrennt
            return
        if error is None:
            self._registers = registers
            if self._status.text() != "Verbunden":
                self._notify(f"Mit {client.host}:{client.port} verbunden.")
            self._last_poll_error = None
            self._set_invalid(self._connect_button, False)
            self._status.setText("Verbunden")
        else:
            self._registers = {}
            self._status.setText("Lesefehler" if client.connected else "Verbindungsfehler")
            if self._pending_write is not None:
                self._pending_write = None
                self._notify(f"Nicht geschrieben: {error}")
            elif error != self._last_poll_error:
                self._notify(str(error))
            self._last_poll_error = str(error)
        self._update_values()
        self._update_write_ui()
        if self._pending_write is not None:
            self._on_tick()

    def _on_write_width_changed(self):
        coils = self._write_function.currentData() == WRITE_MULTIPLE_COILS
        double_word = not coils and self._write_width.currentIndex() == 1
        self._write_order.setEnabled(double_word)
        self._write_address.setMaximum(65534 if double_word else 65535)

    def _on_write_function_changed(self):
        coils = self._write_function.currentData() == WRITE_MULTIPLE_COILS
        self._write_register_options.setVisible(not coils)
        self._write_group.setTitle("Coils schreiben" if coils else "Vollständige Register schreiben")
        self._write_value_label.setText("Coils (Adresse →)" if coils else "Neuer Wert")
        self._write_value.setPlaceholderText(
            "z. B. 1 0 1 1 – linke Ziffer = Startadresse" if coils
            else "Neuer Wert, z. B. 123 oder 0x7B"
        )
        self._write_group.setToolTip(
            "0/1-Folge von links nach rechts für aufeinanderfolgende Coil-Adressen." if coils
            else "Schreibt vollständige Register. Offset und Bitlänge der Abfrage gelten hier nicht."
        )
        self._write_value.clear()
        self._on_write_width_changed()
        self._on_write_target_changed()
        if coils:
            self._notify("FC15: 0/1-Folge von links nach rechts ab der Startadresse eingeben.")

    def _on_write_target_changed(self):
        address = self._write_address.value()
        if self._write_function.currentData() == WRITE_MULTIPLE_COILS:
            self._write_button.setText(f"Coils ab {address} schreiben")
            return
        quantity = self._write_width.currentIndex() + 1
        target = str(address) if quantity == 1 else f"{address}–{address + 1}"
        self._write_button.setText(f"Register {target} schreiben")

    def _on_query_selected(self):
        row = self._table.currentRow()
        if (0 <= row < len(self._queries)
                and not self._writing and self._pending_write is None):
            query = self._queries[row]
            if query.function == READ_DISCRETE_INPUTS:
                self._notify(
                    "Discrete Inputs (FC02) sind nur lesbar. Schreibziel separat auswählen."
                )
                return
            self._write_function.setCurrentIndex(0)
            self._write_width.setCurrentIndex(query.quantity - 1)
            self._write_order.setCurrentIndex(0 if query.high_first else 1)
            self._write_address.setValue(query.address)
            self._write_value.clear()
            self._notify(
                f"„{query.name}“: Registeradresse, Breite und Wortfolge zum Schreiben übernommen."
            )

    def _notify(self, text: str):
        self.message.emit(f"Modbus: {text}")

    @staticmethod
    def _set_invalid(widget: QWidget, invalid: bool):
        if bool(widget.property("invalid")) == invalid:
            return
        widget.setProperty("invalid", invalid)
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()

    def _update_write_ui(self):
        active = self._writing or self._pending_write is not None
        self._connect_button.setEnabled(not active)
        for widget in (
            self._write_function, self._write_address, self._write_width, self._write_value,
        ):
            widget.setEnabled(not active)
        self._write_order.setEnabled(
            not active and self._write_function.currentData() != WRITE_MULTIPLE_COILS
            and self._write_width.currentIndex() == 1
        )
        self._write_button.setEnabled(not active)

    def _request_write(self):
        if self._writing or self._pending_write is not None:
            return
        if not self._write_value.text().strip():
            self._set_invalid(self._write_value, True)
            self._write_value.setFocus()
            self._notify("Bitte einen Wert zum Schreiben eingeben.")
            return
        address = self._write_address.value()
        coils = self._write_function.currentData() == WRITE_MULTIPLE_COILS
        try:
            if coils:
                values = _parse_coils(self._write_value.text())
                if address + len(values) > 65536:
                    raise ValueError("Die Coil-Folge reicht über Adresse 65535 hinaus.")
                function = WRITE_MULTIPLE_COILS
                end = address + len(values) - 1
                description = f"Coils {address}–{end} ({len(values)} Stück)"
            else:
                bits = WRITE_WIDTHS[self._write_width.currentIndex()]
                value = _parse_write_value(self._write_value.text(), bits)
                values = split_value(value, bits // WORD_BITS, self._write_order.currentIndex() == 0)
                function = WRITE_SINGLE_REGISTER if len(values) == 1 else WRITE_MULTIPLE_REGISTERS
                description = f"Register {address}: {_format_value(value)}"
        except ValueError as exc:
            self._set_invalid(self._write_value, True)
            self._write_value.setFocus()
            self._notify(str(exc))
            return
        if self._client is None or not self._client.connected:
            self._set_invalid(self._connect_button, True)
            if not self._ip.text().strip():
                self._set_invalid(self._ip, True)
                self._ip.setFocus()
            else:
                self._connect_button.setFocus()
            self._notify(
                "Keine Verbindung zum Gerät. Bitte Verbindung herstellen und erneut schreiben."
            )
            return
        self._set_invalid(self._write_value, False)
        self._set_invalid(self._connect_button, False)
        self._pending_write = WriteRequest(function, address, values, description)
        self._update_write_ui()
        self._on_tick()

    @Slot(object, object, object)
    def _on_write_finished(self, client, request, error):
        self._busy = False
        self._writing = False
        if client is not self._client:
            client.close()
            self._update_write_ui()
            return
        if error is None:
            self._notify(f"{request.description} vom Gerät bestätigt.")
        else:
            self._notify(f"Schreiben fehlgeschlagen: {error}")
        self._registers = {}
        self._update_values()
        self._update_write_ui()
        self._on_tick()

    def _on_read_function_changed(self):
        discrete = self._read_function.currentData() == READ_DISCRETE_INPUTS
        self._length_label.setText("Anzahl Eingänge" if discrete else "Bitlänge")
        self._address.setToolTip(
            "0-basierte Eingangsadresse" if discrete else "0-basierte Registeradresse"
        )
        self._length.setToolTip(
            "1–32 aufeinanderfolgende Eingänge. Startadresse entspricht Bit 0 (rechts)." if discrete
            else "Anzahl der auszuwertenden Bits (höchstens 32 einschließlich Offset)."
        )
        self._length.setValue(1 if discrete else WORD_BITS)
        self._on_query_bits_changed()

    def _on_query_bits_changed(self):
        discrete = self._read_function.currentData() == READ_DISCRETE_INPUTS
        self._offset.setEnabled(not discrete)
        self._length.setMaximum(MAX_BITS if discrete else MAX_BITS - self._offset.value())
        double_word = not discrete and self._offset.value() + self._length.value() > WORD_BITS
        self._read_order.setEnabled(double_word)
        quantity = self._length.value() if discrete else (2 if double_word else 1)
        self._address.setMaximum(65536 - quantity)

    def _add_query(self):
        function = self._read_function.currentData()
        discrete = function == READ_DISCRETE_INPUTS
        self._queries.append(
            Query(self._name.text().strip(), self._address.value(),
                  0 if discrete else self._offset.value(), self._length.value(),
                  self._read_order.currentIndex() == 0, function)
        )
        self._name.clear()
        self._refresh_table()

    def _remove_query(self):
        row = self._table.currentRow()
        if 0 <= row < len(self._queries):
            del self._queries[row]
            self._refresh_table()

    def _refresh_table(self):
        self._table.setRowCount(len(self._queries))
        for row, query in enumerate(self._queries):
            discrete = query.function == READ_DISCRETE_INPUTS
            order = ("Hi-Lo" if query.high_first else "Lo-Hi") if (
                not discrete and query.quantity == 2
            ) else NO_VALUE
            texts = (
                query.name, NO_VALUE, NO_VALUE, NO_VALUE, str(query.address),
                NO_VALUE if discrete else str(query.offset), str(query.length), order,
                f"FC{query.function:02d}",
            )
            for column, text in enumerate(texts):
                item = QTableWidgetItem(text)
                if discrete and column == 3:
                    item.setToolTip("Bit 0 (rechts) entspricht der Startadresse des Eingangsbereichs.")
                if column == 0 or column in VALUE_COLUMNS:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                else:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._table.setItem(row, column, item)
        self._update_values()

    def _update_values(self):
        for row, query in enumerate(self._queries):
            registers = self._registers.get(query.key)
            if registers is None:
                texts = (NO_VALUE, NO_VALUE, NO_VALUE)
            else:
                value = query.extract(registers, high_first=query.high_first)
                hex_digits = (query.length + 3) // 4
                texts = (
                    str(value), f"0x{value:0{hex_digits}X}",
                    _format_binary(value, query.length),
                )
            for column, text in zip(VALUE_COLUMNS, texts):
                self._table.item(row, column).setText(text)


def _format_value(value: int) -> str:
    return f"{value}  (0x{value:X})"


def _format_binary(value: int, bits: int) -> str:
    width = ((bits + 3) // 4) * 4
    binary = f"{value:0{width}b}"
    return " ".join(binary[index:index + 4] for index in range(0, width, 4))
