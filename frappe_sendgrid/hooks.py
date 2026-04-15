app_name = "frappe_sendgrid"
app_title = "Frappe Sendgrid"
app_publisher = "CoreAxis Solutions"
app_description = "Sends Frappe emails via SendGrid HTTP API instead of SMTP"
app_email = "lubshad4u4@gmail.com"
app_license = "mit"

after_install = "frappe_sendgrid.install.after_install"

# Override Frappe's SMTP transmission with SendGrid HTTP API.
# Receives: (queue_doc, sender, recipient, message_bytes)
override_email_send = "frappe_sendgrid.utils.email_sender.send_via_sendgrid"

# Extend EmailAccount to skip SMTP validation for "Sendgrid HTTP" service
override_doctype_class = {
	"Email Account": "frappe_sendgrid.overrides.email_account.SendgridEmailAccount",
	"Email Queue": "frappe_sendgrid.overrides.email_queue.SendgridEmailQueue",
}

# Inject client-side defaults for "Sendgrid HTTP" service option
doctype_js = {
	"Email Account": "public/js/email_account.js"
}
