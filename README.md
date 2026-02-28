# TrailCurrent Cabinet and Door Sensor

Sensor module that monitors cabinet and door open/closed states using reed switches and reports status over a CAN bus interface. Part of the [TrailCurrent](https://trailcurrent.com) open-source vehicle platform.

## Hardware Overview

- **Microcontroller:** ESP32-C6
- **Function:** Cabinet and door state monitoring with CAN bus reporting
- **Key Features:**
  - 10 reed switch inputs for open/closed detection
  - CAN bus communication at 500 kbps
  - DIP switch selectable CAN address (up to 8 modules per bus)
  - Over-the-air (OTA) firmware updates via WiFi (triggered over CAN)
  - RGB LED status indicator
  - Custom flash partition layout with dual OTA slots
  - FreeCAD enclosure design

### Design Specifications

- **Operating Temperature:** -20°C to +70°C
- **Power:** 12V vehicle house battery via 5V DC-DC converter and 3.3V regulator
- **Data Rate:** 5 transmissions per second
- **Target Cost:** < $5 per unit

## CAN Bus Addressing

Each module uses a 3-position DIP switch to select its CAN message ID from a reserved block of 8 IDs (0x0A-0x11). This allows up to 8 modules on the same CAN bus, each reporting the state of up to 10 doors/cabinets.

| DIP SW3 | DIP SW2 | DIP SW1 | Address | CAN ID | DBC Message Name     |
|---------|---------|---------|---------|--------|----------------------|
| OFF     | OFF     | OFF     | 0       | 0x0A   | CabinetDoorStatus0   |
| OFF     | OFF     | ON      | 1       | 0x0B   | CabinetDoorStatus1   |
| OFF     | ON      | OFF     | 2       | 0x0C   | CabinetDoorStatus2   |
| OFF     | ON      | ON      | 3       | 0x0D   | CabinetDoorStatus3   |
| ON      | OFF     | OFF     | 4       | 0x0E   | CabinetDoorStatus4   |
| ON      | OFF     | ON      | 5       | 0x0F   | CabinetDoorStatus5   |
| ON      | ON      | OFF     | 6       | 0x10   | CabinetDoorStatus6   |
| ON      | ON      | ON      | 7       | 0x11   | CabinetDoorStatus7   |

DIP switch position 4 enables the 120-ohm CAN bus termination resistor.

### CAN Message Format

Each module transmits a 2-byte message at 5 Hz (200 ms interval):

| Byte | Bits  | Description                          |
|------|-------|--------------------------------------|
| 0    | 0-7   | Door status 1-8 (RSW01-RSW08)       |
| 1    | 0-1   | Door status 9-10 (RSW09-RSW10)      |
| 1    | 2-7   | Reserved                             |

Each bit represents one reed switch: `1` = door open, `0` = door closed.

### CAN Control Messages

The module also listens for control messages from other nodes:

- **CAN ID 0x00 - OTA Update Notification:** Contains a 3-byte MAC address suffix. If it matches this module's hostname, the module connects to WiFi using stored credentials and enters OTA update mode.
- **CAN ID 0x01 - WiFi Credential Configuration:** Multi-message protocol to receive and store WiFi SSID and password in NVS flash for future OTA updates.

## Hardware Requirements

### Components

- **Microcontroller:** ESP32-C6-Super-Mini
- **CAN Transceiver:** SN65HVD230
- **Sensors:** Normally Open (NO) reed switches
- **Address Selection:** 4-position DIP switch (3 address bits + CAN termination)
- **Power:** Buck converter (12V to 5V to 3.3V)
- **Connectors:** JST XH 2.54 4-pin

### KiCAD Library Dependencies

This project uses the consolidated [TrailCurrentKiCADLibraries](https://github.com/trailcurrentoss/TrailCurrentKiCADLibraries).

**Setup:**

```bash
# Clone the library alongside this project
git clone git@github.com:trailcurrentoss/TrailCurrentKiCADLibraries.git

# Set environment variables (add to ~/.bashrc or ~/.zshrc)
# Adjust paths to where you cloned the library
export TRAILCURRENT_SYMBOL_DIR="../TrailCurrentKiCADLibraries/symbols"
export TRAILCURRENT_FOOTPRINT_DIR="../TrailCurrentKiCADLibraries/footprints"
export TRAILCURRENT_3DMODEL_DIR="../TrailCurrentKiCADLibraries/3d_models"
```

See [KICAD_ENVIRONMENT_SETUP.md](https://github.com/trailcurrentoss/TrailCurrentKiCADLibraries/blob/main/KICAD_ENVIRONMENT_SETUP.md) in the library repository for detailed setup instructions.

### GPIO Pin Assignments

| GPIO  | Function     | Notes                                    |
|-------|-------------|------------------------------------------|
| 0-7   | RSW03-RSW10 | Reed switch inputs (internal pull-up)     |
| 8     | RGB LED     | Built-in WS2812 on ESP32-C6 SuperMini    |
| 14    | CAN TX      | To SN65HVD230 transceiver                |
| 15    | CAN RX      | From SN65HVD230 transceiver              |
| 16    | RSW01       | TX pin, free since USB CDC is used       |
| 17    | RSW02       | RX pin, free since USB CDC is used       |
| 18-20 | ADDR01-03   | DIP switch address bits (internal pull-up)|

## Opening the Project

1. **Set up environment variables** (see Library Dependencies above)
2. **Open KiCAD:**
   ```bash
   kicad EDA/TrailCurrentCabinetAndDoorSensorModule/TrailCurrentCabinetAndDoorSensorModule.kicad_pro
   ```
3. **Verify libraries load** - All symbol and footprint libraries should resolve without errors
4. **View 3D models** - Open PCB and press `Alt+3` to view the 3D visualization

## Firmware

See `src/` directory for PlatformIO-based firmware.

**Setup:**
```bash
# Install PlatformIO (if not already installed)
pip install platformio

# Build firmware
pio run

# Upload to board (serial)
pio run -t upload

# Upload via OTA (after initial flash)
pio run -t upload --upload-port esp32c6-DEVICE_ID
```

### Firmware Dependencies

This firmware depends on the following public libraries:

- **[C6SuperMiniRgbLedLibrary](https://github.com/trailcurrentoss/C6SuperMiniRgbLedLibrary)** (v0.0.1) - RGB LED status indicator driver
- **[Esp32C6OtaUpdateLibrary](https://github.com/trailcurrentoss/Esp32C6OtaUpdateLibrary)** (v0.0.1) - Over-the-air firmware update functionality
- **[Esp32C6TwaiTaskBasedLibrary](https://github.com/trailcurrentoss/Esp32C6TwaiTaskBasedLibrary)** (v0.0.3) - CAN bus communication interface
- **[ESP32ArduinoDebugLibrary](https://github.com/trailcurrentoss/ESP32ArduinoDebugLibrary)** - Debug macros with compile-time removal

All dependencies are automatically resolved by PlatformIO during the build process.

## Manufacturing

- **PCB Files:** Ready for fabrication via standard PCB services (JLCPCB, OSH Park, etc.)
- **BOM Generation:** Export BOM from KiCAD schematic (Tools > Generate BOM)
- **Enclosure:** FreeCAD design included in `CAD/` directory
- **JLCPCB Assembly:** See [BOM_ASSEMBLY_WORKFLOW.md](https://github.com/trailcurrentoss/TrailCurrentKiCADLibraries/blob/main/BOM_ASSEMBLY_WORKFLOW.md) for detailed assembly workflow

## Documentation

- **Requirements:** See `DOCS/Requirements/high-level-requirements.md` for detailed specifications

## Project Structure

```
├── CAD/                          # FreeCAD enclosure design
├── DOCS/                         # Requirements documentation
│   └── Requirements/
│       └── high-level-requirements.md
├── EDA/                          # KiCAD hardware design files
│   └── TrailCurrentCabinetAndDoorSensorModule/
│       ├── *.kicad_pro           # KiCAD project
│       ├── *.kicad_sch           # Schematic
│       └── *.kicad_pcb           # PCB layout
├── src/                          # Firmware source
│   └── main.cpp                  # Main application
├── platformio.ini                # Build configuration
└── partitions.csv                # ESP32 flash partition layout
```

## License

MIT License - See LICENSE file for details.

This is open source hardware. You are free to use, modify, and distribute these designs for personal or commercial purposes.

## Contributing

Improvements and contributions are welcome! Please submit issues or pull requests.

## Support

For questions about:
- **KiCAD setup:** See [KICAD_ENVIRONMENT_SETUP.md](https://github.com/trailcurrentoss/TrailCurrentKiCADLibraries/blob/main/KICAD_ENVIRONMENT_SETUP.md)
- **Assembly workflow:** See [BOM_ASSEMBLY_WORKFLOW.md](https://github.com/trailcurrentoss/TrailCurrentKiCADLibraries/blob/main/BOM_ASSEMBLY_WORKFLOW.md)
