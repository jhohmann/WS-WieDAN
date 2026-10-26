CREATE TABLE database_info (
    singleton INTEGER PRIMARY KEY CHECK (singleton=1),
    uid TEXT NOT NULL,
    data_version TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE projects (
    uid TEXT PRIMARY KEY,
    project_id TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    full_name TEXT NOT NULL,
    live INTEGER NOT NULL CHECK (live IN (0,1)),
    control TEXT NOT NULL,
    product TEXT NOT NULL,
    track_origin_description TEXT NOT NULL DEFAULT ''
);
CREATE TABLE credentials (
    project_uid TEXT NOT NULL REFERENCES projects(uid),
    name TEXT NOT NULL,
    values_json TEXT NOT NULL,
    PRIMARY KEY (project_uid,name)
);
CREATE TABLE device_categories (id TEXT PRIMARY KEY, label TEXT NOT NULL UNIQUE);
CREATE TABLE device_types (
    id TEXT PRIMARY KEY, definition_json TEXT NOT NULL,
    category_id TEXT REFERENCES device_categories(id)
);
CREATE TABLE logging_sets (id TEXT PRIMARY KEY, definition_json TEXT NOT NULL);
CREATE TABLE vehicles (
    uid TEXT PRIMARY KEY,
    project_uid TEXT NOT NULL REFERENCES projects(uid),
    path TEXT NOT NULL,
    label TEXT NOT NULL,
    product TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    UNIQUE(project_uid,path), UNIQUE(project_uid,uid)
);
CREATE TABLE nodes (
    uid TEXT PRIMARY KEY,
    project_uid TEXT NOT NULL REFERENCES projects(uid),
    path TEXT NOT NULL,
    parent_uid TEXT,
    vehicle_uid TEXT,
    label TEXT NOT NULL,
    state TEXT,
    ordinal INTEGER NOT NULL,
    UNIQUE(project_uid,path), UNIQUE(project_uid,uid),
    FOREIGN KEY(project_uid,parent_uid) REFERENCES nodes(project_uid,uid),
    FOREIGN KEY(project_uid,vehicle_uid) REFERENCES vehicles(project_uid,uid)
);
CREATE TABLE devices (
    uid TEXT PRIMARY KEY,
    project_uid TEXT NOT NULL REFERENCES projects(uid),
    path TEXT NOT NULL,
    node_uid TEXT NOT NULL,
    type_id TEXT NOT NULL REFERENCES device_types(id),
    label TEXT,
    pingable INTEGER CHECK (pingable IN (0,1)),
    ip TEXT NOT NULL,
    connection_overrides TEXT NOT NULL DEFAULT '{}',
    commissioning_overrides TEXT NOT NULL DEFAULT '{}',
    installation_position REAL,
    track_start REAL,
    track_end REAL,
    ordinal INTEGER NOT NULL,
    UNIQUE(project_uid,path),
    FOREIGN KEY(project_uid,node_uid) REFERENCES nodes(project_uid,uid)
);
CREATE TABLE assets (
    project_uid TEXT NOT NULL REFERENCES projects(uid),
    name TEXT NOT NULL,
    content BLOB NOT NULL,
    PRIMARY KEY(project_uid,name)
);
CREATE INDEX devices_project ON devices(project_uid);
CREATE INDEX nodes_project ON nodes(project_uid);
CREATE TABLE device_parameters (
    device_uid TEXT NOT NULL REFERENCES devices(uid),
    name TEXT NOT NULL,
    value_json TEXT NOT NULL,
    PRIMARY KEY(device_uid,name)
);
CREATE TABLE device_field_definitions (
    uid TEXT PRIMARY KEY,
    type_id TEXT NOT NULL REFERENCES device_types(id),
    name TEXT NOT NULL CHECK (length(trim(name)) > 0),
    value_type TEXT NOT NULL CHECK (value_type IN ('text','number','boolean')),
    UNIQUE(type_id,name)
);
CREATE TABLE device_field_values (
    device_uid TEXT NOT NULL REFERENCES devices(uid) ON DELETE CASCADE,
    field_uid TEXT NOT NULL REFERENCES device_field_definitions(uid),
    value_json TEXT NOT NULL,
    PRIMARY KEY(device_uid,field_uid)
);
