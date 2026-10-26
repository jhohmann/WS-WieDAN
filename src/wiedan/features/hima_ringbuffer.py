"""Projektunabhängiges HIMA-Werkzeug zum automatischen Auslesen eines Ringbuffers."""
import csv
import io
from threading import Event

from PySide6.QtCore import (
    QAbstractTableModel, QIODevice, QModelIndex, QObject, QRunnable, QSaveFile,
    Qt, QThreadPool, Signal, Slot,
)
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QFileDialog, QGridLayout, QGroupBox, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QProgressBar, QPushButton, QSpinBox, QTableView,
    QVBoxLayout, QWidget,
)

from wiedan.core.hima_ringbuffer import (
    CHANNEL_COUNT, RESET_PULSE_MS, SAMPLE_COUNT, TRIGGER_ROW, Dataset, ReadCancelled,
    ReadConfig, pulse_reset, read_dataset,
)
from wiedan.core.modbus import ModbusError, ModbusTcpClient


class _Signals(QObject):
    progress = Signal(int)
    finished = Signal(object, object)  # Ergebnis, Fehlertext


class _Task(QRunnable):
    def __init__(self, client, action, cancel, config=None, coil=None):
        super().__init__()
        self.client, self.action, self.cancel = client, action, cancel
        self.config, self.coil = config, coil
        self.signals = _Signals()

    def run(self):
        result, error = None, None
        try:
            if self.cancel.is_set():
                raise ReadCancelled()
            if self.action == "connect":
                self.client.connect()
            elif self.action == "read":
                result = read_dataset(self.client, self.config, self.cancel, self.signals.progress.emit)
            elif self.action == "reset":
                pulse_reset(self.client, self.coil)
        except ReadCancelled:
            error = "Abgebrochen. Kein neuer Datensatz übernommen."
        except (ModbusError, ValueError) as exc:
            error = str(exc)
        finally:
            if error or self.cancel.is_set():
                self.client.close()
        self.signals.finished.emit(result, error)


class _DatasetModel(QAbstractTableModel):
    HEADERS = ("Zyklus zum Trigger", "Pufferadresse", "Zeit (16 Bit)",
               *(f"Kanal {number}" for number in range(1, CHANNEL_COUNT + 1)))

    def __init__(self, parent=None):
        super().__init__(parent)
        self.dataset: Dataset | None = None

    def set_dataset(self, dataset):
        self.beginResetModel()
        self.dataset = dataset
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() or self.dataset is None else len(self.dataset.samples)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.HEADERS[section]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or self.dataset is None:
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            sample = self.dataset.samples[index.row()]
            cycle = index.row() - TRIGGER_ROW
            values = ("0 · Trigger" if cycle == 0 else str(cycle), sample.address,
                      sample.time, *sample.channels)
            return str(values[index.column()])
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignCenter
        return None


def _spin(low, high, value=None):
    widget = QSpinBox()
    widget.setRange(low, high)
    widget.setValue(low if value is None else value)
    return widget


def _address():
    widget = _spin(-1, 65535)
    widget.setSpecialValueText("Bitte angeben")
    widget.setToolTip("Modbus-Adresse, 0-basiert (0–65535)")
    return widget


class HimaRingbuffer(QWidget):
    message = Signal(str)

    def __init__(self):
        super().__init__()
        self._client = None
        self._task = None
        self._cancel = Event()
        self._disconnect_requested = False

        self._ip = QLineEdit()
        self._ip.setPlaceholderText("IP-Adresse der HIMA-SPS")
        self._port = _spin(1, 65535, 502)
        self._unit = _spin(0, 255, 0)
        self._timeout = _spin(1, 30, 5)
        self._timeout.setSuffix(" s")
        self._timeout.setToolTip(
            "Maximale Wartezeit bei der Modbus-Übertragung. Zum Ändern Verbindung trennen. "
            "Die Wartezeit zwischen Schreiben und Lesen wird separat eingestellt."
        )
        self._connect = QPushButton("Verbinden")
        self._connect.clicked.connect(self._toggle_connection)
        connection = QHBoxLayout()
        for label, widget in (("IP", self._ip), ("Port", self._port), ("Unit-ID", self._unit),
                              ("Antwort-Timeout", self._timeout)):
            connection.addWidget(QLabel(label))
            connection.addWidget(widget, 1 if widget is self._ip else 0)
        connection.addWidget(self._connect)

        self._config_group = QGroupBox("SPS-Schnittstelle · Modbus-Adressen sind 0-basiert")
        grid = QGridLayout(self._config_group)
        self._read_address = _address()
        self._read_address.setValue(0)
        self._time = _address()
        self._time.setValue(0)
        self._trigger = _address()
        self._trigger.setValue(9)
        self._coil = _address()
        self._coil.setValue(0)
        self._channels = [_address() for _ in range(CHANNEL_COUNT)]
        for number, widget in enumerate(self._channels, 1):
            widget.setValue(number)
        fields = [("ReadIndex schreiben (FC16)", self._read_address), ("Reset-Coil (FC05)", self._coil),
                  ("Zeit lesen (FC03)", self._time), ("Triggerposition lesen (FC03)", self._trigger)]
        fields.extend((f"Kanal {number} lesen (FC03)", widget)
                      for number, widget in enumerate(self._channels, 1))
        for position, (label, widget) in enumerate(fields):
            row, col = divmod(position, 2)
            grid.addWidget(QLabel(label), row, col * 2)
            grid.addWidget(widget, row, col * 2 + 1)
        self._settle = _spin(0, 60000, 50)
        self._settle.setSuffix(" ms")
        self._settle.setToolTip("Wartezeit zwischen bestätigtem Leseadresse-Schreiben und Lesen der Werte.")
        grid.addWidget(QLabel("Triggerposition: 0–999"), 6, 0, 1, 2)
        grid.addWidget(QLabel("Wartezeit je Sample"), 6, 2)
        grid.addWidget(self._settle, 6, 3)

        self._read = QPushButton("Datensatz auslesen")
        self._read.clicked.connect(self._start_read)
        self._abort = QPushButton("Abbrechen")
        self._abort.clicked.connect(self._abort_read)
        self._reset_button = QPushButton("Reset (Impuls 1 → 0)")
        self._reset_button.setToolTip(f"Reset-Coil setzen, {RESET_PULSE_MS} ms warten und wieder löschen.")
        self._reset_button.clicked.connect(self._reset)
        actions = QHBoxLayout()
        for button in (self._read, self._abort):
            actions.addWidget(button)
        actions.addStretch()
        actions.addWidget(self._reset_button)

        self._progress = QProgressBar()
        self._progress.setRange(0, SAMPLE_COUNT)
        self._progress.setValue(0)
        self._progress.setFormat("%v / 1000 Samples")
        self._status = QLabel("Getrennt")
        self._status.setTextFormat(Qt.TextFormat.PlainText)
        self._status.setWordWrap(True)
        hint = QLabel("1000 Samples · 8 Kanäle · 899 Zyklen vor / 100 nach dem Trigger. "
                      "Der SPS-Datensatz muss während der Auslesung unverändert bleiben.")
        hint.setWordWrap(True)
        self._result = QLabel("Noch kein Datensatz ausgelesen. Werte werden als UINT16 angezeigt.")
        self._result.setWordWrap(True)
        self._jump = QPushButton("Zum Trigger")
        self._jump.clicked.connect(self._jump_to_trigger)
        self._export = QPushButton("CSV exportieren …")
        self._export.clicked.connect(self._export_csv)
        self._export.setToolTip("Den angezeigten vollständigen Datensatz als CSV speichern.")
        result_row = QHBoxLayout()
        result_row.addWidget(self._result, 1)
        result_row.addWidget(self._jump)
        result_row.addWidget(self._export)
        self._model = _DatasetModel(self)
        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setStretchLastSection(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 8)
        layout.addLayout(connection)
        layout.addWidget(self._config_group)
        layout.addWidget(hint)
        layout.addLayout(actions)
        layout.addWidget(self._progress)
        layout.addWidget(self._status)
        layout.addLayout(result_row)
        layout.addWidget(self._table, 1)
        QApplication.instance().aboutToQuit.connect(self.shutdown)
        self._update_ui()

    def _notify(self, text):
        self._status.setText(text)
        self.message.emit(f"HIMA-Ringbuffer: {text}")

    def _update_ui(self):
        busy = self._task is not None
        connected = self._client is not None and self._client.connected
        for widget in (self._ip, self._port, self._unit, self._timeout):
            widget.setEnabled(not busy and not connected)
        self._connect.setText("Trennen" if connected else "Verbinden")
        self._connect.setEnabled(not busy)
        self._config_group.setEnabled(not busy)
        for button in (self._read, self._reset_button):
            button.setEnabled(connected and not busy)
        self._abort.setEnabled(busy and self._task.action == "read" and not self._cancel.is_set())
        self._jump.setEnabled(self._model.dataset is not None)
        self._export.setEnabled(self._model.dataset is not None and not busy)

    def _start_task(self, action, **kwargs):
        self._cancel = Event()
        self._disconnect_requested = False
        task = _Task(self._client, action, self._cancel, **kwargs)
        task.signals.progress.connect(self._progress.setValue)
        task.signals.finished.connect(self._finished)
        self._task = task
        self._update_ui()
        QThreadPool.globalInstance().start(task)

    def _toggle_connection(self):
        if self._task is not None:
            return
        if self._client is not None:
            self._client.close()
            self._client = None
            self._notify("Getrennt")
            self._update_ui()
            return
        host = self._ip.text().strip()
        if not host:
            self._notify("Bitte die IP-Adresse der SPS angeben.")
            self._ip.setFocus()
            return
        self._client = ModbusTcpClient(host, self._port.value(), self._unit.value(),
                                       timeout=self._timeout.value())
        self._notify("Verbindung wird aufgebaut …")
        self._start_task("connect")

    def _start_read(self):
        if self._task is not None or self._client is None:
            return
        config = ReadConfig(self._read_address.value(), tuple(widget.value() for widget in self._channels),
                            self._time.value(), self._trigger.value(), 0,
                            self._settle.value())
        try:
            config.validate()
        except ValueError as exc:
            self._notify(str(exc))
            return
        self._progress.setValue(0)
        self._notify("Datensatz wird automatisch ausgelesen …")
        if self._model.dataset is not None:
            self._result.setText("Angezeigt wird weiterhin der zuletzt vollständig ausgelesene Datensatz.")
        self._start_task("read", config=config)

    def _abort_read(self):
        if self._task is None or self._task.action != "read":
            return
        self._cancel.set()
        self._notify("Auslesung wird abgebrochen …")
        self._update_ui()

    def _reset(self):
        if self._task is not None or self._client is None:
            return
        if self._coil.value() < 0:
            self._notify("Bitte die Modbus-Adresse des Reset-Coils angeben.")
            self._coil.setFocus()
            return
        self._notify("Reset-Impuls 1 → 0 wird geschrieben …")
        self._start_task("reset", coil=self._coil.value())

    @Slot(object, object)
    def _finished(self, dataset, error):
        task, self._task = self._task, None
        if error:
            self._client.close()
            self._client = None
            self._notify(f"{error} Verbindung getrennt.")
        elif self._cancel.is_set() or self._disconnect_requested:
            self._client.close()
            self._client = None
            self._notify("Abgebrochen und getrennt. Kein neuer Datensatz übernommen.")
        elif task.action == "connect":
            self._notify(f"Verbunden mit {self._client.host}:{self._client.port}")
        elif task.action == "read":
            self._model.set_dataset(dataset)
            self._table.scrollToTop()
            self._result.setText(f"1000 Samples · Trigger bei Pufferadresse {dataset.trigger_address} · "
                                 f"Sequenzstart bei Pufferadresse {dataset.samples[0].address}")
            self._notify("Datensatz vollständig ausgelesen und nach Triggerposition sortiert.")
        elif task.action == "reset":
            self._notify(f"Reset-Coil {task.coil}: Impuls 1 → 0 bestätigt.")
        self._update_ui()

    def _jump_to_trigger(self):
        if self._model.dataset is not None:
            self._table.selectRow(TRIGGER_ROW)
            self._table.scrollTo(self._model.index(TRIGGER_ROW, 0),
                                 QAbstractItemView.ScrollHint.PositionAtCenter)

    def _export_csv(self):
        dataset = self._model.dataset
        if dataset is None or self._task is not None:
            return
        dialog = QFileDialog(self, "HIMA-Ringbuffer als CSV speichern")
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dialog.setNameFilter("CSV-Dateien (*.csv)")
        dialog.setDefaultSuffix("csv")
        dialog.selectFile("HIMA-Ringbuffer.csv")
        if not dialog.exec():
            return
        filename = dialog.selectedFiles()[0]
        output = io.StringIO(newline="")
        writer = csv.writer(output, delimiter=";")
        writer.writerow(_DatasetModel.HEADERS)
        writer.writerows(
            (row - TRIGGER_ROW, sample.address, sample.time, *sample.channels)
            for row, sample in enumerate(dataset.samples)
        )
        payload = output.getvalue().encode("utf-8-sig")
        target = QSaveFile(filename)
        if not target.open(QIODevice.OpenModeFlag.WriteOnly):
            self._notify(f"CSV konnte nicht gespeichert werden: {target.errorString()}")
            return
        if target.write(payload) != len(payload):
            error = target.errorString()
            target.cancelWriting()
            self._notify(f"CSV konnte nicht gespeichert werden: {error}")
            return
        if not target.commit():
            self._notify(f"CSV konnte nicht gespeichert werden: {target.errorString()}")
            return
        self._notify(f"{len(dataset.samples)} Samples als CSV gespeichert: {filename}")

    def shutdown(self):
        self._disconnect_requested = True
        if self._task is not None:
            self._cancel.set()
        elif self._client is not None:
            self._client.close()
            self._client = None
