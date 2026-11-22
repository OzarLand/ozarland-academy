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

  function init() {
    initSearchTriggers();
    initSearchScope();
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
