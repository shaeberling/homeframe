// Panel ownership: the single GxEPD2 instance, plus refresh bookkeeping.
#pragma once

#include <GxEPD2_BW.h>
#include <gdem/GxEPD2_1330_GDEM133T91.h>

#include "config.h"

using HfPanel   = GxEPD2_1330_GDEM133T91;
using HfDisplay = GxEPD2_BW<HfPanel, HF_PAGE_HEIGHT>;

extern HfDisplay display;

// Brings up SPI and the panel, and clears it with one full refresh.
void hfDisplayBegin();

// True when the next refresh should be a full one (ghosting cleanup, or the
// first update after boot). Callers pass the result to hfDisplayRefreshed().
bool hfDisplayWantsFullRefresh();

// Records that a refresh happened, so the full/partial cadence stays on track.
void hfDisplayRefreshed(bool was_full);

// Pushes an entire native-orientation 1bpp frame (HF_FRAME_BYTES, 1 = white)
// straight to controller memory and refreshes. Bypasses the paged buffer.
void hfDisplayPushFrame(const uint8_t* frame);

// Drops panel driving voltages. Safe to call repeatedly; the next write powers
// the panel back on by itself.
void hfDisplaySleep();
