"""Non-executable public checksum/CRC fixture; never a firmware build."""
import struct
from m9_first_migration import arduino_crc


def inert_image(size=100000):
    if size % 16 or size < 64000:
        raise ValueError("fixture size")
    raw = bytearray(size)
    struct.pack_into("<BBBBI",raw,0,0xE9,1,2,0x40,0x40100000)
    struct.pack_into("<II",raw,8,0x40100000,16)
    raw[16:32] = b"INERT-NOT-CODE!!"
    checksum = 0xEF
    for byte in raw[16:32]: checksum ^= byte
    raw[47] = checksum
    struct.pack_into("<BBBBI",raw,0x1000,0xE9,2,2,0x40,0x40100008)
    struct.pack_into("<II",raw,0x1008,0x40100000,16)
    struct.pack_into("<II",raw,0x1020,0x40201028,size-0x1030)
    label = b"INERT_PUBLIC_FIXTURE_NOT_BOOTABLE"
    raw[0x1028:0x1028+len(label)] = label
    checksum = 0xEF
    for byte in raw[0x1010:0x1020] + raw[0x1028:size-8]: checksum ^= byte
    raw[size-1] = checksum
    struct.pack_into("<II",raw,0x1010,size,arduino_crc(raw))
    return bytes(raw)
