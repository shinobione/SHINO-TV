"""Pure local mocks; never connect to a SmallTV or read owner credentials."""
import contextlib, io, unittest
from unittest.mock import patch
import provision_home_wifi as wifi
import hashlib,json
from email.message import Message
from urllib.request import BaseHandler,build_opener,ProxyHandler,HTTPPasswordMgrWithDefaultRealm,parse_http_list,parse_keqv_list
from urllib.response import addinfourl
from shino_link import LinkEngine
from test_shino_link import SAMPLE
from push_fsless_metrics import SendStatus

class ProvisionTests(unittest.TestCase):
    def test_real_urllib_digest_is_sent_before_password_body(self):
        class Transport(BaseHandler):
            handler_order=400
            anonymous_posts=0
            def http_open(self,request):
                auth=request.get_header('Authorization');headers=Message()
                if not auth:
                    if request.get_method()=='POST':self.anonymous_posts+=1
                    headers['WWW-Authenticate']='Digest realm="SHINO-FirstBoot", nonce="fixture", qop="auth", opaque="test"'
                    code,body=401,b''
                else:
                    f=parse_keqv_list(parse_http_list(auth[7:]))
                    md5=lambda s:hashlib.md5(s.encode()).hexdigest()
                    expected=md5(':'.join((md5('lab:SHINO-FirstBoot:fixture-password'),'fixture',f['nc'],f['cnonce'],'auth',md5(request.get_method()+':'+request.selector))))
                    if f['response']!=expected:raise AssertionError('Digest method/URI mismatch')
                    code=200
                    body=json.dumps({'intent':'a'*32} if request.get_method()=='GET' else {'saved':True,'readback_verified':True}).encode()
                result=addinfourl(io.BytesIO(body),headers,request.full_url,code);result.msg='fixture';return result
        root='http://192.168.4.1'+wifi.BASE
        manager=HTTPPasswordMgrWithDefaultRealm();manager.add_password('SHINO-FirstBoot',root,'lab','fixture-password')
        transport=Transport();opener=build_opener(ProxyHandler({}),wifi.NoRedirect(),wifi.WifiDigest(manager,root),transport)
        wifi.provision(opener,wifi.encode_change('lab','fixture1'))
        self.assertEqual(transport.anonymous_posts,0)

    def test_public_fixture_protocol_and_rejections(self):
        b=wifi.encode_change('lab','fixture1')
        self.assertEqual(b,bytearray(b'C\x03\x08labfixture1'))
        for name,password in [('', 'fixture1'),('s'*33,'fixture1'),('lab','short'),('lab','g'*64),('lab','x\n'*5),('unicode\u00e9','fixture1')]:
            with self.assertRaises(wifi.ProvisionError):wifi.encode_change(name,password)
        self.assertEqual(len(wifi.encode_change('s'*32,'a'*64)),99)

    def test_once_verified_and_payload_wiped(self):
        payload=wifi.encode_change('lab','fixture1')
        with patch.object(wifi,'exchange',side_effect=[{'intent':'a'*32},{'saved':True,'readback_verified':True}]) as send:
            wifi.provision(object(),payload)
        self.assertEqual(send.call_count,2)
        self.assertFalse(any(payload))

    def test_no_automatic_retry_on_lost_ack_and_wipe(self):
        payload=wifi.encode_change('lab','fixture1')
        with patch.object(wifi,'exchange',side_effect=[{'intent':'a'*32},wifi.ProvisionError('lost')]) as send:
            with self.assertRaises(wifi.ProvisionError):wifi.provision(object(),payload)
        self.assertEqual(send.call_count,2);self.assertFalse(any(payload))

    def test_redirected_input_never_prompts_or_connects(self):
        with patch.object(wifi.sys.stdin,'isatty',return_value=False),patch.object(wifi,'opener_for') as opener,patch.object(wifi.getpass,'getpass') as prompt,contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(wifi.main(['--change','--credentials-file','private-placeholder.txt']),1)
        opener.assert_not_called();prompt.assert_not_called()

    def test_live_retarget_preserves_single_engine_and_refreshes_digest(self):
        sent=[]
        engine=LinkEngine('192.168.4.1',object(),lambda:SAMPLE,
            sender=lambda h,o,s,timeout: sent.append(h) or SendStatus.ACCEPTED,
            opener_factory=lambda:object())
        engine.step(0);engine.retarget('192.168.1.12');engine.step(1)
        self.assertEqual(sent,['192.168.4.1','192.168.1.12']);self.assertEqual(engine.accepted,2)
        self.assertEqual(engine.generation,2)
        engine.retarget('192.168.4.1');engine.step(2)
        self.assertEqual(sent[-1],'192.168.4.1')
        with self.assertRaises(ValueError):engine.retarget('8.8.8.8')
        self.assertEqual(engine.host,'192.168.4.1')

if __name__=='__main__':unittest.main()
