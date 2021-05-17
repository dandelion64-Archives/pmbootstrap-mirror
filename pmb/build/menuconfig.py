# Copyright 2021 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import os
import logging

import pmb.build
import pmb.build.autodetect
import pmb.build.checksum
import pmb.build.other
import pmb.chroot
import pmb.chroot.apk
import pmb.chroot.other
import pmb.helpers.pmaports
import pmb.helpers.run
import pmb.parse


def get_arch(args, apkbuild):
    """
    Take the architecture from the APKBUILD or complain if it's ambiguous. This
    function only gets called if --arch is not set.

    :param apkbuild: looks like: {"pkgname": "linux-...",
                                  "arch": ["x86_64", "armhf", "aarch64"]}
                     or: {"pkgname": "linux-...", "arch": ["armhf"]}
    """
    pkgname = apkbuild["pkgname"]

    # Disabled package (arch="")
    if not apkbuild["arch"]:
        raise RuntimeError(f"'{pkgname}' is disabled (arch=\"\"). Please use"
                           " '--arch' to specify the desired architecture.")

    # Multiple architectures
    if len(apkbuild["arch"]) > 1:
        raise RuntimeError(f"'{pkgname}' supports multiple architectures"
                           f" ({', '.join(apkbuild['arch'])}). Please use"
                           " '--arch' to specify the desired architecture.")

    return apkbuild["arch"][0]


def menuconfig(args, pkgname):
    # Pkgname: allow omitting "linux-" prefix
    if pkgname.startswith("linux-"):
        pkgname_ = pkgname.split("linux-")[1]
        logging.info(f"PROTIP: You can simply do 'pmbootstrap kconfig edit "
                     f"{pkgname_}'")
    else:
        pkgname = f"linux-{pkgname}"

    # Read apkbuild
    aport = pmb.helpers.pmaports.find(args, pkgname)
    apkbuild = pmb.parse.apkbuild(args, f"{aport}/APKBUILD")
    arch = args.arch or get_arch(args, apkbuild)
    suffix = pmb.build.autodetect.suffix(args, apkbuild, arch)
    cross = pmb.build.autodetect.crosscompile(args, apkbuild, arch, suffix)
    hostspec = pmb.parse.arch.alpine_to_hostspec(arch)

    # Set up build tools and makedepends
    pmb.build.init(args, suffix)
    if cross:
        pmb.build.init_compiler(args, [], cross, arch)
    depends = apkbuild["makedepends"]
    kopt = "menuconfig"
    copy_xauth = False
    if args.xconfig:
        depends += ["qt5-qtbase-dev", "font-noto"]
        kopt = "xconfig"
        copy_xauth = True
    elif args.nconfig:
        kopt = "nconfig"
        depends += ["ncurses-dev"]
    else:
        depends += ["ncurses-dev"]

    depends += ["diffconfig", "mergeconfig"]
    pmb.chroot.apk.install(args, depends)

    # Copy host's .xauthority into native
    if copy_xauth:
        pmb.chroot.other.copy_xauthority(args)

    # Patch and extract sources
    pmb.build.copy_to_buildpath(args, pkgname)
    logging.info("(native) extract kernel source")
    pmb.chroot.user(args, ["abuild", "unpack"], "native", "/home/pmos/build")
    logging.info("(native) apply patches")
    fragments = "pmb:kconfig-fragments" in apkbuild["options"]
    if fragments:
        pmb.build.other.create_pmos_config(args, apkbuild, arch)
    pmb.chroot.user(args, ["abuild", "prepare"], "native",
                    "/home/pmos/build", output="interactive",
                    env={"CARCH": arch})

    outputdir = pmb.build.other.get_outputdir(args, pkgname, apkbuild)
    config = None
    if fragments:
        fragment_name = pmb.build.other \
            .get_fragment_name(args, arch,
                               f"{args.work}/chroot_native/{outputdir}")
        config = f"{fragment_name}.{arch}"
    else:
        config = ".config"

    # Run make menuconfig
    logging.info(f"(native) make {kopt}")
    env = {"ARCH": pmb.parse.arch.alpine_to_kernel(arch),
           "DISPLAY": os.environ.get("DISPLAY"),
           "XAUTHORITY": "/home/pmos/.Xauthority"}
    if cross:
        env["CROSS_COMPILE"] = f"{hostspec}-"
        env["CC"] = f"{hostspec}-gcc"

    pmb.chroot.user(args, ["make", kopt], "native",
                    outputdir, output="tui", env=env)

    if fragments:
        logging.info("(native) diffconfig")
        cmd = f"diffconfig -m .config.old .config > {config}.temp"
        pmb.chroot.user(args, ["sh", "-c", cmd], "native", outputdir)
        logging.info("(native) mergeconfig")
        pmb.chroot.user(args, ["mergeconfig", "-m", config,
                               f"{config}.temp"],
                        "native", outputdir,
                        env={"KCONFIG_CONFIG": config})
        pmb.chroot.user(args, ["chmod", "644", config], "native", outputdir)

    # Update the aport (config or config diff and checksum)
    logging.info("Copy kernel config back to aport-folder")
    source = f"{args.work}/chroot_native{outputdir}/{config}"
    if fragments:
        target = f"{aport}/{config}"
        pmb.helpers.run.user(args, ["cp", source, target])
        config_path = f"{args.work}/chroot_native{outputdir}/.config"
        pmb.parse.kconfig.check_file(args, config_path, details=True)
    else:
        # Find the updated config
        if not os.path.exists(source):
            raise RuntimeError(f"No kernel config generated: {source}")
        target = f"{aport}/config-{apkbuild['_flavor']}.{arch}"
        pmb.helpers.run.user(args, ["cp", source, target])
        pmb.parse.kconfig.check(args, apkbuild["_flavor"],
                                force_anbox_check=False,
                                force_nftables_check=False,
                                force_containers_check=False,
                                force_zram_check=False,
                                details=True)

    pmb.build.checksum.update(args, pkgname)
