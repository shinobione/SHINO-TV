"""Finite research controller core. Injected I/O; never contacts a device itself.

One scope-bound Digest context, serial controls and a peer-aware quiet slot.
Only explicit 401 may repeat a control; 200, malformed success and uncertain
transport never repeat it. Cookie observation has no access to this context.
"""
import json
import threading
import unittest
from urllib.request import parse_http_list, parse_keqv_list


class ControlStop(RuntimeError):
    """Only fixed sanitized codes may reach public diagnostics."""


class PeerSlot:
    def __init__(self, snapshot, now, sleep, log=lambda *a: None):
        self.snapshot, self.now, self.sleep, self.log = snapshot, now, sleep, log

    def wait(self, deadline):
        start = self.now()
        bound = min(deadline, start + 1.25)
        while self.now() < bound:
            peer = self.snapshot()
            due = peer['completed_monotonic'] + peer['retry_seconds']
            # An ordinary protected exchange takes <180 ms on retained traces.
            # Do not enter just before or during the existing sender's request.
            if self.now() < due - .18:
                if self.now() > start:
                    self.log('peer slot wait', {'milliseconds': round((self.now()-start)*1000, 3)})
                return
            self.sleep(min(.02, max(0, bound-self.now())))
        raise ControlStop('PEER_SLOT_BOUND')


class DigestControls:
    REQUEST_LIMIT = 3  # Lower than the previous four; no retry-limit inflation.
    ENDPOINTS = ('/', '/api/v1/bridge/m8', '/api/v1/bridge/status',
                 '/api/v1/bridge/factory-return')

    def __init__(self, wire, authorize, slot, now, log=lambda *a: None):
        self._wire, self._authorize, self._slot = wire, authorize, slot
        self._now, self._log = now, log
        self._challenge = None
        self._lock = threading.Lock()
        self.requests = self.rejections = self.successes = 0

    def get(self, path, deadline=None):
        if not path.startswith('/') or path.startswith('//') or path.split('?')[0] not in self.ENDPOINTS:
            raise ControlStop('ENDPOINT_SCOPE')
        if not self._lock.acquire(blocking=False):
            raise ControlStop('PARALLEL_PROTECTED_CONTROL')
        try:
            deadline = self._now()+3 if deadline is None else deadline
            for _ in range(self.REQUEST_LIMIT):
                self._slot.wait(deadline)
                remaining = deadline-self._now()
                if remaining <= .05:
                    raise ControlStop('CONTROL_DEADLINE')
                authorization = None
                if self._challenge is not None:
                    try:
                        authorization = self._authorize(path, self._challenge)
                    except Exception:
                        raise ControlStop('DIGEST_CONSTRUCTION') from None
                    if not authorization:
                        raise ControlStop('DIGEST_CONSTRUCTION')
                self.requests += 1
                try:
                    status, raw, challenge = self._wire(path, authorization, min(3, remaining))
                except Exception:
                    raise ControlStop('CONTROL_TRANSPORT_UNCERTAIN') from None
                self._log('serial protected HTTP', {'endpoint': path.split('?')[0],
                    'status': status, 'preemptive': authorization is not None,
                    'request_number': self.requests})
                if status == 200:
                    self.successes += 1
                    # Even malformed success cannot justify repeating an action.
                    return raw
                if status != 401:
                    raise ControlStop('CONTROL_HTTP_'+str(status))
                self.rejections += 1
                try:
                    if not challenge or not challenge.lower().startswith('digest '):
                        raise ValueError()
                    parsed = parse_keqv_list(parse_http_list(challenge[7:]))
                    if parsed.get('realm') != 'SHINO-FirstBoot' or not parsed.get('nonce') or not parsed.get('opaque') or parsed.get('qop') != 'auth':
                        raise ValueError()
                except Exception:
                    raise ControlStop('DIGEST_CHALLENGE_INVALID') from None
                self._challenge = parsed
                # Next iteration waits for a quiet sender slot, rather than
                # racing its in-flight auth exchange with an immediate retry.
            raise ControlStop('CONTROL_HTTP_401_BOUND')
        finally:
            self._lock.release()


class ControllerTests(unittest.TestCase):
    def setup_controller(self, statuses=None, rotation=False):
        clock=[0.0]; peer=[{'completed_monotonic':0.0,'retry_seconds':2.0}]
        logs=[]; received=[]; calls=[]; mutations=[]; nonce=[1]
        def sleep(seconds):
            clock[0]+=seconds
            if clock[0]>=2.1 and peer[0]['completed_monotonic']==0:
                nonce[0]+=1  # Existing sender completed its independent exchange.
                peer[0]={'completed_monotonic':clock[0],'retry_seconds':2.0}
        def challenge():
            return 'Digest realm="SHINO-FirstBoot", qop="auth", nonce="n'+str(nonce[0])+'", opaque="o'+str(nonce[0])+'"'
        def authorize(path,c): return c['nonce']
        statuses=iter(statuses) if statuses is not None else None
        def wire(path,auth,timeout):
            calls.append(path);received.append(auth)
            status=next(statuses) if statuses is not None else (200 if auth=='n'+str(nonce[0]) else 401)
            if status==401:
                nonce[0]+=1
                result=(401,b'',challenge())
                if rotation and len(calls)==1:clock[0]=2.0
                return result
            if status==200:mutations.append(path)
            return status,b'{"action_ok":true}',None
        slot=PeerSlot(lambda:peer[0],lambda:clock[0],sleep,lambda *a:logs.append(a))
        ctx=DigestControls(wire,authorize,slot,lambda:clock[0],lambda *a:logs.append(a))
        return ctx,clock,calls,received,mutations,logs

    def test_bootstrap_then_preemptive_same_context(self):
        ctx,_,calls,auth,mutations,_=self.setup_controller()
        ctx.get('/');ctx.get('/api/v1/bridge/m8?action=issue&nonce=synthetic')
        self.assertEqual(len(calls),3);self.assertIsNone(auth[0]);self.assertTrue(all(auth[1:]))
        self.assertEqual(len(mutations),2)

    def test_concurrent_rotation_yields_to_peer_then_recovers(self):
        ctx,clock,calls,auth,mutations,logs=self.setup_controller(rotation=True)
        ctx.get('/api/v1/bridge/m8?action=issue&nonce=synthetic')
        self.assertEqual(len(calls),3);self.assertEqual(len(mutations),1)
        self.assertGreaterEqual(clock[0],2.1);self.assertTrue(any(x[0]=='peer slot wait' for x in logs))
        self.assertTrue(all(auth[1:]))

    def test_retained_immediate_retry_storm_fails_peer_yield_recovers(self):
        def model(coordinate):
            clock=[2.0];nonce=[1];finished=[False]
            peer=[{'completed_monotonic':0.0,'retry_seconds':2.0}]
            def sleep(seconds):
                clock[0]+=seconds
                if clock[0]>=2.1:
                    finished[0]=True;nonce[0]+=1
                    peer[0]={'completed_monotonic':clock[0],'retry_seconds':2.0}
            def wire(path,value,timeout):
                # A queued sender rejection changes the sole server challenge
                # between receipt of the reader challenge and its next retry.
                if not finished[0]:nonce[0]+=1
                if value=='n'+str(nonce[0]):return 200,b'accepted',None
                nonce[0]+=1
                return 401,b'',('Digest realm="SHINO-FirstBoot", qop="auth", nonce="n'+str(nonce[0])+'", opaque="o"')
            class Immediate:
                def wait(self,deadline):pass
            slot=PeerSlot(lambda:peer[0],lambda:clock[0],sleep) if coordinate else Immediate()
            ctx=DigestControls(wire,lambda p,c:c['nonce'],slot,lambda:clock[0])
            ctx._challenge={'nonce':'n1'}
            return ctx
        naive=model(False)
        with self.assertRaisesRegex(ControlStop,'401_BOUND'):naive.get('/api/v1/bridge/m8')
        self.assertEqual(naive.rejections,3)
        corrected=model(True);self.assertEqual(corrected.get('/api/v1/bridge/m8'),b'accepted')
        self.assertEqual(corrected.rejections,1);self.assertEqual(corrected.requests,2)

    def test_repeated_rotation_stops_at_three(self):
        ctx,_,calls,_,mutations,_=self.setup_controller([401,401,401,200])
        with self.assertRaisesRegex(ControlStop,'401_BOUND'):ctx.get('/api/v1/bridge/m8')
        self.assertEqual(len(calls),3);self.assertEqual(mutations,[])

    def test_successful_state_change_never_repeated(self):
        ctx,_,calls,_,mutations,_=self.setup_controller([200])
        ctx.get('/api/v1/bridge/m8?action=reset')
        self.assertEqual(len(calls),1);self.assertEqual(len(mutations),1)

    def test_malformed_success_is_not_repeated(self):
        ctx,*_=self.setup_controller()
        ctx._wire=lambda *a:(200,b'invalid json',None)
        with self.assertRaises(ValueError):json.loads(ctx.get('/api/v1/bridge/m8?action=reset'))
        self.assertEqual(ctx.requests,1)

    def test_real_digest_response_matches_pinned_md5_query_profile(self):
        import hashlib
        from urllib.request import Request,HTTPDigestAuthHandler,HTTPPasswordMgrWithDefaultRealm
        origin='http://192.168.4.1';realm='SHINO-FirstBoot';user='test-user';password='test-password'
        store=HTTPPasswordMgrWithDefaultRealm();store.add_password(realm,origin+'/',user,password)
        auth=HTTPDigestAuthHandler(store);paths=[];accepted=[]
        challenge='Digest realm="SHINO-FirstBoot", qop="auth", nonce="offline-secret-n", opaque="offline-secret-o"'
        H=lambda v:hashlib.md5(v.encode()).hexdigest()
        def wire(path,value,timeout):
            paths.append(path)
            if value is None:return 401,b'',challenge
            c=parse_keqv_list(parse_http_list(value))
            self.assertEqual(c['uri'],path)
            expected=H(H(user+':'+realm+':'+password)+':'+c['nonce']+':'+c['nc']+':'+c['cnonce']+':auth:'+H('GET:'+path))
            self.assertEqual(c['response'],expected);accepted.append(path)
            return 200,b'{"action_ok":true}',None
        class Quiet:
            def wait(self,deadline):pass
        ctx=DigestControls(wire,lambda path,c:auth.get_authorization(Request(origin+path),c),Quiet(),lambda:0)
        ctx.get('/api/v1/bridge/m8?action=issue&nonce=proof-A')
        ctx.get('/api/v1/bridge/m8?action=issue&nonce=proof-B')
        self.assertEqual(ctx.requests,3);self.assertEqual(len(accepted),2)

    def test_authorization_failure_is_sanitized(self):
        ctx,*_=self.setup_controller()
        ctx.get('/')
        def broken(*a):raise ValueError('password-secret nonce-secret')
        ctx._authorize=broken
        with self.assertRaisesRegex(ControlStop,'^DIGEST_CONSTRUCTION$'):ctx.get('/api/v1/bridge/m8')

    def test_uncertain_transport_no_retry_no_exception_secrets(self):
        ctx,_,_,_,_,logs=self.setup_controller()
        def wire(*a): raise TimeoutError('password-secret Authorization nonce-secret C:/private/key')
        ctx._wire=wire
        with self.assertRaisesRegex(ControlStop,'^CONTROL_TRANSPORT_UNCERTAIN$'):ctx.get('/api/v1/bridge/m8')
        self.assertEqual(ctx.requests,1);self.assertNotIn('password-secret',str(logs))

    def test_scope_and_no_parallel_controls(self):
        ctx,*_=self.setup_controller()
        for path in ('http://other/m8','//other/m8','/update','/api/v1/bridge/m8/other'):
            with self.assertRaisesRegex(ControlStop,'ENDPOINT_SCOPE'):ctx.get(path)
        ctx._lock.acquire()
        try:
            with self.assertRaisesRegex(ControlStop,'PARALLEL'):ctx.get('/api/v1/bridge/m8')
        finally:ctx._lock.release()
        self.assertEqual(ctx.requests,0)

    def test_log_is_sanitized(self):
        ctx,_,_,_,_,logs=self.setup_controller()
        ctx.get('/api/v1/bridge/m8?action=issue&nonce=private-proof-secret')
        rendered=json.dumps(logs)
        for secret in ('private-proof-secret','n2','o2','Authorization','password'):
            self.assertNotIn(secret,rendered)

    def test_peer_slot_is_bounded_and_sender_not_changed(self):
        clock=[2.0];peer={'completed_monotonic':0.0,'retry_seconds':2.0}
        def sleep(seconds):clock[0]+=seconds
        slot=PeerSlot(lambda:dict(peer),lambda:clock[0],sleep)
        with self.assertRaisesRegex(ControlStop,'PEER_SLOT_BOUND'):slot.wait(10)
        self.assertLessEqual(clock[0],3.251);self.assertEqual(peer['retry_seconds'],2.0)

    def test_403_and_invalid_challenge_do_not_storm(self):
        ctx,*_=self.setup_controller([403])
        with self.assertRaisesRegex(ControlStop,'HTTP_403'):ctx.get('/api/v1/bridge/m8')
        self.assertEqual(ctx.requests,1)
        ctx._wire=lambda *a:(401,b'',None)
        with self.assertRaisesRegex(ControlStop,'CHALLENGE_INVALID'):ctx.get('/api/v1/bridge/m8')


def report():
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(ControllerTests)
    result=unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():raise SystemExit(1)
    return {'tests':result.testsRun,'failures':0,'request_limit':3,'peer_slot_bound_seconds':1.25,
            'device_contacts':0,'device_writes':0,'credentials_or_nonce_values_logged':False}


if __name__=='__main__':print(json.dumps(report(),indent=2))
