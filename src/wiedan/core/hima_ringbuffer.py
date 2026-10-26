"""HIMA-Ringbuffer: 1000 Samples, acht 16-Bit-Kanäle und 100 Posttriggerzyklen."""
from collections.abc import Callable
from dataclasses import dataclass
from threading import Event
from time import sleep

from wiedan.core.modbus import ModbusError, ModbusTcpClient

SAMPLE_COUNT = 1000
CHANNEL_COUNT = 8
POSTTRIGGER_CYCLES = 100
TRIGGER_ROW = SAMPLE_COUNT - POSTTRIGGER_CYCLES - 1
RESET_PULSE_MS = 50


@dataclass(frozen=True)
class Sample:
    address: int
    channels: tuple[int, ...]
    time: int


@dataclass(frozen=True)
class Dataset:
    samples: tuple[Sample, ...]
    trigger_address: int


def sort_samples(samples: list[Sample], trigger_address: int, index_base: int) -> Dataset:
    """Start ist der erste Speicherplatz nach dem letzten Posttrigger-Sample."""
    if index_base not in (0, 1):
        raise ValueError("Ringbuffer-Indizes müssen bei 0 oder 1 beginnen.")
    if len(samples) != SAMPLE_COUNT or [sample.address for sample in samples] != list(
        range(index_base, index_base + SAMPLE_COUNT)
    ):
        raise ValueError("Der Ringbuffer-Datensatz ist unvollständig oder nicht in Adressfolge.")
    trigger = trigger_address - index_base
    if not 0 <= trigger < SAMPLE_COUNT:
        raise ValueError("Die Triggerposition liegt außerhalb des Ringbuffers.")
    start = (trigger + POSTTRIGGER_CYCLES + 1) % SAMPLE_COUNT
    return Dataset(tuple(samples[start:] + samples[:start]), trigger_address)


@dataclass(frozen=True)
class ReadConfig:
    address_register: int
    channel_registers: tuple[int, ...]
    time_register: int
    trigger_register: int
    index_base: int
    settle_ms: int

    def validate(self):
        reads = (*self.channel_registers, self.time_register, self.trigger_register)
        if len(self.channel_registers) != CHANNEL_COUNT:
            raise ValueError("Es müssen acht Kanalregister angegeben werden.")
        if any(not 0 <= address <= 65535 for address in (self.address_register, *reads)):
            raise ValueError("Bitte alle Modbus-Registeradressen angeben (0–65535).")
        if self.index_base not in (0, 1):
            raise ValueError("Bitte die Indexbasis des Ringbuffers auswählen.")
        if not 0 <= self.settle_ms <= 60000:
            raise ValueError("Bitte die Wartezeit nach dem Schreiben der Leseadresse angeben.")


class ReadCancelled(Exception):
    """Auslesung vom Benutzer abgebrochen; Teilwerte werden nicht übernommen."""


def _read_blocks(addresses: tuple[int, ...]) -> list[tuple[int, int]]:
    """Nur tatsächlich konfigurierte, benachbarte Register gemeinsam lesen."""
    blocks: list[tuple[int, int]] = []
    for address in sorted(set(addresses)):
        if blocks and blocks[-1][0] + blocks[-1][1] == address:
            start, count = blocks[-1]
            blocks[-1] = (start, count + 1)
        else:
            blocks.append((address, 1))
    return blocks


def read_dataset(
    client: ModbusTcpClient, config: ReadConfig, cancel: Event,
    progress: Callable[[int], None],
) -> Dataset:
    config.validate()
    samples: list[Sample] = []
    trigger_address = None
    blocks = _read_blocks((*config.channel_registers, config.time_register, config.trigger_register))
    for offset in range(SAMPLE_COUNT):
        if cancel.is_set():
            raise ReadCancelled()
        address = config.index_base + offset
        try:
            client.write_multiple_registers(config.address_register, [address])
        except ModbusError as exc:
            raise ModbusError(
                f"Sample {offset + 1}/{SAMPLE_COUNT}: ReadIndex {address} auf Register "
                f"{config.address_register} schreiben fehlgeschlagen. {exc}"
            ) from exc
        if cancel.wait(config.settle_ms / 1000):
            raise ReadCancelled()
        values = {}
        for start, count in blocks:
            if cancel.is_set():
                raise ReadCancelled()
            try:
                registers = client.read_holding_registers(start, count)
            except ModbusError as exc:
                raise ModbusError(
                    f"Sample {offset + 1}/{SAMPLE_COUNT} (ReadIndex {address}): "
                    f"Register {start}–{start + count - 1} lesen fehlgeschlagen. {exc}"
                ) from exc
            values.update(zip(range(start, start + count), registers))
        trigger = values[config.trigger_register]
        if not config.index_base <= trigger < config.index_base + SAMPLE_COUNT:
            raise ValueError(f"Ungültige Triggerposition: {trigger}.")
        if trigger_address is not None and trigger != trigger_address:
            raise ValueError("Die Triggerposition hat sich während der Auslesung geändert. Erneut auslesen.")
        trigger_address = trigger
        samples.append(Sample(address, tuple(values[reg] for reg in config.channel_registers),
                              values[config.time_register]))
        progress(offset + 1)
    if cancel.is_set():
        raise ReadCancelled()
    return sort_samples(samples, trigger_address, config.index_base)


def pulse_reset(client: ModbusTcpClient, coil: int):
    """1 → 0; auch beim Beenden darf das Löschen nicht durch Abbruch entfallen."""
    try:
        client.write_single_coil(coil, 1)
        sleep(RESET_PULSE_MS / 1000)
    finally:
        try:
            client.write_single_coil(coil, 0)
        except ModbusError as exc:
            raise ModbusError(
                f"Reset-Coil {coil}: Löschen auf 0 nicht bestätigt. Coil-Zustand prüfen. {exc}"
            ) from exc
