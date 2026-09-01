#include "frame.h"

#include <HTTPClient.h>
#include <WiFi.h>
#include <WiFiClient.h>

#include "config.h"
#include "display.h"

// One native-orientation frame: 120 bytes per row x 680 rows, MSB = leftmost
// pixel, 1 = white. Sent to the SSD1677 verbatim, so no decoding step and no
// second copy — which matters on a WROOM-32D with no PSRAM.
static uint8_t* s_frame = nullptr;

// Echoed back as If-None-Match so an unchanged dashboard costs one 304 instead
// of 81600 bytes and a panel refresh.
static String   s_etag;
static char     s_error[96] = "";
static uint32_t s_transfer_ms = 0;

static void setError(const char* fmt, ...)
{
  va_list args;
  va_start(args, fmt);
  vsnprintf(s_error, sizeof(s_error), fmt, args);
  va_end(args);
  log_w("frame: %s", s_error);
}

bool hfFrameBegin()
{
  if (s_frame) return true;

  s_frame = static_cast<uint8_t*>(malloc(HF_FRAME_BYTES));
  if (!s_frame)
  {
    setError("out of memory for %d byte frame", HF_FRAME_BYTES);
    return false;
  }
  memset(s_frame, 0xFF, HF_FRAME_BYTES);  // white
  return true;
}

const char* hfFrameLastError() { return s_error; }

uint32_t hfFrameLastTransferMs() { return s_transfer_ms; }

// Drains exactly HF_FRAME_BYTES from the response body. Returns false on
// timeout or premature close — a partial frame is never shown, since half a
// dashboard looks like a bug rather than an outage.
//
// Throughput here is governed by how promptly we drain LWIP's receive buffer:
// every byte consumed reopens the TCP window. Sleeping a fixed interval per
// segment, as an available()/delay() loop does, throttles the whole transfer.
static bool readBody(WiFiClient* stream)
{
  size_t         got = 0;
  const uint32_t started = millis();
  const uint32_t deadline = started + HF_FRAME_READ_TIMEOUT_MS;
  size_t         next_mark = HF_FRAME_BYTES / 4;
  uint32_t       idle_since = started;

  while (got < HF_FRAME_BYTES)
  {
    // Non-blocking: takes whatever is buffered right now rather than waiting
    // for a full chunk, so the window reopens at the earliest moment.
    const int n = stream->read(s_frame + got, HF_FRAME_BYTES - got);

    if (n > 0)
    {
      got += n;
      idle_since = millis();

      if (got >= next_mark)
      {
        log_i("  %u%% at %ums", (unsigned)(got * 100 / HF_FRAME_BYTES),
              (unsigned)(millis() - started));
        next_mark += HF_FRAME_BYTES / 4;
      }
      continue;
    }

    if (!stream->connected() && !stream->available())
    {
      setError("connection closed at %u/%d bytes", (unsigned)got, HF_FRAME_BYTES);
      return false;
    }

    if (millis() > deadline)
    {
      setError("read timeout at %u/%d bytes after %ums", (unsigned)got,
               HF_FRAME_BYTES, (unsigned)(millis() - started));
      return false;
    }

    // Yield to the WiFi task without sleeping. Back off only once the stream
    // has genuinely gone quiet, so a stall does not spin the CPU for 25s.
    if (millis() - idle_since > 250) delay(2);
    else                             delay(0);
  }

  s_transfer_ms = millis() - started;
  log_i("body read complete: %d bytes in %ums", HF_FRAME_BYTES,
        (unsigned)s_transfer_ms);
  return true;
}

HfFetchResult hfFrameFetch()
{
  if (!s_frame && !hfFrameBegin()) return HfFetchResult::Failed;

  WiFiClient client;
  HTTPClient http;

  const String url = String(HF_SERVER_BASE) + HF_FRAME_PATH;
  if (!http.begin(client, url))
  {
    setError("bad url: %s", url.c_str());
    return HfFetchResult::Failed;
  }

  http.setTimeout(HF_HTTP_TIMEOUT_MS);
  http.setConnectTimeout(HF_HTTP_TIMEOUT_MS);
  http.useHTTP10(true);  // no chunked encoding, so Content-Length is trustworthy
  if (s_etag.length()) http.addHeader("If-None-Match", s_etag);
  if (strlen(HF_SERVER_TOKEN)) http.addHeader("X-Homeframe-Token", HF_SERVER_TOKEN);

  // Device telemetry. The dashboard is rendered server-side, so anything the
  // panel should show about itself has to travel up with the request.
  http.addHeader("X-Homeframe-Version", HF_FIRMWARE_VERSION);
  http.addHeader("X-Homeframe-Rssi", String(WiFi.RSSI()));
  http.addHeader("X-Homeframe-Heap", String(ESP.getFreeHeap()));
  http.addHeader("X-Homeframe-Uptime", String(millis() / 1000));
  http.addHeader("X-Homeframe-Transfer", String(s_transfer_ms));
  // ESP32 classic only has the deprecated ROM sensor; it reads high and is
  // useful as a trend, not an absolute.
  http.addHeader("X-Homeframe-Temp", String(temperatureRead(), 1));

  static const char* kCollect[] = { "ETag" };
  http.collectHeaders(kCollect, 1);

  const int code = http.GET();

  if (code == HTTP_CODE_NOT_MODIFIED)
  {
    http.end();
    s_error[0] = '\0';
    return HfFetchResult::Unchanged;
  }

  if (code != HTTP_CODE_OK)
  {
    setError(code > 0 ? "http %d" : "connect failed (%d)", code);
    http.end();
    return HfFetchResult::Failed;
  }

  const int len = http.getSize();
  if (len >= 0 && len != HF_FRAME_BYTES)
  {
    setError("expected %d bytes, server sent %d", HF_FRAME_BYTES, len);
    http.end();
    return HfFetchResult::Failed;
  }

  const bool ok = readBody(http.getStreamPtr());
  const String etag = http.header("ETag");
  http.end();

  if (!ok) return HfFetchResult::Failed;

  s_etag = etag;
  s_error[0] = '\0';
  hfDisplayPushFrame(s_frame);
  return HfFetchResult::Updated;
}

void hfFrameInvalidate()
{
  s_etag = "";
}
