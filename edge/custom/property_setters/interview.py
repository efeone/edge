def get_interview_property_setters():
	'''
		Edge specific property setters that need to be added to the Interview DocType
	'''
	return [
		{
			"doctype_or_field": "DocField",
			"doc_type": "Interview",
			"field_name": "scheduled_on",
			"property": "set_only_once",
			"property_type": "Check",
			"value":0
		},
		{
			"doctype_or_field": "DocField",
			"doc_type": "Interview",
			"field_name": "from_time",
			"property": "set_only_once",
			"property_type": "Check",
			"value":0
		},
		{
			"doctype_or_field": "DocField",
			"doc_type": "Interview",
			"field_name": "to_time",
			"property": "set_only_once",
			"property_type": "Check",
			"value":0
		},
		
	]