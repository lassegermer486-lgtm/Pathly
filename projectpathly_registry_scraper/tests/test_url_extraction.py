"""
Website extraction from state sources. The HTML below is trimmed from
the live pages (September/October 2026).
"""

from bs4 import BeautifulSoup

from registry.adapters.bb import BrandenburgAdapter
from registry.adapters.be import BerlinAdapter
from registry.adapters.ni import NiedersachsenAdapter
from registry.adapters.sl import SaarlandAdapter
from registry.adapters.th import ThueringenAdapter


NI_PROFILE = """
<div class="kachel__content hochschul-detail__kachel-content">
  <div class="kachel__titel">Kurzinfo</div>
  <div class="kachel__text">öffentlich-rechtlich</div>
</div>
<div class="kachel__content hochschul-detail__kachel-content">
  <div class="kachel__titel">Hochschule</div>
  <h3 class="kachel__headline"><span class="kachel__headline-text">
    <a class="kachel__headline-text link--external"
       href="https://www.tu-braunschweig.de/">Technische Universität Braunschweig</a>
  </span></h3>
  <div class="kachel__text hochschul-detail__text">Universitätsplatz 2<br/>38106 Braunschweig</div>
</div>
<div class="kachel__content hochschul-detail__kachel-content">
  <div class="kachel__titel hochschul-detail__kachel-titel">Termine</div>
  <a class="list__listitem-text--link-external"
     href="https://www.tu-braunschweig.de/zsb/termine">Langer Abend</a>
</div>
"""


def test_ni_profile_website():
    assert (
        NiedersachsenAdapter.extract_profile_website(NI_PROFILE)
        == "https://www.tu-braunschweig.de/"
    )


def bb_contact(body):
    return f"""
    <div class="small-12 medium-3 columns trennung">
      <p>Die THB bildet derzeit etwa 2.600 Studierende aus.
         <a href="https://www.facebook.com/MWFKBB/">fb</a></p>
    </div>
    <div class="small-12 medium-3 columns trennung">{body}</div>
    """


def test_bb_profile_website_link():
    html = bb_contact(
        'BTU Cottbus-Senftenberg<br/>Platz der Deutschen Einheit 1<br/>'
        '03046 Cottbus<br/><a href="mailto:studium@b-tu.de">E-Mail</a>'
        '<a href="https://mwfk.brandenburg.de/kontakt">Kontakt</a>'
        '<a href="https://www.b-tu.de/">www.b-tu.de</a>'
    )
    assert BrandenburgAdapter.extract_profile_website(html) == "https://www.b-tu.de/"


def test_bb_profile_website_plain_text():
    html = bb_contact(
        "Technische Hochschule Brandenburg (THB)<br/>Magdeburger Straße 50<br/>"
        "14770 Brandenburg an der Havel<br/>www.th-brandenburg.de<br/>"
        "info@th-brandenburg.de"
    )
    assert BrandenburgAdapter.extract_profile_website(html) == "www.th-brandenburg.de"


def test_bb_profile_without_contact_block():
    assert BrandenburgAdapter.extract_profile_website(bb_contact("Keine Adresse")) is None


TH_OVERVIEW = """
<nav><a href="/hochschulen-in-thueringen/erfurt/">Erfurt</a></nav>
<main id="contentMain">
  <div class="ct21-card"><a href="/hochschulen-in-thueringen/universitaet-erfurt/">
    Universität Erfurt <span>Bild: Hamish J. Appleby</span></a></div>
  <div class="ct21-atts"><ul><li>
    <a href="/hochschulen-in-thueringen/srh-hochschule-fuer-gesundheit-privat/">SRH University (privat)</a>
  </li></ul></div>
  <a href="/hochschulen-in-thueringen/">Wo studieren?</a>
</main>
"""

TH_PROFILE = """
<ul class="links">
  <li><a href="https://www.srh-university.de/de/?utm_source=x">www.srh-university.de</a></li>
  <li><ul class="social"><li><a href="https://www.youtube.com/user/SRH">YouTube</a></li></ul></li>
</ul>
"""


def test_th_portal_profiles_skip_navigation_and_credits():
    profiles = ThueringenAdapter.extract_portal_profiles(
        TH_OVERVIEW,
        "https://campus-thueringen.de/hochschulen-in-thueringen/",
    )
    assert profiles == {
        "Universität Erfurt":
            "https://campus-thueringen.de/hochschulen-in-thueringen/universitaet-erfurt/",
        "SRH University (privat)":
            "https://campus-thueringen.de/hochschulen-in-thueringen/srh-hochschule-fuer-gesundheit-privat/",
    }


def test_th_profile_website():
    assert (
        ThueringenAdapter.extract_profile_website(TH_PROFILE)
        == "https://www.srh-university.de/de/?utm_source=x"
    )


SL_MINISTRY = """
<main class="main">
  <p><a class="external" href="https://www.uni-saarland.de/start/">Universität des Saarlandes</a></p>
  <p><a class="external" href="http://www.hfm.saarland.de/">Hochschule für Musik Saar</a></p>
  <p><a class="external" href="https://www.saarland.de/mfw/">Ministerium</a></p>
</main>
<footer><a class="external" href="https://www.stw-saarland.de/">Studierendenwerk</a></footer>
"""


def test_sl_ministry_websites():
    assert SaarlandAdapter.extract_ministry_websites(SL_MINISTRY) == {
        "Universität des Saarlandes": "https://www.uni-saarland.de/start/",
        "Hochschule für Musik Saar": "http://www.hfm.saarland.de/",
    }


BE_PAGE = """
<h2>Universität der Künste Berlin (UdK)</h2>
<p>Gemeinsam mit der HfM unterhält sie das
   <a href="http://www.jazz-institut-berlin.de/">Jazz-Institut Berlin</a>.</p>
<p><a href="https://www.berlin.de/stadtplan/">Stadtplan</a></p>
<p><a href="http://www.udk-berlin.de">Universität der Künste Berlin:</a>
   Einsteinufer 43 – 53, 10587 Berlin</p>
<h2>Freie Universität Berlin</h2>
<p><a href="http://www.fu-berlin.de">Freie Universität Berlin:</a> Kaiserswerther Straße 16/18</p>
<h2>Senatsverwaltung</h2>
"""


def test_be_prefers_link_named_like_the_institution():
    soup = BeautifulSoup(BE_PAGE, "html.parser")
    adapter = BerlinAdapter("DE-BE", {})
    udk, fu = soup.find_all("h2")[:2]

    assert adapter._find_external_link_after_heading(udk) == "http://www.udk-berlin.de"
    # fu-berlin.de must not be mistaken for a berlin.de link.
    assert adapter._find_external_link_after_heading(fu) == "http://www.fu-berlin.de"
