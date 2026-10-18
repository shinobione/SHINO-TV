"""Exact protocol class excerpt; no provisioning/collection executable."""
from urllib.request import HTTPDigestAuthHandler,parse_http_list,parse_keqv_list
class WifiDigest(HTTPDigestAuthHandler):
    """Use the intent GET's real challenge before sending any password body.

    Pre-body refusal may reset a TCP peer which already sent an unauthorized
    body. Send Digest preemptively after the authenticated intent exchange.
    """
    def __init__(self,manager,root):
        super().__init__(manager);self.challenge=None;self.root=root
    def http_error_401(self,req,fp,code,msg,headers):
        value=headers.get('WWW-Authenticate','')
        if value.startswith('Digest '):
            self.challenge=parse_keqv_list(parse_http_list(value[7:]))
        return super().http_error_401(req,fp,code,msg,headers)
    def http_request(self,req):
        if self.challenge and req.full_url.startswith(self.root) and not req.has_header('Authorization'):
            auth=self.get_authorization(req,self.challenge)
            if auth: req.add_unredirected_header('Authorization','Digest '+auth)
        return req
