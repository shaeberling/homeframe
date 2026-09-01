#include "display.h"

#include <SPI.h>

HfDisplay display(HfPanel(HF_PIN_CS, HF_PIN_DC, HF_PIN_RST, HF_PIN_BUSY));

static uint16_t s_since_full = 0;
static bool     s_first_update = true;

void hfDisplayBegin()
{
  // The ESP32-L wires the panel to the default VSPI pins, but state it
  // explicitly so a rewire only needs config.h touched.
  SPI.begin(HF_PIN_SCK, -1, HF_PIN_MOSI, HF_PIN_CS);

  display.init(115200, true, 2, false);
  display.setRotation(HF_DISPLAY_ROTATION);
  display.setTextColor(GxEPD_BLACK);
  display.clearScreen();

  s_since_full = 0;
  s_first_update = true;
}

bool hfDisplayWantsFullRefresh()
{
  return s_first_update || s_since_full >= HF_FULL_REFRESH_EVERY;
}

void hfDisplayRefreshed(bool was_full)
{
  s_first_update = false;
  if (was_full) s_since_full = 0;
  else          s_since_full++;
}

void hfDisplayPushFrame(const uint8_t* frame)
{
  const bool full = hfDisplayWantsFullRefresh();

  display.epd2.writeImage(frame, 0, 0, HF_PANEL_WIDTH, HF_PANEL_HEIGHT);
  display.epd2.refresh(!full);
  // Differential (fast partial) refresh compares against the controller's
  // "previous" buffer. Without this the next partial update would diff against
  // stale contents and leave artefacts.
  display.epd2.writeImageAgain(frame, 0, 0, HF_PANEL_WIDTH, HF_PANEL_HEIGHT);
  display.epd2.powerOff();

  hfDisplayRefreshed(full);
}

void hfDisplaySleep()
{
  display.powerOff();
}
