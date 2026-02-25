# Wikichoux scripts

[![Code validation](https://github.com/don-vip/wikichoux-scripts/actions/workflows/ci.yml/badge.svg)](https://github.com/don-vip/wikichoux-scripts/actions/workflows/ci.yml)

Collection of Tampermonkey scripts for Wikimedia French politics.

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
