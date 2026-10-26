"""Compatibility imports for existing configuration clients."""

from wiedan.core.working_configuration import (
    DEVICE_TYPES as DEVICE_TYPES,
    PARAMETERS as PARAMETERS,
    W700 as W700,
    Parameter as Parameter,
    apply_template as apply_template,
    available_parameters as available_parameters,
    blank_configuration as blank_configuration,
    configuration_errors as configuration_errors,
    configuration_status as configuration_status,
    list_sets as list_sets,
    load_set as load_set,
    new_set as new_set,
    parse_value as parse_value,
    project_devices as project_devices,
    read_set as read_set,
    save_set as save_set,
    set_path as set_path,
    user_directory as user_directory,
    project_directory as project_directory,
)
