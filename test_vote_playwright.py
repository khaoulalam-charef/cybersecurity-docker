from playwright.sync_api import Page

VOTE_URL = "http://localhost:80"


def test_la_page_de_vote_se_charge(page: Page):
    """Vérifie que la page de vote s'affiche avec les deux boutons de choix.

    Équivalent Playwright du test Selenium test_la_page_de_vote_se_charge.
    """
    page.goto(VOTE_URL)
    assert "vs" in page.title().lower()

    bouton_a = page.locator("#a")
    bouton_b = page.locator("#b")
    assert bouton_a.is_visible()
    assert bouton_b.is_visible()


def test_voter_pour_a_est_pris_en_compte(page: Page):
    """Vérifie qu'un clic sur le bouton A enregistre bien le vote.

    Équivalent Playwright du test Selenium test_voter_pour_a_est_pris_en_compte.
    """
    page.goto(VOTE_URL)
    page.locator("#a").click()

    # Playwright attend automatiquement, pas besoin d'un WebDriverWait manuel :
    # is_disabled() réessaie tout seul jusqu'à ce que la condition soit vraie
    # (ou jusqu'au timeout par défaut de 5 secondes).
    bouton_a = page.locator("#a")
    assert bouton_a.is_disabled()