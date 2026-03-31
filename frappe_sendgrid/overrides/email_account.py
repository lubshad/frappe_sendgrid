from frappe.email.doctype.email_account.email_account import EmailAccount


class SendgridEmailAccount(EmailAccount):
	def validate(self):
		if self.service == "Sendgrid HTTP":
			# Force outgoing-only; no SMTP fields needed
			self.enable_incoming = 0
			self.always_use_account_email_id_as_sender = 1
		super().validate()

	def validate_smtp_conn(self):
		"""Skip SMTP connection test for Sendgrid HTTP — API key is used instead."""
		if self.service == "Sendgrid HTTP":
			return
		super().validate_smtp_conn()

	def get_smtp_server(self):
		"""Return None for Sendgrid HTTP — sending is handled via API, not SMTP."""
		if self.service == "Sendgrid HTTP":
			return None
		return super().get_smtp_server()
