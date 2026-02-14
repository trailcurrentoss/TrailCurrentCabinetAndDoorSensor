# TrailCurrent Cabinet and Door Sensor

Sensor module that monitors cabinet and door open/closed states using reed switches and reports status over a CAN bus interface.

## Hardware Overview

- **Microcontroller:** ESP32-C6
- **Function:** Cabinet and door state monitoring with CAN bus reporting
- **Key Features:**
  - Reed switch sensors for open/closed detection
  - CAN bus communication at 500 kbps
  - DHT22 temperature/humidity monitoring
  - Over-the-air (OTA) firmware updates
  - RGB LED status indicator
  - Custom flash partition layout with dual OTA slots
  - FreeCAD enclosure design

### Design Specifications

- **Operating Temperature:** -20°C to +70°C
- **Power:** 12V vehicle house battery via 5V DC-DC converter and 3.3V regulator
- **Data Rate:** 5 transmissions per second
- **Target Cost:** < $5 per unit

## Hardware Requirements

### Components

- **Microcontroller:** ESP32-C6-Super-Mini
- **CAN Transceiver:** SN65HVD230
- **Sensors:** Reed switches, DHT22 temperature/humidity
- **Power:** Buck converter (12V to 5V to 3.3V)
- **Connectors:** JST XH 2.54 4-pin

### KiCAD Library Dependencies

This project uses the consolidated [TrailCurrentKiCADLibraries](https://github.com/trailcurrentoss/TrailCurrentKiCADLibraries).

**Setup:**

```bash
# Clone the library
git clone git@github.com:trailcurrentoss/TrailCurrentKiCADLibraries.git

# Set environment variables (add to ~/.bashrc or ~/.zshrc)
export TRAILCURRENT_SYMBOL_DIR="/path/to/TrailCurrentKiCADLibraries/symbols"
export TRAILCURRENT_FOOTPRINT_DIR="/path/to/TrailCurrentKiCADLibraries/footprints"
export TRAILCURRENT_3DMODEL_DIR="/path/to/TrailCurrentKiCADLibraries/3d_models"
```

See [KICAD_ENVIRONMENT_SETUP.md](https://github.com/trailcurrentoss/TrailCurrentKiCADLibraries/blob/main/KICAD_ENVIRONMENT_SETUP.md) in the library repository for detailed setup instructions.

## Opening the Project

1. **Set up environment variables** (see Library Dependencies above)
2. **Open KiCAD:**
   ```bash
   kicad EDA/TrailCurrentCabinetAndDoorSensorModule/TrailCurrentCabinetAndDoorSensorModule.kicad_pro
   ```
3. **Verify libraries load** - All symbol and footprint libraries should resolve without errors
4. **View 3D models** - Open PCB and press `Alt+3` to view the 3D visualization

## Firmware

See `src/` directory for PlatformIO-based firmware. The firmware is currently in early development.

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
- **[Adafruit DHT sensor library](https://github.com/adafruit/DHT-sensor-library)** (v1.4.6+) - Temperature and humidity sensor

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
