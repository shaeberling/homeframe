// Homeframe — 13.3" e-paper home dashboard.
//
// Normal operation: poll the homeframe server for a pre-rendered 1bpp frame
// and push it to the panel. When the server or the network is unavailable for
// long enough, fall back to a screen the ESP32 draws itself, so the frame
// degrades to a clock rather than to a stale or blank panel.
#include <Arduino.h>
#include <time.h>

#include "config.h"
#include "display.h"
#include "fallback.h"
#include "frame.h"
#include "net.h"

namespace {

enum class Mode { Booting, Server, Fallback };

Mode     s_mode          = Mode::Booting;
uint32_t s_last_poll_ms  = 0;
uint32_t s_last_good_ms  = 0;   // millis() when a server frame last reached the panel
uint16_t s_failures      = 0;
int      s_fallback_minute = -1;

int currentMinute()
{
  if (!hfTimeValid()) return -1;
  time_t now = time(nullptr);
  struct tm tm_local;
  localtime_r(&now, &tm_local);
  return tm_local.tm_min;
}

HfFallbackStatus currentStatus()
{
  HfFallbackStatus s;
  s.wifi_connected       = hfWifiConnected();
  s.ip                   = s.wifi_connected ? hfWifiIp() : String("");
  s.rssi                 = s.wifi_connected ? hfWifiRssi() : 0;
  s.last_error           = hfFrameLastError();
  s.last_good_ms         = s_last_good_ms;
  s.consecutive_failures = s_failures;
  return s;
}

void enterFallback()
{
  log_w("falling back to on-device screen after %u failures", s_failures);
  s_mode = Mode::Fallback;
  hfRenderFallback(currentStatus());
  s_fallback_minute = currentMinute();
}

void poll()
{
  if (!hfWifiEnsure())
  {
    s_failures++;
  }
  else
  {
    // Whatever is on the panel right now is not the server's frame, so a 304
    // would leave the outage screen up. Ask for the body unconditionally.
    if (s_mode != Mode::Server) hfFrameInvalidate();

    switch (hfFrameFetch())
    {
      case HfFetchResult::Updated:
        s_failures     = 0;
        s_last_good_ms = millis();
        s_mode         = Mode::Server;
        break;

      case HfFetchResult::Unchanged:
        s_failures = 0;
        break;

      case HfFetchResult::Failed:
        s_failures++;
        break;
    }
  }

  if (s_failures >= HF_FALLBACK_AFTER_FAILURES && s_mode != Mode::Fallback)
  {
    enterFallback();
  }
}

}  // namespace

void setup()
{
  Serial.begin(115200);
  delay(100);
  log_i("homeframe %s starting", HF_FIRMWARE_VERSION);

  hfDisplayBegin();
  hfShowSplash();

  log_i("heap before frame alloc: %u free, %u largest block",
        ESP.getFreeHeap(), ESP.getMaxAllocHeap());

  if (!hfFrameBegin())
  {
    log_e("cannot allocate frame buffer: %s", hfFrameLastError());
  }

  log_i("heap after frame alloc:  %u free, %u largest block",
        ESP.getFreeHeap(), ESP.getMaxAllocHeap());

  hfWifiBegin();

  log_i("heap after wifi up:      %u free, %u largest block",
        ESP.getFreeHeap(), ESP.getMaxAllocHeap());
  hfTimeBegin();

  poll();
  s_last_poll_ms = millis();
}

void loop()
{
  const uint32_t now = millis();

  if (now - s_last_poll_ms >= HF_POLL_INTERVAL_MS)
  {
    s_last_poll_ms = now;
    poll();
  }

  // Keep the fallback clock honest while the server is away.
  if (s_mode == Mode::Fallback)
  {
    const int minute = currentMinute();
    if (minute >= 0 && minute != s_fallback_minute)
    {
      hfRenderFallback(currentStatus());
      s_fallback_minute = minute;
    }
  }

  delay(200);
}
