from frappe_books.inventory.variants import seed_attributes


def execute():
	"""Give an existing site the Size, Shoe Size and Color attributes a new site starts with."""
	seed_attributes()
