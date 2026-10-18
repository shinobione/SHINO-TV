#pragma once
#ifdef __cplusplus
#include <Arduino.h>
#endif
#include <string.h>
#ifndef PROGMEM
#define PROGMEM
#endif
#define memcpy_P memcpy
#define pgm_read_byte(p) (*(const unsigned char*)(p))
#define pgm_read_word(p) (*(const unsigned short*)(p))
#define pgm_read_dword(p) (*(const unsigned int*)(p))

#define memcmp_P memcmp
