"""Lesbare Hierarchiepfade; UUIDs bleiben unabhängig von Namen und Zuordnungen."""

import re


def path_component(label):
    return re.sub(r"[^\w.-]+", "_", label.strip()).strip("_.") or "node"


def refresh_paths(nodes, devices, original_nodes, original_devices):
    def component(row, originals):
        original = originals.get(row["uid"], row)
        if (row["label"] or "").strip() == (original["label"] or "").strip():
            return original["path"].rsplit("/", 1)[-1]
        return path_component(row["label"] or row.get("type_id", "node"))

    pending = set(nodes)
    while pending:
        ready = [uid for uid in pending if nodes[uid]["parent_uid"] not in pending]
        if not ready:
            raise ValueError("Die Node-Struktur enthält einen Kreis.")
        for uid in ready:
            row = nodes[uid]
            parent = nodes.get(row["parent_uid"])
            row["path"] = (parent["path"] + "/" if parent else "") + component(row, original_nodes)
            pending.remove(uid)
    for row in devices.values():
        row["path"] = nodes[row["node_uid"]]["path"] + "/" + component(row, original_devices)
    for rows in (nodes, devices):
        if len({row["path"] for row in rows.values()}) != len(rows):
            raise ValueError("Die Namen ergeben eine doppelte Kennung innerhalb desselben Nodes. "
                             "Bitte eine eindeutige Bezeichnung wählen.")


def refresh_stored_paths(connection, project_uid, original_nodes, original_devices):
    nodes = {row["uid"]: dict(row) for row in connection.execute(
        "SELECT * FROM nodes WHERE project_uid=?", (project_uid,))}
    devices = {row["uid"]: dict(row) for row in connection.execute(
        "SELECT * FROM devices WHERE project_uid=?", (project_uid,))}
    old_paths = {table: {uid: row["path"] for uid, row in rows.items()}
                 for table, rows in (("nodes", nodes), ("devices", devices))}
    refresh_paths(nodes, devices, original_nodes, original_devices)
    for table, rows in (("nodes", nodes), ("devices", devices)):
        changed = [row for uid, row in rows.items() if row["path"] != old_paths[table][uid]]
        for row in changed:
            connection.execute(f"UPDATE {table} SET path=? WHERE uid=?", (f"~{row['uid']}", row["uid"]))
        for row in changed:
            connection.execute(f"UPDATE {table} SET path=? WHERE uid=?", (row["path"], row["uid"]))
