extern "C" {
/* Copyright (c) 2015 Ivan Grokhotkov. All rights reserved. 
 * This file is part of eboot bootloader.
 *
 * Redistribution and use is permitted according to the conditions of the
 * 3-clause BSD license to be found in the LICENSE file.
 */
 
#ifndef EBOOT_COMMAND_H
#define EBOOT_COMMAND_H

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

extern volatile uint32_t m9_host_rtc[32];
#define RTC_MEM m9_host_rtc

enum action_t {
    ACTION_COPY_RAW = 0x00000001,
    ACTION_LOAD_APP = 0xffffffff
};

#define EBOOT_MAGIC 	 0xeb001000
#define EBOOT_MAGIC_MASK 0xfffff000

struct eboot_command {
    uint32_t magic;
    enum action_t action;
    uint32_t args[29];
    uint32_t crc32;
};


int eboot_command_read(struct eboot_command* cmd);
void eboot_command_write(struct eboot_command* cmd);
void eboot_command_clear();

#endif //EBOOT_COMMAND_H

}
