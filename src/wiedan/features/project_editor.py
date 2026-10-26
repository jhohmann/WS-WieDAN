"""Engineering: Projektbaum und Eigenschaften auf einem gemeinsamen Entwurf."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
    QMessageBox, QPushButton, QScrollArea, QSplitter, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)

from wiedan.core.engineering import ProjectDraft
from wiedan.core.master_data import FIELDS, device_field_available
from wiedan.core.project_database import connect, database_path
from wiedan.core.working_configuration import available_parameters
from wiedan.features.device_catalog import DevicePicker
from wiedan.ui.icons import icon, node_icon_name, pick

ROLE = Qt.ItemDataRole.UserRole
ICON_ROLE = ROLE + 1


class ProjectEditor(QWidget):
    saved = Signal(str)
    context_changed = Signal()

    def __init__(self):
        super().__init__()
        self.draft = None
        self.before_save = lambda: True
        self._project_uid = None
        self._icon_color = self.palette().color(QPalette.ColorRole.Text).name()
        layout = QVBoxLayout(self)
        actions = QHBoxLayout()
        for title, callback in (("Neues Projekt", self.new_project), ("Speichern", self.save),
                                ("Verwerfen", self.discard)):
            button = QPushButton(title)
            button.setAutoDefault(False)
            button.clicked.connect(callback)
            actions.addWidget(button)
            if title == "Speichern":
                self.save_button = button
        actions.addStretch()
        self.view = QComboBox()
        self.view.addItems(["Anlagenstruktur", "Nach Gerätekategorie"])
        self.view.currentIndexChanged.connect(lambda: self._rebuild())
        actions.addWidget(self.view)
        layout.addLayout(actions)
        split = QSplitter()
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Projekt / Node / Gerät", "Zuordnung"])
        self.tree.setColumnWidth(0, 280)
        self.tree.currentItemChanged.connect(self._selected)
        left_layout.addWidget(self.tree)
        row = QHBoxLayout()
        self.node_button = QPushButton("Node hinzufügen")
        self.device_button = QPushButton("Gerät hinzufügen …")
        self.remove_button = QPushButton("Entfernen")
        for button, callback in ((self.node_button, self._add_node), (self.device_button, self._add_device),
                                 (self.remove_button, self._remove)):
            button.setAutoDefault(False)
            button.clicked.connect(callback)
            row.addWidget(button)
        left_layout.addLayout(row)
        split.addWidget(left)
        self.properties = QWidget()
        self.form = QFormLayout(self.properties)
        self.form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.properties)
        split.addWidget(scroll)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        layout.addWidget(split, 1)
        self.status = QLabel("Projekt auswählen oder ein neues Projekt anlegen.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self._rebuild()

    def set_project(self, project):
        self._project_uid = project.uid if project else None
        self.draft = ProjectDraft(project.database_path, project.uid) if project else None
        self._rebuild()
        self.context_changed.emit()

    def new_project(self):
        if not self.can_leave():
            return
        self.draft = ProjectDraft(database_path())
        self._rebuild()
        self.context_changed.emit()

    def set_icon_color(self, color):
        self._icon_color = color
        pending = [self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount())]
        while pending:
            item = pending.pop()
            name = item.data(0, ICON_ROLE)
            if name:
                item.setIcon(0, icon(name, color))
            pending.extend(item.child(i) for i in range(item.childCount()))

    def _set_item_icon(self, item, name):
        item.setData(0, ICON_ROLE, name)
        item.setIcon(0, icon(name, self._icon_color))

    def _identity(self):
        item = self.tree.currentItem()
        return item.data(0, ROLE) if item else None

    def _node_target(self):
        identity = self._identity()
        if identity and identity[0] == "nodes":
            return identity[1]
        if identity and identity[0] == "devices":
            return self.draft.devices[identity[1]]["node_uid"]
        return None

    def _rebuild(self, selected=None):
        selected = selected or self._identity()
        expanded = {key for key, item in getattr(self, "items", {}).items() if item.isExpanded()}
        same_project = ("projects", self.draft.project["uid"]) in getattr(self, "items", {}) if self.draft else False
        self.tree.blockSignals(True)
        self.tree.clear()
        self.items = {}
        if self.draft:
            root = QTreeWidgetItem(self.tree, [self.draft.project["display_name"], "Projekt"])
            root.setData(0, ROLE, ("projects", self.draft.project["uid"]))
            self._set_item_icon(root, "project")
            self.items[("projects", self.draft.project["uid"])] = root
            nodes = self.draft.nodes

            def add_nodes(parent, parent_uid):
                for uid, node in nodes.items():
                    if node["parent_uid"] == parent_uid:
                        item = QTreeWidgetItem(parent, [node["label"], "Node"])
                        item.setData(0, ROLE, ("nodes", uid))
                        self._set_item_icon(item, node_icon_name(
                            node["path"], is_root=parent_uid is None,
                            vehicle_product=self.draft.vehicle_products.get(node["vehicle_uid"]),
                            is_vehicle=node["vehicle_uid"] is not None))
                        self.items[("nodes", uid)] = item
                        add_nodes(item, uid)

            if self.view.currentIndex() == 0:
                add_nodes(root, None)
            categories = {}
            for uid, device in self.draft.devices.items():
                definition = self.draft.types[device["type_id"]]
                category = definition.get("category")
                category_label = self.draft.categories.get(category, "Nicht zugeordnet")
                node = nodes[device["node_uid"]]
                if self.view.currentIndex() == 1:
                    if category not in categories:
                        categories[category] = QTreeWidgetItem(root, [category_label])
                        self._set_item_icon(categories[category], pick(category, "device"))
                    parent = categories[category]
                    detail = f"{node['label']} · {node['path']}"
                else:
                    parent = self.items[("nodes", device["node_uid"])]
                    detail = category_label
                label = device["label"] or definition["label"]
                item = QTreeWidgetItem(parent, [label, detail])
                self._set_item_icon(item, pick(category, "device"))
                item.setToolTip(0, f"{device['path']}\n{device['ip']}")
                item.setData(0, ROLE, ("devices", uid))
                self.items[("devices", uid)] = item
            root.setExpanded(True)
            for key, item in self.items.items():
                if key in expanded or not same_project and key[0] == "nodes" and self.draft.nodes[key[1]]["parent_uid"] is None:
                    item.setExpanded(True)
            for item in categories.values():
                item.setExpanded(True)
                item.sortChildren(0, Qt.SortOrder.AscendingOrder)
            if categories:
                root.sortChildren(0, Qt.SortOrder.AscendingOrder)
            self.tree.setCurrentItem(self.items.get(tuple(selected) if selected else None, root))
            parent = self.tree.currentItem().parent()
            while parent:
                parent.setExpanded(True)
                parent = parent.parent()
        self.tree.blockSignals(False)
        self._selected()
        self._summary()

    def _selected(self, *_args):
        while self.form.count():
            item = self.form.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        identity = self._identity()
        self.node_button.setEnabled(self.draft is not None)
        self.device_button.setEnabled(self.draft is not None and self._node_target() is not None)
        self.remove_button.setEnabled(bool(identity and identity[0] != "projects"))
        if not identity or not self.draft:
            return
        kind, uid = identity
        data = self.draft.row(kind, uid)
        if kind == "projects":
            key = QLineEdit(data["project_id"])
            key.setReadOnly(not self.draft.is_new)
            key.setPlaceholderText("Eindeutige Projektkennung, z. B. CK_Neuanlage")
            key.textEdited.connect(lambda value: self._edit(kind, uid, "project_id", value))
            self.form.addRow("Projektkennung", key)
        else:
            self.form.addRow("Kennung", QLabel(data["path"]))
            self._parent_field(kind, uid, data)
        if kind == "devices":
            definition = self.draft.types[data["type_id"]]
            self.form.addRow("Gerätetyp", QLabel(definition["label"]))
            self.form.addRow("Kategorie", QLabel(self.draft.categories.get(definition.get("category"), "Nicht zugeordnet")))
            self.form.addRow("Protokoll", QLabel(str(definition.get("connection", {}).get("protocol", ""))))
            role_spec = available_parameters(data["type_id"]).get("role")
            if role_spec:
                role = QComboBox()
                role.addItem("Nicht festgelegt", None)
                for choice in role_spec.choices:
                    role.addItem(choice, choice)
                current = self.draft.parameters.get(uid, {}).get("role")
                role.setCurrentIndex(role.findData(current))
                role.currentIndexChanged.connect(lambda: self._role_changed(uid, role.currentData()))
                self.form.addRow("Geräterolle", role)
        for field, (title, value_type) in FIELDS[kind].items():
            if kind == "devices" and not device_field_available(field, self.draft.parameters.get(uid, {}).get("role")):
                continue
            value = data[field]
            if value_type == "bool":
                widget = QCheckBox()
                widget.setChecked(bool(value))
                widget.toggled.connect(lambda checked, k=field: self._edit(kind, uid, k, int(checked)))
            elif value_type == "optional_bool":
                widget = QComboBox()
                for text, setting in (("Typvorgabe", None), ("Ja", 1), ("Nein", 0)):
                    widget.addItem(text, setting)
                widget.setCurrentIndex(widget.findData(value))
                widget.currentIndexChanged.connect(lambda _index, w=widget, k=field: self._edit(kind, uid, k, w.currentData()))
            else:
                widget = QLineEdit("" if value is None else str(value))
                if field == "ip":
                    widget.setPlaceholderText("Optional – kann später vergeben werden")
                if kind == "devices" and field == "label":
                    widget.setPlaceholderText("Leer = Bezeichnung aus dem Gerätetyp")
                widget.textEdited.connect(lambda text, k=field: self._edit(kind, uid, k, text))
            self.form.addRow(title, widget)
        if kind == "devices":
            self._documentation_fields(uid, data["type_id"])

    def _documentation_fields(self, uid, type_id):
        self.form.addRow(QLabel("Dokumentationsfelder"))
        definitions = {key: definition for key, definition in self.draft.field_definitions.items()
                       if definition["type_id"] == type_id}
        if not definitions:
            hint = QLabel("Felder unter Einstellungen → Gerätekatalog → Dokumentationsfelder anlegen.")
            hint.setWordWrap(True)
            self.form.addRow(hint)
        for key, definition in definitions.items():
            value = self.draft.documentation.get(uid, {}).get(key)
            if definition["value_type"] == "boolean":
                widget = QComboBox()
                for label, setting in (("Nicht angegeben", None), ("Ja", True), ("Nein", False)):
                    widget.addItem(label, setting)
                widget.setCurrentIndex(widget.findData(value))
                widget.currentIndexChanged.connect(lambda _i, k=key, w=widget: self._document_changed(uid, k, w.currentData()))
            else:
                widget = QLineEdit("" if value is None else str(value))
                if definition["value_type"] == "number":
                    widget.setPlaceholderText("Zahl; leer = nicht angegeben")
                widget.textEdited.connect(lambda text, k=key: self._document_changed(uid, k, text))
            self.form.addRow(definition["name"], widget)

    def _document_changed(self, uid, key, value):
        self.draft.documentation.setdefault(uid, {})[key] = value
        self._summary()

    def _role_changed(self, uid, role):
        values = self.draft.parameters.setdefault(uid, {})
        if role is None:
            values.pop("role", None)
            if not values:
                self.draft.parameters.pop(uid, None)
        else:
            values["role"] = role
        self._selected()
        self._summary()

    def _parent_field(self, kind, uid, data):
        parent = QComboBox()
        if kind == "nodes":
            parent.addItem("Direkt unter dem Projekt", None)
        excluded = self.draft.descendants(uid) if kind == "nodes" else set()
        for key, node in self.draft.nodes.items():
            if key not in excluded:
                parent.addItem(f"{node['label']} · {node['path']}", key)
        field = "parent_uid" if kind == "nodes" else "node_uid"
        parent.setCurrentIndex(parent.findData(data[field]))
        parent.currentIndexChanged.connect(lambda: self._move(kind, uid, parent.currentData()))
        self.form.addRow("Übergeordneter Node" if kind == "nodes" else "Node", parent)

    def _edit(self, kind, uid, field, value):
        self.draft.row(kind, uid)[field] = value
        if field in {"display_name", "label"}:
            item = self.items.get((kind, uid))
            if item:
                item.setText(0, str(value or "Ohne Bezeichnung"))
        self._summary()

    def _move(self, kind, uid, parent_uid):
        try:
            self.draft.move(kind, uid, parent_uid)
        except ValueError as exc:
            QMessageBox.warning(self, "Zuordnung", str(exc))
        self._rebuild((kind, uid))

    def _add_node(self):
        name, ok = QInputDialog.getText(self, "Node hinzufügen", "Bezeichnung")
        if ok:
            try:
                uid = self.draft.add_node(name, self._node_target())
                self.view.setCurrentIndex(0)
                self._rebuild(("nodes", uid))
            except ValueError as exc:
                QMessageBox.warning(self, "Node", str(exc))

    def _add_device(self):
        dialog = DevicePicker(self.draft.types, self.draft.categories, self)
        if dialog.exec() == dialog.DialogCode.Accepted:
            uid = self.draft.add_device(dialog.selected_type(), self._node_target())
            self._rebuild(("devices", uid))

    def _remove(self):
        kind, uid = self._identity()
        if QMessageBox.question(self, "Entfernen", "Ausgewähltes Element aus dem Projekt entfernen? "
                                "Die Änderung wird erst beim Speichern übernommen.") != QMessageBox.StandardButton.Yes:
            return
        try:
            self.draft.remove(kind, uid)
            self._rebuild()
        except ValueError as exc:
            QMessageBox.warning(self, "Entfernen", str(exc))

    def _summary(self):
        dirty = self.draft is not None and self.draft.dirty
        self.save_button.setEnabled(dirty)
        self.status.setText("Ungespeicherte Änderungen" if dirty else "Projekt gespeichert" if self.draft
                            else "Projekt auswählen oder ein neues Projekt anlegen.")

    def save(self):
        if not self.draft:
            return True
        if not self.before_save():
            return False
        try:
            uid = self.draft.save()
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Projekt speichern", str(exc))
            return False
        self._project_uid = uid
        self._rebuild()
        self.saved.emit(uid)
        return True

    def discard(self):
        if self.draft and self.draft.dirty:
            if QMessageBox.question(self, "Verwerfen", "Ungespeicherte Projektänderungen verwerfen?") != QMessageBox.StandardButton.Yes:
                return
        self.draft = ProjectDraft(database_path(), self._project_uid) if self._project_uid else None
        self._rebuild()
        self.context_changed.emit()

    def can_leave(self):
        if not self.draft or not self.draft.dirty:
            return True
        answer = QMessageBox.question(self, "Projekteditor", "Projektänderungen speichern?",
                                      QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard |
                                      QMessageBox.StandardButton.Cancel)
        if answer == QMessageBox.StandardButton.Save:
            return self.save()
        if answer == QMessageBox.StandardButton.Discard:
            self.draft = ProjectDraft(database_path(), self._project_uid) if self._project_uid else None
            self._rebuild()
            self.context_changed.emit()
            return True
        return False


class ProjectEditorDialog(QDialog):
    """Getrennter Projekteditor, ausschließlich aus den Einstellungen geöffnet."""

    project_requested = Signal(str)

    def __init__(self, editor, parent=None):
        super().__init__(parent)
        self.editor = editor
        self.setWindowTitle("Projekteditor")
        self.resize(1150, 740)
        layout = QVBoxLayout(self)
        selection = QHBoxLayout()
        label = QLabel("Projekt")
        self.projects = QComboBox()
        self.projects.setPlaceholderText("Projekt auswählen oder neues Projekt anlegen")
        label.setBuddy(self.projects)
        selection.addWidget(label)
        selection.addWidget(self.projects, 1)
        layout.addLayout(selection)
        layout.addWidget(editor, 1)
        close = QPushButton("Schließen")
        close.setAutoDefault(False)
        close.clicked.connect(self.reject)
        layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
        self.projects.currentIndexChanged.connect(self._request_project)
        editor.context_changed.connect(lambda: self.select_project(editor._project_uid))

    def select_project(self, uid):
        self.projects.blockSignals(True)
        try:
            self.projects.clear()
            with connect() as connection:
                for row in connection.execute("SELECT uid,display_name FROM projects ORDER BY display_name"):
                    self.projects.addItem(row["display_name"], row["uid"])
            if self.editor.draft and self.editor.draft.is_new:
                self.projects.addItem("Neues Projekt (ungespeichert)", None)
                self.projects.setCurrentIndex(self.projects.count() - 1)
            else:
                self.projects.setCurrentIndex(self.projects.findData(uid))
        finally:
            self.projects.blockSignals(False)

    def _request_project(self):
        uid = self.projects.currentData()
        if uid is not None:
            self.project_requested.emit(uid)

    def reject(self):
        if self.editor.can_leave():
            super().reject()
