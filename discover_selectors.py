"""
Script de diagnostic — à exécuter UNE FOIS localement.
Il se connecte au portail, dumpe le HTML de la page de login et de la page
des notes, puis affiche les sélecteurs trouvés.

Usage:
    python3 discover_selectors.py
"""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()  # charge automatiquement le fichier .env

PORTAL_URL   = os.getenv("PORTAL_URL",        "https://portail.collegeblondin.qc.ca/pednet")
LOGIN_PATH   = os.getenv("PORTAL_LOGIN_PATH", "/login.coba")
NOTES_PATH   = os.getenv("PORTAL_NOTES_PATH", "")   # laissez vide si inconnu
USERNAME     = os.getenv("PORTAL_USERNAME",   "")
PASSWORD     = os.getenv("PORTAL_PASSWORD",   "")


async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)  # visible pour déboguer
        page = await browser.new_page()

        # ── 1. Page de login ────────────────────────────────────────────────
        print(f"\n[1] Navigation vers {PORTAL_URL + LOGIN_PATH}")
        await page.goto(PORTAL_URL + LOGIN_PATH)
        await page.wait_for_load_state("networkidle")

        html_login = await page.content()
        Path("debug_login.html").write_text(html_login, encoding="utf-8")
        print("    HTML sauvegardé dans debug_login.html")

        # Afficher tous les inputs présents
        inputs = await page.query_selector_all("input")
        print(f"\n    Inputs trouvés ({len(inputs)}) :")
        for el in inputs:
            name  = await el.get_attribute("name")  or ""
            id_   = await el.get_attribute("id")    or ""
            type_ = await el.get_attribute("type")  or "text"
            print(f"      type={type_!r:12}  name={name!r:20}  id={id_!r}")

        buttons = await page.query_selector_all("button, input[type='submit']")
        print(f"\n    Boutons trouvés ({len(buttons)}) :")
        for el in buttons:
            type_ = await el.get_attribute("type") or ""
            text  = (await el.inner_text()).strip()[:60]
            cls   = await el.get_attribute("class") or ""
            print(f"      type={type_!r:12}  text={text!r:30}  class={cls!r}")

        # ── 2. Login ────────────────────────────────────────────────────────
        if USERNAME and PASSWORD:
            print(f"\n[2] Tentative de connexion avec {USERNAME!r} …")

            # Essayer les sélecteurs les plus courants
            candidates_user = [
                "#C135D_txtCodeUsager",
                "input[name='C135D_txtCodeUsager']",
                "input[name='username']", "input[name='user']",
                "input[name='login']",    "input[name='usager']",
                "input[type='text']",
            ]
            candidates_pass = [
                "#C135D_txtMotDePasse",
                "input[name='C135D_txtMotDePasse']",
                "input[name='password']", "input[name='pass']",
                "input[type='password']",
            ]
            candidates_btn = [
                "button[type='submit']", "input[type='submit']",
                "button.bouton-souleve", "button:has-text('SE CONNECTER')",
                "button:has-text('Connexion')", "button",
            ]

            sel_user = sel_pass = sel_btn = None
            for s in candidates_user:
                if await page.query_selector(s):
                    sel_user = s; break
            for s in candidates_pass:
                if await page.query_selector(s):
                    sel_pass = s; break
            for s in candidates_btn:
                if await page.query_selector(s):
                    sel_btn = s; break

            print(f"    SELECTOR_USERNAME_INPUT = {sel_user!r}")
            print(f"    SELECTOR_PASSWORD_INPUT = {sel_pass!r}")
            print(f"    SELECTOR_LOGIN_BUTTON   = {sel_btn!r}")

            if sel_user and sel_pass and sel_btn:
                await page.fill(sel_user, USERNAME)
                await page.fill(sel_pass, PASSWORD)
                await page.click(sel_btn)
                await page.wait_for_load_state("networkidle")
                print(f"\n    URL après login : {page.url}")

                html_post = await page.content()
                Path("debug_after_login.html").write_text(html_post, encoding="utf-8")
                print("    HTML sauvegardé dans debug_after_login.html")
            else:
                print("    Impossible de trouver automatiquement les sélecteurs de login.")
                print("    Ouvrez debug_login.html dans un navigateur et inspectez les champs.")
                await browser.close()
                return
        else:
            print("\n[!] PORTAL_USERNAME / PORTAL_PASSWORD non définis — skip du login")
            await browser.close()
            return

        # ── 3. Page des notes ───────────────────────────────────────────────
        if NOTES_PATH:
            print(f"\n[3] Navigation vers {PORTAL_URL + NOTES_PATH}")
            await page.goto(PORTAL_URL + NOTES_PATH)
            await page.wait_for_load_state("networkidle")
        else:
            print(f"\n[3] URL actuelle après login : {page.url}")
            print("    Naviguez manuellement vers la page des notes dans le navigateur ouvert.")
            print("    Appuyez sur Entrée ici quand vous êtes sur la page des notes…")
            input()

        html_notes = await page.content()
        Path("debug_notes.html").write_text(html_notes, encoding="utf-8")
        print("    HTML sauvegardé dans debug_notes.html")

        # Chercher des structures répétitives (candidates note containers)
        for tag in ["div", "li", "article", "tr"]:
            els = await page.query_selector_all(tag)
            # Identifier les classes qui se répètent au moins 3 fois
            from collections import Counter
            classes: list[str] = []
            for el in els:
                cls = await el.get_attribute("class")
                if cls:
                    classes.append(cls.strip())
            counter = Counter(classes)
            repeated = [(c, n) for c, n in counter.items() if n >= 3]
            if repeated:
                print(f"\n    <{tag}> répétés (≥3x) — candidats containers :")
                for cls, n in sorted(repeated, key=lambda x: -x[1])[:10]:
                    print(f"      {n}x  {tag}.{cls.split()[0]!r}")

        print("\n[4] Envoyez les fichiers debug_*.html à Claude pour qu'il identifie les sélecteurs.")
        print("    Fermez le navigateur quand vous avez terminé.")
        input("    Appuyez sur Entrée pour fermer…")
        await browser.close()


asyncio.run(main())
