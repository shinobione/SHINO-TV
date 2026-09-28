// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// Host-only Arduino.h shim for compiling the UNMODIFIED FslessMetrics.cpp.
// NEVER included by firmware builds; no Wi-Fi, flash, hardware, credentials.
#include <cstdint>
#include <string>
struct String : public std::string {
    using std::string::string;
    using std::string::operator=;
};
#define F(literal) (literal)
uint32_t millis();
