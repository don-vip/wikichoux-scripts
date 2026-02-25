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

  async function processDeputy(li) {
    const link = li.querySelector("a[href]");
    const img = li.querySelector("img");
    const h3 = li.querySelector("h3");

    if (!link || !img || !h3) return;

    const anId = extractANIdentifier(link.getAttribute("href"));
    if (!anId) return;

    let imageUrl;
    try {
      imageUrl = await fetchWikidataImageByANId(anId);
    } catch (e) {
      console.warn("Wikidata error for AN ID", anId, e);
      return;
    }

    if (!imageUrl) return;

    // Clone original <li>
    const wikidataLi = li.cloneNode(true);

    const wikidataImg = wikidataLi.querySelector("img");
    const wikidataLink = wikidataLi.querySelector("a");
    const wikidataH3 = wikidataLi.querySelector("h3");

    // Replace image
    wikidataImg.src = imageUrl;
    wikidataImg.style.width = IMAGE_WIDTH;
    wikidataImg.style.objectFit = "contain";

    // Link to Commons file page
    wikidataLink.href = commonsFilePageFromImageUrl(imageUrl);
    wikidataLink.target = "_blank";
    wikidataLink.title = "Photo issue de Wikimedia Commons (Wikidata)";

    // Label
    wikidataH3.textContent = `${wikidataH3.textContent} (Wikimedia)`;
    wikidataH3.style.opacity = "0.8";

    // Visual distinction
    wikidataLi.style.outline = "2px dashed #777";
    wikidataLi.style.outlineOffset = "-4px";

    // Insert just after official entry
    li.insertAdjacentElement("afterend", wikidataLi);
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
