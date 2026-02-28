#include <Arduino.h>
#include <debug.h>
#include "OtaUpdate.h"
#include "RgbLed.h"
#include "TwaiTaskBased.h"
#include <Preferences.h>
#include <driver/gpio.h>

// =============================================================================
// Pin Definitions (from schematic global labels)
// =============================================================================

// Reed switch inputs (Normally Open - close when magnet nearby / door closed)
// HIGH = door open, LOW = door closed (using internal pull-ups)
static const gpio_num_t RSW_PINS[] = {
  GPIO_NUM_16,  // RSW01 (TX pin - free since USB CDC is used for Serial)
  GPIO_NUM_17,  // RSW02 (RX pin - free since USB CDC is used for Serial)
  GPIO_NUM_0,   // RSW03
  GPIO_NUM_1,   // RSW04
  GPIO_NUM_2,   // RSW05
  GPIO_NUM_3,   // RSW06
  GPIO_NUM_4,   // RSW07
  GPIO_NUM_5,   // RSW08
  GPIO_NUM_6,   // RSW09
  GPIO_NUM_7,   // RSW10
};
static const uint8_t NUM_RSW = sizeof(RSW_PINS) / sizeof(RSW_PINS[0]);

// DIP switch address pins (active LOW - switches pull to GND when ON)
static const gpio_num_t ADDR_PINS[] = {
  GPIO_NUM_18,  // ADDR01 (bit 0 - LSB)
  GPIO_NUM_19,  // ADDR02 (bit 1)
  GPIO_NUM_20,  // ADDR03 (bit 2 - MSB)
};
static const uint8_t NUM_ADDR_PINS = sizeof(ADDR_PINS) / sizeof(ADDR_PINS[0]);

// CAN bus pins
static const gpio_num_t CAN_TX_PIN = GPIO_NUM_14;
static const gpio_num_t CAN_RX_PIN = GPIO_NUM_15;

// RGB LED (built-in WS2812 on GPIO8)
static const uint8_t RGB_LED_PIN = 8;

// =============================================================================
// CAN Bus Configuration
// =============================================================================

// CAN IDs 0x0A-0x11 reserved for up to 8 Cabinet/Door Sensor modules.
// Higher priority (lower ID) than DeviceStatusReport (0x1B).
// DIP switches select offset: CAN_ID = CAN_BASE_ID + dip_value (0-7)
static const uint32_t CAN_BASE_ID = 0x0A;
static const uint32_t CAN_BAUDRATE = 500000;

// Transmit interval (200ms = 5 Hz)
static const unsigned long TX_INTERVAL_MS = 200;

// Debounce time for reed switch readings
static const unsigned long DEBOUNCE_MS = 50;

// =============================================================================
// Global State
// =============================================================================

RgbLed statusLed(RGB_LED_PIN);
OtaUpdate otaUpdate(statusLed, 180000, "", "");

uint32_t canMessageId = CAN_BASE_ID;
unsigned long lastTxTime = 0;

// Debounced reed switch state
uint16_t debouncedState = 0;
uint16_t lastRawState = 0;
unsigned long lastChangeTime = 0;

// WiFi credential reception state (CAN ID 0x01 protocol)
bool wifiConfigInProgress = false;
uint8_t wifiSsidBuffer[33];
uint8_t wifiPasswordBuffer[64];
uint8_t wifiSsidLen = 0;
uint8_t wifiPasswordLen = 0;
uint8_t wifiSsidReceived = 0;
uint8_t wifiPasswordReceived = 0;

// =============================================================================
// WiFi Credential Storage
// =============================================================================

void saveWifiCredentials(const char* ssid, const char* password) {
  Preferences prefs;
  prefs.begin("wifi", false);
  prefs.putString("ssid", ssid);
  prefs.putString("password", password);
  prefs.end();
  debugf("[WiFi] Credentials saved to NVS (SSID: %s)\n", ssid);
}

void handleWifiConfigMessage(const twai_message_t &msg) {
  uint8_t msgType = msg.data[0];

  switch (msgType) {
    case 0x01: {
      wifiSsidLen = msg.data[1];
      wifiPasswordLen = msg.data[2];
      wifiSsidReceived = 0;
      wifiPasswordReceived = 0;
      memset(wifiSsidBuffer, 0, sizeof(wifiSsidBuffer));
      memset(wifiPasswordBuffer, 0, sizeof(wifiPasswordBuffer));
      wifiConfigInProgress = true;
      debugf("[WiFi] Config start: SSID len=%d, Password len=%d\n",
             wifiSsidLen, wifiPasswordLen);
      break;
    }
    case 0x02: {
      if (!wifiConfigInProgress) break;
      uint8_t dataBytes = msg.data_length_code - 2;
      uint8_t remaining = wifiSsidLen - wifiSsidReceived;
      if (dataBytes > remaining) dataBytes = remaining;
      if (wifiSsidReceived + dataBytes <= 32) {
        memcpy(wifiSsidBuffer + wifiSsidReceived, &msg.data[2], dataBytes);
        wifiSsidReceived += dataBytes;
      }
      break;
    }
    case 0x03: {
      if (!wifiConfigInProgress) break;
      uint8_t dataBytes = msg.data_length_code - 2;
      uint8_t remaining = wifiPasswordLen - wifiPasswordReceived;
      if (dataBytes > remaining) dataBytes = remaining;
      if (wifiPasswordReceived + dataBytes <= 63) {
        memcpy(wifiPasswordBuffer + wifiPasswordReceived, &msg.data[2], dataBytes);
        wifiPasswordReceived += dataBytes;
      }
      break;
    }
    case 0x04: {
      if (!wifiConfigInProgress) break;
      wifiConfigInProgress = false;

      uint8_t checksum = 0;
      for (uint8_t i = 0; i < wifiSsidReceived; i++) checksum ^= wifiSsidBuffer[i];
      for (uint8_t i = 0; i < wifiPasswordReceived; i++) checksum ^= wifiPasswordBuffer[i];

      if (checksum == msg.data[1] &&
          wifiSsidReceived == wifiSsidLen &&
          wifiPasswordReceived == wifiPasswordLen) {
        wifiSsidBuffer[wifiSsidReceived] = '\0';
        wifiPasswordBuffer[wifiPasswordReceived] = '\0';
        saveWifiCredentials((const char*)wifiSsidBuffer,
                            (const char*)wifiPasswordBuffer);
      } else {
        debugf("[WiFi] Config failed: checksum %s, SSID %d/%d, Password %d/%d\n",
               (checksum == msg.data[1]) ? "OK" : "MISMATCH",
               wifiSsidReceived, wifiSsidLen,
               wifiPasswordReceived, wifiPasswordLen);
      }
      break;
    }
  }
}

// =============================================================================
// CAN Bus Callbacks
// =============================================================================

void onCanRx(const twai_message_t &msg) {
  if (msg.identifier == 0x00) {
    // OTA update notification - check if it's for this device
    char updateForHostName[14];
    String currentHostName = otaUpdate.getHostName();
    sprintf(updateForHostName, "esp32c6-%X%X%X",
            msg.data[0], msg.data[1], msg.data[2]);

    if (currentHostName.equals(updateForHostName)) {
      debugln("[OTA] Hostname matched - reading WiFi credentials from NVS");

      Preferences prefs;
      prefs.begin("wifi", true);
      String ssid = prefs.getString("ssid", "");
      String password = prefs.getString("password", "");
      prefs.end();

      if (ssid.length() > 0 && password.length() > 0) {
        debugf("[OTA] Using stored WiFi credentials (SSID: %s)\n", ssid.c_str());
        OtaUpdate ota(statusLed, 180000, ssid.c_str(), password.c_str());
        ota.waitForOta();
        debugln("[OTA] OTA mode exited - resuming normal operation");
      } else {
        debugln("[OTA] ERROR: No WiFi credentials in NVS - cannot start OTA");
      }
    }
  } else if (msg.identifier == 0x01) {
    handleWifiConfigMessage(msg);
  }
}

void onCanTx(bool ok) {
  debug_if(!ok, "[CAN] TX FAIL");
}

// =============================================================================
// Reed Switch Reading
// =============================================================================

uint16_t readReedSwitches() {
  uint16_t state = 0;
  for (uint8_t i = 0; i < NUM_RSW; i++) {
    // HIGH = door open (pull-up, NO reed switch open)
    // LOW = door closed (reed switch closed by magnet)
    if (digitalRead(RSW_PINS[i]) == HIGH) {
      state |= (1 << i);
    }
  }
  return state;
}

uint16_t readDebouncedSwitches() {
  uint16_t rawState = readReedSwitches();

  if (rawState != lastRawState) {
    lastRawState = rawState;
    lastChangeTime = millis();
  }

  if ((millis() - lastChangeTime) >= DEBOUNCE_MS) {
    debouncedState = rawState;
  }

  return debouncedState;
}

// =============================================================================
// DIP Switch Address Reading
// =============================================================================

uint8_t readDipAddress() {
  uint8_t addr = 0;
  for (uint8_t i = 0; i < NUM_ADDR_PINS; i++) {
    // DIP switches pull to GND when ON (active LOW with pull-up)
    // ON = LOW = bit set
    if (digitalRead(ADDR_PINS[i]) == LOW) {
      addr |= (1 << i);
    }
  }
  return addr;
}

// =============================================================================
// CAN Message Transmission
// =============================================================================

void sendDoorStatus(uint16_t doorState) {
  twai_message_t msg = {};
  msg.identifier = canMessageId;
  msg.data_length_code = 2;

  // Byte 0: RSW01-RSW08 (bits 0-7), 1=open, 0=closed
  msg.data[0] = (uint8_t)(doorState & 0xFF);

  // Byte 1: RSW09-RSW10 (bits 0-1), bits 2-7 reserved
  msg.data[1] = (uint8_t)((doorState >> 8) & 0x03);

  TwaiTaskBased::send(msg);
}

// =============================================================================
// Setup
// =============================================================================

void setup() {
  Serial.begin(115200);
#if DEBUG == 0
  Serial.println("Debug disabled - no further serial output.");
#else
  debugln("[INIT] Cabinet & Door Sensor starting");
#endif

  // Initialize RGB LED (built-in WS2812 on GPIO8)
  statusLed.begin();
  statusLed.setBrightnessPercent(1);

  // Configure reed switch inputs with internal pull-ups
  for (uint8_t i = 0; i < NUM_RSW; i++) {
    pinMode(RSW_PINS[i], INPUT_PULLUP);
  }
  debugf("[INIT] Configured %d reed switch inputs\n", NUM_RSW);

  // Configure DIP switch address pins with internal pull-ups
  for (uint8_t i = 0; i < NUM_ADDR_PINS; i++) {
    pinMode(ADDR_PINS[i], INPUT_PULLUP);
  }

  // Read DIP switch address and compute CAN message ID
  uint8_t dipAddr = readDipAddress();
  canMessageId = CAN_BASE_ID + dipAddr;
  debugf("[INIT] DIP address: %d, CAN ID: 0x%02X\n", dipAddr, canMessageId);

  // Initialize CAN bus
  TwaiTaskBased::onReceive(onCanRx);
  TwaiTaskBased::onTransmit(onCanTx);
  TwaiTaskBased::begin(CAN_TX_PIN, CAN_RX_PIN, CAN_BAUDRATE);
  debugln("[INIT] TWAI started on GPIO14 (TX) / GPIO15 (RX)");

  // Read initial state
  debouncedState = readReedSwitches();
  lastRawState = debouncedState;
  lastChangeTime = millis();

  debugf("[INIT] Initial door state: 0x%04X\n", debouncedState);
  statusLed.green();
  debugln("[INIT] Setup complete");
}

// =============================================================================
// Main Loop
// =============================================================================

void loop() {
  uint16_t currentState = readDebouncedSwitches();

  unsigned long now = millis();
  if (now - lastTxTime >= TX_INTERVAL_MS) {
    lastTxTime = now;
    sendDoorStatus(currentState);
  }
}
