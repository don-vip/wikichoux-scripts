#!/usr/bin/env python3
"""Complete French deputy positions (P39) on Wikidata from the Sycomore
database of the French National Assembly, for every legislature.

Legislatures are processed in chronological order, and the deputies of each
one in alphabetical order. For each mandate read on the Sycomore record:

- Wikidata mandate with the same dates: add the legislature (P2937) and, when
  missing, the constituency (P768);
- no matching Wikidata mandate: complete the deputy mandate without any
  qualifier if there is one, otherwise create a new one (dates, legislature,
  constituency), referenced by the Sycomore record;
- Wikidata mandate spanning several legislatures, whose start and end dates
  are those of the first and last Sycomore mandates it covers: split it into
  one mandate per Sycomore mandate;
- anything else (different dates, ambiguous mandates...) is reported as
  "TO CHECK" and left untouched.

Sycomore only gives the department: it is used as constituency only for
legislatures elected by departmental ballot, and the chosen item is the one
existing at the mandate start date (P571/P576).

On every mandate processed (created, completed, split or already existing),
the generic position "member of the French National Assembly" is replaced by
the position of its legislature when there is one (LEGISLATURE_POSITIONS, e.g.
"deputy to the Estates General of 1789", which also replaces a department
position), or else by the deputy position of its
department (e.g. "deputy of the Seine") when one exists: the department is the
constituency of the mandate, or else the one read on Sycomore.

Sycomore records are kept in a JSON cache, so the script can be restarted
without downloading everything again.
"""

import argparse
import datetime
import getpass
import html
import json
import os
import re
import sys
import time
import unicodedata

import requests

WIKIDATA = "https://www.wikidata.org/w/api.php"
SPARQL = "https://query.wikidata.org/sparql"
SYCOMORE = "https://www2.assemblee-nationale.fr/sycomore/"
CACHE = "sycomore_cache.json"
DEPUTY = "Q3044918"  # member of the French National Assembly
ASSEMBLY_PRESIDENT = "Q1758037"
SYCOMORE_DATABASE = "Q15271528"

# (Sycomore id, Wikidata item, elected by departmental ballot), in chronological order
LEGISLATURES = [
    (
        "1",
        "Q876424",
        False,
    ),  # Assemblée nationale constituante (1789), elected by bailliage
    ("2", "Q780457", True),  # Assemblée nationale législative (1791)
    ("3", "Q219825", True),  # Convention nationale
    ("4", "Q617290", True),  # Conseil des Cinq-Cents
    ("5", "Q727834", True),  # Corps législatif (1800-1814)
    ("12", "Q61009176", True),  # Chambre des députés des départements (1814)
    ("6", "Q199955", True),  # Chambre des représentants (Hundred Days)
    ("7", "Q1060780", True),  # Bourbon Restoration
    ("8", "Q3025325", True),
    ("9", "Q61001737", False),
    ("10", "Q51844414", False),
    ("13", "Q51844406", False),  # July Monarchy
    ("14", "Q51844400", False),
    ("15", "Q51844386", False),
    ("16", "Q51844381", False),
    ("17", "Q51844286", False),
    ("18", "Q33523154", False),
    ("19", "Q33522599", False),
    ("20", "Q2867090", True),  # Assemblée nationale constituante (1848)
    ("21", "Q2867094", True),  # Assemblée nationale législative (1849)
    ("22", "Q33523493", False),  # Second Empire
    ("23", "Q33758116", False),
    ("24", "Q33758518", False),
    ("25", "Q33759105", False),
    ("26", "Q2867086", True),  # Assemblée nationale (1871)
    ("27", "Q33754196", False),  # Third Republic
    ("28", "Q33757119", False),
    ("29", "Q33756706", False),
    ("30", "Q33756209", True),  # list ballot of 1885
    ("31", "Q33755832", False),
    ("32", "Q33755445", False),
    ("33", "Q33322771", False),
    ("34", "Q33323082", False),
    ("35", "Q33323183", False),
    ("36", "Q33369535", False),
    ("37", "Q33528422", False),
    ("38", "Q33724121", True),  # list ballot of 1919
    ("39", "Q16683492", True),  # list ballot of 1924
    ("40", "Q33728280", False),
    ("41", "Q16683508", False),
    ("42", "Q16683505", False),
    ("43", "Q24932926", True),  # Constituent assemblies of 1945 and 1946
    ("44", "Q24932932", True),
    ("45", "Q3154305", True),  # Fourth Republic
    ("46", "Q3146706", True),
    ("47", "Q3146696", True),
    ("48", "Q3154303", False),  # Fifth Republic
    ("49", "Q3146705", False),
    ("50", "Q3146694", False),
    ("51", "Q2380278", False),
    ("52", "Q3555150", False),
    ("53", "Q3552959", False),
    ("54", "Q3552950", False),
    ("55", "Q3552944", True),  # proportional ballot of 1986
    ("56", "Q3147021", False),
    ("57", "Q3570849", False),
    ("58", "Q3570394", False),
    ("59", "Q3570376", False),
    ("60", "Q3025921", False),
    ("61", "Q3570385", False),
    ("62", "Q24939798", False),
    ("63", "Q112567597", False),
    ("64", "Q126471296", False),
]
# Search parameters of the legislatures that cannot be searched by legislature id:
# the deputies of the Estates-General / Constituent Assembly are in a separate base
SPECIAL_SEARCHES = {
    "1": dict(
        base="etats_generaux",
        debutmin="17/06/1789",
        finmin="30/09/1791",
        choixdate="dateau",
        legislature="",
    ),
}
# Position replacing the generic one for all the mandates of a legislature,
# by legislature item (as in LEGISLATURES, not the assembly item)
LEGISLATURE_POSITIONS = {
    "Q876424": "Q59309522",  # deputy to the Estates General of 1789
    "Q219825": "Q20808382",  # deputy to the National Convention
    "Q617290": "Q28218611",  # member of the Council of Five Hundred
    "Q727834": "Q28226953",  # deputy to the Corps législatif (1800-1814)
    # Chamber of Representatives (Hundred Days, 1815)
    "Q199955": "Q73196649",
    # Chamber of Deputies of the Departments (Bourbon Restoration, 1814-1815, 1815-1830)
    "Q61009176": "Q115144034",
    "Q1060780": "Q115144034",
    "Q3025325": "Q115144034",
    "Q61001737": "Q115144034",
    "Q51844414": "Q115144034",
}
LEGISLATURE_INFO = {
    an_id: (qid, departmental) for an_id, qid, departmental in LEGISLATURES
}
assert set(LEGISLATURE_POSITIONS) <= {
    qid for _, qid, _ in LEGISLATURES
}, "LEGISLATURE_POSITIONS keys must be legislature items of LEGISLATURES: %s" % (
    set(LEGISLATURE_POSITIONS) - {qid for _, qid, _ in LEGISLATURES}
)
# Qualifiers of a mandate spanning several legislatures, and which piece(s) of the split keep them
SPLIT_QUALIFIERS = {
    "P580": None,
    "P582": None,
    "P2937": None,
    "P768": "all",
    "P1001": "all",
    "P1365": "first",
    "P1366": "last",
    "P1534": "last",
}
# French month names, as written on Sycomore records
MONTHS = [
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
]
# Departments (current, former, overseas, of Algeria, of Spain) and colonies
DEPARTMENT_CLASSES = [
    "Q6465",
    "Q19953632",
    "Q202216",
    "Q3044799",
    "Q3044810",
    "Q133156",
]
# Sycomore names missing or ambiguous on Wikidata whatever the date
DEPARTMENT_OVERRIDES = {
    "Basses-Alpes": "Q3131",
    "Rhône": "Q46130",
    "Mont-Blanc": "Q2528268",
    "Etablissements français de l’Inde": "Q646374",
}
# Words of the (French) edit summary for each kind of change
SUMMARY_WORDS = {
    "create": "création",
    "complete": "complément",
    "split": "découpage",
    "legislature": "législature",
    "constituency": "circonscription",
    "position": "fonction",
}

session = requests.Session()
session.headers["User-Agent"] = (
    "SycomoreLegislaturesBot/1.0 (https://github.com/don-vip/wikichoux-scripts)"
)


def get(url, **params):
    """GET with retries; a Sycomore outage pauses the script instead of stopping it."""
    attempt = 0
    while True:
        try:
            r = session.get(url, params=params, timeout=60)
            if r.status_code not in (429, 500, 502, 503, 504):
                r.raise_for_status()
                return r
            error = "HTTP %d" % r.status_code
        except (
            requests.ConnectionError,
            requests.Timeout,
            requests.exceptions.ChunkedEncodingError,
        ) as e:
            error = type(e).__name__
        attempt += 1
        if attempt >= 6 and not url.startswith(SYCOMORE):
            raise requests.HTTPError("%s: %s" % (url, error))
        delay = min(10 * attempt, 600)
        if attempt >= 6:
            print(
                "  (%s unavailable: %s, retrying in %d s)" % (url, error, delay),
                flush=True,
            )
        time.sleep(delay)


def api_get(**params):
    return get(WIKIDATA, format="json", formatversion="2", **params).json()


def api_post(already_done=None, **data):
    """POST with retries. Before sending again after a lost connection, already_done()
    can return the result of a request that was processed anyway (else None)."""
    data.update(format="json", formatversion="2", maxlag="5")
    attempt = 0
    while True:
        try:
            r = session.post(WIKIDATA, data=data, timeout=60)
            error = "HTTP %d" % r.status_code
        except (
            requests.ConnectionError,
            requests.Timeout,
            requests.exceptions.ChunkedEncodingError,
        ) as e:
            r, error = None, type(e).__name__
        if r is not None and r.status_code not in (500, 502, 503, 504):
            r.raise_for_status()
        else:
            attempt += 1
            if attempt >= 6:
                raise requests.HTTPError("%s: %s" % (WIKIDATA, error))
            delay = 10 * attempt
            print("  (Wikidata: %s, retrying in %d s)" % (error, delay), flush=True)
            time.sleep(delay)
            res = already_done and already_done()
            if res:
                return res
            continue
        res = r.json()
        if res.get("error", {}).get("code") in ("maxlag", "ratelimited"):
            time.sleep(int(r.headers.get("Retry-After", 10)))
            continue
        return res


def sparql(query):
    return get(SPARQL, query=query, format="json").json()["results"]["bindings"]


def qid_of(uri):
    return uri.rsplit("/", 1)[1]


def login(user, password):
    """Log in to Wikidata and return a CSRF token."""
    token = api_get(action="query", meta="tokens", type="login")["query"]["tokens"][
        "logintoken"
    ]
    res = api_post(action="login", lgname=user, lgpassword=password, lgtoken=token)
    if res.get("login", {}).get("result") != "Success":
        # Main account password (not a bot password): use clientlogin
        token = api_get(action="query", meta="tokens", type="login")["query"]["tokens"][
            "logintoken"
        ]
        res = api_post(
            action="clientlogin",
            username=user,
            password=password,
            logintoken=token,
            loginreturnurl="https://www.wikidata.org/",
        )
        if res.get("clientlogin", {}).get("status") != "PASS":
            sys.exit("Login failed: %s" % json.dumps(res, ensure_ascii=False))
    return api_get(action="query", meta="tokens")["query"]["tokens"]["csrftoken"]


# --- Sycomore ---------------------------------------------------------------


def sort_key(text):
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def sycomore_deputies(legislature):
    """[(Sycomore id, name)] of the deputies of a legislature, in alphabetical order."""
    params = dict(
        base="tous_departements",
        regle_nom="est",
        nom="",
        departement="",
        choixdate="intervalle",
        debutmin="  /  /    ",
        finmin="  /  /    ",
        dateau="  /  /    ",
        legislature=legislature,
        choixordre="chrono",
    )
    params.update(SPECIAL_SEARCHES.get(legislature, {}))
    deputies, offset = {}, 0
    while True:
        page = get(SYCOMORE + "resultats/%d" % offset, **params).text
        rows = re.findall(
            r'<td data-sort="([^"]*)">\s*<a href="/sycomore/fiche/(\d+)">(.*?)</a>',
            page,
            re.S,
        )
        for surname, sid, name in rows:
            name = re.sub(
                r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", name))
            ).strip()
            deputies[sid] = (sort_key(html.unescape(surname)), sort_key(name), name)
        total = re.search(r"trouvés : (\d+)", page)
        offset += 500
        if not rows or not total or offset >= int(total.group(1)):
            break
        time.sleep(0.5)
    return [(sid, v[2]) for sid, v in sorted(deputies.items(), key=lambda kv: kv[1])]


def wd_time(day, month, year):
    return "+%s-%02d-%02dT00:00:00Z" % (year, MONTHS.index(month) + 1, int(day))


def parse_fiche(page):
    """{legislature: [[start, end or None, department or None], ...]} in Wikidata format."""
    date = r"(\d+)(?:er)? (%s) (\d{4})" % "|".join(MONTHS)
    mandates = {}
    for m in re.finditer(
        r'<dt>Législature</dt>\s*<dd>\s*<a[^>]*href="/sycomore/liste/(\d+)".*?'
        r"<dt>Mandat</dt>\s*<dd>(.*?)</dd>(.*?)</dl>",
        page,
        re.S,
    ):
        text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", m.group(2))))
        dep = re.search(r"<dt>Département</dt>\s*<dd>(.*?)</dd>", m.group(3), re.S)
        dep = html.unescape(dep.group(1)).strip() if dep else None
        full = re.search(r"Du %s au %s" % (date, date), text)
        ongoing = re.search(r"Depuis le %s" % date, text)
        if full:
            mandate = [wd_time(*full.groups()[:3]), wd_time(*full.groups()[3:]), dep]
        elif ongoing:
            mandate = [wd_time(*ongoing.groups()), None, dep]
        else:
            mandate = [None, None, text.strip()]  # unknown format, reported later
        mandates.setdefault(m.group(1), []).append(mandate)
    return mandates


class FicheCache:
    """Parsed Sycomore records, saved to a JSON file every 50 downloads."""

    def __init__(self, path):
        self.path = path
        self.data = {}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                self.data = json.load(f)
        self.unsaved = 0

    def mandates(self, sid):
        if sid not in self.data:
            self.data[sid] = parse_fiche(get(SYCOMORE + "fiche/" + sid).text)
            time.sleep(0.5)
            self.unsaved += 1
            if self.unsaved >= 50:
                self.save()
        return self.data[sid]

    def save(self):
        with open(self.path + ".tmp", "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False)
        os.replace(self.path + ".tmp", self.path)
        self.unsaved = 0


# --- Wikidata ---------------------------------------------------------------


def sycomore_items():
    """Sycomore id (P1045) -> [QID]."""
    result = {}
    for b in sparql("SELECT ?item ?id WHERE { ?item wdt:P1045 ?id }"):
        result.setdefault(b["id"]["value"], []).append(qid_of(b["item"]["value"]))
    return result


def deputy_positions():
    """Deputy positions: subclasses of Q3044918, except assembly presidencies."""
    rows = sparql(
        "SELECT DISTINCT ?p WHERE { ?p wdt:P279+ wd:%s. MINUS { ?p wdt:P279* wd:%s } }"
        % (DEPUTY, ASSEMBLY_PRESIDENT)
    )
    return {DEPUTY} | {qid_of(b["p"]["value"]) for b in rows}


def department_positions():
    """Department QID -> deputy position of this department (P1001), when unique."""
    rows = sparql(
        "SELECT ?p ?d WHERE { ?p wdt:P279 wd:%s; wdt:P1001 ?d. "
        "FILTER NOT EXISTS { ?p wdt:P1001 ?other. FILTER(?other != ?d) } }" % DEPUTY
    )
    positions = {}
    for b in rows:
        positions.setdefault(qid_of(b["d"]["value"]), set()).add(
            qid_of(b["p"]["value"])
        )
    return {d: p.pop() for d, p in positions.items() if len(p) == 1}


class Departments:
    """Resolution of a department name into the item existing at a given date."""

    def __init__(self):
        self.labels, self.aliases, self.periods = {}, {}, {}
        rows = sparql(
            "SELECT DISTINCT ?d ?name ?kind ?start ?end WHERE { VALUES ?cls { %s } ?d wdt:P31 ?cls. "
            '{ ?d rdfs:label ?name. BIND("l" AS ?kind) } UNION { ?d skos:altLabel ?name. BIND("a" AS ?kind) } '
            'FILTER(LANG(?name) = "fr") OPTIONAL { ?d wdt:P571 ?start } OPTIONAL { ?d wdt:P576 ?end } }'
            % " ".join("wd:" + c for c in DEPARTMENT_CLASSES)
        )
        for b in rows:
            qid = qid_of(b["d"]["value"])
            names = self.labels if b["kind"]["value"] == "l" else self.aliases
            names.setdefault(b["name"]["value"], set()).add(qid)
            start, end = self.periods.get(qid, (None, None))
            # Several dates are possible: keep the widest period
            s = b.get("start", {}).get("value", "")[:10] or None
            e = b.get("end", {}).get("value", "")[:10] or None
            self.periods[qid] = (
                min(filter(None, [start, s]), default=None),
                max(filter(None, [end, e]), default=None),
            )

    def exists_at(self, qid, day):
        start, end = self.periods.get(qid, (None, None))
        return (start is None or start <= day) and (end is None or day < end)

    def resolve(self, name, start):
        """QID or None, and the error message if any."""
        if not name:
            return None, "no department on the record"
        if name in DEPARTMENT_OVERRIDES:
            return DEPARTMENT_OVERRIDES[name], None
        day = start[1:11]
        for candidates in (self.labels.get(name, set()), self.aliases.get(name, set())):
            valid = {q for q in candidates if self.exists_at(q, day)}
            if len(valid) == 1:
                return valid.pop(), None
            if len(valid) > 1:
                return None, "department « %s » ambiguous on %s: %s" % (
                    name,
                    day,
                    ", ".join(sorted(valid)),
                )
        return None, "department « %s » not found on %s" % (name, day)


def item_id(snak):
    return (
        snak.get("datavalue", {}).get("value", {}).get("id")
        if snak.get("snaktype") == "value"
        else None
    )


def time_value(qualifiers, prop):
    for snak in qualifiers.get(prop, []):
        if snak.get("snaktype") == "value":
            return snak["datavalue"]["value"]
    return None


def day_range(value):
    """Range of days covered by a Wikidata date, according to its precision."""
    if value is None or value["precision"] < 9:
        return None
    year, month, day = value["time"][1:11].split("-")
    if value["precision"] == 9 or month == "00":
        return year + "-01-01", year + "-12-31"
    if value["precision"] == 10 or day == "00":
        return "%s-%s-01" % (year, month), "%s-%s-31" % (year, month)
    return (value["time"][1:11],) * 2


def overlaps(claim, start, end):
    qualifiers = claim.get("qualifiers", {})
    s, e = day_range(time_value(qualifiers, "P580")), day_range(
        time_value(qualifiers, "P582")
    )
    if not s and not e:
        return False
    lo, hi = (s or e)[0], (e or s)[1]
    return lo <= (end[1:11] if end else "9999") and hi >= start[1:11]


def same_dates(claim, start, end):
    qualifiers = claim.get("qualifiers", {})
    for prop, expected in (("P580", start), ("P582", end)):
        value = time_value(qualifiers, prop)
        if expected is None:
            if value is not None:
                return False
        elif value is None or value["precision"] != 11 or value["time"] != expected:
            return False
    return True


def contains(value, day):
    """Can the Wikidata date (according to its precision) denote this day?"""
    r = day_range(value)
    return r is not None and r[0] <= day[1:11] <= r[1]


def item_snak(prop, qid):
    return {
        "snaktype": "value",
        "property": prop,
        "datavalue": {
            "type": "wikibase-entityid",
            "value": {"entity-type": "item", "id": qid},
        },
    }


def time_snak(prop, value):
    return {
        "snaktype": "value",
        "property": prop,
        "datavalue": {
            "type": "time",
            "value": {
                "time": value,
                "timezone": 0,
                "before": 0,
                "after": 0,
                "precision": 11,
                "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
            },
        },
    }


def add_qualifier(claim, snak):
    claim.setdefault("qualifiers", {}).setdefault(snak["property"], []).append(snak)
    order = claim.setdefault("qualifiers-order", [])
    if snak["property"] not in order:
        order.append(snak["property"])


def new_claim(start, end, legislature, dep_qid, sycomore_id, position=DEPUTY):
    claim = {
        "type": "statement",
        "rank": "normal",
        "mainsnak": item_snak("P39", position),
    }
    if dep_qid:
        add_qualifier(claim, item_snak("P768", dep_qid))
    add_qualifier(claim, time_snak("P580", start))
    if end:
        add_qualifier(claim, time_snak("P582", end))
    add_qualifier(claim, item_snak("P2937", legislature))
    claim["references"] = [
        {
            "snaks-order": ["P248", "P1045", "P813"],
            "snaks": {
                "P248": [item_snak("P248", SYCOMORE_DATABASE)],
                "P1045": [
                    {
                        "snaktype": "value",
                        "property": "P1045",
                        "datavalue": {"type": "string", "value": sycomore_id},
                    }
                ],
                "P813": [
                    time_snak(
                        "P813", datetime.date.today().strftime("+%Y-%m-%dT00:00:00Z")
                    )
                ],
            },
        }
    ]
    return claim


def copy_claim(claim):
    return json.loads(json.dumps(claim))


# --- Processing -------------------------------------------------------------


class Bot:
    def __init__(self, token=None, legislatures=LEGISLATURES, cache=CACHE):
        """Without token, nothing is written to Wikidata (dry run)."""
        self.token = token
        self.user = (
            api_get(action="query", meta="userinfo")["query"]["userinfo"]["name"]
            if token
            else None
        )
        self.legislatures = legislatures
        self.cache = FicheCache(cache)
        self.by_sycomore = sycomore_items()
        self.positions = deputy_positions()
        self.department_positions = department_positions()
        self.departments = Departments()
        self.periods = {}
        # Dry run: QID -> {claim id: claim} of the edits not sent, applied to the entities read again later
        self.simulated = {}
        self.stats = {
            "qualified": 0,
            "created": 0,
            "completed": 0,
            "split": 0,
            "refined": 0,
            "already correct": 0,
            "to check": 0,
        }

    def entities(self, ids):
        """Wikidata items by batches of 50 (a Sycomore record can have several items)."""
        entities = {}
        for i in range(0, len(ids), 50):
            res = api_get(
                action="wbgetentities",
                ids="|".join(ids[i : i + 50]),
                props="claims|info",
            )
            if "entities" not in res:
                raise RuntimeError("wbgetentities: %s" % res.get("error"))
            entities.update(res["entities"])
        for qid, simulated in self.simulated.items():
            if qid in entities:
                p39 = entities[qid].setdefault("claims", {}).setdefault("P39", [])
                index = {c["id"]: i for i, c in enumerate(p39)}
                for cid, claim in simulated.items():
                    if cid in index:
                        p39[index[cid]] = claim
                    else:
                        p39.append(claim)
        return entities

    def exists_at(self, qid, day):
        """Does the item exist at this date (according to P571/P576)?"""
        if qid not in self.periods:
            claims = api_get(action="wbgetentities", ids=qid, props="claims")[
                "entities"
            ][qid].get("claims", {})
            days = {
                p: [
                    c["mainsnak"]["datavalue"]["value"]["time"][1:11]
                    for c in claims.get(p, [])
                    if c["mainsnak"].get("snaktype") == "value"
                ]
                for p in ("P571", "P576")
            }
            self.periods[qid] = (
                min(days["P571"], default=None),
                max(days["P576"], default=None),
            )
        start, end = self.periods[qid]
        return (start is None or start <= day[1:11]) and (
            end is None or day[1:11] < end
        )

    def problem(self, who, reason):
        self.stats["to check"] += 1
        print("  TO CHECK %s: %s" % (who, reason), flush=True)

    def constituency(self, who, dep, start, departmental):
        if not departmental:
            return None
        qid, error = self.departments.resolve(dep, start)
        if error:
            self.problem(who, "constituency not added, " + error)
        return qid

    def position(self, claim, legislature, dep, start):
        """Position of the legislature (replacing the generic position or a department
        one), or else deputy position of the department (replacing the generic position)
        of a mandate, or None if there is nothing more precise."""
        current = item_id(claim["mainsnak"])
        if legislature in LEGISLATURE_POSITIONS:
            if current == DEPUTY or current in self.department_positions.values():
                return LEGISLATURE_POSITIONS[legislature]
            return None
        if current != DEPUTY:
            return None
        deps = {item_id(s) for s in claim.get("qualifiers", {}).get("P768", [])} & set(
            self.department_positions
        )
        if len(deps) != 1:
            deps = {self.departments.resolve(dep, start)[0]} & set(
                self.department_positions
            )
        return self.department_positions[deps.pop()] if deps else None

    def refine(self, claim, legislature, dep, start, changed, actions):
        """Replace the generic position of a mandate by a more precise one."""
        position = self.position(claim, legislature, dep, start)
        if position:
            claim = changed.setdefault(claim["id"], copy_claim(claim))
            claim["mainsnak"] = item_snak("P39", position)
            actions.append("position")

    def run(self):
        for an_id, legislature, departmental in self.legislatures:
            deputies = sycomore_deputies(an_id)
            print(
                "\n=== Sycomore legislature %s (%s): %d deputies"
                % (an_id, legislature, len(deputies)),
                flush=True,
            )
            for i in range(0, len(deputies), 50):
                batch = deputies[i : i + 50]
                qids = {sid: self.by_sycomore.get(sid, []) for sid, _ in batch}
                entities = self.entities(
                    sorted({q for items in qids.values() for q in items})
                )
                for sid, name in batch:
                    if len(qids[sid]) != 1:
                        self.problem(
                            "%sfiche/%s (%s)" % (SYCOMORE, sid, name),
                            (
                                "no Wikidata item"
                                if not qids[sid]
                                else "several items: " + ", ".join(qids[sid])
                            ),
                        )
                        continue
                    qid = qids[sid][0]
                    self.process(
                        qid, entities[qid], sid, name, an_id, legislature, departmental
                    )
            self.cache.save()
        print("\nDone: %s" % ", ".join("%d %s" % (v, k) for k, v in self.stats.items()))

    def process(self, qid, entity, sid, name, an_id, legislature, departmental):
        who = "%s (%s)" % (qid, name)
        mandates = self.cache.mandates(sid).get(an_id, [])
        if not mandates:
            self.problem(
                who, "no mandate of this legislature read on Sycomore record %s" % sid
            )
            return
        claims = [
            c
            for c in entity.get("claims", {}).get("P39", [])
            if item_id(c["mainsnak"]) in self.positions
        ]
        tagged = [
            c
            for c in claims
            if legislature
            in {item_id(s) for s in c.get("qualifiers", {}).get("P2937", [])}
        ]
        free = [c for c in claims if not c.get("qualifiers", {}).get("P2937")]
        changed, used, actions, handled = {}, set(), [], set()

        for start, end, dep in mandates:
            if start in handled:  # already processed by the split of a mandate
                continue
            if start is None:
                self.problem(
                    who, "unreadable mandate on Sycomore record %s: %s" % (sid, dep)
                )
                continue
            # Mandate already qualified with this legislature
            done = [
                c
                for c in tagged
                if c["id"] not in used
                and (
                    len(mandates) == 1
                    or same_dates(c, start, end)
                    or overlaps(c, start, end)
                )
            ]
            if len(done) == 1:
                claim = done[0]
                used.add(claim["id"])
                count = len(actions)
                if not claim.get("qualifiers", {}).get("P768"):
                    dep_qid = self.constituency(who, dep, start, departmental)
                    if dep_qid:
                        claim = changed.setdefault(claim["id"], copy_claim(claim))
                        add_qualifier(claim, item_snak("P768", dep_qid))
                        actions.append("constituency")
                self.refine(claim, legislature, dep, start, changed, actions)
                if len(actions) == count:
                    self.stats["already correct"] += 1
                continue
            if len(done) > 1:
                self.problem(
                    who,
                    "%d mandates already qualified with legislature %s"
                    % (len(done), legislature),
                )
                continue

            candidates = [
                c
                for c in free
                if c["id"] not in used
                and (same_dates(c, start, end) or overlaps(c, start, end))
            ]
            exact = [c for c in candidates if same_dates(c, start, end)]
            if len(candidates) > 1 and len(exact) == 1:
                candidates = exact
            if len(candidates) > 1:
                self.problem(
                    who,
                    "%d candidate mandates for %s → %s"
                    % (len(candidates), start[1:11], end and end[1:11]),
                )
                continue
            if not candidates:
                dep_qid = self.constituency(who, dep, start, departmental)
                claim = new_claim(start, end, legislature, dep_qid, sid)
                position = self.position(claim, legislature, dep, start) or DEPUTY
                claim["mainsnak"] = item_snak("P39", position)
                # Deputy mandate without any qualifier: complete it instead of adding another one
                bare = [
                    c
                    for c in free
                    if c["id"] not in used
                    and item_id(c["mainsnak"]) in (DEPUTY, position)
                    and not c.get("qualifiers")
                ]
                if bare:
                    used.add(bare[0]["id"])
                    claim["id"] = bare[0]["id"]
                    claim["rank"] = bare[0].get("rank", "normal")
                    claim["references"] = [
                        {k: v for k, v in r.items() if k != "hash"}
                        for r in bare[0].get("references", [])
                    ] + claim["references"]
                    changed[claim["id"]] = claim
                    actions.append("complete")
                    continue
                changed["new%d" % len(changed)] = claim
                actions.append("create")
                continue
            claim = candidates[0]
            used.add(claim["id"])
            if not exact:
                pieces, error = self.split(who, claim, claims, sid)
                if pieces:
                    for i, piece in enumerate(pieces):
                        changed[piece.get("id", "new%d-%d" % (len(changed), i))] = piece
                    handled |= {
                        time_value(p["qualifiers"], "P580")["time"] for p in pieces
                    }
                    actions.append("split")
                    continue
                qualifiers = claim.get("qualifiers", {})
                wd = [time_value(qualifiers, p) for p in ("P580", "P582")]
                self.problem(
                    who,
                    "dates different from Sycomore %s (Wikidata %s → %s, Sycomore %s → %s)%s"
                    % (
                        sid,
                        *[v and v["time"][1:11] for v in wd],
                        start[1:11],
                        end and end[1:11],
                        ", split impossible: " + error if error else "",
                    ),
                )
                continue
            dep_qid = self.constituency(who, dep, start, departmental)
            claim = changed.setdefault(claim["id"], copy_claim(claim))
            add_qualifier(claim, item_snak("P2937", legislature))
            if dep_qid and not claim["qualifiers"].get("P768"):
                add_qualifier(claim, item_snak("P768", dep_qid))
            actions.append("legislature")
            self.refine(claim, legislature, dep, start, changed, actions)

        if changed:
            self.save(qid, who, entity, list(changed.values()), legislature, actions)

    def split(self, who, claim, claims, sid):
        """Split a Wikidata mandate covering several Sycomore mandates.
        Return (list of mandates to save, None) or (None, reason of the refusal)."""
        qualifiers = claim.get("qualifiers", {})
        wd_start, wd_end = time_value(qualifiers, "P580"), time_value(
            qualifiers, "P582"
        )
        mandates = sorted(
            (m[0], m[1], m[2], an_id)
            for an_id, ms in self.cache.mandates(sid).items()
            for m in ms
            if m[0] and an_id in LEGISLATURE_INFO and overlaps(claim, m[0], m[1])
        )
        if len(mandates) < 2:
            return None, None
        if not contains(wd_start, mandates[0][0]):
            return (
                None,
                "the start does not match the Sycomore mandate of %s"
                % mandates[0][0][1:11],
            )
        last_end = mandates[-1][1]
        if (wd_end is None) != (last_end is None) or (
            last_end and not contains(wd_end, last_end)
        ):
            return None, "the end does not match the Sycomore mandate ending on %s" % (
                last_end and last_end[1:11]
            )
        unknown = set(qualifiers) - set(SPLIT_QUALIFIERS)
        if unknown:
            return None, "qualifiers impossible to distribute: %s" % ", ".join(
                sorted(unknown)
            )
        for other in claims:
            if other["id"] != claim["id"] and any(
                overlaps(other, m[0], m[1])
                or LEGISLATURE_INFO[m[3]][0]
                in {item_id(s) for s in other.get("qualifiers", {}).get("P2937", [])}
                for m in mandates
            ):
                return (
                    None,
                    "another Wikidata mandate (%s) covers the same period"
                    % other["id"],
                )

        same_dep = len({m[2] for m in mandates}) == 1
        references = [
            {k: v for k, v in r.items() if k != "hash"}
            for r in claim.get("references", [])
        ]
        pieces = []
        for i, (start, end, dep, an_id) in enumerate(mandates):
            legislature, departmental = LEGISLATURE_INFO[an_id]
            piece = new_claim(start, end, legislature, None, sid)
            # The original position (e.g. member of the Convention) may only apply to the first mandate
            if i == 0:
                piece["mainsnak"] = claim["mainsnak"]
            piece["rank"] = claim.get("rank", "normal")
            piece["references"] = references + piece["references"]
            for prop, where in SPLIT_QUALIFIERS.items():
                if (
                    where is None
                    or where == "first"
                    and i > 0
                    or where == "last"
                    and i < len(mandates) - 1
                ):
                    continue
                for snak in qualifiers.get(prop, []):
                    value = item_id(snak)
                    # Constituency copied only if the department does not change and it exists at this date
                    if where == "all" and not (
                        same_dep and value and self.exists_at(value, start)
                    ):
                        continue
                    add_qualifier(piece, {k: v for k, v in snak.items() if k != "hash"})
            if not piece["qualifiers"].get("P768"):
                dep_qid = self.constituency(who, dep, start, departmental)
                if dep_qid:
                    add_qualifier(piece, item_snak("P768", dep_qid))
            position = self.position(piece, legislature, dep, start)
            if position:
                piece["mainsnak"] = item_snak("P39", position)
            pieces.append(piece)
        pieces[0]["id"] = claim["id"]  # the first piece replaces the original mandate
        return pieces, None

    def save(self, qid, who, entity, claims, legislature, actions):
        if self.token:

            def already_done():
                """Was the edit saved before the connection was lost?"""
                rev = api_get(
                    action="query", prop="revisions", titles=qid, rvprop="ids|user"
                )["query"]["pages"][0]["revisions"][0]
                if rev["revid"] == entity["lastrevid"]:
                    return None
                if rev["user"] != self.user:
                    return {
                        "error": {
                            "info": "connection lost, edited by %s since" % rev["user"]
                        }
                    }
                return {"success": 1}

            res = api_post(
                already_done=already_done,
                action="wbeditentity",
                id=qid,
                baserevid=entity["lastrevid"],
                token=self.token,
                data=json.dumps({"claims": claims}),
                summary="Mandat de député (législature [[%s]]) vérifié sur la base Sycomore : %s"
                % (legislature, ", ".join(sorted({SUMMARY_WORDS[a] for a in actions}))),
            )
            if "error" in res:
                self.problem(who, "API error: %s" % res["error"].get("info"))
                return
            time.sleep(1)
        else:
            simulated = self.simulated.setdefault(qid, {})
            for claim in claims:
                claim.setdefault("id", "%s$dry-run-%d" % (qid, len(simulated)))
                simulated[claim["id"]] = claim
        for action, stat in (
            ("create", "created"),
            ("complete", "completed"),
            ("split", "split"),
            ("position", "refined"),
        ):
            self.stats[stat] += actions.count(action)
        self.stats["qualified"] += actions.count("legislature") + actions.count(
            "constituency"
        )
        print("  %-11s %s" % (", ".join(sorted(set(actions))), who), flush=True)


def main():
    # The Windows console encoding (e.g. cp1252) cannot print every name or arrow
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--user",
        help="Wikidata login (bot password recommended), required unless --dry-run",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="do not write anything to Wikidata"
    )
    parser.add_argument(
        "--legislatures",
        help="comma-separated Sycomore legislature ids to process (default: all, e.g. 2,30,61)",
    )
    parser.add_argument(
        "--cache",
        default=CACHE,
        help="Sycomore records cache file (default: %(default)s)",
    )
    args = parser.parse_args()

    legislatures = LEGISLATURES
    if args.legislatures:
        wanted = args.legislatures.split(",")
        unknown = set(wanted) - set(LEGISLATURE_INFO)
        if unknown:
            parser.error("unknown legislatures: %s" % ", ".join(sorted(unknown)))
        legislatures = [leg for leg in LEGISLATURES if leg[0] in wanted]
    token = None
    if not args.dry_run:
        if not args.user:
            parser.error("--user is required unless --dry-run")
        session.headers["User-Agent"] = (
            "SycomoreLegislaturesBot/1.0 (https://www.wikidata.org/wiki/User:%s)"
            % (args.user.split("@")[0].replace(" ", "_"))
        )
        password = os.environ.get("WIKIDATA_PASSWORD") or getpass.getpass(
            "Wikidata password: "
        )
        token = login(args.user, password)

    bot = Bot(token, legislatures, args.cache)
    try:
        bot.run()
    finally:
        bot.cache.save()


if __name__ == "__main__":
    main()
