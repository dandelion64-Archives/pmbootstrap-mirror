# Copyright 2022 Anjandev Momi
# SPDX-License-Identifier: GPL-3.0-or-later

import os
from pathlib import Path
import pmb.chroot


def static_code_analysis(args, abs_pmbootinchroot, suffix="native"):
    pmb.chroot.root(args, ["./.ci/prepare.sh"], suffix, working_dir=abs_pmbootinchroot,
                    output="stdout")
    pmb.chroot.user(args, ["./test/static_code_analysis.sh"], suffix,
                    working_dir=abs_pmbootinchroot, output_return=True,
                    output="stdout")


def vermin(args, abs_pmbootinchroot, suffix="native"):
    from pmb.chroot.apk import install
    install(args, ["py3-pip"], suffix)
    pmb.chroot.user(args, ["pip3", "-q", "--disable-pip-version-check", "install", "vermin"],
                    suffix, working_dir=abs_pmbootinchroot,
                    output="stdout")
    pmb.chroot.user(args, ["./.ci/vermin.sh"], suffix, working_dir=abs_pmbootinchroot,
                    output="stdout")


def pytest(args, abs_pmbootinchroot, suffix="native"):
    pmb.chroot.root(args, ["./.ci/prepare.sh"], suffix, working_dir=abs_pmbootinchroot,
                    output="stdout")
    pmb.chroot.user(args, ["./.ci/pytest.sh"], suffix, working_dir=abs_pmbootinchroot,
                    output="stdout")


def mv_pmbootstrap(args, suffix="native"):
    hostpmbootstrap = str(Path(os.path.realpath(os.path.dirname(__file__))).parent)
    abs_pmbootinchroot = "/home/pmos/pmbootstrap"

    # Clean up folder
    pmbootstrap_chroot = args.work + "/chroot_" + suffix + abs_pmbootinchroot
    if os.path.exists(pmbootstrap_chroot):
        pmb.chroot.root(args, ["rm", "-rf", abs_pmbootinchroot], suffix)

    # Copy pmbootstrap contents with resolved symlinks
    pmb.helpers.run.root(args, ["cp", "-r", hostpmbootstrap, pmbootstrap_chroot])
    pmb.chroot.root(args, ["chown", "-R", "pmos:pmos",
                           abs_pmbootinchroot], suffix)

    return abs_pmbootinchroot
