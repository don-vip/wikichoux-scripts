// ==UserScript==
// @name         Display Wikimedia picture of French representatives
// @namespace    https://github.org/don-vip/wikichoux-scripts
// @version      2026-02-27
// @description  Display picture of French representatives from their Wikidata item, on French Parliament websites (National Assembly and Senate)
// @match        https://www2.assemblee-nationale.fr/deputes/liste/alphabetique
// @match        https://www2.assemblee-nationale.fr/deputes/liste/clos
// @match        https://www2.assemblee-nationale.fr/deputes/liste/departements
// @match        https://www2.assemblee-nationale.fr/deputes/liste/groupe-politique
// @match        https://www2.assemblee-nationale.fr/deputes/liste/photo
// @match        https://www2.assemblee-nationale.fr/deputes/liste/regions
// @match        https://www2.assemblee-nationale.fr/deputes/liste/tableau
// @match        https://www.assemblee-nationale.fr/dyn/seance-publique/derouleur
// @grant        none
// ==/UserScript==

(() => {
  "use strict";

  /* =========================
     CONFIG
  ========================== */

  const WD_ENDPOINT = "https://query.wikidata.org/sparql";
  const REQUEST_DELAY_MS = 150;
  const LOADING_IMAGE = "https://upload.wikimedia.org/wikipedia/commons/b/b1/Loading_icon.gif";
  const FALLBACK_IMAGE = "https://upload.wikimedia.org/wikipedia/commons/thumb/7/78/Sin_foto.svg/120px-Sin_foto.svg.png";
  const CACHE_PREFIX = "an_wd_photo_";
  const CACHE_EXPIRATION_DAYS = 1;
  const CACHE_EXPIRATION_MS = CACHE_EXPIRATION_DAYS * 24 * 60 * 60 * 1000;
  const CONCURRENCY = 5;

  /* =========================
     CACHE
  ========================== */

  function setCachedImage(anId, image, item) {
    localStorage.setItem(CACHE_PREFIX + anId, JSON.stringify({
        image,
        item,
        timestamp: Date.now()
    }));
  }

  function getCachedImage(anId) {
      const raw = localStorage.getItem(CACHE_PREFIX + anId);
      if (!raw) return null;

      try {
          const data = JSON.parse(raw);
          if (Date.now() - data.timestamp > CACHE_EXPIRATION_MS) {
              localStorage.removeItem(CACHE_PREFIX + anId);
              return null;
          }
          return { image: data.image, item: data.item };
      } catch (e) {
          localStorage.removeItem(CACHE_PREFIX + anId);
          return { image: null, item: null };
      }
  }

  /* =========================
     UTILS
  ========================== */

  function extractANIdentifier(href) {
    const match = href.match(/PA(\d+)/);
    return match ? match[1] : null;
  }

  function commonsFilePageFromImageUrl(imageUrl) {
    const fileName = decodeURIComponent(imageUrl.split("/").pop());
    return `https://commons.wikimedia.org/wiki/File:${fileName}`;
  }

  async function fetchWikidataImageAndItemByANId(anId) {
    const query = `
      SELECT ?person ?image WHERE {
        ?person wdt:P4123 "${anId}".
        OPTIONAL { ?person wdt:P18 ?image. }
      }
      LIMIT 1
    `;

    const url = WD_ENDPOINT + "?format=json&query=" + encodeURIComponent(query);
    const response = await fetch(url, {
      headers: {
        "Accept": "application/sparql+json"
      }
    });

    console.info("wc-french_parliament_images : " + response);

    if (!response.ok) return null;

    const data = await response.json();
    if (!data.results.bindings[0]) return { image: null, item: null };
    const b = data.results.bindings[0];
    return {
        image: b.image?.value ? forceHttps(b.image.value) : null,
        item: b.person?.value ?? null
    };
  }

  function forceHttps(url) {
    if (!url) return url;
    return url.replace(/^http:\/\//i, "https://");
  }

  function createMiniImageLink() {
    const a = document.createElement("a");
    a.href = "#";
    a.target = "_self";
    a.title = "Chargement…";
    a.style.display = "inline";
    a.style.whiteSpace = "nowrap";
    a.style.marginRight = "6px";
    a.style.verticalAlign = "middle";

    const img = document.createElement("img");
    img.src = LOADING_IMAGE;
    img.width = 16;
    img.height = 16;
    img.style.display = "inline";
    img.style.objectFit = "contain";
    img.style.verticalAlign = "middle";

    a.appendChild(img);
    return { a, img };
  }

  /* =========================
     https://www2.assemblee-nationale.fr/deputes/liste/alphabetique
     https://www2.assemblee-nationale.fr/deputes/liste/departements
     https://www2.assemblee-nationale.fr/deputes/liste/regions
     https://www2.assemblee-nationale.fr/deputes/liste/groupe-politique
  ========================== */

  async function fillAlphabeticalLi(anId, li, photoLink, img) {
    const cached = getCachedImage(anId);
    let imageUrl;
    let itemUrl;

    if (cached) {
      imageUrl = cached.image ?? FALLBACK_IMAGE;
      itemUrl = cached.item ?? null;
    } else {
      const wd = await fetchWikidataImageAndItemByANId(anId);
      imageUrl = wd.image ?? FALLBACK_IMAGE;
      itemUrl = wd.item ?? null;
      setCachedImage(anId, wd.image, wd.item);
    }

    const nameLink = li.querySelector("a[href*='/deputes/fiche/']");

    img.src = imageUrl !== FALLBACK_IMAGE
      ? imageUrl + "?width=16"
      : FALLBACK_IMAGE;

    if (imageUrl !== FALLBACK_IMAGE) {
      photoLink.href = commonsFilePageFromImageUrl(imageUrl);
      photoLink.target = "_blank";
      photoLink.title = "Photo via Wikimedia Commons";
      nameLink.style.color = "#1a7f37";
    } else if (itemUrl) {
      photoLink.href = itemUrl;
      photoLink.target = "_blank";
      photoLink.title = "Pas de photo, voir l’item Wikidata";
      nameLink.style.color = "#c1121f";
    } else {
      photoLink.href = "#";
      photoLink.title = "Pas de photo ni d’item Wikidata";
      photoLink.target = "_self";
      nameLink.style.color = "#c1121f";
    }
  }

  async function processAlphabeticalLis(lis) {
    let index = 0;

    async function worker() {
      while (index < lis.length) {
        const i = index++;
        const li = lis[i];
        const nameLink = li.querySelector("a");
        if (!nameLink) continue;

        const anId = extractANIdentifier(nameLink.href);
        if (!anId) continue;

        const { a: photoLink, img } = createMiniImageLink();
        nameLink.insertAdjacentElement("beforebegin", photoLink);

        await fillAlphabeticalLi(anId, li, photoLink, img);
        await new Promise(r => setTimeout(r, REQUEST_DELAY_MS));
      }
    }

    const workers = [];
    for (let i = 0; i < CONCURRENCY; i++) {
      workers.push(worker());
    }
    await Promise.all(workers);
  }

  /* =========================
     https://www2.assemblee-nationale.fr/deputes/liste/tableau
     https://www2.assemblee-nationale.fr/deputes/liste/clos
  ========================== */

  function addDeputesPhotoHeader(table) {
    const theadRow = table.querySelector("thead tr");
    if (!theadRow) return;

    const th = document.createElement("th");
    th.textContent = "Photo";
    th.style.width = "72px";
    th.style.textAlign = "center";

    theadRow.insertBefore(th, theadRow.firstChild);
  }

  function createDeputesPhotoCell() {
    const td = document.createElement("td");
    td.style.textAlign = "center";

    const a = document.createElement("a");
    a.href = "#";
    a.title = "Chargement…";

    const img = document.createElement("img");
    img.src = LOADING_IMAGE;
    img.width = 64;
    img.height = 64;
    img.style.objectFit = "contain";

    a.appendChild(img);
    td.appendChild(a);

    return { td, a, img };
  }

  async function fillDeputesRow(anId, nameLink, photoLink, img) {
    const cached = getCachedImage(anId);
    let imageUrl;
    let itemUrl;

    if (cached) {
      imageUrl = cached.image ?? FALLBACK_IMAGE;
      itemUrl = cached.item ?? null;
    } else {
      const wd = await fetchWikidataImageAndItemByANId(anId);
      imageUrl = wd.image ?? FALLBACK_IMAGE;
      itemUrl = wd.item ?? null;
      setCachedImage(anId, wd.image, wd.item);
    }

    img.src = imageUrl !== FALLBACK_IMAGE
      ? imageUrl + "?width=64"
      : FALLBACK_IMAGE;

    if (imageUrl !== FALLBACK_IMAGE) {
      photoLink.href = commonsFilePageFromImageUrl(imageUrl);
      photoLink.target = "_blank";
      photoLink.title = "Photo via Wikimedia Commons";
      nameLink.style.color = "#1a7f37";
    } else if (itemUrl) {
      photoLink.href = itemUrl;
      photoLink.target = "_blank";
      photoLink.title = "Pas de photo, voir l’item Wikidata";
      nameLink.style.color = "#c1121f";
    } else {
      photoLink.href = "#";
      photoLink.title = "Pas de photo ni d’item Wikidata";
      nameLink.style.color = "#c1121f";
    }
  }

  async function processDeputesTable(table) {
    addDeputesPhotoHeader(table);

    const rows = [...table.querySelectorAll("tbody tr")];
    let index = 0;

    async function worker() {
      while (index < rows.length) {
        const i = index++;
        const tr = rows[i];

        const nameLink = tr.querySelector("td a[href*='/deputes/fiche/']");
        if (!nameLink) continue;

        const anId = extractANIdentifier(nameLink.href);
        if (!anId) continue;

        const { td, a: photoLink, img } = createDeputesPhotoCell();

        tr.insertBefore(td, tr.firstChild);

        await fillDeputesRow(anId, nameLink, photoLink, img);
        await new Promise(r => setTimeout(r, REQUEST_DELAY_MS));
      }
    }

    const workers = [];
    for (let i = 0; i < CONCURRENCY; i++) {
      workers.push(worker());
    }
    await Promise.all(workers);
  }

  /* =========================
     https://www2.assemblee-nationale.fr/deputes/liste/photo
  ========================== */

  function createPlaceholderLi(originalLi) {
      const li = document.createElement("li");
      li.classList.add("shown");
      li.dataset.couleur = originalLi.dataset.couleur;
      li.dataset.urlimage = LOADING_IMAGE;

      const originalA = originalLi.querySelector("a");
      if (originalA) {
          const newA = document.createElement("a");
          newA.href = "#";
          newA.title = "Chargement...";
          newA.target = "_self";

          const img = originalA.querySelector("img");
          const h3 = originalA.querySelector("h3");
          if (img) {
            const newImg = img.cloneNode(true);
            newImg.src = LOADING_IMAGE;
            newA.appendChild(newImg);
          }
          if (h3) {
            const newH3 = h3.cloneNode(true);
            newH3.textContent = `${h3.textContent} (Wikimedia)`;
            newH3.style.opacity = "0.8";
            newA.appendChild(newH3);
          }

          li.appendChild(newA);
      }

      // Visual distinction
      li.style.outline = "2px dashed #777";
      li.style.outlineOffset = "-4px";

      return li;
  }

  async function fillWikidataLi(anId, placeholderLi) {
    const cached = getCachedImage(anId);
    let imageUrl; let itemUrl;

    if (cached) {
        imageUrl = cached.image ?? FALLBACK_IMAGE;
        itemUrl = cached.item ?? null;
    } else {
        const wd = await fetchWikidataImageAndItemByANId(anId);
        imageUrl = wd.image ?? FALLBACK_IMAGE;
        itemUrl = wd.item ?? null;
        setCachedImage(anId, wd.image, wd.item);
    }

    const a = placeholderLi.querySelector("a");
    const img = a.querySelector("img");
    const h3 = a.querySelector("h3");

    img.src = imageUrl + "?width=120";
    img.style.objectFit = "contain";

    if (imageUrl !== FALLBACK_IMAGE) {
        a.href = commonsFilePageFromImageUrl(imageUrl);
        a.title = "Photo via Wikimedia Commons (Wikidata)";
        a.target = "_blank";
        h3.textContent += " (Wikimedia)";
        h3.style.opacity = "0.8";
    } else if (itemUrl) {
        a.href = itemUrl;
        a.title = "Pas de photo, voir l'item Wikidata";
        a.target = "_blank";
        h3.textContent += " (Pas de photo)";
        h3.style.opacity = "0.5";
    } else {
        a.href = "#";
        a.title = "Pas de photo et item Wikidata introuvable";
        a.target = "_self";
        h3.textContent += " (Pas de photo)";
        h3.style.opacity = "0.5";
    }
  }

  async function processAllWikidataLis(wikidataLis) {
    let index = 0;

    async function worker() {
      while (index < wikidataLis.length) {
        const i = index++;
        const { originalLi, placeholderLi } = wikidataLis[i];
        const anId = extractANIdentifier(originalLi.querySelector("a").href);
        if (anId) {
          await fillWikidataLi(anId, placeholderLi);
          await new Promise(r => setTimeout(r, REQUEST_DELAY_MS));
        }
      }
    }

    const workers = [];
    for (let i = 0; i < CONCURRENCY; i++) workers.push(worker());
    await Promise.all(workers);
  }

  /* =========================
     https://www.assemblee-nationale.fr/dyn/seance-publique/derouleur
  ========================== */

  async function fetchDerouleurJson() {
    const url = "https://www.assemblee-nationale.fr/local/derouleur/derouleur.json";
    const res = await fetch(url);
    if (!res.ok) return null;
    return res.json();
  }

  function extractDeputesFromDerouleur(json) {
    const lignes = json?.racine?.contenu?.phase?.ligne;
    if (!Array.isArray(lignes)) return [];

    return lignes
      .filter(l =>
        l.ligne_libelle_1 &&
        l.depute_tribun_id &&
        l.ligne_amendement_uid
      )
      .map(l => ({
        anId: l.depute_tribun_id,
        libelle: l.ligne_libelle_1,
        uid: l.ligne_amendement_uid
      }));
  }

  function waitForDerouleurHtml() {
    return new Promise(resolve => {
      const check = () => {
        if (document.querySelector("span[id^='LIB_']")) {
          resolve();
        } else {
          setTimeout(check, 300);
        }
      };
      check();
    });
  }

  function extractDeputyLabel(text) {
    const m = text.match(/\b(M\.|Mme)\s+[A-ZÀ-Ÿ\-]+/);
    return m ? m[0] : null;
  }

  function observeDerouleurDomLive(linesByUid) {
    const observer = new MutationObserver(mutations => {
      for (const m of mutations) {
        for (const node of m.addedNodes) {
          if (!(node instanceof HTMLElement)) continue;

          // le span est ajouté directement
          if (node.matches?.("span[id^='LIB_']")) {
            const uid = node.id.replace("LIB_", "");
            const line = linesByUid.get(uid);
            if (line) enhanceDerouleurLine(line);
          }

          // ou il est plus profond
          const spans = node.querySelectorAll?.("span[id^='LIB_']");
          for (const span of spans || []) {
            const uid = span.id.replace("LIB_", "");
            const line = linesByUid.get(uid);
            if (line) enhanceDerouleurLine(line);
          }
        }
      }
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true
    });
  }

  function indexDerouleurLines(lines) {
    const map = new Map();
    for (const l of lines) {
      map.set(l.uid, l);
    }
    return map;
  }

  async function enhanceDerouleurLine({ anId, uid }) {
    const span = document.querySelector(`#LIB_${uid}`);
    if (!span) return;
    const originalText = span.textContent;
    const deputyLabel = extractDeputyLabel(originalText);
    if (!deputyLabel) return;

    if (span.dataset.wcEnhanced) return;
    span.dataset.wcEnhanced = "1";
    span.textContent = originalText.replace(deputyLabel, "").replace(/\s+$/, "") + " ";

    const { a: photoLink, img } = createMiniImageLink();

    const nameSpan = document.createElement("span");
    nameSpan.textContent = deputyLabel;
    nameSpan.style.display = "inline";
    nameSpan.style.whiteSpace = "nowrap";

    span.append(photoLink, document.createTextNode(" "), nameSpan);

    const cached = getCachedImage(anId);
    let imageUrl; let itemUrl;

    if (cached) {
      imageUrl = cached.image ?? FALLBACK_IMAGE;
      itemUrl = cached.item ?? null;
    } else {
      const wd = await fetchWikidataImageAndItemByANId(anId);
      imageUrl = wd.image ?? FALLBACK_IMAGE;
      itemUrl = wd.item ?? null;
      setCachedImage(anId, wd.image, wd.item);
    }

    img.src = imageUrl !== FALLBACK_IMAGE
      ? imageUrl + "?width=16"
      : FALLBACK_IMAGE;

    if (imageUrl !== FALLBACK_IMAGE) {
      photoLink.href = commonsFilePageFromImageUrl(imageUrl);
      photoLink.target = "_blank";
      nameSpan.style.color = "#1a7f37";
    } else if (itemUrl) {
      photoLink.href = itemUrl;
      photoLink.target = "_blank";
      nameSpan.style.color = "#c1121f";
    } else {
      photoLink.href = "#";
      nameSpan.style.color = "#c1121f";
    }
  }

  /* =========================
     MAIN
  ========================== */

  async function main() {
    console.info("wc-french_parliament_images : starting");

    const alphaLists = document.querySelectorAll(".col-container ul");
    if (alphaLists.length) {
      // https://www2.assemblee-nationale.fr/deputes/liste/alphabetique
      // https://www2.assemblee-nationale.fr/deputes/liste/departements
      // https://www2.assemblee-nationale.fr/deputes/liste/regions
      // https://www2.assemblee-nationale.fr/deputes/liste/groupe-politique
      const lis = [...document.querySelectorAll(".col-container ul li")];
      await processAlphabeticalLis(lis);
    } else {
      const grid = document.querySelector("#grid");
      if (grid) {
        // https://www2.assemblee-nationale.fr/deputes/liste/photo
        const deputies = [...grid.querySelectorAll(":scope > li")];
        const wikidataLis = deputies.map(li => {
          const placeholderLi = createPlaceholderLi(li);
          li.insertAdjacentElement("afterend", placeholderLi);
          return { originalLi: li, placeholderLi };
        });
        await processAllWikidataLis(wikidataLis);
      } else {
        const closTable = document.querySelector("table.clos");
        if (closTable) {
          // https://www2.assemblee-nationale.fr/deputes/liste/clos
          await processDeputesTable(closTable);
        } else {
          const deputesTable = document.querySelector("table.deputes");
          // https://www2.assemblee-nationale.fr/deputes/liste/tableau
          if (deputesTable) {
            await processDeputesTable(deputesTable);
          } else if (location.pathname.includes("/dyn/seance-publique/derouleur")) {
            // https://www.assemblee-nationale.fr/dyn/seance-publique/derouleur
            const json = await fetchDerouleurJson();
            if (json) {
              const lines = extractDeputesFromDerouleur(json);
              const indexed = indexDerouleurLines(lines);
              observeDerouleurDomLive(indexed);
            }
          }
        }
      }
    }

    console.info("wc-french_parliament_images : done");
  }

  main();

})();
