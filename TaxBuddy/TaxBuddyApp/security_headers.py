"""
TaxBuddyApp/security_headers.py
Adds the headers the GEO/SEO checker asked for, without breaking ads or scripts.

settings MIDDLEWARE (production): add these two lines right after
'django.middleware.security.SecurityMiddleware':
    'django.middleware.http.ConditionalGetMiddleware',   # ETag -> cheap re-crawls (304)
    'TaxBuddyApp.security_headers.SecurityHeadersMiddleware',
"""

# Safe policy: does NOT restrict scripts/styles/images (AdSense, GA, CDNs keep working).
# It only blocks plugins, base-tag hijacking and framing of the site by other domains,
# and upgrades any http:// resource to https://.
CSP = "upgrade-insecure-requests; object-src 'none'; base-uri 'self'; frame-ancestors 'self'"

PERMISSIONS = "camera=(), microphone=(), geolocation=(), payment=(), usb=()"


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.headers.setdefault("Content-Security-Policy", CSP)
        response.headers.setdefault("Permissions-Policy", PERMISSIONS)
        ctype = response.headers.get("Content-Type", "")
        if ctype.startswith("text/html") and "Cache-Control" not in response.headers:
            # browsers/crawlers may keep the page but must re-check it (ETag makes that a 304)
            response.headers["Cache-Control"] = "no-cache"
        return response
