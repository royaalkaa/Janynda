import base64
import io

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.conf import settings


def _generate_qr_b64(data: str) -> str:
    """Генерирует QR-код из строки, возвращает base64 PNG."""
    try:
        import qrcode
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#111827", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
    except ImportError:
        return ""


@login_required
def payment_view(request):
    kaspi_phone = getattr(settings, "KASPI_PHONE", "+7 (777) 000-00-00")
    kaspi_name  = getattr(settings, "KASPI_NAME",  "Janynda")
    kaspi_url   = getattr(settings, "KASPI_URL",   f"https://kaspi.kz/pay/{kaspi_phone}")

    qr_b64 = _generate_qr_b64(kaspi_url)

    return render(request, "payment/index.html", {
        "kaspi_phone": kaspi_phone,
        "kaspi_name":  kaspi_name,
        "kaspi_url":   kaspi_url,
        "qr_b64":      qr_b64,
    })
