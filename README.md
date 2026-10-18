# Wikichoux scripts

[![Code validation](https://github.com/don-vip/wikichoux-scripts/actions/workflows/ci.yml/badge.svg)](https://github.com/don-vip/wikichoux-scripts/actions/workflows/ci.yml)

Collection of Tampermonkey and Python scripts for Wikimedia French politics.

Inspired by [musicbrainz-scripts](https://github.com/loujine/musicbrainz-scripts)

## Compatibility

Scripts are tested with the latest stable version of Firefox and Tampermonkey.
They should work with most recent browsers and with ViolentMonkey.

## Installing

For installation, follow the [Tampermonkey manual](https://www.tampermonkey.net/scripts.php?locale=fr#gh)

### Scripts to display information

#### Display Wikimedia picture of French representatives

Display picture of French representatives from their Wikidata item, on French Parliament websites (National Assembly and Senate)

[![Source](https://raw.github.com/jerone/UserScripts/master/_resources/Source-button.png)](https://github.com/don-vip/wikichoux-scripts/blob/master/wc-french_parliament_images.user.js)
[![Install](https://raw.github.com/jerone/UserScripts/master/_resources/Install-button.png)](https://raw.githubusercontent.com/don-vip/wikichoux-scripts/master/wc-french_parliament_images.user.js)

## Python scripts

Python scripts require Python 3 and [requests](https://pypi.org/project/requests/) (`pip install requests`).

### Complete French deputy positions on Wikidata from Sycomore

[`sycomore_legislatures.py`](sycomore_legislatures.py) completes the "position held: member of the French National Assembly" ([P39](https://www.wikidata.org/wiki/Property:P39)) statements of Wikidata items, for every legislature since 1789, from the [Sycomore](https://www2.assemblee-nationale.fr/sycomore/) database of the French National Assembly. Deputies are matched through their Sycomore ID ([P1045](https://www.wikidata.org/wiki/Property:P1045)).

For each mandate read on a Sycomore record:

- if a Wikidata mandate has the same dates, the legislature ([P2937](https://www.wikidata.org/wiki/Property:P2937)) is added, and the constituency ([P768](https://www.wikidata.org/wiki/Property:P768)) if missing;
- if no Wikidata mandate matches, a new one is created with dates, legislature and constituency, referenced by the Sycomore record;
- if a Wikidata mandate spans several legislatures, and its start and end dates are those of the first and last Sycomore mandates it covers, it is split into one mandate per Sycomore mandate;
- anything else (different dates, ambiguous mandates, items missing or duplicated, unknown departments…) is reported as `TO CHECK` and left untouched.

Sycomore only gives the department. It is used as the constituency only for legislatures elected by departmental ballot, and the item chosen is the one that existed when the mandate started ([P571](https://www.wikidata.org/wiki/Property:P571)/[P576](https://www.wikidata.org/wiki/Property:P576)).

Usage:

```
# Simulation: reads Sycomore and Wikidata, writes nothing
python3 sycomore_legislatures.py --dry-run

# Only some legislatures (Sycomore IDs, see LEGISLATURES in the script)
python3 sycomore_legislatures.py --dry-run --legislatures 2,30,61

# Real run (a bot password is recommended)
WIKIDATA_PASSWORD=... python3 sycomore_legislatures.py --user "MyUser@MyBot"
```

If `WIKIDATA_PASSWORD` is not set, the script asks for the password. Records read from Sycomore are cached in `sycomore_cache.json` (or the file given with `--cache`), so the script can be restarted without downloading them again. A full run reads about 16,000 records and takes several hours. In dry-run mode, the simulated edits are taken into account when the same items are read again for later legislatures.

## Contributors

[List of contributors](https://github.com/don-vip/wikichoux-scripts/graphs/contributors)

… and thanks to [Projet Arcadie](https://projetarcadie.com/) for suggestions, feedback, and taking so much free pictures <3.

## License

[MIT](https://opensource.org/licenses/MIT)

## Tests

You can run automatic python tests with e.g.:
```
SHOW=1 pytest -s tests/
```

## Reporting bugs & Contributing

Please submit all patches to [github](https://github.com/don-vip/wikichoux-scripts/pulls) for review.
