// ==UserScript==
// @name         Display Wikimedia picture of French representatives
// @namespace    https://github.org/don-vip/wikichoux-scripts
// @version      2026-02-25
// @description  Display picture of French representatives from their Wikidata item, on French Parliament websites (National Assembly and Senate)
// @match        https://www2.assemblee-nationale.fr/deputes/liste/photo
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

  /* =========================
     PLACEHOLDER CLONE
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
     MAIN
  ========================== */

  async function main() {
    const grid = document.querySelector("#grid");
    if (!grid) return;

    console.info("wc-french_parliament_images : starting");
    const deputies = [...grid.querySelectorAll(":scope > li")];

    const wikidataLis = deputies.map(li => {
      const placeholderLi = createPlaceholderLi(li);
      li.insertAdjacentElement("afterend", placeholderLi);
      return { originalLi: li, placeholderLi };
    });

    await processAllWikidataLis(wikidataLis);
    console.info("wc-french_parliament_images : done");
  }

  main();

})();
