from frappe_books.inventory.labels import seed_label_templates


def execute():
	"""Give an existing site the ready price tag a new site starts with."""
	seed_label_templates()
