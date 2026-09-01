#include "net.h"

#include <WiFi.h>
#include <time.h>

#include "config.h"

bool hfWifiBegin()
{
  WiFi.persistent(false);
  WiFi.mode(WIFI_STA);
  // Mains-powered: trade idle current for a stable link and faster transfers.
  WiFi.setSleep(false);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  const uint32_t started = millis();
  while (WiFi.status() != WL_CONNECTED &&
         millis() - started < HF_WIFI_CONNECT_TIMEOUT_MS)
  {
    delay(200);
  }

  if (WiFi.status() == WL_CONNECTED)
  {
    log_i("wifi up: %s rssi %d", WiFi.localIP().toString().c_str(), WiFi.RSSI());
    return true;
  }
  log_w("wifi failed to associate with %s", WIFI_SSID);
  return false;
}

bool hfWifiEnsure()
{
  if (WiFi.status() == WL_CONNECTED) return true;
  log_w("wifi link lost, reconnecting");
  WiFi.disconnect();
  return hfWifiBegin();
}

bool    hfWifiConnected() { return WiFi.status() == WL_CONNECTED; }
String  hfWifiIp()        { return WiFi.localIP().toString(); }
int32_t hfWifiRssi()      { return WiFi.RSSI(); }

void hfTimeBegin()
{
  configTime(0, 0, HF_NTP_1, HF_NTP_2);
  setenv("TZ", HF_TZ, 1);
  tzset();
}

bool hfTimeValid()
{
  // Anything before 2021 means SNTP has not landed yet.
  return time(nullptr) > 1609459200;
}

String hfTimeFormat(const char* fmt)
{
  if (!hfTimeValid()) return String("");

  time_t now = time(nullptr);
  struct tm tm_local;
  localtime_r(&now, &tm_local);

  char buf[64];
  strftime(buf, sizeof(buf), fmt, &tm_local);
  return String(buf);
}

uint32_t hfMinutesSince(uint32_t since_ms)
{
  if (since_ms == 0) return 0;
  return (millis() - since_ms) / 60000UL;
}
