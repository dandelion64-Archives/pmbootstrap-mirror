# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
from pmb.core.context import Context
from pmb.helpers import logging
import os
import pathlib

import pmb.build
import pmb.config
import pmb.chroot
import pmb.chroot.apk
from pmb.types import PmbArgs
import pmb.helpers.run
import pmb.parse.arch
from pmb.core import Chroot, get_context


def init_abuild_minimal(chroot: Chroot=Chroot.native()):
    """Initialize a minimal chroot with abuild where one can do 'abuild checksum'."""
    marker = chroot / "tmp/pmb_chroot_abuild_init_done"
    if os.path.exists(marker):
        return

    pmb.chroot.apk.install(["abuild"], chroot, build=False)

    # Fix permissions
    pmb.chroot.root(["chown", "root:abuild",
                           "/var/cache/distfiles"], chroot)
    pmb.chroot.root(["chmod", "g+w",
                           "/var/cache/distfiles"], chroot)

    # Add user to group abuild
    pmb.chroot.root(["adduser", "pmos", "abuild"], chroot)

    pathlib.Path(marker).touch()


def init(chroot: Chroot=Chroot.native()):
    """Initialize a chroot for building packages with abuild."""
    marker = chroot / "tmp/pmb_chroot_build_init_done"
    if marker.exists():
        return

    # Initialize chroot, install packages
    pmb.chroot.init(Chroot.native())
    pmb.chroot.init(chroot)
    init_abuild_minimal(chroot)

    pmb.chroot.apk.install(pmb.config.build_packages, chroot,
                           build=False)

    # Generate package signing keys
    if not os.path.exists(get_context().config.work / "config_abuild/abuild.conf"):
        logging.info(f"({chroot}) generate abuild keys")
        pmb.chroot.user(["abuild-keygen", "-n", "-q", "-a"],
                        chroot, env={"PACKAGER": "pmos <pmos@local>"})

        # Copy package signing key to /etc/apk/keys
        for key in (chroot / "mnt/pmbootstrap/abuild-config").glob("*.pub"):
            key = key.relative_to(chroot.path)
            pmb.chroot.root(["cp", key, "/etc/apk/keys/"], chroot)

    apk_arch = chroot.arch

    # Add apk wrapper that runs native apk and lies about arch
    if pmb.parse.arch.cpu_emulation_required(apk_arch) and \
            not (chroot / "usr/local/bin/abuild-apk").exists():
        with (chroot / "tmp/apk_wrapper.sh").open("w") as handle:
            content = f"""
                #!/bin/sh

                # With !pmb:crossdirect, cross compilation is entriely done
                # in QEMU, no /native dir gets mounted inside the foreign arch
                # chroot.
                if ! [ -d /native ]; then
                    exec /usr/bin/abuild-apk "$@"
                fi

                export LD_PRELOAD_PATH=/native/usr/lib:/native/lib
                args=""
                for arg in "$@"; do
                    if [ "$arg" == "--print-arch" ]; then
                        echo "{apk_arch}"
                        exit 0
                    fi
                    args="$args $arg"
                done
                /native/usr/bin/abuild-apk $args
            """
            lines = content.split("\n")[1:]
            for i in range(len(lines)):
                lines[i] = lines[i][16:]
            handle.write("\n".join(lines))
        pmb.chroot.root(["cp", "/tmp/apk_wrapper.sh",
                               "/usr/local/bin/abuild-apk"], chroot)
        pmb.chroot.root(["chmod", "+x", "/usr/local/bin/abuild-apk"], chroot)

    # abuild.conf: Don't clean the build folder after building, so we can
    # inspect it afterwards for debugging
    pmb.chroot.root(["sed", "-i", "-e", "s/^CLEANUP=.*/CLEANUP=''/",
                           "/etc/abuild.conf"], chroot)

    # abuild.conf: Don't clean up installed packages in strict mode, so
    # abuild exits directly when pressing ^C in pmbootstrap.
    pmb.chroot.root(["sed", "-i", "-e",
                           "s/^ERROR_CLEANUP=.*/ERROR_CLEANUP=''/",
                           "/etc/abuild.conf"], chroot)

    pathlib.Path(marker).touch()


def init_compiler(context: Context, depends, cross, arch):
    cross_pkgs = ["ccache-cross-symlinks", "abuild"]
    if "gcc4" in depends:
        cross_pkgs += ["gcc4-" + arch]
    elif "gcc6" in depends:
        cross_pkgs += ["gcc6-" + arch]
    else:
        cross_pkgs += ["gcc-" + arch, "g++-" + arch]
    if "clang" in depends or "clang-dev" in depends:
        cross_pkgs += ["clang"]
    if cross == "crossdirect":
        cross_pkgs += ["crossdirect"]
        if "rust" in depends or "cargo" in depends:
            if context.ccache:
                cross_pkgs += ["sccache"]
            # crossdirect for rust installs all build dependencies in the
            # native chroot too, as some of them can be required for building
            # native macros / build scripts
            cross_pkgs += depends

    pmb.chroot.apk.install(cross_pkgs, Chroot.native())
