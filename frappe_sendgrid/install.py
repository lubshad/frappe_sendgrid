import frappe


def after_install():
	_add_sendgrid_http_service_option()


def _add_sendgrid_http_service_option():
	meta = frappe.get_meta("Email Account")
	service_field = meta.get_field("service")
	current_options = service_field.options or ""

	if "Sendgrid HTTP" in current_options:
		return

	frappe.make_property_setter(
		{
			"doctype": "Email Account",
			"fieldname": "service",
			"property": "options",
			"value": current_options + "\nSendgrid HTTP",
			"property_type": "Text",
		}
	)
	frappe.db.commit()
