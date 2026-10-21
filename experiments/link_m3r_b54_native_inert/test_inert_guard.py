"""Execute the actual SCons guard under a strict fake environment, no serial I/O."""
import hashlib, json, runpy, sys, tempfile, types, unittest
from pathlib import Path
from unittest.mock import patch

GUARD=Path(__file__).with_name('inert_guard.py')

class Env:
    def __init__(self,root,name): self.root=root;self.name=name;self.replaced={};self.appended={};self.actions=[]
    def subst(self,key): return {'$PIOENV':self.name,'$PROJECT_DIR':str(self.root),'$BUILD_DIR':str(self.root/'build')}[key]
    def Append(self,**kw): self.appended.update(kw)
    def Replace(self,**kw): self.replaced.update(kw)
    def AddPostAction(self,*args): self.actions.append(args)

class GuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        (self.root/'input').write_bytes(b'fixture')
        (self.root/'INERT_INPUTS.json').write_text(json.dumps({'input':hashlib.sha256(b'fixture').hexdigest()}))
    def load(self,targets=(),name='b54_inert_handoff'):
        env=Env(self.root,name);module=types.ModuleType('SCons.Script');module.Import=lambda *args:None;module.COMMAND_LINE_TARGETS=targets
        with patch.dict(sys.modules,{'SCons':types.ModuleType('SCons'),'SCons.Script':module}):
            result=runpy.run_path(str(GUARD),init_globals={'env':env})
        return env,result
    def test_both_environments(self):
        for name in ('b54_inert_base','b54_inert_handoff'):
            env,_=self.load(name=name);self.assertEqual(len(env.actions),1);self.assertIn('-include',env.appended['CXXFLAGS'])
    def test_unknown_environment(self):
        with self.assertRaisesRegex(RuntimeError,'Unknown'):self.load(name='release')
    def test_all_hardware_targets_refused(self):
        for target in ('upload','uploadfs','erase','program','buildfs','monitor','debug','test','custom-upload'):
            with self.subTest(target=target),self.assertRaisesRegex(RuntimeError,'prohibited'):self.load([target])
    def test_input_tamper(self):
        (self.root/'input').write_bytes(b'changed')
        with self.assertRaisesRegex(RuntimeError,'drift'):self.load()
    def test_missing_input(self):
        (self.root/'INERT_INPUTS.json').write_text('{"absent":"00"}')
        with self.assertRaises(FileNotFoundError):self.load()
    def test_uploader_callable_refused(self):
        env,_=self.load();self.assertEqual(env.replaced['UPLOAD_PORT'],'INERT_NO_PORT')
        with self.assertRaisesRegex(RuntimeError,'no physical uploader'):env.replaced['UPLOADCMD']()
    def test_actual_postaction_makes_nonbootable(self):
        env,m=self.load();(self.root/'build').mkdir();p=self.root/'build/firmware.bin';raw=b'\xe9'+b'fixture'*50;p.write_bytes(raw)
        m['make_unbootable'](None,None,env);r=json.loads(p.with_name('inert-bin.json').read_text())
        self.assertEqual(p.read_bytes(),b'\0'+raw[1:]);self.assertFalse(r['bootable']);self.assertEqual(r['bytes'],len(raw));self.assertEqual(r['inert_bin_sha256'],hashlib.sha256(p.read_bytes()).hexdigest());self.assertEqual(r['raw_source_bin_sha256'],hashlib.sha256(raw).hexdigest())
    def test_invalid_header_refused(self):
        env,m=self.load();(self.root/'build').mkdir();p=self.root/'build/firmware.bin';p.write_bytes(b'not ESP')
        with self.assertRaisesRegex(RuntimeError,'header'):m['make_unbootable'](None,None,env)
        self.assertEqual(p.read_bytes(),b'not ESP')

if __name__=='__main__':unittest.main(verbosity=2)
