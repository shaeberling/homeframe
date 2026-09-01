// Homeframe — compile-time configuration.
//
// Hardware: Good Display ESP32-L(C02) driver board (ESP32-WROOM-32D, no PSRAM)
//           + GDEM133T91 13.3" 960x680 monochrome panel (SSD1677, 24-pin FPC).
#pragma once

#include <stdint.h>

// ---------------------------------------------------------------- panel pins
// Wiring for the Good Display ESP32-L development kit, as documented by GxEPD2
// (examples/GxEPD2_Example/GxEPD2_wiring_examples.h). The DESPI-C02 adapter is
// hard-wired to these GPIOs — do not change unless you rewire the board.
#define HF_PIN_BUSY 13
#define HF_PIN_RST  12
#define HF_PIN_DC   14
#define HF_PIN_CS   27
#define HF_PIN_SCK  18  // VSPI default
#define HF_PIN_MOSI 23  // VSPI default

// ------------------------------------------------------------ panel geometry
#define HF_PANEL_WIDTH   960
#define HF_PANEL_HEIGHT  680
#define HF_FRAME_BYTES   ((HF_PANEL_WIDTH / 8) * HF_PANEL_HEIGHT)  // 81600

// Height of one GxEPD2 page for on-device (fallback) drawing. 136 divides 680
// evenly into 5 pages of 16320 bytes each. Larger = fewer passes, more RAM.
#define HF_PAGE_HEIGHT 136

// Rotation for on-device drawing only: 0/2 = landscape, 1/3 = portrait.
// This does NOT rotate server-rendered frames — those arrive as native
// 960x680 scanlines, so the server must rotate them to match. Keep
// HF_DISPLAY_ROTATION and the server's ORIENTATION in agreement.
#define HF_DISPLAY_ROTATION 0

// ------------------------------------------------------------------ refresh
// Fast partial refresh takes ~0.6s and does not flash; full refresh takes
// ~4.5s and inverts the panel, but clears accumulated ghosting. Do a full
// refresh every N updates, and always on boot.
#define HF_FULL_REFRESH_EVERY 20

// --------------------------------------------------------------- networking
#define HF_POLL_INTERVAL_MS       60000UL   // how often to ask the server for a frame
#define HF_HTTP_TIMEOUT_MS        20000UL   // per-request timeout
#define HF_FRAME_READ_TIMEOUT_MS  25000UL   // whole-body read budget for 81600 bytes
#define HF_WIFI_CONNECT_TIMEOUT_MS 20000UL

// Consecutive failed polls before the frame gives up on the server and draws
// its own status screen. At a 60s poll interval, 3 = about three minutes.
#define HF_FALLBACK_AFTER_FAILURES 3

// ------------------------------------------------------------------- clock
// POSIX TZ string. Default is America/Los_Angeles (PST/PDT).
// Others: "CET-1CEST,M3.5.0,M10.5.0/3" (Berlin), "EST5EDT,M3.2.0,M11.1.0" (US East).
#define HF_TZ        "PST8PDT,M3.2.0,M11.1.0"
// Fallback-clock format. 1 = 24-hour (metric convention), 0 = 12-hour + AM/PM.
// Keep in agreement with HF_UNITS on the server so both screens read alike.
#define HF_CLOCK_24H 1

#define HF_NTP_1     "pool.ntp.org"
#define HF_NTP_2     "time.google.com"

#include "secrets.h"
