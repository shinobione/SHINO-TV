"""Exact protocol class excerpt; no provisioning/collection executable."""
from urllib.request import HTTPRedirectHandler
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None
