from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Portal URLs
    portal_url: str = "https://portal.example.com"
    portal_login_path: str = "/login"
    portal_notes_path: str = "/notes"

    # Credentials
    portal_username: str = ""
    portal_password: str = ""

    # CSS selectors for login form
    selector_username_input: str = "input[name='username']"
    selector_password_input: str = "input[name='password']"
    selector_login_button: str = "button[type='submit']"

    # CSS selectors for notes extraction
    selector_note_container: str = "div.note-card"
    selector_note_title: str = "h2.note-title"
    selector_note_body: str = "p.note-body"
    selector_note_date: str = ""  # optional — leave empty to skip

    # Optional: element that proves login succeeded (leave empty to skip check)
    selector_login_success: str = ""

    # Scraper behaviour
    session_ttl_seconds: int = 600
    playwright_headless: bool = True
    playwright_timeout_ms: int = 10000


settings = Settings()
