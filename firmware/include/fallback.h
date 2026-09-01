// On-device screens: drawn by the ESP32 itself when the server is unreachable,
// so an outage shows a live clock and a diagnosis instead of a frozen or blank
// panel.
#pragma once

#include <Arduino.h>

struct HfFallbackStatus {
  bool        wifi_connected;
  String      ip;
  int32_t     rssi;
  const char* last_error;
  uint32_t    last_good_ms;         // millis() of last displayed frame, 0 = never
  uint16_t    consecutive_failures;
};

// Shown once at boot, before WiFi is up.
void hfShowSplash();

void hfRenderFallback(const HfFallbackStatus& status);
