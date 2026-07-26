"""
Tests automatisés Selenium pour l'application Docker Voting App.

Ces tests pilotent un vrai navigateur pour vérifier le comportement
fonctionnel de bout en bout : vote, mise à jour des résultats en temps réel.

Prérequis avant de lancer :
    1. Le projet doit tourner : docker compose up -d
    2. Installer les dépendances :  pip install -r requirements-test.txt
    3. Avoir Google Chrome installé sur la machine

Lancer les tests :
    pytest test_vote_automatise.py -v
"""

import time
import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

VOTE_URL = "http://localhost:80"
RESULT_URL = "http://localhost:81"


@pytest.fixture
def driver():
    """Crée une instance Chrome headless (sans fenêtre visible) pour chaque test."""
    options = Options()
    #options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    drv = webdriver.Chrome(options=options)
    drv.implicitly_wait(5)
    yield drv
    drv.quit()


def test_la_page_de_vote_se_charge(driver):
    """Vérifie que la page de vote s'affiche avec les deux boutons de choix."""
    driver.get(VOTE_URL)
    assert "vs" in driver.title.lower()

    bouton_a = driver.find_element(By.ID, "a")
    bouton_b = driver.find_element(By.ID, "b")
    assert bouton_a.is_displayed()
    assert bouton_b.is_displayed()


def test_voter_pour_a_est_pris_en_compte(driver):
    """Vérifie qu'un clic sur le bouton A enregistre bien le vote (bouton désactivé + coche affichée)."""
    driver.get(VOTE_URL)
    driver.find_element(By.ID, "a").click()

    # Après soumission, la page recharge et le bouton "a" devient désactivé
    # avec une icône de validation (comportement défini dans index.html).
    # Délai élargi à 10s : ce comportement dépend d'un script jQuery chargé
    # depuis un CDN externe (code.jquery.com), qui peut être plus lent au
    # premier appel réseau.
    WebDriverWait(driver, 10).until(
        lambda d: d.find_element(By.ID, "a").get_attribute("disabled") is not None
    )
    bouton_a = driver.find_element(By.ID, "a")
    assert bouton_a.get_attribute("disabled") is not None


def test_voter_pour_b_est_pris_en_compte(driver):
    """Même vérification pour le bouton B."""
    driver.get(VOTE_URL)
    driver.find_element(By.ID, "b").click()

    WebDriverWait(driver, 10).until(
        lambda d: d.find_element(By.ID, "b").get_attribute("disabled") is not None
    )
    bouton_b = driver.find_element(By.ID, "b")
    assert bouton_b.get_attribute("disabled") is not None


def test_le_vote_se_reflete_sur_la_page_resultat(driver):
    """
    Test de bout en bout : vote sur la page vote, puis vérifie que le
    nombre total de votes affiché sur la page result augmente (mise à jour
    en temps réel via Redis + Socket.io).

    Note : on vérifie le TOTAL plutôt que le pourcentage affiché, car le
    pourcentage est arrondi (Math.round côté client) — après de nombreuses
    exécutions de test successives, le total de votes accumulés peut être
    assez élevé pour qu'un vote supplémentaire ne fasse pas bouger le
    pourcentage arrondi, alors que le total, lui, augmente toujours.
    """
    driver.get(RESULT_URL)
    total_avant = driver.find_element(By.ID, "result").text

    # On vote pour "a" (Cats) dans un second onglet
    driver.execute_script("window.open('');")
    driver.switch_to.window(driver.window_handles[1])
    driver.get(VOTE_URL)
    driver.find_element(By.ID, "a").click()
    time.sleep(1)  # laisse le temps au vote d'être écrit dans Redis
    driver.close()
    driver.switch_to.window(driver.window_handles[0])

    # Le résultat doit se mettre à jour sans recharger la page (Socket.io),
    # le serveur pousse une mise à jour chaque seconde (cf server.js)
    WebDriverWait(driver, 15).until(
        lambda d: d.find_element(By.ID, "result").text != total_avant
    )
    time.sleep(5)

def test_le_compteur_total_de_votes_augmente(driver):
    """Vérifie que le nombre total de votes affiché augmente après un vote."""
    driver.get(RESULT_URL)
    texte_avant = driver.find_element(By.ID, "result").text

    driver.execute_script("window.open('');")
    driver.switch_to.window(driver.window_handles[1])
    driver.get(VOTE_URL)
    driver.find_element(By.ID, "b").click()
    driver.close()
    driver.switch_to.window(driver.window_handles[0])

    WebDriverWait(driver, 10).until(
        lambda d: d.find_element(By.ID, "result").text != texte_avant
    )