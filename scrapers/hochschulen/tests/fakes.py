"""Offline network for resolver tests: URL -> (status, html)."""

from registry.enrichment.website_resolver import FetchResult, WebsiteResolver


class FakeResolver(WebsiteResolver):
    def __init__(self, pages, redirects=None):
        super().__init__(known_cities=frozenset({"hamburg"}))
        self.pages = pages
        self.redirects = redirects or {}
        self.hosts = {url.split("/")[2] for url in pages} | {
            url.split("/")[2] for url in self.redirects
        }

    def host_exists(self, host):
        return host in self.hosts

    def fetch(self, url, verify=True):
        final = self.redirects.get(url, url)
        if final not in self.pages:
            return FetchResult(url, error="ConnectionError")
        status, html = self.pages[final]
        return FetchResult(url, final_url=final, status=status, html=html)
