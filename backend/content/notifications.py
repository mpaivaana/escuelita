"""Aviso por e-mail quando chega uma mensagem pelo formulário de contato.

Desligado por padrão: só envia se CONTACT_NOTIFY_EMAIL e EMAIL_HOST estiverem definidos (ver .env.example).
Uma falha no envio nunca derruba o formulário: a mensagem já está salva e aparece no gestor.
"""
import logging

from django.conf import settings
from django.core.mail import EmailMessage

log = logging.getLogger("escuelita")


def notify_contact(message) -> bool:
    """Envia a mensagem para CONTACT_NOTIFY_EMAIL. O Reply-To é o e-mail de quem escreveu."""
    recipients = settings.CONTACT_NOTIFY_EMAIL
    if not recipients or not settings.EMAIL_HOST:
        return False
    subject = " ".join(message.subject.split())  # uma linha só: quebras de linha em cabeçalho são recusadas
    body = (
        f"Nuevo mensaje desde el formulario de contacto del sitio.\n\n"
        f"Nombre: {message.name}\n"
        f"Correo: {message.email}\n"
        f"Idioma: {message.language}\n"
        f"Asunto: {subject}\n\n"
        f"{message.message}\n\n"
        f"Puedes responder directamente a este correo."
    )
    try:
        EmailMessage(
            subject=f"[Escuelita] {subject}"[:200],
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipients,
            reply_to=[message.email],
        ).send(fail_silently=False)
    except Exception as exc:
        log.warning("Aviso de contato não enviado: %s: %s", type(exc).__name__, str(exc)[:200])
        return False
    return True
