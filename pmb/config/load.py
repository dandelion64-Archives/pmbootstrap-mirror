# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
from pmb.helpers import logging
import configparser
import os
import sys
import pmb.config
from pmb.core.types import PmbArgs

__cfg: configparser.ConfigParser


def sanity_check(args: PmbArgs, cfg, key, allowed, print_path):
    value = cfg["pmbootstrap"][key]

    if value in allowed:
        return

    logging.error(f"pmbootstrap.cfg: invalid value for {key}: '{value}'")
    logging.error(f"Allowed: {', '.join(allowed)}")

    if print_path:
        logging.error(f"Fix it here and try again: {args.config}")

    sys.exit(1)


def sanity_checks(args: PmbArgs, cfg, print_path=True):
    for key, allowed in pmb.config.allowed_values.items():
        sanity_check(args, cfg, key, allowed, print_path)


def get(k: str):
    global __cfg
    if "__cfg" in globals() and __cfg is not None:
        return __cfg["pmbootstrap"][k]

    raise RuntimeError("Config not loaded yet")


def load(args: PmbArgs):
    global __cfg

    cfg = configparser.ConfigParser()
    if os.path.isfile(args.config):
        cfg.read(args.config)

    if "pmbootstrap" not in cfg:
        cfg["pmbootstrap"] = {}
    if "providers" not in cfg:
        cfg["providers"] = {}

    for key in pmb.config.defaults:
        if key in pmb.config.config_keys and key not in cfg["pmbootstrap"]:
            cfg["pmbootstrap"][key] = str(pmb.config.defaults[key])

        # We used to save default values in the config, which can *not* be
        # configured in "pmbootstrap init". That doesn't make sense, we always
        # want to use the defaults from pmb/config/__init__.py in that case,
        # not some outdated version we saved some time back (eg. aports folder,
        # postmarketOS binary packages mirror).
        if key not in pmb.config.config_keys and key in cfg["pmbootstrap"]:
            logging.debug("Ignored unconfigurable and possibly outdated"
                          " default value from config:"
                          f" {cfg['pmbootstrap'][key]}")
            del cfg["pmbootstrap"][key]

    sanity_checks(args, cfg)

    __cfg = cfg
    return cfg

def save(args: PmbArgs, cfg):
    global __cfg
    logging.debug(f"Save config: {args.config}")
    os.makedirs(os.path.dirname(args.config), 0o700, True)
    with open(args.config, "w") as handle:
        cfg.write(handle)

    # FIXME: bad bad bad bad bad
    __cfg = cfg

