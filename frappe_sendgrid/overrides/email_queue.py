import frappe
from frappe import _
from frappe.email.doctype.email_queue.email_queue import EmailQueue, SendMailContext
from frappe.utils import get_hook_method


class SendgridSendMailContext(SendMailContext):
	def fetch_outgoing_server(self):
		self.email_account_doc = self.queue_doc.get_email_account(raise_error=True)

		if self.email_account_doc.service == "Frappe Mail":
			if not self.frappe_mail_client:
				self.frappe_mail_client = self.email_account_doc.get_frappe_mail_client()
		elif self.email_account_doc.service == "Sendgrid HTTP" and get_hook_method("override_email_send"):
			return
		elif not self.smtp_server:
			self.smtp_server = self.email_account_doc.get_smtp_server()


class SendgridEmailQueue(EmailQueue):
	def send(self, smtp_server_instance=None, frappe_mail_client=None, force_send: bool = False):
		if not self.can_send_now() and not force_send:
			return

		with SendgridSendMailContext(self, smtp_server_instance, frappe_mail_client) as ctx:
			ctx.fetch_outgoing_server()

			def validate_and_prepare_message(raw_message: bytes) -> bytes:
				msg = raw_message if isinstance(raw_message, bytes) else raw_message.encode("utf-8")

				if ctx.smtp_server.session.has_extn("SIZE"):
					if max_size := ctx.smtp_server.session.esmtp_features.get("size"):
						max_size = int(max_size)

						if max_size > 0:
							msg_size = len(msg)

							if msg_size > max_size:
								msg_size_mb = msg_size / (1024 * 1024)
								max_size_mb = max_size / (1024 * 1024)
								frappe.throw(
									_(
										"Email size {0:.2f} MB exceeds the maximum allowed size of {1:.2f} MB"
									).format(msg_size_mb, max_size_mb)
								)

				return msg

			def get_smtp_options() -> tuple[list[str], list[str]]:
				mail_options: list[str] = []
				rcpt_options: list[str] = []

				if not ctx.smtp_server.session.has_extn("DSN"):
					return mail_options, rcpt_options

				if dsn_notify_type := ctx.email_account_doc.dsn_notify_type:
					mail_options.extend(["RET=FULL", f"ENVID={self.name}"])
					rcpt_options.append(f"NOTIFY={dsn_notify_type}")

				return mail_options, rcpt_options

			last_message = None

			for recipient in self.recipients:
				if recipient.is_mail_sent():
					continue

				message = ctx.build_message(recipient.recipient)
				last_message = message

				if method := get_hook_method("override_email_send"):
					method(self, self.sender, recipient.recipient, message)

				elif not frappe.in_test or frappe.flags.testing_email:
					if ctx.email_account_doc.service == "Frappe Mail":
						ctx.frappe_mail_client.send_raw(
							sender=self.sender,
							recipients=recipient.recipient,
							message=message,
							is_newsletter=self.reference_doctype == "Newsletter",
						)
					else:
						msg_bytes = validate_and_prepare_message(message)
						mail_options, rcpt_options = get_smtp_options()

						ctx.smtp_server.session.sendmail(
							from_addr=self.sender,
							to_addrs=recipient.recipient,
							msg=msg_bytes,
							mail_options=mail_options,
							rcpt_options=rcpt_options,
						)

				ctx.update_recipient_status_to_sent(recipient)

			if frappe.in_test and not frappe.flags.testing_email:
				frappe.flags.sent_mail = last_message
				return

			if last_message and ctx.email_account_doc.append_emails_to_sent_folder:
				ctx.email_account_doc.append_email_to_sent_folder(last_message)
