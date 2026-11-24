# Omni Scooter BLE Protocol (A3A4) – reverse engineered from BleTool 3.9.23

Source: `BleTool-3.9.23.apk` (`com.omni.production.check`), decoded in `decoded/`.
The protocol is used by Omni IoT devices (including Ninebot/Segway scooters,
`NBScooter` in the app) and carries the same data that is subsequently reported to
telematics platforms (cf. the flespi parameters in `flespi`; see the mapping at the end).

The classes are located under `decoded/smali/com/omni/support/ble/protocol/scooter/` and
`.../protocol/base/a3a4/`. The commands are declared as a Kotlin interface
(`ScooterCommands.smali`) with annotations (`@CommandID`, `@U8/@U16/@U32`) which a
Retrofit-like proxy (`ProtocolRetrofit`) converts into byte streams.

## 1. BLE Layer (GATT)

Nordic UART Service (NUS):

| Role | UUID |
|---|---|
| Service | `6E400001-B5A3-F393-E0A9-E50E24DCCA9E` |
| Write (to device) | `6E400002-B5A3-F393-E0A9-E50E24DCCA9E` |
| Notify (from device) | `6E400003-B5A3-F393-E0A9-E50E24DCCA9E` |
| CCC descriptor | `00002902-0000-1000-8000-00805F9B34FB` |

Source: `profile/sub/ScooterProfileManager.smali`.

## 2. Frame Format (A3A4Pack)

A logical frame before obfuscation:

```
Offset  Field     Size  Description
0       prefix1   1     0xA3
1       prefix2   1     0xA4
2       length    1     number of payload bytes (excluding header and CRC)
3       random    1     random number 0x00–0xFE (new for each frame)
4       key       1     session key (0 until getKey has run; see §4)
5       cmd       1     command ID (see §5)
6..     payload   length command data; multi-byte fields are big-endian
```

### On-the-wire obfuscation (`Pack.scooterDecode`)

Before transmission, the frame is transformed:

- Bytes 0–2: unchanged (`A3 A4 LEN`)
- Byte 3: `random + 0x32` (mod 256)
- Bytes 4 to end: `plain[i] XOR random` (that is, key, cmd, and the whole payload are XORed)

**CRC-8/MAXIM** (poly 0x31, init 0x00, refin=refout=true, xorout 0x00), calculated
over the entire obfuscated frame, is then appended. Total length = `length + 7`.

### Reception (`A3A4Pack.setBuffer`)

1. Verify the CRC-8 (the final byte).
2. `random = raw[3] - 0x32`
3. `key = raw[4] ^ random` (read but not used by the app)
4. `cmd = raw[5] ^ random`
5. `payload[i] = raw[6+i] ^ random`

Responses use the **same cmd** as the request (except transmission commands
0xFA/0xFB/0xFC, which have explicit request/response pairs; see §5).

Multi-byte integers (U16/U32) are **big-endian** (`BufferConverter.getU16`: first
byte << 8).

## 3. Example Frames (verified against the app's own CRC table)

`getScooterInfo(control=1)`, random=0x10, key=0x00:

```
plaintext : a3 a4 01 10 00 60 01
on the wire: a3 a4 01 42 10 70 11 aa
                    ^^ 0x10+0x32    ^^ CRC8
```

`getLockInfo(control=1)`:

```
on the wire: a3 a4 01 42 10 21 11 19
```

Example `getScooterInfo` response (power=87 %, speedMode=2, speed=0,
singleRidingMileage=1234, remainingMileage=45210), random=0x55:

```
on the wire: a3 a4 08 87 55 35 02 57 55 55 51 87 e5 cf 78
```

## 4. Key Handshake

On connection, the app sends `getKey(deviceKey)` (cmd 0x01), where `deviceKey` is a
string (the QR-code contents, scanned in the app). The `ScooterKeyResult` response
contains `isSuccess` and a one-byte `key`, which the app stores in the session
(`ScooterSession.initConfig`) and subsequently puts in byte 4 of every outgoing
frame. Before the handshake, key = 0.

## 5. Command Table

The payload column lists fields in order; U8/U16/U32 are as specified by the
annotations. `→ response` is the result class that parses the response payload.

| Cmd | Method | Payload (request) | Response |
|---|---|---|---|
| 0x01 | getKey | deviceKey (string) | ScooterKeyResult {isSuccess, key} |
| 0x05 | unlock | control U8, timestamp U32, U32, unlockType U8 | ScooterUnlockResult |
| 0x05 | unlockReply | control U8 | – (NoResponse) |
| 0x10 | error | – | ErrorResult |
| 0x15 | lock | control U8 (default 1) | ScooterLockResult |
| 0x15 | lockReply | control U8 (default 2) | – (NoResponse) |
| 0x31 | getLockInfo | control U8 (default 1) | ScooterLockInfoResult (see §6) |
| 0x32 | trackerReset | 4×U8 (default 0xFF) | – (NoResponse) |
| 0x32 | updateBleKey | key bytes | ScooterUpdateBleKeyResult |
| 0x33 | trackerSetting | heartbeat U16, wifiScanTime U8, wifiUploadTime U16, gpsUploadTime U16, lowBatteryAlarm U8 | Boolean |
| 0x33 | updateVoice | U8 | BooleanResult |
| 0x34 | autoUnlock | switch U8, U8 | BooleanResult |
| 0x35 | autoLock | switch U8, lockWay U8, distance U8, delay U8 | BooleanResult |
| 0x36 | getMacBondCount | U8 | ScooterMacBondCount |
| 0x37 | getMacBondInfo | macIndex U8 | ScooterBondMacInfo |
| 0x38 | syncTime | year, month, day, hour, minute, second (6×U8) | BooleanResult |
| 0x39 | getDealHistory | U8 | ScooterAutoUnlockHistory |
| 0x3A | addMac | mac[6], uid[] | BooleanResult |
| 0x3B | deleteMac | mac[6] | BooleanResult |
| 0x3C | getAutoUnlockSetting | control U8 | ScooterAutoUnlockSetting |
| 0x51 | getOldData | U8 | ScooterOldDataResult |
| 0x52 | cleanOldData | U8 (default 1) | Boolean |
| 0x60 | getScooterInfo | control U8 (default 1) | ScooterInfoResult (see §7) |
| 0x61 | setScooterConfig | speedMode, throttleResponse, taillightFlashing, +1 (4×U8) | Boolean |
| 0x62 | scooterConfig | save, cruise, startMode, low, middle, high (6×U8) | Boolean |
| 0x81 | getBatteryStatus | operation U8 (default 0x21) | ScooterBatteryLockStatusResult {operation, status} |
| 0x81 | setOutLockControl | control U8 | ScooterOutLockControlResult |
| 0x82 | lanternControl | light U8, rgb U32, speed U8, brightness U8, mode U8 | Boolean |
| 0x91 | powerControl | control U8 | – (NoResponse) |
| 0xC7 | readLog | U8 | LogCommand (string) |
| 0xC7 | rgbTest | U8 (default 2) | ScooterRGBTestResult |
| 0xC7 | startReadBatteryInfo | U8 (→ responseCmd 0xFB) | ScooterStartReadResult |
| 0xFA | startRead | – (→ responseCmd 0xFB) | ScooterStartReadResult |
| 0xFB | startWrite | type U8, totalPack U16, crc U16, updateKey U8 (→ 0xFC) | WriteResult |
| 0xFC | read | pack U16, deviceType U8 (→ 0xFB) | ReadResult |
| 0x00 | write | pack U16, data[] (→ 0xFC) | WriteResult (TransmissionCommand) |
| – | endWrite | pack U16, data[] | – (NoResponse) |

Note the collisions: 0x32, 0x33, 0x81, and 0xC7 are used for two or three distinct
commands—the app selects the method by context (which screen/function is active);
the device most likely distinguishes them by payload length.

## 6. getLockInfo (0x31) – Response Payload, 7 Bytes

```
Offset  Field           Type  Description
0–1     voltage         U16BE battery voltage (mV; the app logs the raw value)
2       status          U8    status bits (see below)
3       (reserved)      U8    skipped (offset(1))
4       mainVersion     U8    firmware major version
5       minorVersion    U8    firmware minor version
6       numberOfEdits   U8    number of configuration changes
```

Status bits according to `ScooterLockInfoResult.setBuffer`:

- `isUnlock = (status | 1) == 1` → true only when status is 0 or 1
- `hasOldData = (status | 0x40) == 1` → can never be true (the expression is always
  false regardless of status; probably an app bug—the intent was likely
  `status & 0x40` or `(status | 0x40) == status`)

Maps to flespi: `battery.voltage`, `lock.status`, `software.version`.

## 7. getScooterInfo (0x60) – Response Payload, 8 Bytes

```
Offset  Field                Type   Description
0       power                U8     battery level, %
1       speedMode            U8     1=low, 2=medium, 3=high (cf. flespi speed.mode)
2–3     speed                U16BE  speed (raw value; probably 0.01 km/h or m/h)
4–5     singleRidingMileage  U16BE  distance since start (trip.mileage)
6–7     remainingMileage     U16BE  remaining range (remaining.range)
```

The scaling for speed/mileage is not apparent from the model class (the app displays
the raw values); calibrate against a real device. A U16 raw value /100 = km or km/h,
respectively, is the most likely scale (1234 → 12.34).

Maps to flespi: `scooter.battery.level`, `speed.mode`, `position.speed`,
`trip.mileage`, `remaining.range`.

## 8. flespi ↔ BLE Command Mapping

| flespi parameter | BLE source |
|---|---|
| battery.voltage | getLockInfo 0x31 → voltage |
| lock.status / wheel.lock.status | getLockInfo 0x31 → status/isUnlock; controlled through lock 0x15 / unlock 0x05 |
| battery.lock.status | getBatteryStatus 0x81 |
| scooter.battery.level | getScooterInfo 0x60 → power |
| speed.mode | getScooterInfo 0x60 → speedMode; set via setScooterConfig 0x61 |
| position.speed | getScooterInfo 0x60 → speed |
| trip.mileage | getScooterInfo 0x60 → singleRidingMileage |
| remaining.range | getScooterInfo 0x60 → remainingMileage |
| software.version | getLockInfo 0x31 → mainVersion/minorVersion |
| bluetooth.mac.address | getMacBondInfo 0x37 / addMac 0x3A |
| power.status | powerControl 0x91 |
| unlock.timestamp | unlock 0x05 (the timestamp field in the request) |
| gsm.*, position.lat/long, ai.*, helmet.*, fall.alarm, total.* | NOT available over BLE—reported upstream only via GSM/GPS in the IoT device |

The BMS's detailed battery data (cell voltages, current, cycles, temperature—the
equivalents of `battery.cell.*`, `battery.charging.cycles`, and
`battery.temperature`) is in the meter protocols
(`protocol/meter/zy/ZyBMS.smali`, `protocol/meter/bf/BfBatteryInfo.smali`), not in
the scooter protocol.
