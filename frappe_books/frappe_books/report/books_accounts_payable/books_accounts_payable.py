from frappe_books.reports import ageing

DOCTYPE = "Books Purchase Invoice"


def execute(filters=None):
	return ageing.get_columns(DOCTYPE), ageing.get_data(DOCTYPE, filters or {})


def get_default_filters():
	return ageing.get_default_filters()
