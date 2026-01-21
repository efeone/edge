from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
import frappe


#Custom Property Setter imports for Edge
from edge.custom.property_setters.interview import get_interview_property_setters

def after_install():
	#Creating edge specific Property Setters
	create_property_setters(get_property_setters())
	

def after_migrate():
	after_install()



def delete_custom_fields(custom_fields: dict):
	'''
		Method to Delete custom fields
		args:
			custom_fields: a dict like `{'Task': [{fieldname: 'your_fieldname', ...}]}`
	'''
	for doctype, fields in custom_fields.items():
		frappe.db.delete(
			"Custom Field",
			{
				"fieldname": ("in", [field["fieldname"] for field in fields]),
				"dt": doctype,
			},
		)
		frappe.clear_cache(doctype=doctype)


def create_property_setters(property_setter_datas):
	'''
		Method to create custom property setters
		args:
			property_setter_datas : list of dict of property setter obj
	'''
	for property_setter_data in property_setter_datas:
		if frappe.db.exists("Property Setter", property_setter_data):
			continue
		property_setter = frappe.new_doc("Property Setter")
		property_setter.update(property_setter_data)
		property_setter.flags.ignore_permissions = True
		property_setter.insert()

def get_property_setters():
	'''
		PW IOI specific property setters that need to be added to the Standard DocTypes
	'''
	property_setters = (get_interview_property_setters())
	return property_setters