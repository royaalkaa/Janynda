"""
Management command: auto_translate
====================================
Автоматически переводит незаполненные строки в .po файлах
через Google Translate (бесплатно, без API-ключа).

Использование:
    python manage.py auto_translate             # все языки
    python manage.py auto_translate --lang kk  # только казахский
    python manage.py auto_translate --lang en  # только английский

После команды запустите:
    python manage.py compilemessages
"""

import os
from pathlib import Path

from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = "Авто-перевод .po файлов через Google Translate (deep-translator)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--lang",
            type=str,
            default=None,
            help="Код языка для перевода (kk / en). По умолчанию — все кроме ru.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            default=False,
            help="Перевести даже уже заполненные строки.",
        )

    def handle(self, *args, **options):
        try:
            import polib
        except ImportError:
            self.stderr.write(self.style.ERROR(
                "Установите polib: pip install polib"
            ))
            return

        try:
            from deep_translator import GoogleTranslator
        except ImportError:
            self.stderr.write(self.style.ERROR(
                "Установите deep-translator: pip install deep-translator"
            ))
            return

        locale_dir = Path(settings.LOCALE_PATHS[0])
        target_lang = options["lang"]
        force = options["force"]

        # Языки для перевода (кроме исходного ru)
        langs = {"kk": "kk", "en": "en"}
        if target_lang:
            if target_lang not in langs:
                self.stderr.write(self.style.ERROR(
                    f"Неизвестный язык: {target_lang}. Доступны: {', '.join(langs)}"
                ))
                return
            langs = {target_lang: langs[target_lang]}

        for lang_code, gt_code in langs.items():
            po_path = locale_dir / lang_code / "LC_MESSAGES" / "django.po"
            if not po_path.exists():
                self.stdout.write(self.style.WARNING(
                    f"  [{lang_code}] Файл не найден: {po_path}"
                ))
                self.stdout.write(f"  Запустите: python manage.py makemessages -l {lang_code} --no-wrap")
                continue

            self.stdout.write(f"\n→ Переводим [{lang_code}] из {po_path}")
            po = polib.pofile(str(po_path))

            translator = GoogleTranslator(source="ru", target=gt_code)
            translated = 0
            skipped = 0
            errors = 0

            entries = po.untranslated_entries() if not force else (
                po.untranslated_entries() + po.translated_entries()
            )

            for entry in entries:
                if not entry.msgid.strip():
                    continue
                try:
                    result = translator.translate(entry.msgid)
                    if result:
                        entry.msgstr = result
                        translated += 1
                        self.stdout.write(f"  ✓ {entry.msgid[:50]!r} → {result[:50]!r}")
                except Exception as exc:
                    errors += 1
                    self.stderr.write(f"  ✗ Ошибка для {entry.msgid[:40]!r}: {exc}")

            po.save()
            self.stdout.write(self.style.SUCCESS(
                f"  [{lang_code}] Переведено: {translated}, пропущено: {skipped}, ошибок: {errors}"
            ))

        self.stdout.write(self.style.SUCCESS(
            "\n✅ Готово! Теперь запустите: python manage.py compilemessages"
        ))
