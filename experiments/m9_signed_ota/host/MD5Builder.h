#pragma once
#include "Arduino.h"
// Unused cryptography in signed mode; test asserts native signing skips MD5.
struct MD5Builder {void begin(){}void add(uint8_t*,size_t){}void calculate(){}
    void getBytes(uint8_t*){}String toString()const{return "HOST_UNSIGNED_MD5_NOT_IMPLEMENTED";}};
