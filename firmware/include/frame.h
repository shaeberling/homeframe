// Fetching server-rendered frames and pushing them to the panel.
#pragma once

#include <Arduino.h>

enum class HfFetchResult {
  Updated,    // new frame received and displayed
  Unchanged,  // server said 304, panel already correct
  Failed,     // network, HTTP or short-read error; see hfFrameLastError()
};

// Allocates the 81600-byte frame buffer. Call once, before hfFrameFetch().
bool hfFrameBegin();

HfFetchResult hfFrameFetch();

const char* hfFrameLastError();

// Duration of the most recent successful body transfer, milliseconds. Reported
// to the server as telemetry and shown on the dashboard's status bar.
uint32_t hfFrameLastTransferMs();

// Forgets the cached ETag, forcing the next fetch to return a full body even
// if the dashboard has not changed. Needed whenever something other than a
// server frame is on the panel.
void hfFrameInvalidate();
