#pragma once
#include <string.h>
#define PROGMEM
#define PGM_P const char*
#define pgm_read_byte(p) (*(const unsigned char*)(p))
#define pgm_read_word(p) (*(const unsigned short*)(p))
#define pgm_read_dword(p) (*(const unsigned int*)(p))
#define memcpy_P memcpy
