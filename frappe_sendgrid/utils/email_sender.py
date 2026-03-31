import base64
import email as email_lib
from email.header import decode_header, make_header

import frappe
import requests


def send_via_sendgrid(queue_doc, sender: str, recipient: str, message: bytes) -> None:
	"""Route email via SendGrid HTTP API if the account service is 'Sendgrid HTTP',
	otherwise fall back to standard SMTP sending.
	"""
	email_account_doc = None
	if queue_doc.email_account:
		email_account_doc = frappe.get_cached_doc("Email Account", queue_doc.email_account)

	if email_account_doc and email_account_doc.service == "Sendgrid HTTP":
		api_key = email_account_doc.get_password("password") or frappe.conf.get("sendgrid_api_key")
		if not api_key:
			frappe.throw(
				"SendGrid API Key is not set. Enter it in the Email Account password field "
				"or add 'sendgrid_api_key' to site_config.json."
			)
		payload = _build_payload(sender, recipient, message)
		_post_to_sendgrid(api_key, payload)
	else:
		# Not a Sendgrid HTTP account — send via SMTP as Frappe normally would
		_send_via_smtp(email_account_doc, sender, recipient, message)


def _send_via_smtp(email_account_doc, sender: str, recipient: str, message: bytes) -> None:
	msg_bytes = message if isinstance(message, bytes) else message.encode("utf-8")
	smtp_server = email_account_doc.get_smtp_server()
	smtp_server.session.sendmail(
		from_addr=sender,
		to_addrs=recipient,
		msg=msg_bytes,
	)


def _decode_header_value(value: str | None) -> str:
	if not value:
		return ""
	return str(make_header(decode_header(value)))


def _build_payload(sender: str, recipient: str, message: bytes) -> dict:
	msg = email_lib.message_from_bytes(message) if isinstance(message, bytes) else email_lib.message_from_string(message)

	subject = _decode_header_value(msg.get("Subject", ""))
	reply_to = msg.get("Reply-To")

	text_body = None
	html_body = None
	attachments = []

	if msg.is_multipart():
		for part in msg.walk():
			content_type = part.get_content_type()
			disposition = str(part.get_content_disposition() or "")

			if disposition == "attachment":
				attachments.append(_build_attachment(part))
			elif content_type == "text/plain" and not disposition:
				text_body = _decode_part(part)
			elif content_type == "text/html" and not disposition:
				html_body = _decode_part(part)
	else:
		content_type = msg.get_content_type()
		if content_type == "text/html":
			html_body = _decode_part(msg)
		else:
			text_body = _decode_part(msg)

	# SendGrid requires at least one content entry; text/plain must come before text/html
	content = []
	if text_body:
		content.append({"type": "text/plain", "value": text_body})
	if html_body:
		content.append({"type": "text/html", "value": html_body})
	if not content:
		content.append({"type": "text/plain", "value": " "})

	payload: dict = {
		"personalizations": [{"to": [{"email": recipient}]}],
		"from": {"email": sender},
		"subject": subject,
		"content": content,
	}

	if reply_to:
		payload["reply_to"] = {"email": _decode_header_value(reply_to)}

	if attachments:
		payload["attachments"] = attachments

	return payload


def _decode_part(part) -> str:
	charset = part.get_content_charset() or "utf-8"
	payload = part.get_payload(decode=True)
	if payload is None:
		return ""
	return payload.decode(charset, errors="replace")


def _build_attachment(part) -> dict:
	filename = _decode_header_value(part.get_filename() or "attachment")
	content_type = part.get_content_type()
	payload = part.get_payload(decode=True) or b""
	encoded = base64.b64encode(payload).decode()
	return {
		"content": encoded,
		"type": content_type,
		"filename": filename,
	}


def _post_to_sendgrid(api_key: str, payload: dict) -> None:
	response = requests.post(
		"https://api.sendgrid.com/v3/mail/send",
		json=payload,
		headers={
			"Authorization": f"Bearer {api_key}",
			"Content-Type": "application/json",
		},
		timeout=30,
	)

	if response.status_code not in (200, 202):
		error_body = response.text[:500]
		frappe.throw(f"SendGrid API error {response.status_code}: {error_body}")
