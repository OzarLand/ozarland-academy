/*
 * Kolla-Ansible Academy portal: progressive enhancement only.
 *
 *  1. Search triggers: any [data-portal-search] button opens the theme's
 *     search dialog.
 *  2. assets/data/updates.json (written by tools/site/prebuild.py from the
 *     Git history) feeds the "Last updated" line of each page and the
 *     "Recently updated" list of the home page (at most N pages, whole days
 *     only; N is the value of data-portal-recent).
 *  3. Wide tables and diagrams scroll sideways inside a wrapper: a wrapper
 *     that really scrolls becomes reachable with the keyboard (Tab, then the
 *     arrow keys) and gets a name for screen readers.
 *  4. Release selector of the header (overrides/partials/releases.html). The
 *     list is in the page and every entry is a plain link to the home page
 *     of a release. Here: Escape and a click outside close the list, and a
 *     link to another available release opens the page being read in that
 *     release when its updates.json lists it, its home page otherwise.
 *
 * Nothing here carries content. When JavaScript is off or updates.json is
 * missing, the page simply shows less: both elements stay hidden or keep
 * their fallback.
 */
(function () {
  "use strict";

  /* ---------------------------------------------------------- 1. Search */

  function initSearchTriggers() {
    var search = document.querySelector('[data-md-component="search"]');
    // The theme hides its search when the index cannot be used.
    if (!search || search.hidden) return;
    var opener = search.querySelector("button") || search;
    document.querySelectorAll("[data-portal-search]").forEach(function (trigger) {
      trigger.hidden = false;
      trigger.addEventListener("click", function () {
        opener.click();
      });
    });
  }

  /* ----------------------------------------------------- 2. updates.json */

  var ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

  function timeElement(date) {
    var time = document.createElement("time");
    time.dateTime = date;
    time.textContent = date;
    return time;
  }

  function fillLastUpdated(pages) {
    var line = document.querySelector("[data-portal-updated]");
    if (!line) return;
    var url = line.getAttribute("data-portal-updated");
    var page = pages.find(function (entry) {
      return entry.url === url;
    });
    if (!page || !ISO_DATE.test(page.updated)) return;
    line.textContent = "Last updated ";
    line.appendChild(timeElement(page.updated));
    line.hidden = false;
  }

  // Most recently updated pages, whole days only: pages that share a date
  // cannot be ranked, so a day is listed in full or not at all. Right after
  // a commit that touches every page there is no list, only the page's own
  // fallback sentence.
  function mostRecent(pages, limit) {
    var dated = pages
      .filter(function (entry) {
        return entry.url !== "" && entry.title && ISO_DATE.test(entry.updated);
      })
      .sort(function (a, b) {
        return a.updated < b.updated ? 1 : a.updated > b.updated ? -1 : a.title.localeCompare(b.title);
      });
    var recent = [];
    for (var start = 0; start < dated.length; ) {
      var end = start;
      while (end < dated.length && dated[end].updated === dated[start].updated) end++;
      if (end > limit) break;
      recent = dated.slice(0, end);
      start = end;
    }
    return recent;
  }

  function fillRecentlyUpdated(pages, base) {
    var target = document.querySelector("[data-portal-recent]");
    if (!target) return;
    var limit = parseInt(target.getAttribute("data-portal-recent"), 10) || 8;
    var recent = mostRecent(pages, limit);
    if (!recent.length) return;

    var list = document.createElement("ul");
    list.className = "portal-recent";
    recent.forEach(function (entry) {
      var item = document.createElement("li");
      var link = document.createElement("a");
      link.href = new URL(entry.url, base).href;
      link.textContent = entry.title;
      item.appendChild(link);
      item.appendChild(timeElement(entry.updated));
      list.appendChild(item);
    });
    // The fallback sentence of the page (link to the commit history) stays below.
    target.prepend(list);
  }

  function initUpdates() {
    var meta = document.querySelector('meta[name="portal-updates"]');
    if (!meta || !window.fetch) return;
    if (!document.querySelector("[data-portal-updated], [data-portal-recent]")) return;
    var source = new URL(meta.content, document.baseURI);
    // updates.json lives in <site>/assets/data/: the site root is two levels up.
    var base = new URL("../../", source);
    fetch(source)
      .then(function (response) {
        return response.ok ? response.json() : null;
      })
      .then(function (data) {
        if (!data || !Array.isArray(data.pages)) return;
        fillLastUpdated(data.pages);
        fillRecentlyUpdated(data.pages, base);
      })
      .catch(function () {
        /* No file, no network, invalid JSON: stay silent. */
      });
  }

  /* ------------------------------------------------- 3. Scrolling regions */

  function nameOf(region) {
    // The nearest heading above the table or diagram, when there is one.
    for (var el = region; el && !el.matches("article"); el = el.parentElement) {
      for (var prev = el.previousElementSibling; prev; prev = prev.previousElementSibling) {
        if (/^H[1-6]$/.test(prev.tagName)) {
          var text = prev.textContent.replace(/\u00b6/g, "").trim();
          if (text) return text;
        }
      }
    }
    return "";
  }

  function markScrollRegions() {
    document
      .querySelectorAll(".md-typeset__scrollwrap, .md-typeset div.mermaid")
      .forEach(function (region) {
        var scrolls = region.scrollWidth > region.clientWidth + 1;
        if (scrolls && !region.hasAttribute("tabindex")) {
          var kind = region.classList.contains("mermaid") ? "Diagram" : "Table";
          var name = nameOf(region);
          region.setAttribute("tabindex", "0");
          region.setAttribute("role", "region");
          region.setAttribute("aria-label", name ? kind + ": " + name : kind);
          region.setAttribute("data-portal-scroll", "");
        } else if (!scrolls && region.hasAttribute("data-portal-scroll")) {
          ["tabindex", "role", "aria-label", "data-portal-scroll"].forEach(function (attr) {
            region.removeAttribute(attr);
          });
        }
      });
  }

  function initScrollRegions() {
    // The theme wraps the tables, and Mermaid draws the diagrams, after this
    // script has started: look again once the page has settled.
    markScrollRegions();
    window.addEventListener("load", function () {
      markScrollRegions();
      setTimeout(markScrollRegions, 1500);
    });
    var pending;
    window.addEventListener("resize", function () {
      clearTimeout(pending);
      pending = setTimeout(markScrollRegions, 200);
    });
  }

  /* ---------------------------------------------------- 4. Release selector */

  function initReleases() {
    var box = document.querySelector("[data-portal-release]");
    if (!box) return;
    var menu = box.querySelector("details");
    if (menu) {
      var summary = menu.querySelector("summary");
      menu.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && menu.open) {
          menu.open = false;
          summary.focus();
        }
      });
      document.addEventListener("click", function (event) {
        if (menu.open && !menu.contains(event.target)) menu.open = false;
      });
      menu.addEventListener("focusout", function (event) {
        if (menu.open && event.relatedTarget && !menu.contains(event.relatedTarget)) menu.open = false;
      });
    }

    // Path of the page inside its release ("operations/reconfigure-nova/").
    // Empty on a home page, absent outside the site of a release.
    var page = box.getAttribute("data-page");
    if (!page || !window.fetch) return;
    box.querySelectorAll('a[data-portal-release-link="available"]').forEach(function (link) {
      if (link.hasAttribute("aria-current")) return;
      link.addEventListener("click", function (event) {
        if (event.defaultPrevented || event.button || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        var home = link.href;
        fetch(new URL("assets/data/updates.json", home))
          .then(function (response) {
            return response.ok ? response.json() : null;
          })
          .then(function (data) {
            var found =
              data &&
              Array.isArray(data.pages) &&
              data.pages.some(function (entry) {
                return entry.url === page;
              });
            window.location.assign(found ? new URL(page, home).href + window.location.hash : home);
          })
          .catch(function () {
            window.location.assign(home);
          });
      });
    });
  }

  /* --------------------------------------------------- 5. Search scope
   * Each site has its own search: the field of the search dialog says which
   * one ("Search VM runbooks"), so a reader does not expect results from the
   * other modules. The dialog of the theme lives in an open shadow root that
   * is created on first use; if its markup changes, the field keeps the
   * theme's placeholder. */

  function initSearchScope() {
    var meta = document.querySelector('meta[name="portal-search-scope"]');
    if (!meta || !window.MutationObserver) return;
    var label = "Search " + meta.content;
    function name(root) {
      var input = root.querySelector("input[role=combobox]");
      if (input && input.placeholder !== label) {
        input.placeholder = label;
        input.setAttribute("aria-label", label);
      }
    }
    function attach(root) {
      if (root.ozSearchScope) return;
      root.ozSearchScope = true;
      new MutationObserver(function () {
        name(root);
      }).observe(root, { childList: true, subtree: true });
      name(root);
    }
    function scan() {
      Array.prototype.forEach.call(document.body.children, function (element) {
        if (element.shadowRoot) attach(element.shadowRoot);
      });
    }
    new MutationObserver(scan).observe(document.body, { childList: true });
    scan();
  }

  /* ----------------------------------------------- 6. Search every module
   * The learning-path home (overrides/academy.html) searches the pages and
   * section headings of every site, from assets/data/portal-search.json
   * (tools/site/releases.py, portal_search): {sites: [{title, path}],
   * entries: [[site, location, page title, heading, extract]]}. Every word
   * of the query must appear; a match in a heading or a title ranks first.
   * The query is kept in the address (?q=) so a search can be shared. */

  function fold(text) {
    return text.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  }

  function initSearchAll() {
    var box = document.querySelector("[data-portal-search-all]");
    if (!box || !window.fetch) return;
    var form = box.querySelector("[data-portal-search-all-form]");
    var input = form.querySelector("input");
    var status = box.querySelector("[data-portal-search-all-status]");
    var list = box.querySelector("[data-portal-search-all-results]");
    var root = box.getAttribute("data-portal-root");
    var index = null;
    var loading = null;
    var pending = 0;
    input.disabled = false;
    status.textContent = "";

    function load() {
      if (!loading) {
        loading = fetch(box.getAttribute("data-portal-search-all"))
          .then(function (response) {
            if (!response.ok) throw new Error(response.status);
            return response.json();
          })
          .then(function (data) {
            index = data;
            data.entries.forEach(function (entry) {
              entry.push(fold(entry[2]), fold(entry[3]), fold(entry[4]));
            });
          })
          .catch(function () {
            status.textContent = "The search could not be loaded: use the search of each module.";
          });
      }
      return loading;
    }

    function score(entry, terms, phrase) {
      var total = entry[3] ? 0 : 2;
      // The words of the query side by side, in the title or the heading.
      if (phrase.indexOf(" ") > 0 && (entry[3] ? entry[6] : entry[5]).replace(/[^a-z0-9_]+/g, " ").indexOf(phrase) >= 0) total += 10;
      for (var i = 0; i < terms.length; i++) {
        var term = terms[i];
        var points = 0;
        // A page title (entry[5]) is worth more than a heading (entry[6]),
        // a match at the start of a word more than one inside it.
        var at = entry[5].indexOf(term);
        if (at >= 0) points = Math.max(points, at === 0 || !/[a-z0-9]/.test(entry[5][at - 1]) ? (entry[3] ? 4 : 12) : (entry[3] ? 2 : 8));
        at = entry[6].indexOf(term);
        if (at >= 0) points = Math.max(points, at === 0 || !/[a-z0-9]/.test(entry[6][at - 1]) ? 9 : 6);
        if (!points && entry[7].indexOf(term) >= 0) points = 1;
        if (!points) return 0;
        total += points;
      }
      return total;
    }

    function render(query) {
      list.textContent = "";
      var terms = fold(query).split(/[^a-z0-9_]+/).filter(function (term) {
        return term.length > 1;
      });
      if (!terms.length || !index) {
        status.textContent = "";
        return;
      }
      var found = [];
      var phrase = terms.join(" ");
      index.entries.forEach(function (entry) {
        var points = score(entry, terms, phrase);
        if (points) found.push([points + (index.sites[entry[0]].boost || 0), entry]);
      });
      found.sort(function (a, b) {
        return b[0] - a[0];
      });
      var perPage = {};
      var shown = 0;
      for (var i = 0; i < found.length && shown < 25; i++) {
        var entry = found[i][1];
        var site = index.sites[entry[0]];
        var key = entry[0] + " " + entry[1].split("#")[0];
        perPage[key] = (perPage[key] || 0) + 1;
        if (perPage[key] > 2) continue;
        shown += 1;
        var item = document.createElement("li");
        var link = document.createElement("a");
        link.href = root + site.path + entry[1];
        link.textContent = entry[3] || entry[2];
        item.appendChild(link);
        var where = document.createElement("span");
        where.className = "oz-search-all__where";
        where.textContent = site.title + (entry[3] ? " › " + entry[2] : "");
        item.appendChild(where);
        if (entry[4]) {
          var extract = document.createElement("p");
          extract.textContent = entry[4];
          item.appendChild(extract);
        }
        list.appendChild(item);
      }
      status.textContent = shown
        ? found.length > shown
          ? "The " + shown + " best of " + found.length + " matches."
          : shown + (shown === 1 ? " match." : " matches.")
        : "Nothing in the titles and headings. Try another word, or open a module and use its own search (the magnifier in its header), which reads the full text.";
    }

    function run() {
      var query = input.value.trim();
      if (window.history && history.replaceState) {
        var url = new URL(window.location.href);
        if (query) url.searchParams.set("q", query);
        else url.searchParams.delete("q");
        history.replaceState(null, "", url.href);
      }
      load().then(function () {
        render(query);
      });
    }

    input.addEventListener("focus", load);
    input.addEventListener("input", function () {
      clearTimeout(pending);
      pending = setTimeout(run, 150);
    });
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      run();
    });
    var initial = new URLSearchParams(window.location.search).get("q");
    if (initial) {
      input.value = initial;
      run();
    }
  }

  function init() {
    initSearchTriggers();
    initSearchScope();
    initSearchAll();
    initUpdates();
    initScrollRegions();
    initReleases();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();
