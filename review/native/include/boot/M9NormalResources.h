// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include "boot/M9ResourceObserver.h"
namespace M9NormalResources {
using M9MountProbeResources::Heap;
using M9MountProbeResources::validHeap;
using M9MountProbeResources::validStack;
constexpr uint32_t HEAP_FLOOR = 20480, BLOCK_FLOOR = 16384, CONT_FLOOR = 2048;
constexpr uint8_t FRAG_CEILING = 25;
struct Observation {
    uint32_t setup_start = 0, setup_min = 0, fs_start = 0, fs_min = 0;
    uint32_t runtime_start = 0, runtime_min = 0, samples = 0, rejected = 0;
    Heap after_fs, after_setup, latest;
    uint32_t min_heap = 0, min_block = 0;
    uint8_t max_frag = 0;
    bool valid = false;
};
static_assert(sizeof(Observation) <= 96, "StageA scalar observer budget");
inline bool floors(const Observation& s) {
    return s.valid && s.samples > 0 && s.min_heap >= HEAP_FLOOR &&
        s.min_block >= BLOCK_FLOOR && s.max_frag <= FRAG_CEILING &&
        s.setup_min >= CONT_FLOOR && s.fs_min >= CONT_FLOOR && s.runtime_min >= CONT_FLOOR;
}
template<class Source> class Observer {
public:
    explicit Observer(Source& source) : source_(source) {}
    void beforeSetup() {
        if (phase_ != 0) return;
        reset(); state_.setup_start = start_; state_.setup_min = start_;
        observeHeap(state_.latest); phase_ = 1;
    }
    void beforeFs() {
        if (phase_ != 1) return;
        capture(state_.setup_min); reset();
        state_.fs_start = start_; state_.fs_min = start_; phase_ = 2;
    }
    void afterFs() {
        if (phase_ != 2) return;
        capture(state_.fs_min);
        if (state_.fs_min < state_.setup_min) state_.setup_min = state_.fs_min;
        observeHeap(state_.after_fs); reset(); phase_ = 3;
    }
    void afterSetup() {
        if (phase_ != 3) return;
        capture(state_.setup_min); observeHeap(state_.after_setup); reset();
        state_.runtime_start = start_; state_.runtime_min = start_;
        last_ = source_.now(); phase_ = 4; state_.valid = valid_;
    }
    void poll() {
        if (phase_ != 4) return;
        const uint32_t now = source_.now();
        if (static_cast<uint32_t>(now - last_) < 1000) return;
        last_ = now; // One attempt, no catch-up burst, even on rejection/wrap.
        Heap heap; source_.heap(heap);
        const uint32_t stack = source_.stack();
        if (!validHeap(heap) || !validStack(stack) || stack > state_.runtime_min) {
            reject(); return;
        }
        state_.latest = heap; minima(heap); state_.runtime_min = stack;
        if (state_.samples != UINT32_MAX) ++state_.samples;
        state_.valid = valid_;
    }
    const Observation& status() const { return state_; }
private:
    void reject() { valid_ = false; state_.valid = false;
        if (state_.rejected != UINT32_MAX) ++state_.rejected; }
    void reset() {
        source_.resetStack(); start_ = previous_ = source_.stack();
        if (!validStack(start_)) { start_ = previous_ = 0; reject(); }
    }
    void capture(uint32_t& minimum) {
        const uint32_t stack = source_.stack();
        if (!validStack(stack) || stack > previous_) { reject(); return; }
        previous_ = stack; if (stack < minimum) minimum = stack;
    }
    void minima(const Heap& heap) {
        if (state_.min_heap == 0 || heap.free < state_.min_heap) state_.min_heap = heap.free;
        if (state_.min_block == 0 || heap.largest < state_.min_block) state_.min_block = heap.largest;
        if (heap.fragmentation > state_.max_frag) state_.max_frag = heap.fragmentation;
    }
    void observeHeap(Heap& out) {
        Heap heap; source_.heap(heap);
        if (!validHeap(heap)) { reject(); return; }
        out = heap; minima(heap);
    }
    Source& source_; Observation state_;
    uint32_t start_ = 0, previous_ = 0, last_ = 0;
    uint8_t phase_ = 0; bool valid_ = true;
};
} // namespace M9NormalResources
