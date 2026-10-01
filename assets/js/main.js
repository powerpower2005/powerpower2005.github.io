(function () {
  "use strict";
  var root = document.documentElement;
  var darkQuery = window.matchMedia("(prefers-color-scheme: dark)");
  var mobileQuery = window.matchMedia("(max-width: 759px)");
  var post = document.querySelector("article.post");
  var content = document.querySelector(".post-content");

  function parseJSON(text, fallback) { try { return JSON.parse(text || ""); } catch (e) { return fallback; } }
  var T = parseJSON(post && post.getAttribute("data-i18n"), {});
  var isEn = (root.lang || "").indexOf("en") === 0;
  if (!T.copy) T = isEn ? { copy: "Copy", copied: "Copied", copyLink: "Copy link" } : { copy: "복사", copied: "복사됨", copyLink: "링크 복사" };

  function esc(s) { var d = document.createElement("div"); d.textContent = s == null ? "" : String(s); return d.innerHTML; }

  /* ───────── 토스트 ───────── */
  var toastTimer;
  function toast(msg) {
    var el = document.querySelector(".bc-toast");
    if (!el) return;
    el.textContent = msg;
    el.hidden = false;
    requestAnimationFrame(function () { el.classList.add("show"); });
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () {
      el.classList.remove("show");
      setTimeout(function () { el.hidden = true; }, 250);
    }, 4500);
  }

  /* ───────── 다크 모드 ───────── */
  function currentTheme() {
    var t = root.getAttribute("data-theme");
    if (t === "light" || t === "dark") return t;
    return darkQuery.matches ? "dark" : "light";
  }
  function giscusTheme() { return currentTheme() === "dark" ? "noborder_dark" : "noborder_light"; }
  function syncGiscus() {
    var frame = document.querySelector("iframe.giscus-frame");
    if (frame) frame.contentWindow.postMessage({ giscus: { setConfig: { theme: giscusTheme() } } }, "https://giscus.app");
  }
  var toggle = document.querySelector(".theme-toggle");
  if (toggle) toggle.addEventListener("click", function () {
    var next = currentTheme() === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    try { localStorage.setItem("theme", next); } catch (e) {}
    syncGiscus();
  });
  if (darkQuery.addEventListener) darkQuery.addEventListener("change", syncGiscus);

  /* ───────── 검색 단축키 (⌘K / Ctrl+K) ───────── */
  var searchLink = document.querySelector(".icon-link");
  var isMac = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
  var kbd = document.querySelector(".kbd");
  if (kbd && !isMac) kbd.textContent = "Ctrl K";
  document.addEventListener("keydown", function (e) {
    if ((e.metaKey || e.ctrlKey) && (e.key || "").toLowerCase() === "k" && searchLink) {
      e.preventDefault();
      var input = document.querySelector(".search-input");
      if (input) input.focus(); else location.href = searchLink.href;
    }
  });

  /* ───────── 휴대폰 메뉴 서랍 ───────── */
  var drawer = document.getElementById("drawer");
  var backdrop = document.querySelector(".drawer-backdrop");
  var menuBtn = document.querySelector(".menu-btn");
  function setDrawer(open) {
    if (!drawer) return;
    drawer.hidden = !open;
    backdrop.hidden = !open;
    if (menuBtn) menuBtn.setAttribute("aria-expanded", open ? "true" : "false");
    document.body.style.overflow = open ? "hidden" : "";
    if (open) { var c = drawer.querySelector(".drawer-close"); if (c) c.focus(); }
    else if (menuBtn) menuBtn.focus();
  }
  if (menuBtn) menuBtn.addEventListener("click", function () { setDrawer(true); });
  if (backdrop) backdrop.addEventListener("click", function () { setDrawer(false); });
  if (drawer) {
    drawer.querySelector(".drawer-close").addEventListener("click", function () { setDrawer(false); });
    drawer.addEventListener("click", function (e) { if (e.target.closest("a")) setDrawer(false); });
  }
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && drawer && !drawer.hidden) setDrawer(false); });
  mobileQuery.addEventListener && mobileQuery.addEventListener("change", function (e) { if (!e.matches && drawer && !drawer.hidden) setDrawer(false); });

  /* ───────── 목차 ───────── */
  function slug(text) {
    return text.trim().toLowerCase().replace(/[^\p{L}\p{N}\s-]/gu, "").replace(/\s+/g, "-");
  }
  function buildToc() {
    if (!content || !post) return;
    var headings = Array.prototype.slice.call(content.querySelectorAll(":scope > h2, :scope > h3"));
    var used = {};
    headings.forEach(function (h) {
      if (!h.id) {
        var base = slug(h.textContent) || "section", id = base, n = 1;
        while (used[id] || document.getElementById(id)) id = base + "-" + n++;
        h.id = id;
      }
      used[h.id] = true;
    });
    var min = parseInt(post.getAttribute("data-toc-min"), 10) || 3;
    if (post.hasAttribute("data-toc-off") || headings.length < min) return;

    document.querySelectorAll("ol.toc-list").forEach(function (ol) {
      headings.forEach(function (h) {
        var li = document.createElement("li");
        li.className = "toc-" + h.tagName.toLowerCase();
        var a = document.createElement("a");
        a.href = "#" + encodeURIComponent(h.id);
        a.textContent = h.textContent;
        a.setAttribute("data-target", h.id);
        a.addEventListener("click", function (e) {
          e.preventDefault();
          h.scrollIntoView({ behavior: "smooth", block: "start" });
          history.replaceState(null, "", "#" + encodeURIComponent(h.id));
        });
        li.appendChild(a);
        ol.appendChild(li);
      });
    });
    var body = document.querySelector(".toc-body");
    if (body) body.hidden = false;
    var mobile = document.querySelector(".toc-mobile");
    if (mobile) {
      mobile.hidden = false;
      var btn = mobile.querySelector(".toc-toggle"), list = mobile.querySelector(".toc-list"), icon = mobile.querySelector(".toc-icon");
      btn.addEventListener("click", function () {
        var open = list.hidden;
        list.hidden = !open;
        btn.setAttribute("aria-expanded", open ? "true" : "false");
        icon.textContent = open ? "−" : "+";
      });
    }

    // 읽는 중인 소제목: 화면 위 160px을 지나간 마지막 소제목
    var links = document.querySelectorAll(".toc-desktop .toc-list a");
    var ticking = false;
    function update() {
      ticking = false;
      var active = headings[0].id;
      headings.forEach(function (h) { if (h.getBoundingClientRect().top < 160) active = h.id; });
      links.forEach(function (a) { a.classList.toggle("active", a.getAttribute("data-target") === active); });
    }
    window.addEventListener("scroll", function () { if (!ticking) { ticking = true; requestAnimationFrame(update); } }, { passive: true });
    update();

    if (location.hash && location.hash.indexOf("#b-") !== 0) {
      var target = document.getElementById(decodeURIComponent(location.hash.slice(1)));
      if (target) target.scrollIntoView();
    }
  }

  /* ───────── 코드 블록: 언어 이름 + 복사 버튼 ───────── */
  function decorateCode() {
    if (!content) return;
    content.querySelectorAll("div.highlight").forEach(function (block) {
      var pre = block.querySelector("pre");
      var code = block.querySelector("code") || pre;
      if (!pre || block.querySelector(".code-head")) return;
      var wrap = block.closest("[class*='language-']");
      var m = wrap && wrap.className.match(/language-([\w+#-]+)/);
      var lang = m && m[1] !== "plaintext" && m[1] !== "text" ? m[1] : "";
      var head = document.createElement("div");
      head.className = "code-head";
      head.innerHTML = "<span>" + esc(lang) + "</span>";
      if (navigator.clipboard) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "copy-btn";
        btn.textContent = T.copy;
        btn.addEventListener("click", function () {
          navigator.clipboard.writeText(code.innerText.replace(/\n$/, "")).then(function () {
            btn.textContent = T.copied;
            btn.classList.add("done");
            setTimeout(function () { btn.textContent = T.copy; btn.classList.remove("done"); }, 1600);
          });
        });
        head.appendChild(btn);
      }
      block.insertBefore(head, pre);
    });
  }

  /* ───────── 이미지: 캡션 + 클릭 확대 ───────── */
  function decorateImages() {
    if (!content) return;
    content.querySelectorAll(":scope > p").forEach(function (p) {
      var media = p.querySelectorAll("img, video");
      if (media.length !== 1 || p.textContent.trim()) return;
      var el = media[0];
      p.classList.add("figure");
      var caption = el.getAttribute("title") || el.getAttribute("alt") || el.getAttribute("aria-label");
      if (caption) {
        var c = document.createElement("span");
        c.className = "figcaption";
        c.setAttribute("aria-hidden", "true");
        c.textContent = caption;
        p.appendChild(c);
      }
    });

    var overlay = document.querySelector(".zoom-overlay");
    if (!overlay) return;
    var big = overlay.querySelector("img");
    function close() { overlay.hidden = true; big.removeAttribute("src"); document.removeEventListener("keydown", onKey); }
    function onKey(e) { if (e.key === "Escape") close(); }
    overlay.addEventListener("click", close);
    content.addEventListener("click", function (e) {
      var img = e.target.closest("img");
      if (!img || img.closest("a")) return;
      big.src = img.currentSrc || img.src;
      big.alt = img.alt;
      overlay.hidden = false;
      document.addEventListener("keydown", onKey);
    });
  }

  /* ───────── 공유 ───────── */
  function enableShare() {
    var copy = document.querySelector("[data-copy-link]");
    if (copy) copy.addEventListener("click", function () {
      var url = location.href.split("#")[0];
      var done = function () {
        copy.textContent = T.copied;
        copy.classList.add("done");
        setTimeout(function () { copy.textContent = T.copyLink; copy.classList.remove("done"); }, 1600);
      };
      if (navigator.clipboard) navigator.clipboard.writeText(url).then(done);
      else window.prompt("", url);
    });
    var native = document.querySelector("[data-native-share]");
    if (native && navigator.share) {
      native.hidden = false;
      native.addEventListener("click", function () {
        navigator.share({ title: document.title, url: location.href.split("#")[0] }).catch(function () {});
      });
    }
  }

  /* ───────── 댓글 (giscus) ───────── */
  function loadGiscus() {
    var box = document.getElementById("giscus");
    if (!box) return;
    var s = document.createElement("script");
    s.src = "https://giscus.app/client.js";
    s.async = true;
    s.crossOrigin = "anonymous";
    var attrs = {
      "data-repo": box.dataset.repo,
      "data-repo-id": box.dataset.repoId,
      "data-category": box.dataset.category,
      "data-category-id": box.dataset.categoryId,
      "data-category-strict": "1",
      // 한국어판과 영어판이 같은 댓글창을 쓰도록 원본 글 기준의 고정 주제를 사용
      "data-mapping": "specific",
      "data-term": box.dataset.term,
      "data-strict": "1",
      "data-reactions-enabled": "1",
      "data-emit-metadata": "0",
      "data-input-position": "top",
      "data-lang": box.dataset.lang === "en" ? "en" : "ko",
      "data-loading": "lazy",
      "data-theme": giscusTheme()
    };
    Object.keys(attrs).forEach(function (k) { s.setAttribute(k, attrs[k]); });
    box.appendChild(s);
  }

  /* ───────── 문단 댓글 ───────── */
  function blockComments() {
    if (!content || !post) return;
    var blocks = Array.prototype.slice.call(content.querySelectorAll("[data-block]"));
    if (!blocks.length) return;
    var S = parseJSON(post.getAttribute("data-bc"), {});
    var dataEl = document.getElementById("block-threads");
    var data = dataEl ? (parseJSON(dataEl.textContent, {}).threads || {}) : {};
    var canWrite = !!document.getElementById("giscus");
    if (!canWrite && !Object.keys(data).length) return;

    var layer = document.createElement("div");
    layer.className = "bc-layer";
    post.appendChild(layer);
    var bubble = '<svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true"><path d="M4 5h16v11H9l-5 4z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>';
    var markers = [];
    function isHeading(b) { return /^H[1-6]$/.test(b.tagName); }

    blocks.forEach(function (b) {
      var list = data[b.getAttribute("data-block")];
      if (!list) return;
      var n = list.reduce(function (sum, c) { return sum + 1 + (c.replies ? c.replies.length : 0); }, 0);
      var m = document.createElement("button");
      m.type = "button";
      m.className = "bc-marker has-comments";
      m.innerHTML = bubble + "<span>" + n + "</span>";
      m.setAttribute("aria-label", n + " " + (S.count || ""));
      m.addEventListener("click", function (e) { e.stopPropagation(); current === b ? close() : open(b); });
      layer.appendChild(m);
      markers.push({ el: m, block: b });
    });

    var adder = null;
    if (canWrite) {
      adder = document.createElement("button");
      adder.type = "button";
      adder.className = "bc-marker bc-add";
      adder.innerHTML = bubble + "<span>+</span>";
      adder.setAttribute("aria-label", S.add || "");
      adder.hidden = true;
      adder.addEventListener("click", function (e) { e.stopPropagation(); if (adder._block) open(adder._block); });
      layer.appendChild(adder);
    }

    function topOf(b) { return b.getBoundingClientRect().top - post.getBoundingClientRect().top; }
    function markerX() {
      var gutter = parseFloat(getComputedStyle(post).paddingRight) || 56;
      return post.clientWidth - gutter + (mobileQuery.matches ? 4 : 16);
    }
    function place() {
      var x = markerX() + "px";
      markers.forEach(function (m) { m.el.style.left = x; m.el.style.top = topOf(m.block) + 4 + "px"; });
      if (adder && adder._block) { adder.style.left = x; adder.style.top = topOf(adder._block) + 4 + "px"; }
      if (panel && panel.classList.contains("bc-side") && current) panel.style.top = topOf(current) - 8 + "px";
    }
    place();
    if ("ResizeObserver" in window) { var ro = new ResizeObserver(place); ro.observe(content); ro.observe(post); }
    window.addEventListener("resize", function () { place(); if (panel) reopen(); });
    window.addEventListener("load", place);

    function showAdder(b) {
      if (!adder || isHeading(b)) { if (adder) adder.hidden = true; return; }
      adder._block = b;
      adder.hidden = !!data[b.getAttribute("data-block")];
      place();
    }
    var hoverable = window.matchMedia("(hover: hover)");
    content.addEventListener("mouseover", function (e) {
      if (!hoverable.matches) return;
      var b = e.target.closest("[data-block]");
      if (b) showAdder(b);
    });
    content.addEventListener("click", function (e) {
      if (hoverable.matches || e.target.closest("a, img, button, video, pre")) return;
      var b = e.target.closest("[data-block]");
      if (b) showAdder(b);
    });

    // 스레드 패널
    var panel = null, sheetBg = null, current = null;
    var palette = ["#6d5bd0", "#d0835b", "#3a8fd0", "#0f766e", "#b3478f", "#5b8a3a"];
    function avatar(c) {
      if (c.avatar) return '<img class="bc-avatar" src="' + esc(c.avatar) + '" alt="" loading="lazy">';
      var code = 0;
      for (var i = 0; i < (c.author || "").length; i++) code += c.author.charCodeAt(i);
      return '<span class="bc-avatar" style="background:' + palette[code % palette.length] + '">' + esc((c.author || "?").charAt(0).toUpperCase()) + "</span>";
    }
    function comment(c, reply) {
      return '<article class="bc-comment' + (reply ? " bc-reply" : "") + '"><header>' + avatar(c) +
        '<a class="bc-name" href="' + esc(c.profile) + '" target="_blank" rel="noopener">' + esc(c.author) + "</a>" +
        (c.owner ? '<span class="bc-badge">' + esc(S.author) + "</span>" : "") +
        '<a class="bc-date" href="' + esc(c.url) + '" target="_blank" rel="noopener">' + esc(c.date) + "</a></header>" +
        '<div class="bc-body">' + c.html + "</div></article>";
    }
    function useSide() {
      if (window.innerWidth < 1280) return false;
      return post.getBoundingClientRect().right + 12 + 320 <= window.innerWidth - 8;
    }
    function markerOf(b) { for (var i = 0; i < markers.length; i++) if (markers[i].block === b) return markers[i].el; return adder && adder._block === b ? adder : null; }

    function close() {
      if (!panel) return;
      panel.remove();
      if (sheetBg) sheetBg.remove();
      panel = sheetBg = null;
      if (current) {
        current.classList.remove("bc-active");
        var mk = markerOf(current);
        if (mk) mk.classList.remove("is-open");
      }
      current = null;
      document.body.style.overflow = "";
      document.removeEventListener("keydown", onKey);
    }
    function onKey(e) { if (e.key === "Escape") close(); }
    function reopen() { var b = current; close(); if (b) open(b); }

    function open(b) {
      close();
      current = b;
      b.classList.add("bc-active");
      var id = b.getAttribute("data-block");
      var list = data[id] || [];
      var side = useSide();
      panel = document.createElement("aside");
      panel.className = "bc-panel " + (side ? "bc-side" : "bc-sheet");
      panel.setAttribute("aria-label", S.title || "");
      var html = '<div class="bc-head"><strong>' + esc(S.title) + '</strong><button type="button" class="bc-close" aria-label="' + esc(S.close) + '">×</button></div><div class="bc-list">';
      list.forEach(function (c) {
        html += '<div class="bc-thread">' + comment(c, false);
        (c.replies || []).forEach(function (r) { html += comment(r, true); });
        html += '<a class="bc-reply-link" href="' + esc(c.url) + '" target="_blank" rel="noopener">' + esc(S.reply) + " ↗</a></div>";
      });
      if (!list.length) html += '<p class="bc-empty">' + esc(S.empty) + "</p>";
      html += "</div>";
      if (canWrite) html += '<div class="bc-foot"><button type="button" class="bc-write">' + esc(S.write) + '</button><p class="bc-note">' + esc(S.delay) + "</p></div>";
      panel.innerHTML = html;
      // 프로필 사진을 못 불러오면 이름 첫 글자로 대신 표시
      panel.querySelectorAll("img.bc-avatar").forEach(function (img) {
        img.addEventListener("error", function () {
          var name = img.parentNode.querySelector(".bc-name");
          var tmp = document.createElement("div");
          tmp.innerHTML = avatar({ author: name ? name.textContent : "?" });
          img.replaceWith(tmp.firstChild);
        });
      });
      if (side) {
        post.appendChild(panel);
        panel.style.top = topOf(b) - 8 + "px";
      } else {
        sheetBg = document.createElement("div");
        sheetBg.className = "bc-backdrop";
        sheetBg.addEventListener("click", close);
        document.body.appendChild(sheetBg);
        document.body.appendChild(panel);
        document.body.style.overflow = "hidden";
      }
      var mk = markerOf(b);
      if (mk) mk.classList.add("is-open");
      panel.querySelector(".bc-close").addEventListener("click", close);
      var w = panel.querySelector(".bc-write");
      if (w) w.addEventListener("click", function () { write(b); });
      document.addEventListener("keydown", onKey);
      history.replaceState(null, "", "#" + id);
    }

    // 댓글 쓰기: 문단 링크와 인용문을 복사하고 아래 댓글창으로 이동
    function write(b) {
      var id = b.getAttribute("data-block");
      var url = location.href.split("#")[0] + "#" + id;
      var text = (b.innerText || "").replace(/\s+/g, " ").trim();
      if (text.length > 80) text = text.slice(0, 80) + "…";
      var marker = "[¶ " + S.marker + "](" + url + ")\n> " + text + "\n\n";
      var done = function () { toast(S.copied); };
      if (navigator.clipboard) navigator.clipboard.writeText(marker).then(done, function () { window.prompt("", marker); });
      else window.prompt("", marker);
      close();
      var box = document.getElementById("giscus");
      if (box) box.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    document.addEventListener("click", function (e) {
      if (panel && !panel.contains(e.target) && !e.target.closest(".bc-marker") && !e.target.closest(".bc-backdrop")) close();
    });

    // 문단 링크(#b-…)로 들어오거나 주소의 문단 표시가 바뀌면 그 문단의 스레드를 엽니다
    function openFromHash() {
      var m = location.hash.match(/^#(b-[0-9a-f]{8}(?:-\d+)?)$/);
      if (!m) return;
      var target = content.querySelector('[data-block="' + m[1] + '"]');
      if (target && target !== current) { target.scrollIntoView({ block: "center" }); open(target); }
    }
    window.addEventListener("hashchange", openFromHash);
    openFromHash();
  }

  /* ───────── 태그 화면: 하나만 골라 보기 ───────── */
  function tagFilter() {
    var chips = document.querySelectorAll(".tag-chip");
    if (!chips.length) return;
    var groups = document.querySelectorAll(".tag-group");
    var sideRows = document.querySelectorAll(".side-row[data-tag]");
    function apply() {
      var tag = decodeURIComponent(location.hash.slice(1));
      var exists = tag && document.getElementById(tag);
      if (!exists) tag = "";
      groups.forEach(function (g) { g.hidden = !!tag && g.id !== tag; });
      chips.forEach(function (c) { c.classList.toggle("is-active", c.getAttribute("data-tag") === tag); });
      sideRows.forEach(function (r) { r.classList.toggle("is-active", r.getAttribute("data-tag") === tag); });
      if (tag) window.scrollTo(0, 0);
    }
    chips.forEach(function (c) {
      c.addEventListener("click", function (e) {
        e.preventDefault();
        var tag = c.getAttribute("data-tag");
        history.replaceState(null, "", tag ? "#" + tag : location.pathname);
        apply();
      });
    });
    window.addEventListener("hashchange", apply);
    apply();
  }

  /* ───────── 검색 (Pagefind) ───────── */
  function search() {
    var box = document.querySelector(".search");
    if (!box) return;
    var input = box.querySelector(".search-input");
    var out = box.querySelector(".search-results");
    var label = box.getAttribute("data-results");
    var empty = box.getAttribute("data-empty");
    var pagefind = null, seq = 0, timer;

    function load() {
      if (pagefind) return Promise.resolve(pagefind);
      return import(box.getAttribute("data-pagefind")).then(function (pf) {
        pagefind = pf;
        return pf.options ? pf.options({ excerptLength: 28 }).then(function () { return pf; }) : pf;
      });
    }
    function highlight(text, terms) {
      var html = esc(text);
      terms.forEach(function (t) {
        if (!t) return;
        var re = new RegExp("(" + t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")", "gi");
        html = html.replace(re, "<mark>$1</mark>");
      });
      return html;
    }
    function render(q, results) {
      if (!q) { out.innerHTML = ""; return; }
      if (!results.length) { out.innerHTML = '<p class="search-empty">' + esc(empty) + "</p>"; return; }
      var terms = q.split(/\s+/).filter(Boolean);
      var html = '<p class="search-count">' + results.length + esc(label) + "</p>";
      results.forEach(function (r) {
        var meta = [r.meta.date, r.meta.tags].filter(Boolean).join(" · ");
        html += '<a class="search-result" href="' + esc(r.url) + '">' +
          '<span class="search-result-title">' + highlight(r.meta.title || r.url, terms) + "</span>" +
          '<span class="search-result-excerpt">' + r.excerpt + "</span>" +
          (meta ? '<span class="search-result-meta">' + esc(meta) + "</span>" : "") + "</a>";
      });
      out.innerHTML = html;
    }
    function run() {
      var q = input.value.trim();
      var my = ++seq;
      var url = new URL(location.href);
      if (q) url.searchParams.set("q", q); else url.searchParams.delete("q");
      history.replaceState(null, "", url);
      if (!q) { render("", []); return; }
      load().then(function (pf) { return pf.search(q); }).then(function (res) {
        return Promise.all(res.results.slice(0, 30).map(function (r) { return r.data(); }));
      }).then(function (items) {
        if (my === seq) render(q, items);
      }).catch(function () {
        if (my === seq) out.innerHTML = '<p class="search-empty">' + (isEn ? "The search index is built during deployment." : "검색 색인은 배포할 때 만들어져요. 내 컴퓨터에서는 README의 검색 확인 방법을 참고하세요.") + "</p>";
      });
    }
    input.addEventListener("input", function () { clearTimeout(timer); timer = setTimeout(run, 150); });
    input.addEventListener("keydown", function (e) {
      if (e.key === "Escape") { input.value = ""; run(); }
    });
    var q = new URLSearchParams(location.search).get("q");
    if (q) { input.value = q; run(); }
    input.focus();
  }

  buildToc();
  decorateCode();
  decorateImages();
  enableShare();
  loadGiscus();
  blockComments();
  tagFilter();
  search();
})();
