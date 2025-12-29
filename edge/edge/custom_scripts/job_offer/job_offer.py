# Copyright (c) 2025, efeone and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import get_url

@frappe.whitelist(allow_guest=True)
def update_job_offer_status(applicant, status):
	"""
	Update Job Offer status via email button click
	"""

	if status not in ["Accepted", "Rejected"]:
		frappe.throw(_("Invalid status."))

	if not frappe.db.exists("Job Offer", applicant):
		frappe.throw(_("Job Offer not found."))

	frappe.db.set_value(
		"Job Offer",
		applicant,
		"status",
		status,
		update_modified=False
	)
	frappe.db.commit()

	indicator = "green" if status == "Accepted" else "red"

	html = f"""
		<div style="max-width:600px;margin:40px auto;
		font-family:Arial,sans-serif;text-align:center;">
			<h2>{status}!</h2>
			<p style="font-size:16px;color:#555;">
				Your job offer has been <strong>{status.lower()}</strong> successfully.
			</p>
		</div>
	"""

	frappe.respond_as_web_page(
		title=_("Job Offer Response"),
		html=html,
		indicator_color=indicator
	)

@frappe.whitelist()
def send_offer_letter(job_offer):
	"""
	Send Offer Letter Email with PDF Attachment
	"""

	job_offer_doc = frappe.get_doc("Job Offer", job_offer)
	settings = frappe.get_single("Utility Settings")

	context = {
		"doc": job_offer_doc
	}

	if settings.job_offer_email_template:
		template = frappe.get_doc(
			"Email Template",
			settings.job_offer_email_template
		)

		subject = frappe.render_template(template.subject, context)

		content = frappe.render_template(
			template.response_html,
			context
		)
	else:
		subject = _("Job Offer from {0}").format(job_offer_doc.company)
		content = _("Dear {0}").format(job_offer_doc.applicant_name)

	pdf_data = frappe.get_print(
		"Job Offer",
		job_offer_doc.name,
		print_format=settings.job_offer_print_format or "Standard",
		as_pdf=True
	)

	frappe.sendmail(
		recipients=[job_offer_doc.applicant_email],
		subject=subject,
		message=content,
		header=["Job Offer Notification", "blue"],
		attachments=[{
			"fname": f"{job_offer_doc.name}.pdf",
			"fcontent": pdf_data
		}]
	)

	return _("Offer letter sent successfully")
