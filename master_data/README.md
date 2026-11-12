# Master data catalog

The business setup page (after sign-up) offers each kind of business its usual items, grouped, with
descriptions, units, taka prices and pictures. Books ships a small starter catalog in
`frappe_books/data/business_types`. This folder holds the full catalog that sites read online, so the
item lists can grow and change without an app release.

| Business type | Groups | Items |
| --- | ---: | ---: |
| Pharmacy | 12 | 258 |
| Restaurant | 17 | 261 |
| Grocery | 14 | 273 |
| Clothing (fashion) | 9 | 149 |
| Electronics & mobile | 6 | 157 |
| Hardware & Sanitary (new) | 10 | 117 |
| Stationery & Books (new) | 8 | 107 |
| Cosmetics & Beauty Parlour (new) | 8 | 112 |
| Bakery & Sweet Shop (new) | 9 | 100 |

Prices are typical Bangladesh retail prices in taka, as a starting point. The user sees and edits
every price on the setup page before anything is made.

## Layout

```
master_data/
  sources/<type>/type.json   label, icon, questions, groups and units of one business type
  sources/<type>/items.csv   its items, one row each
  dist/catalog.json          what sites read: built from sources, do not edit by hand
  images.json                pictures found by --images, kept so builds need no network (optional)
  build.py                   checks the sources and builds dist/catalog.json
```

### items.csv columns

| Column | What it holds |
| --- | --- |
| `group` | One of the groups in `type.json` |
| `name` | The item's name, which is also its code. Unique in the type, one line, 140 characters at most |
| `type` | `Product` or `Service` |
| `uom` | One of the units in `type.json`, or a unit every site has: Unit, Kg, Gram, Meter, Hour, Day |
| `rate` | Price in taka |
| `tags` | Option ids from the type's question, separated by spaces. The item is offered when the user picks one of them |
| `image_query` | A phrase to find a picture on Wikipedia, like `Kacchi biryani`. Like items can share one |
| `description` | One line shown under the item and saved on it |
| `image` | Optional `https` picture address. Wins over `image_query` |

Edit the CSV in Excel or Google Sheets (save as CSV, UTF-8), or any text editor.

## Building

```
python3 master_data/build.py           # check the sources and write dist/catalog.json
python3 master_data/build.py --check   # what CI runs: fails if the catalog is invalid or not rebuilt
python3 master_data/build.py --images  # also find pictures on Wikipedia and keep them in images.json
```

The build cleans the catalog with the app's own rules (`frappe_books/onboarding/catalog.py`) and
stops on anything a site would drop or get wrong: an unknown group, unit or tag, a missing price or
description, a name used twice, more than 500 items or 60 groups in a type. A type that has the id
of a shipped type replaces the shipped one on a site, so the build also stops if it leaves out any
shipped item.

`--images` needs access to en.wikipedia.org. It is optional: without it, the setup page looks
pictures up by `image_query` when the user picks a business type.

## Hosting

A site reads the catalog from the address in its `books_master_data_url` site config, keeps it for
six hours, and merges it over the shipped types by id. Any `https` address that serves the JSON works.

The repository is public, so the simplest host is GitHub itself, once this folder is on `develop`:

```
bench --site <site> set-config books_master_data_url \
  https://raw.githubusercontent.com/BizSouq/fr-sme-books/develop/master_data/dist/catalog.json
```

Every site then picks up a merged change to the catalog within six hours, with no deploy. To change
what sites see, edit the sources, run the build, and merge.

Other hosts work the same way: a CDN or object storage bucket (upload `dist/catalog.json`), or the
company's own web server. The catalog's host is also trusted for item pictures, so product photos
can be served from the same place and named in the `image` column. Pictures from any other host
must be listed in the site's `books_image_hosts` config, or they are not downloaded.

To stop using the online catalog, remove the config: `bench --site <site> set-config
books_master_data_url ""`. The site falls back to the shipped starter catalog.
