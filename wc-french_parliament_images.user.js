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
  const IMAGE_WIDTH = "120px";
  const REQUEST_DELAY_MS = 150;
  const FALLBACK_IMAGE = "https://upload.wikimedia.org/wikipedia/commons/thumb/7/78/Sin_foto.svg/120px-Sin_foto.svg.png";
  const CACHE_PREFIX = "an_wd_photo_";
  const CACHE_EXPIRATION_DAYS = 1;
  const CACHE_EXPIRATION_MS = CACHE_EXPIRATION_DAYS * 24 * 60 * 60 * 1000;

  /* =========================
     CACHE
  ========================== */

  function setCachedImage(anId, imageUrl) {
    localStorage.setItem(CACHE_PREFIX + anId, JSON.stringify({
        url: imageUrl,
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
          return data.url;
      } catch (e) {
          localStorage.removeItem(CACHE_PREFIX + anId);
          return null;
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

  async function fetchWikidataImageByANId(anId) {
    const query = `
      SELECT ?image WHERE {
        ?person wdt:P4123 "${anId}";
                wdt:P18 ?image.
      }
      LIMIT 1
    `;

    const url =
      WD_ENDPOINT +
      "?format=json&query=" +
      encodeURIComponent(query);

    const response = await fetch(url, {
      headers: {
        "Accept": "application/sparql+json"
      }
    });

    if (!response.ok) return null;

    const data = await response.json();
    return data.results.bindings[0]?.image?.value ?? null;
  }

  /* =========================
     MAIN LOGIC
  ========================== */

  function cloneLiWithoutCurtain(originalLi, imageUrl) {
      const li = document.createElement("li");
      li.classList.add("shown");
      li.dataset.couleur = originalLi.dataset.couleur;
      li.dataset.urlimage = imageUrl;

      const originalA = originalLi.querySelector("a");
      if (originalA) {
          const newA = document.createElement("a");
          newA.href = commonsFilePageFromImageUrl(imageUrl);
          newA.title = "Photo issue de Wikimedia Commons (Wikidata)";
          newA.target = "_blank";

          const img = originalA.querySelector("img");
          const h3 = originalA.querySelector("h3");
          if (img) {
            const newImg = img.cloneNode(true);
            newImg.src = imageUrl;
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

  async function processDeputy(li) {
    const link = li.querySelector("a[href]");
    const img = li.querySelector("img");
    const h3 = li.querySelector("h3");

    if (!link || !img || !h3) return;

    const anId = extractANIdentifier(link.getAttribute("href"));
    if (!anId) return;

    let imageUrl = getCachedImage(anId);
    if (!imageUrl) {
      try {
        imageUrl = await fetchWikidataImageByANId(anId) ?? FALLBACK_IMAGE;
        setCachedImage(anId, imageUrl);
      } catch (e) {
        console.warn("Wikidata error for AN ID", anId, e);
        return;
      }
    }

    // Insert Wikimedia image just after official one
    li.insertAdjacentElement("afterend", cloneLiWithoutCurtain(li, imageUrl));
  }

  async function main() {
    const grid = document.querySelector("#grid");
    if (!grid) return;

    const deputies = [...grid.querySelectorAll(":scope > li")];

    for (const li of deputies) {
      await processDeputy(li);
      await new Promise(r => setTimeout(r, REQUEST_DELAY_MS));
    }

    console.info("wc-french_parliament_images : done");
  }

  main();
})();
