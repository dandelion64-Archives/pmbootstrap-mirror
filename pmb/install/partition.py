# Copyright 2022 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import os
import time
import pmb.chroot
import pmb.config
import pmb.install.losetup


def partitions_mount(args, root_id, sdcard, boot_id=1):
    """
    Mount blockdevices of partitions inside native chroot
    :param root_id: root partition id
    :param sdcard: path to sdcard device (e.g. /dev/mmcblk0) or None
    :param boot_id: boot partition id
    """
    prefix = sdcard
    if not sdcard:
        img_path = "/home/pmos/rootfs/" + args.device + ".img"
        prefix = pmb.install.losetup.device_by_back_file(args, img_path)

    partition_prefix = None
    tries = 20
    for i in range(tries):
        for symbol in ["p", ""]:
            if os.path.exists(prefix + symbol + "1"):
                partition_prefix = symbol
        if partition_prefix is not None:
            break
        logging.debug(f"NOTE: ({i + 1}/{tries}) failed to find the install "
                      "partition. Retrying...")
        time.sleep(0.1)

    if partition_prefix is None:
        raise RuntimeError("Unable to find the partition prefix,"
                           " expected the first partition of " +
                           prefix + " to be located at " + prefix +
                           "1 or " + prefix + "p1!")

    for i in [boot_id, root_id]:
        source = prefix + partition_prefix + str(i)
        target = args.work + "/chroot_native/dev/installp" + str(i)
        pmb.helpers.mount.bind_file(args, source, target)


def partition_read(args, path):
    cmd = ['parted', '--script', path, 'unit', 's', 'print']
    raw = pmb.chroot.root(args, cmd, check=True, output_return=True)
    header = True
    result = []
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("Number "):
            header = False
            continue
        elif header:
            continue
        part = line.split()
        if len(part) < 4:
            continue
        result.append([
            int(part[0]),       # Partition number
            int(part[1][:-1]),  # Start sector
            int(part[2][:-1])   # End sector
        ])

    return result


def partition(args, size_boot, size_reserve, towboot):
    """
    Partition /dev/install and create /dev/install{p1,p2,p3}:
    * /dev/installp1: boot
    * /dev/installp2: root (or reserved space)
    * /dev/installp3: (root, if reserved space > 0)

    When adjusting this function, make sure to also adjust
    ondev-prepare-internal-storage.sh in postmarketos-ondev.git!

    :param size_boot: size of the boot partition in MiB
    :param size_reserve: empty partition between root and boot in MiB (pma#463)
    :param tow_boot: true if tow-boot is present on the install device, false
    if not
    """
    # Convert to MB and print info
    mb_boot = f"{round(size_boot)}M"
    mb_reserved = f"{round(size_reserve)}M"
    mb_root_start = f"{round(size_boot) + round(size_reserve)}M"
    logging.info(f"(native) partition /dev/install (boot: {mb_boot},"
                 f" reserved: {mb_reserved}, root: the rest)")

    filesystem = args.deviceinfo["boot_filesystem"] or "ext2"

    # Actual partitioning with 'parted'. Using check=False, because parted
    # sometimes "fails to inform the kernel". In case it really failed with
    # partitioning, the follow-up mounting/formatting will not work, so it
    # will stop there (see #463).
    boot_part_start = args.deviceinfo["boot_part_start"] or "2048"

    if towboot:
        # Don't create a new partition table, Tow-Boot has already done that.
        # Read the existing partitions to clean existing installations on the
        # shared storage.

        # Make sure the backup GPT table is at the end of the disk
        pmb.chroot.root(args, ["sgdisk", "-e", "/dev/install"], check=True)

        current_partitions = partition_read(args, "/dev/install")
        boot_part_start = str(current_partitions[0][2] + 1)

        commands = []

        # Remove existing partitions after the tow-boot partition
        if len(current_partitions) > 1:
            for part in current_partitions[1:]:
                commands += [
                    ["rm", str(part[0])]
                ]

        commands += [
            ["mkpart", "primary", filesystem, boot_part_start + 's', mb_boot]
        ]
    else:
        partition_type = args.deviceinfo["partition_type"] or "msdos"
        commands = [
            ["mktable", partition_type],
            ["mkpart", "primary", filesystem, boot_part_start + 's', mb_boot],
        ]

    if size_reserve:
        mb_reserved_end = f"{round(size_reserve + size_boot)}M"
        commands += [["mkpart", "primary", mb_boot, mb_reserved_end]]

    commands += [["mkpart", "primary", mb_root_start, "100%"]]

    if towboot:
        commands += [["set", "2", "boot", "on"]]
    else:
        commands += [["set", "1", "boot", "on"]]

    for command in commands:
        pmb.chroot.root(args, ["parted", "-s", "/dev/install"] +
                        command, check=False)
