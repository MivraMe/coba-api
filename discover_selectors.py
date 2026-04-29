"""
Script de diagnostic — à exécuter UNE FOIS localement.
Il se connecte au portail, dumpe le HTML de la page de login et de la page
des notes, puis affiche les sélecteurs trouvés.

Usage:
    python3 discover_selectors.py
"""

import asyncio
import os
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()  # charge automatiquement le fichier .env

PORTAL_URL = os.getenv("PORTAL_URL",        "https://portail.collegeblondin.qc.ca/pednet")
LOGIN_PATH = os.getenv("PORTAL_LOGIN_PATH", "/login.coba")
NOTES_PATH = os.getenv("PORTAL_NOTES_PATH", "")
USERNAME   = os.getenv("PORTAL_USERNAME",   "")
PASSWORD   = os.getenv("PORTAL_PASSWORD",   "")


async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        page = await browser.new_page()

        # ── 1. Page de login ────────────────────────────────────────────────
        print(f"\n[1] Navigation vers {PORTAL_URL + LOGIN_PATH}")
        await page.goto(PORTAL_URL + LOGIN_PATH)
        await page.wait_for_load_state("networkidle")

        Path("debug_login.html").write_text(await page.content(), encoding="utf-8")
        print("    HTML sauvegardé dans debug_login.html")

        inputs = await page.query_selector_all("input")
        print(f"\n    Inputs trouvés ({len(inputs)}) :")
        for el in inputs:
            name  = await el.get_attribute("name")  or ""
            id_   = await el.get_attribute("id")    or ""
            type_ = await el.get_attribute("type")  or "text"
            print(f"      type={type_!r:12}  name={name!r:30}  id={id_!r}")

        buttons = await page.query_selector_all("button, input[type='submit']")
        print(f"\n    Boutons trouvés ({len(buttons)}) :")
        for el in buttons:
            type_ = await el.get_attribute("type") or ""
            text  = (await el.inner_text()).strip()[:60]
            cls   = await el.get_attribute("class") or ""
            print(f"      type={type_!r:12}  text={text!r:30}  class={cls!r}")

        # ── 2. Login ────────────────────────────────────────────────────────
        if not (USERNAME and PASSWORD):
            print("\n[!] PORTAL_USERNAME / PORTAL_PASSWORD non définis dans .env — abandon")
            await browser.close()
            return

        print(f"\n[2] Connexion avec {USERNAME!r} …")

        # Sélecteurs robustes : ends-with sur name pour ignorer le préfixe dynamique
        sel_user = "input[name$='txtCodeUsager']"
        sel_pass = "input[name$='txtMotDePasse']"
        sel_btn  = "button[type='submit']"

        # Vérifie que les sélecteurs trouvent bien quelque chose
        found_user = await page.query_selector(sel_user)
        found_pass = await page.query_selector(sel_pass)
        found_btn  = await page.query_selector(sel_btn)
        print(f"    username field trouvé : {found_user is not None}  ({sel_user})")
        print(f"    password field trouvé : {found_pass is not None}  ({sel_pass})")
        print(f"    bouton trouvé         : {found_btn  is not None}  ({sel_btn})")

        if not (found_user and found_pass and found_btn):
            print("\n    [ERREUR] Un sélecteur n'a pas été trouvé.")
            print("    Vérifiez debug_login.html pour les bons attributs.")
            input("    Appuyez sur Entrée pour fermer…")
            await browser.close()
            return

        await page.fill(sel_user, USERNAME)
        await page.fill(sel_pass, PASSWORD)

        print("    Clic sur SE CONNECTER …")
        await page.click(sel_btn)

        # Attendre que l'URL change (= login réussi) ou timeout (= échec)
        try:
            await page.wait_for_url(
                lambda url: LOGIN_PATH not in url,
                timeout=15000,
            )
            await page.wait_for_load_state("networkidle")
            print(f"    Login RÉUSSI  →  URL : {page.url}")
        except Exception:
            print(f"    Login ÉCHOUÉ  — URL après soumission : {page.url}")
            print("    Causes possibles : mauvais mot de passe, CAPTCHA, ou erreur réseau.")
            Path("debug_after_login.html").write_text(await page.content(), encoding="utf-8")
            print("    HTML sauvegardé dans debug_after_login.html (regardez les messages d'erreur)")
            input("    Appuyez sur Entrée pour fermer…")
            await browser.close()
            return

        Path("debug_after_login.html").write_text(await page.content(), encoding="utf-8")
        print("    HTML sauvegardé dans debug_after_login.html")

        # ── 2b. Contenu de chaque élément de navigation (treeview) ──────────
        print("\n[2b] Labels du menu de navigation (treeview__elem) :")
        nav_items = await page.query_selector_all("div.treeview__elem")
        for i, el in enumerate(nav_items):
            try:
                txt = (await el.inner_text()).strip().replace("\n", " ")[:80]
                id_ = await el.get_attribute("id") or ""
                cls = await el.get_attribute("class") or ""
                print(f"      [{i:02d}]  id={id_!r:30}  class={cls!r:30}  text={txt!r}")
            except Exception:
                pass

        print("\n[2c] tr.grid3__row count sur Actualités (avant tout clic) :")
        rows_before = await page.query_selector_all("tr.grid3__row")
        print(f"      {len(rows_before)} rangées trouvées — décompte attendu sur TRAVAUX : 56")

        # ── 3. Page des notes ───────────────────────────────────────────────
        print(f"\n[3] URL après login : {page.url}")
        print("    Dans le navigateur ouvert, naviguez jusqu'à la page qui affiche vos notes.")
        print("    Appuyez sur Entrée ici quand vous êtes sur cette page…")
        input()
        await page.wait_for_load_state("networkidle")
        print(f"    URL de la page des notes : {page.url}")

        Path("debug_notes.html").write_text(await page.content(), encoding="utf-8")
        print("    HTML sauvegardé dans debug_notes.html")

        # Chercher les éléments répétitifs (candidats containers de notes)
        print("\n    Éléments répétés (≥2x) — candidats containers de notes :")
        found_any = False
        for tag in ["div", "li", "article", "tr", "td", "span"]:
            els = await page.query_selector_all(tag)
            classes: list[str] = []
            for el in els:
                cls = await el.get_attribute("class")
                if cls:
                    classes.append(cls.strip())
            for cls, n in sorted(Counter(classes).items(), key=lambda x: -x[1]):
                if n >= 2:
                    first_class = cls.split()[0]
                    print(f"      {n:3}x  <{tag} class='{first_class}...'>  (full: '{cls}')")
                    found_any = True
        if not found_any:
            print("      (aucun élément répété trouvé)")

        # Afficher aussi tous les titres de sections visibles
        print("\n    Textes des <th>, <h1>–<h4> visibles (pour identifier la structure) :")
        for sel in ["h1", "h2", "h3", "h4", "th"]:
            els = await page.query_selector_all(sel)
            for el in els:
                txt = (await el.inner_text()).strip().replace("\n", " ")[:80]
                if txt:
                    print(f"      <{sel}>  {txt!r}")

        print("\n[4] Partagez la sortie de ce terminal avec Claude.")
        print("    Il mettra à jour les sélecteurs dans config.py.")
        input("    Appuyez sur Entrée pour fermer le navigateur…")
        await browser.close()


asyncio.run(main())
