# Copyright 2023 Clayton Craft
# SPDX-License-Identifier: GPL-3.0-or-later
import os
import glob
import pmb.parse
import pmb.helpers.other
from typing import Optional


def list(args, arch):
    """
    Get all UIs, for which aports are available with their description.

    :param arch: device architecture, for which the UIs must be available
    :returns: [("none", "No graphical..."), ("weston", "Wayland reference...")]
    """
    ret = [("none", "Bare minimum OS image for testing and manual"
                    " customization. The \"console\" UI should be selected if"
                    " a graphical UI is not desired.")]
    for path in sorted(glob.glob(args.aports + "/main/postmarketos-ui-*")):
        apkbuild = pmb.parse.apkbuild(f"{path}/APKBUILD")
        ui = os.path.basename(path).split("-", 2)[2]
        if pmb.helpers.package.check_arch(args, apkbuild["pkgname"], arch):
            ret.append((ui, apkbuild["pkgdesc"]))
    return ret


def flatpak_by_default(arch: str, ui: str, disk: Optional[str] = None) -> bool:
    """
    Whether it's recommended to use flatpaks by default for this configuration

    :param arch: device architecture
    :param ui: selected UI
    :returns: True if it's recommended, else False
    """
    if arch not in ("x86_64", "aarch64"):
        return False
    ui = ui.lower()
    if "gnome" not in ui and "plasma" not in ui and "phosh" not in ui:
        return False
    if disk is not None:
        size = pmb.helpers.other.get_device_size(disk)
        # This is just a sanity check. Assume it's possible if no size
        if size and size < 16:
            return False
    return True
