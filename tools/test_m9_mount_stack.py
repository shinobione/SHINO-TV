"""Actual validator ownership/no-allocation and pinned bounded profile-2 changes."""
from pathlib import Path
import tempfile
import unittest
from m9_mount_stack import ROOT, CHANGED, source_audit, frame_gate
import test_m9_mount_probe as probe_tests


class SourceTests(unittest.TestCase):
    def test_h_resource_gate_requires_proof_for_inlined_payload(self):
        from m9_mount_probe import resources
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);su=root/'M9LittleFsMountProbe.cpp.su'
            su.write_text('probe.cpp:1:1:void M9LittleFsMountProbe::begin()\t272\tstatic\nprobe.cpp:2:1:bool M9LittleFsMountProbe::json(char*, size_t)\t80\tstatic\n')
            sections=root/'sections.txt';sections.write_text('.data 0 0\n.rodata 0 0\n.bss 41060 0\n.noinit 56 0\n.text 0 0\n.text1 0 0\n.irom0.text 403299 0\n')
            symbols=root/'symbols.txt';symbols.write_text('40200000 000005ea T M9LittleFsMountProbe::begin()\n3fff0000 00000198 b M9LittleFsMountProbe::(anonymous namespace)::payloadWorkspace\n')
            with self.assertRaises(AssertionError):resources(sections,su)
            self.assertEqual(resources(sections,su,symbols)['probe_stack_frames_bytes']['checkPayloads()'],'INLINED_IN_BEGIN')
            symbols.write_text(symbols.read_text()+'40201000 00000010 T X::checkPayloads()\n')
            with self.assertRaises(AssertionError):resources(sections,su,symbols)

    def test_only_two_authorized_firmware_sources_changed(self):
        audit=source_audit()
        self.assertEqual(audit['firmware_files_checked'],103)
        self.assertEqual(audit['firmware_files_unchanged'],101)
        self.assertEqual(set(audit['firmware_mount_stack_changes']),CHANGED)
        self.assertEqual(audit['installed_candidate_role'],'HISTORICAL_J_PREDECESSOR_ONLY')

    def test_no_scratch_allocation_or_writer_and_profile2_single_instance(self):
        header=(ROOT/'firmware/include/boot/M9ProbeStream.h').read_text(encoding='utf-8')
        for forbidden in ('new ', 'malloc(', 'String', 'LittleFS', 'flashWrite', 'flashErase'):
            self.assertNotIn(forbidden,header)
        probe=(ROOT/'firmware/src/boot/M9LittleFsMountProbe.cpp').read_text(encoding='utf-8')
        self.assertEqual(probe.count('M9ProbeStream::Workspace<Sha256> payloadWorkspace;'),1)
        self.assertLess(probe.index('#if SHINO_BOOT_PROFILE == 2'),probe.index('payloadWorkspace;'))
        self.assertNotIn('Sha256 hash;',probe)

    def test_inlined_frames_require_linked_absence_and_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);su=root/'M9LittleFsMountProbe.cpp.su';symbols=root/'symbols.txt'
            su.write_text('probe.cpp:1:1:void M9LittleFsMountProbe::begin()\t272\tstatic\n')
            base='40200000 000005ea T M9LittleFsMountProbe::begin()\n3fff0000 00000198 b M9LittleFsMountProbe::(anonymous namespace)::payloadWorkspace\n'
            symbols.write_text(base)
            self.assertEqual(frame_gate(root,symbols)['linked_mount_frames_reduction_bytes'],576)
            for mutation in (base+'40200000 00000010 T X::checkPayloads()\n',base.replace('00000198','00000201')):
                symbols.write_text(mutation)
                with self.assertRaises(AssertionError):frame_gate(root,symbols)
            symbols.write_text(base)
            su.write_text('probe.cpp:1:1:void M9LittleFsMountProbe::begin()\t480\tstatic\n')
            with self.assertRaises(AssertionError):frame_gate(root,symbols)


class WorkspaceTests(unittest.TestCase):
    def test_actual_workspace_reentry_early_failure_and_no_heap(self):
        source=r'''
#include "boot/M9ProbeStream.h"
#include <cassert>
#include <cstdlib>
#include <new>
static unsigned allocations=0;
void* operator new(std::size_t size) { ++allocations; if(void* p=std::malloc(size))return p;throw std::bad_alloc(); }
void operator delete(void* p) noexcept { std::free(p); }
void operator delete(void* p,std::size_t) noexcept { std::free(p); }
struct Reader {
    uint8_t bytes[4]={0,1,2,3};size_t offset=0;unsigned reads=0;
    int read(uint8_t* out,size_t wanted) {
        assert(wanted<=256);++reads;
        if(offset==4)return 0;
        out[0]=bytes[offset++];return 1;
    }
    int read(){++reads;return offset==4?-1:bytes[offset++];}
};
struct Hash {
    uint8_t digest[32];size_t offset;
    void begin(){std::memset(digest,0,32);offset=0;}
    void update(const void* p,size_t n){auto bytes=static_cast<const uint8_t*>(p);for(size_t i=0;i<n;++i)digest[offset++%32]^=bytes[i];}
    void end(uint8_t* out){std::memcpy(out,digest,32);}
};
static M9ProbeStream::Workspace<Hash> validationWorkspace;
int main(){
    static_assert(sizeof(validationWorkspace.buffer)==256,"Read bound");
    static_assert(sizeof(validationWorkspace.actual)==32,"Digest bound");
    const uint8_t expected[32]={0,1,2,3};
    auto seed=[](uint32_t,const uint8_t*,size_t){return true;};
    const unsigned before=allocations;Reader outer,nested;uint32_t checked=0,nestedChecked=91;
    auto observer=[&](){
        assert(validationWorkspace.active);
        assert(!M9ProbeStream::validate(nested,4,expected,validationWorkspace,seed,[](){},nestedChecked));
        assert(validationWorkspace.active && nested.reads==0 && nestedChecked==91);
    };
    assert(M9ProbeStream::validate(outer,4,expected,validationWorkspace,seed,observer,checked));
    assert(!validationWorkspace.active && checked==4);
    Reader failure;checked=7;
    assert(!M9ProbeStream::validate(failure,4,expected,validationWorkspace,[](uint32_t,const uint8_t*,size_t){return false;},[](){},checked));
    assert(!validationWorkspace.active && checked==7);
    Reader retry;
    assert(M9ProbeStream::validate(retry,4,expected,validationWorkspace,seed,[](){},checked));
    assert(!validationWorkspace.active && checked==11 && allocations==before);
}
'''
        # Reuse compiler infrastructure only; no duplicate inherited test suite.
        compiler=probe_tests.CompiledTests('test_actual_stream_algorithm_fault_matrix')
        probe_tests.CompiledTests.setUpClass()
        with tempfile.TemporaryDirectory() as tmp:compiler.compile(source,Path(tmp))


if __name__=='__main__':unittest.main()
