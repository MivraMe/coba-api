from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Portal URLs
    portal_url: str = "https://portail.collegeblondin.qc.ca/pednet"
    portal_login_path: str = "/login.coba"

    # CSS selectors for login form
    # The portal uses a dynamic component prefix (e.g. C1C4A_) — ends-with selector
    selector_username_input: str = "input[name$='txtCodeUsager']"
    selector_password_input: str = "input[name$='txtMotDePasse']"
    selector_login_button: str = "button[type='submit']"

    # CSS selectors for data extraction (Collège Blondin — TRAVAUX page)
    selector_course_block: str = "div.tableres"   # one block per course
    selector_course_name: str = "h4"              # course title inside block
    selector_assignment_row: str = "tr.grid3__row"  # one row per assignment

    # Scraper behaviour
    session_ttl_seconds: int = 600
    playwright_headless: bool = True
    playwright_timeout_ms: int = 15000


settings = Settings()
