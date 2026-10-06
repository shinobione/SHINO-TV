// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include "shino_private_policy.h"
#ifndef SHINO_BOOT_PROFILE
#error "Generated private profile required before compiling SHINO firmware"
#endif
#if SHINO_BOOT_PROFILE != 0
#if SHINO_BOOT_PROFILE == 1
#error "Normal SHINO boot is prohibited until a reviewed FS/data migration gate exists."
#elif SHINO_BOOT_PROFILE == 2
#if !defined(SHINO_M9_MOUNT_PROBE) || SHINO_M9_MOUNT_PROBE != 1
#error "Mount probe requires the explicit Mission-9 opt-in environment."
#endif
#else
#error "Unknown SHINO_BOOT_PROFILE."
#endif
#endif
#if defined(SHINO_M9_MOUNT_PROBE) && SHINO_BOOT_PROFILE != 2
#error "Mission-9 mount-probe environment requires profile 2."
#endif
#ifndef SHINO_M9_MOUNT_PROBE_RESOURCE_DIAGNOSTICS
#define SHINO_M9_MOUNT_PROBE_RESOURCE_DIAGNOSTICS 0
#endif
#if SHINO_M9_MOUNT_PROBE_RESOURCE_DIAGNOSTICS != 0 && SHINO_M9_MOUNT_PROBE_RESOURCE_DIAGNOSTICS != 1
#error "Unknown Mission-9 resource diagnostics policy."
#endif
#if SHINO_M9_MOUNT_PROBE_RESOURCE_DIAGNOSTICS == 1 && SHINO_BOOT_PROFILE != 2
#error "Resource diagnostics require the explicit profile-2 mount-probe environment."
#endif
