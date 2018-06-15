#!/bin/sh

downstreamkernel_prepare() {
	default_prepare

	# gcc6 support
	# shellcheck disable=SC2154
	cp -v "$srcdir/compiler-gcc6.h" "$builddir/include/linux/"

	# Remove -Werror from all makefiles
	makefiles="$(find . -type f -name Makefile)
		$(find . -type f -name Kbuild)"
	for i in $makefiles; do
		sed -i 's/-Werror-/-W/g' "$i"
		sed -i 's/-Werror//g' "$i"
	done

	# Prepare kernel config ('yes ""' for kernels lacking olddefconfig)
	# shellcheck disable=SC2154
	cp "$srcdir/$_config" "$builddir"/.config
	# shellcheck disable=SC2154
	yes "" | make ARCH="$_carch" HOSTCC="$HOSTCC" oldconfig
}
