// WiFi association and wall-clock time.
#pragma once

#include <Arduino.h>

// Starts the station interface and blocks up to HF_WIFI_CONNECT_TIMEOUT_MS.
bool hfWifiBegin();

// Reconnects if the link dropped. Cheap when already associated.
bool hfWifiEnsure();

bool     hfWifiConnected();
String   hfWifiIp();
int32_t  hfWifiRssi();

// Kicks off SNTP. Time arrives asynchronously; poll hfTimeValid().
void hfTimeBegin();
bool hfTimeValid();

// Formatted local time. Returns "--:--" / "" before the first SNTP sync.
String hfTimeFormat(const char* fmt);

// Minutes since a millis() timestamp, for "last updated" lines.
uint32_t hfMinutesSince(uint32_t since_ms);
