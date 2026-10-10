// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// Scalar-only observer, source injected for deterministic host qualification.
// Zero stack margin is retained as a real observation, never a passing floor.
#include <cstdint>
#include <climits>
namespace M9MountProbeResources {
struct Heap {
    uint32_t free = 0;
    uint32_t largest = 0;
    uint8_t fragmentation = 0;
};
struct Observation {
    uint32_t mount_phase_cont_stack_start = 0;
    uint32_t mount_phase_cont_stack_min_free = 0;
    Heap heap_after_probe;
    uint32_t runtime_cont_stack_start = 0;
    uint32_t runtime_min_cont_stack_free = 0;
    uint32_t resource_sample_count = 0;
    Heap latest;
    uint32_t lowest_observed_free_heap = 0;
    uint32_t lowest_observed_largest_free_block = 0;
    uint8_t highest_observed_fragmentation_percent = 0;
    uint32_t resource_rejected_sample_count = 0;
    bool resource_measurements_valid = false; // False until setup measurements complete.
};
static_assert(sizeof(Observation) <= 80, "Unreviewed scalar observer growth");
inline bool validHeap(const Heap& heap) {
    // Structural validity for the selected DRAM heap, NOT a physical safety floor.
    return heap.free > 0 && heap.free <= 81920 && heap.largest > 0 &&
           heap.largest <= heap.free && heap.fragmentation <= 100;
}
inline bool validStack(uint32_t bytes) { return bytes <= 4096 && bytes % 4 == 0; }
template<class Source> class Observer {
public:
    explicit Observer(Source& source) : source_(source) {}
    void beforeMount() {
        if (phase_ != Phase::Cold) return;
        source_.resetStack(); // Mount window, exactly once.
        const uint32_t stack = source_.stack();
        if (validStack(stack)) state_.mount_phase_cont_stack_start = stack;
        else reject();
        phase_ = Phase::Mount;
    }
    void afterMount() {
        if (phase_ != Phase::Mount) return;
        const uint32_t stack = source_.stack(); // First observation after probe returns.
        if (!validStack(stack) || stack > state_.mount_phase_cont_stack_start) reject();
        else state_.mount_phase_cont_stack_min_free = stack;
        Heap heap;
        source_.heap(heap);
        if (validHeap(heap)) state_.heap_after_probe = heap;
        else reject(); // Invalid data never enters latest/minimum counters.
        source_.resetStack(); // New runtime watermark, exactly once; never in poll().
        const uint32_t runtimeStack = source_.stack();
        if (validStack(runtimeStack)) state_.runtime_cont_stack_start = runtimeStack;
        else reject();
        state_.runtime_min_cont_stack_free = state_.runtime_cont_stack_start;
        lastAttemptMs_ = source_.now();
        phase_ = Phase::Runtime;
        state_.resource_measurements_valid = valid_;
    }
    void poll() {
        if (phase_ != Phase::Runtime) return;
        const uint32_t now = source_.now();
        if (static_cast<uint32_t>(now - lastAttemptMs_) < 1000) return;
        lastAttemptMs_ = now; // No catch-up burst, including rejected samples.
        Heap heap;
        source_.heap(heap);
        const uint32_t stack = source_.stack();
        if (!validHeap(heap) || !validStack(stack) ||
            stack > state_.runtime_cont_stack_start || stack > state_.runtime_min_cont_stack_free) {
            reject(); state_.resource_measurements_valid = false; return;
        }
        if (state_.resource_sample_count == 0) {
            state_.lowest_observed_free_heap = heap.free;
            state_.lowest_observed_largest_free_block = heap.largest;
            state_.highest_observed_fragmentation_percent = heap.fragmentation;
        } else {
            if (heap.free < state_.lowest_observed_free_heap)
                state_.lowest_observed_free_heap = heap.free;
            if (heap.largest < state_.lowest_observed_largest_free_block)
                state_.lowest_observed_largest_free_block = heap.largest;
            if (heap.fragmentation > state_.highest_observed_fragmentation_percent)
                state_.highest_observed_fragmentation_percent = heap.fragmentation;
        }
        state_.latest = heap;
        state_.runtime_min_cont_stack_free = stack;
        if (state_.resource_sample_count != UINT32_MAX) ++state_.resource_sample_count;
        state_.resource_measurements_valid = valid_; // Rejection latches invalid until a new boot.
    }
    const Observation& status() const { return state_; }
private:
    enum class Phase : uint8_t { Cold, Mount, Runtime };
    void reject() {
        valid_ = false;
        if (state_.resource_rejected_sample_count != UINT32_MAX)
            ++state_.resource_rejected_sample_count;
    }
    Source& source_;
    Observation state_;
    uint32_t lastAttemptMs_ = 0;
    Phase phase_ = Phase::Cold;
    bool valid_ = true;
};
} // namespace M9MountProbeResources
