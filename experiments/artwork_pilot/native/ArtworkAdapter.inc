// Included only in the pilot's generated FirstBootBridge translation unit.
// The only LCD entry point is called AFTER HTTP service returns, from loop().
#include <display/ArtworkPilot.h>
#include <font/glcdfont.h>
namespace {
class ArtworkLcd final : public ArtworkPilot::Canvas {
public:
    void fill(int x, int y, int w, int h, uint16_t color) override {
        DisplayManager::getGfx()->fillRect(x, y, w, h, color);
    }
    void text(int x, int y, const char* s, uint16_t color, uint8_t size) override {
        Arduino_GFX* gfx = DisplayManager::getGfx();
        gfx->setFont(nullptr); // pinned classic 6x8 font, identical to preview
        gfx->setTextSize(size);
        gfx->setTextWrap(false);
        gfx->setTextColor(color);
        gfx->setCursor(x, y);
        gfx->print(s);
    }
    void row(int x, int y, uint16_t* pixels, int count, int repeats) override {
        // Arduino_TFT's RAM overload -> HWSPI::writePixels sends MSB first.
        // Renderer decoded RGB565LE into native words; no reinterpret cast.
        for (int i = 0; i < repeats; ++i)
            DisplayManager::getGfx()->draw16bitRGBBitmap(x, y + i, pixels, count, 1);
    }
    uint8_t glyphColumn(uint8_t ascii, unsigned column) override {
        return pgm_read_byte(&font[ascii*5+column]);
    }
};
static ArtworkLcd artworkLcd;
static ArtworkPilot::Renderer artworkRenderer;
// Numeric-only native timing counters; actual device measurements remain pending.
struct ArtworkTiming { uint32_t lastUs = 0, maxUs = 0, slices = 0; };
static volatile ArtworkTiming artworkTiming;
static bool artworkMetricsFirst = true;
}
void artworkPilotAfterHttp() {
    const uint32_t now = millis();
    const bool old = FslessMetrics::stale(); // unchanged six-second freshness
    if (artworkMetricsFirst ||
        ((telemetryNeedsRedraw || old != stalePreviously) && uint32_t(now-lastDrawMs) >= 250)) {
        const FslessMetrics::Snapshot s = FslessMetrics::snapshot();
        artworkRenderer.setMetrics({s.cpu, s.gpu, s.memoryGb, s.memoryTotalGb,
                                    s.gpuTempC, s.gpuAvailable, old});
        artworkMetricsFirst = false;
        telemetryNeedsRedraw = false;
        stalePreviously = old;
        lastDrawMs = now;
    }
    // No saved image pointer; cooperative single-thread loop cannot service a
    // replacement while this synchronous borrow is in progress. GFX's SDK
    // yield does not call this loop's HTTP owner or mutate receiver ownership.
    const uint32_t before = micros();
    // Clock/weather providers deliberately absent. Invalid defaults render
    // an honest unsynchronized state. No preview fixtures enter this graph.
    // Default policy keeps PAUSED; a later owner choice can call setPolicy().
    if (artworkRenderer.step(artworkLcd, m7Receiver.sink.borrow(), now)) {
        artworkTiming.lastUs = uint32_t(micros()-before);
        if (artworkTiming.lastUs > artworkTiming.maxUs) artworkTiming.maxUs = artworkTiming.lastUs;
        ++artworkTiming.slices;
    }
}
