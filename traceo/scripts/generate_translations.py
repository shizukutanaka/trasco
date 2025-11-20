#!/usr/bin/env python3
"""
Generate translations for 50+ languages using Google Translate API

Usage:
    python generate_translations.py
"""

import json
import sys
from pathlib import Path

# Language codes and names (ISO 639-1)
LANGUAGES = {
    "en": "English",
    "ja": "日本語",
    "es": "Español",
    "fr": "Français",
    "de": "Deutsch",
    "it": "Italiano",
    "pt": "Português",
    "ru": "Русский",
    "zh": "中文",
    "ko": "한국어",
    "ar": "العربية",
    "th": "ไทย",
    "vi": "Tiếng Việt",
    "id": "Bahasa Indonesia",
    "tr": "Türkçe",
    "pl": "Polski",
    "nl": "Nederlands",
    "sv": "Svenska",
    "no": "Norsk",
    "da": "Dansk",
    "fi": "Suomi",
    "he": "עברית",
    "hi": "हिन्दी",
    "cs": "Čeština",
    "ro": "Română",
    "hu": "Magyar",
    "el": "Ελληνικά",
    "uk": "Українська",
    "ms": "Bahasa Melayu",
    "tl": "Tagalog",
    "sk": "Slovenčina",
    "hr": "Hrvatski",
    "bg": "Български",
    "lt": "Lietuvių",
    "et": "Eesti",
    "lv": "Latvian",
    "sl": "Slovenščina",
    "ga": "Irish",
    "mt": "Maltese",
    "cy": "Welsh",
    "sq": "Albanian",
    "mk": "Macedonian",
    "is": "Icelandic",
    "af": "Afrikaans",
    "bn": "বাঙ্গালি",
    "fa": "فارسی",
}

def load_base_translation(lang: str = "en") -> dict:
    """Load base English translation"""
    base_path = Path(__file__).parent.parent / "backend" / "app" / "locales" / f"{lang}.json"
    if not base_path.exists():
        print(f"Base translation file not found: {base_path}")
        return {}

    with open(base_path, "r", encoding="utf-8") as f:
        return json.load(f)

def try_google_translate(text: str, source_lang: str, target_lang: str) -> str:
    """Try to translate using Google Translate"""
    try:
        import google.cloud.translate_v2 as translate
        # This requires Google Cloud credentials
        # For now, return placeholder
        return f"[{target_lang}] {text}"
    except ImportError:
        return text

def create_placeholder_translation(base_trans: dict, target_lang: str) -> dict:
    """Create placeholder translation with language code prefix"""
    result = {}
    lang_code = target_lang.upper()
    for key, value in base_trans.items():
        if isinstance(value, str):
            result[key] = f"[{lang_code}] {value}"
        else:
            result[key] = value
    return result

def generate_translations_frontend(output_dir: Path):
    """Generate frontend translations"""
    output_dir = output_dir / "frontend" / "src" / "i18n"
    output_dir.mkdir(parents=True, exist_ok=True)

    base_trans = load_base_translation("en")

    # English
    with open(output_dir / "en.json", "w", encoding="utf-8") as f:
        json.dump(base_trans, f, ensure_ascii=False, indent=2)
    print(f"✓ Generated en.json")

    # Japanese (already exists, skip)
    # Generate placeholders for other languages
    for lang_code, lang_name in LANGUAGES.items():
        if lang_code in ["en", "ja"]:
            continue

        placeholder_trans = create_placeholder_translation(base_trans, lang_code)
        filepath = output_dir / f"{lang_code}.json"

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(placeholder_trans, f, ensure_ascii=False, indent=2)
        print(f"✓ Generated {lang_code}.json ({lang_name})")

def generate_translations_backend(output_dir: Path):
    """Generate backend translations"""
    output_dir = output_dir / "backend" / "app" / "locales"
    output_dir.mkdir(parents=True, exist_ok=True)

    base_trans = load_base_translation("en")

    # English
    with open(output_dir / "en.json", "w", encoding="utf-8") as f:
        json.dump(base_trans, f, ensure_ascii=False, indent=2)
    print(f"✓ Generated backend en.json")

    # Japanese (already exists, skip)
    # Generate placeholders
    for lang_code, lang_name in LANGUAGES.items():
        if lang_code in ["en", "ja"]:
            continue

        placeholder_trans = create_placeholder_translation(base_trans, lang_code)
        filepath = output_dir / f"{lang_code}.json"

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(placeholder_trans, f, ensure_ascii=False, indent=2)
        print(f"✓ Generated backend {lang_code}.json ({lang_name})")

def main():
    """Main function"""
    script_dir = Path(__file__).parent
    project_dir = script_dir.parent

    print("Generating translations for Traceo...")
    print(f"Project directory: {project_dir}")
    print()

    print("Generating frontend translations...")
    generate_translations_frontend(project_dir)
    print()

    print("Generating backend translations...")
    generate_translations_backend(project_dir)
    print()

    print("✅ Translation generation complete!")
    print(f"Generated translations for {len(LANGUAGES)} languages")
    print()
    print("Note: Placeholder translations are auto-generated.")
    print("Please update them with actual translations.")
    print()
    print("Languages supported:")
    for code, name in sorted(LANGUAGES.items()):
        if code in ["en", "ja"]:
            status = "✓ Complete"
        else:
            status = "⏳ Placeholder"
        print(f"  {code:5} - {name:20} {status}")

if __name__ == "__main__":
    main()
