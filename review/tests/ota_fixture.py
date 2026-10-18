import struct,hashlib,hmac

def arduino_crc(data: bytes) -> int:
    """Core 3.1.2 elf2bin.py/eboot polynomial, with CRC fields zeroed."""
    crc = 0xFFFFFFFF
    for index, byte in enumerate(data):
        if 0x1010 <= index < 0x1018:
            byte = 0
        for mask in (128, 64, 32, 16, 8, 4, 2, 1):
            bit = bool(crc & 0x80000000) ^ bool(byte & mask)
            crc = (crc << 1) & 0xFFFFFFFF
            if bit:
                crc ^= 0x04C11DB7
    return crc

def inert_image(size=100000):
    if size % 16 or size < 64000:
        raise ValueError("fixture size")
    raw = bytearray(size)
    struct.pack_into("<BBBBI",raw,0,0xE9,1,2,0x40,0x4010F000)
    struct.pack_into("<II",raw,8,0x4010F000,16)
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

def fixture(build_id="b"*64,device="0123456789abcdef"):
    raw=bytearray(inert_image());tag=f"SHINO-HTTP-OTA-1|{device}|{build_id}|4m2m|APP_ONLY".encode()
    raw[0x2000:0x2000+len(tag)]=tag;raw[0x1010:0x1018]=bytes(8)
    checksum=0xef
    for x in raw[0x1010:0x1020]+raw[0x1028:len(raw)-8]:checksum^=x
    raw[-1]=checksum;struct.pack_into("<II",raw,0x1010,len(raw),arduino_crc(raw));return bytes(raw)

def signature(identity,nonce,m):
    text=f'SHINO-HTTP-OTA-1\n{identity["device"]}\n{nonce}\n{m["bytes"]}\n{m["sha256"]}\n{m["build_id"]}'
    key=hashlib.sha256(identity["maintenance_password"].encode()).digest()
    return hmac.new(key,text.encode("ascii"),hashlib.sha256).hexdigest()
