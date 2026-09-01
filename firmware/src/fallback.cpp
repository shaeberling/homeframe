#include "fallback.h"

#include <Fonts/FreeSans12pt7b.h>
#include <Fonts/FreeSans18pt7b.h>
#include <Fonts/FreeSansBold12pt7b.h>
#include <Fonts/FreeSansBold24pt7b.h>

#include "display.h"
#include "net.h"

static void drawCentered(const String& text, int16_t center_x, int16_t baseline_y)
{
  int16_t  bx, by;
  uint16_t bw, bh;
  display.getTextBounds(text, 0, baseline_y, &bx, &by, &bw, &bh);
  display.setCursor(center_x - bw / 2 - bx, baseline_y);
  display.print(text);
}

static void drawLabelled(int16_t x, int16_t y, const char* label, const String& value)
{
  display.setFont(&FreeSansBold12pt7b);
  display.setCursor(x, y);
  display.print(label);

  display.setFont(&FreeSans12pt7b);
  display.setCursor(x + 190, y);
  display.print(value);
}

void hfShowSplash()
{
  const int16_t w = display.width();
  const int16_t h = display.height();

  display.setFullWindow();
  display.firstPage();
  do {
    display.fillScreen(GxEPD_WHITE);
    display.setTextColor(GxEPD_BLACK);

    display.setFont(&FreeSansBold24pt7b);
    drawCentered("homeframe", w / 2, h / 2 - 10);

    display.setFont(&FreeSans12pt7b);
    drawCentered(String("v") + HF_FIRMWARE_VERSION + "  -  starting up", w / 2, h / 2 + 40);
  } while (display.nextPage());

  hfDisplayRefreshed(true);  // firstPage/nextPage on a full window is a full refresh
}

void hfRenderFallback(const HfFallbackStatus& status)
{
  const int16_t w = display.width();
  const int16_t h = display.height();
  const bool    full = hfDisplayWantsFullRefresh();

  const String clock = hfTimeValid()
                           ? hfTimeFormat(HF_CLOCK_24H ? "%H:%M" : "%I:%M %p")
                           : String("--:--");
  const String date  = hfTimeValid() ? hfTimeFormat("%A, %e %B %Y") : String("waiting for time sync");

  if (full) display.setFullWindow();
  else      display.setPartialWindow(0, 0, w, h);
  display.firstPage();
  do {
    display.fillScreen(GxEPD_WHITE);
    display.setTextColor(GxEPD_BLACK);

    // Header
    display.setFont(&FreeSansBold12pt7b);
    display.setCursor(48, 56);
    display.print("HOMEFRAME");
    display.setFont(&FreeSans12pt7b);
    display.setCursor(w - 260, 56);
    display.print("server unreachable");
    display.drawFastHLine(48, 76, w - 96, GxEPD_BLACK);

    // Clock — the one thing a hallway frame should always get right.
    display.setFont(&FreeSansBold24pt7b);
    display.setTextSize(3);
    drawCentered(clock, w / 2, h / 2 - 20);
    display.setTextSize(1);

    display.setFont(&FreeSans18pt7b);
    drawCentered(date, w / 2, h / 2 + 50);

    // Diagnostics
    const int16_t box_top = h - 250;
    display.drawFastHLine(48, box_top, w - 96, GxEPD_BLACK);

    int16_t y = box_top + 50;
    drawLabelled(48, y, "WiFi",
                 status.wifi_connected
                     ? status.ip + "   " + String(status.rssi) + " dBm"
                     : String("not connected to ") + WIFI_SSID);

    y += 42;
    drawLabelled(48, y, "Server", String(HF_SERVER_BASE));

    y += 42;
    drawLabelled(48, y, "Last error",
                 strlen(status.last_error) ? String(status.last_error) : String("none"));

    y += 42;
    String last_good = status.last_good_ms
                           ? String(hfMinutesSince(status.last_good_ms)) + " min ago"
                           : String("never since boot");
    drawLabelled(48, y, "Last frame",
                 last_good + "   (" + String(status.consecutive_failures) + " failed polls)");
  } while (display.nextPage());

  hfDisplayRefreshed(full);
}
