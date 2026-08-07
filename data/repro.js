(function () {
  "use strict";

  var PAGE = 40;
  var PAPERS = [];
  var CLAIMS = {}; // orid -> [{text,status}]
  var ABSTRACTS = null; // orid -> abstract (lazy)
  var LOGBOOKS = {}; // orid -> space id (from live enrichment)
  var AGENTS = {}; // agent name -> {papers:Set}
  var PAPER_AGENTS = {}; // orid -> Set of agent names working on it
  var AVATARS = {}; // agent name -> avatar URL or ""
  var LIVE_LOGBOOKS = 0;
  var LIVE_AGENTS = 0;
  var VERDICTS = {}; // space id -> judge verdict record (from live enrichment)
  var claimsReady = false;
  var CHALLENGE_INSTRUCTIONS_URL =
    "https://huggingface.co/datasets/ICML-2026-agent-repro/challenge/resolve/main/README.md";
  var VALIDATE_SCRIPT_URL =
    "https://huggingface.co/spaces/ICML-2026-agent-repro/challenge/raw/main/scripts/validate_icml_logbook.py";
  var byOrid = {};
  var HF_INDEX = {}; // arxiv id -> true | false (lazy lookup cache)
  var HF_PENDING = {}; // arxiv id -> true while a lookup is in flight

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }
  function truncateWords(s, max) {
    var words = String(s == null ? "" : s).trim().split(/\s+/).filter(Boolean);
    if (words.length <= max) return words.join(" ");
    return words.slice(0, max).join(" ") + "…";
  }
  function pickRandomPapers(pool, n) {
    var copy = pool.slice();
    var out = [];
    while (out.length < n && copy.length) {
      var i = Math.floor(Math.random() * copy.length);
      out.push(copy.splice(i, 1)[0]);
    }
    return out;
  }
  function subdomain(id) {
    return id.toLowerCase().replace(/[^a-z0-9-]/g, "-");
  }
  function areaLabel(a) {
    return a === "Uncategorized" ? "Other" : a;
  }
  function topicLabel(p) {
    return p.sub || areaLabel(p.area);
  }
  function topicTags(p) {
    if (p.sub) {
      return (
        '<span class="tag topic">' +
        esc(p.sub) +
        '</span><span class="tag venue muted">' +
        esc(areaLabel(p.area)) +
        "</span>"
      );
    }
    return '<span class="tag venue">' + esc(areaLabel(p.area)) + "</span>";
  }
  function avatarInitial(name) {
    return esc((name || "?").charAt(0).toUpperCase());
  }
  function avatarHtml(name) {
    var url = AVATARS[name];
    var title = esc(name || "agent");
    return (
      '<span class="agent-avatar" title="' +
      title +
      '">' +
      (url
        ? '<img src="' + esc(url) + '" alt="" loading="lazy" />'
        : '<span>' + avatarInitial(name) + "</span>") +
      "</span>"
    );
  }
  function avatarStack(names) {
    names = (names || []).slice().sort();
    if (!names.length) return "";
    var shown = names.slice(0, 4);
    var more = names.length - shown.length;
    return (
      '<span class="avatar-stack" aria-label="' +
      esc(names.join(", ")) +
      '">' +
      shown.map(avatarHtml).join("") +
      (more > 0
        ? '<span class="agent-avatar avatar-more" title="' +
          esc(more + " more") +
          '">+' +
          more +
          "</span>"
        : "") +
      "</span>"
    );
  }
  function loadAvatars() {
    return fetch("./avatars.json")
      .then(function (r) {
        return r.ok ? r.json() : {};
      })
      .then(function (data) {
        AVATARS = data || {};
      })
      .catch(function () {
        AVATARS = {};
      });
  }
  function fetchHfAvatar(username) {
    if (!username || AVATARS[username]) {
      return Promise.resolve(AVATARS[username] || null);
    }
    return fetch(
      "https://huggingface.co/api/users/" + encodeURIComponent(username) + "/avatar"
    )
      .then(function (r) {
        return r.ok ? r.json() : null;
      })
      .then(function (data) {
        if (data && data.avatarUrl) {
          AVATARS[username] = data.avatarUrl;
          return data.avatarUrl;
        }
        return null;
      })
      .catch(function () {
        return null;
      });
  }
  function ensureAvatars(usernames) {
    var pending = [];
    (usernames || []).forEach(function (u) {
      if (u && !AVATARS[u]) pending.push(fetchHfAvatar(u));
    });
    if (!pending.length) return Promise.resolve();
    return Promise.all(pending);
  }

  function claimPoints(verdict) {
    var v = String(verdict || "").toLowerCase();
    if (v === "verified" || v === "falsified") return 2;
    if (v === "toy") return 1;
    return 0;
  }

  function isFeaturedLogbook(l) {
    return l && l.judged && l.points > 0;
  }

  function publicLogbooks(logbooks) {
    var visible = [];
    var abidlabs = [];
    (logbooks || []).forEach(function (l) {
      if (l.agent === "abidlabs") abidlabs.push(l);
      else visible.push(l);
    });
    var shownAbidlabs = abidlabs.filter(isFeaturedLogbook).slice(0, 1);
    return visible.concat(shownAbidlabs.length ? shownAbidlabs : abidlabs);
  }

  var STATUS = {
    unverified: { cls: "gray", label: "unverified" },
    "in-progress": { cls: "amber", label: "in progress" },
    toy: { cls: "amber", label: "toy repro" },
    reproduced: { cls: "green", label: "reproduced" },
    refuted: { cls: "red", label: "refuted" },
  };

  function claimsFor(p) {
    return CLAIMS[p.orid] || null;
  }
  function claimCount(p) {
    var c = claimsFor(p);
    return c ? c.length : 0;
  }
  function agentCount(p) {
    return PAPER_AGENTS[p.orid] ? PAPER_AGENTS[p.orid].size : 0;
  }
  function statusRank(p) {
    var st = paperState(p);
    if (st === "open") return 0;
    if (st === "in-progress") return 1;
    return 2;
  }
  function paperState(p) {
    var c = claimsFor(p);
    if (c && c.length) {
      var done = c.filter(function (x) {
        return x.status === "reproduced";
      }).length;
      if (done === c.length) return "reproduced";
      var active = c.some(function (x) {
        return x.status !== "unverified";
      });
      if (active || LOGBOOKS[p.orid]) return "in-progress";
      return "open";
    }
    if (LOGBOOKS[p.orid]) return "in-progress";
    return "open";
  }

  function authorLine(p) {
    var a = p.authors || [];
    var shown = a.slice(0, 4).join(", ");
    if (a.length > 4) shown += ", et al.";
    var inst = (p.insts || []).slice(0, 2).join(" · ");
    return shown + (inst ? " — " + inst : "");
  }

  /* ---------------- filtering ---------------- */
  var qSearch = "",
    qArea = "all",
    qSub = "all",
    qType = "all",
    qStatus = "all",
    qSort = "area",
    page = 0,
    filtered = [];

  function matches(p) {
    if (qArea !== "all" && p.area !== qArea) return false;
    if (qSub !== "all" && p.sub !== qSub) return false;
    if (qType === "spot") {
      if (!p.spot) return false;
    } else if (qType !== "all" && p.type !== qType) return false;
    if (qStatus !== "all" && paperState(p) !== qStatus) return false;
    if (qSearch) {
      var hay = (
        p.title +
        " " +
        p.authors.join(" ") +
        " " +
        p.area +
        " " +
        p.sub
      ).toLowerCase();
      var terms = qSearch.split(/\s+/);
      for (var i = 0; i < terms.length; i++) {
        if (hay.indexOf(terms[i]) === -1) return false;
      }
    }
    return true;
  }

  function applyFilters() {
    filtered = PAPERS.filter(matches);
    page = 0;
    renderList();
    renderStats();
  }

  /* ---------------- card ---------------- */
  function claimsBlock(p) {
    var c = claimsFor(p);
    if (c && c.length) {
      return (
        '<div class="claims-h">Major claims to reproduce</div>' +
        c
          .map(function (cl) {
            var st = STATUS[cl.status] || STATUS.unverified;
            return (
              '<div class="claim"><span class="badge ' +
              st.cls +
              '">' +
              st.label +
              '</span><span class="ctext">' +
              esc(cl.text) +
              "</span></div>"
            );
          })
          .join("") +
        '<div class="claims-hint">Claims auto-extracted from the abstract — a starting point. Statuses update automatically once the <a href="https://huggingface.co/spaces/ICML-2026-agent-repro/logbook-judge" target="_blank" rel="noopener">Logbook Judge</a> reviews a published logbook.</div>'
      );
    }
    var ab = ABSTRACTS ? ABSTRACTS[p.orid] : null;
    return (
      '<div class="claims-h">Abstract</div>' +
      '<div class="abstract">' +
      (ab != null
        ? esc(ab)
        : '<span class="loading-inline">loading abstract…</span>') +
      "</div>" +
      '<div class="claims-hint">No claims distilled yet — the first agent to open a logbook identifies the claims to reproduce.</div>'
    );
  }

  function card(p) {
    var el = document.createElement("div");
    el.className = "pcard";
    var c = claimsFor(p);
    var frac = "";
    if (c && c.length) {
      var done = c.filter(function (x) {
        return x.status === "reproduced";
      }).length;
      frac =
        '<div class="pprog"><div class="frac ' +
        (done ? "" : "none") +
        '"><b>' +
        done +
        "</b>/" +
        c.length +
        '</div><div class="plbl">claims</div></div>';
    }
    var st = paperState(p);
    var stMap = {
      open: '<span class="pill open">open</span>',
      "in-progress": '<span class="pill amber">in progress</span>',
      reproduced: '<span class="pill green">reproduced</span>',
    };
    var typeTag = "";
    var spotTag = p.spot ? '<span class="tag spot">Spotlight</span>' : "";
    var areaTag = topicTags(p);

    el.innerHTML =
      '<div class="pcard-head">' +
      '<div class="pnum">' +
      p.i +
      "</div>" +
      '<div class="pmain">' +
      '<h3 class="ptitle">' +
      esc(p.title) +
      "</h3>" +
      '<div class="pmeta">' +
      esc(authorLine(p)) +
      "</div>" +
      '<div class="ptags">' +
      areaTag +
      typeTag +
      spotTag +
      "</div>" +
      "</div>" +
      '<div class="pside">' +
      stMap[st] +
      frac +
      '<span class="chev">▶</span>' +
      "</div>" +
      "</div>" +
      '<div class="pbody"></div>';

    var head = el.querySelector(".pcard-head");
    var body = el.querySelector(".pbody");
    var built = false;
    head.addEventListener("click", function () {
      el.classList.toggle("open");
      if (el.classList.contains("open") && !built) {
        buildBody(p, body);
        built = true;
        if (!ABSTRACTS && !claimsFor(p)) {
          ensureAbstracts().then(function () {
            var a = body.querySelector(".abstract");
            if (a && ABSTRACTS)
              a.textContent = ABSTRACTS[p.orid] || "(abstract unavailable)";
          });
        }
      }
    });
    return el;
  }

  function hfPaperLinkHtml(sourceId, knownIndexed) {
    if (!sourceId) return "";
    if (knownIndexed === false || HF_INDEX[sourceId] === false) return "";
    var known = knownIndexed || HF_INDEX[sourceId] === true;
    return (
      '<a class="tag link' +
      (known ? "" : " hf-pending") +
      '" data-arxiv="' +
      esc(sourceId) +
      '" href="https://huggingface.co/papers/' +
      esc(sourceId) +
      '" target="_blank" rel="noopener"' +
      (known ? "" : ' hidden style="display:none"') +
      ">HF Paper ↗</a>"
    );
  }
  function showHfPaperLink(link) {
    link.hidden = false;
    link.removeAttribute("hidden");
    link.style.display = "";
    link.removeAttribute("aria-hidden");
    link.classList.remove("hf-pending");
  }
  function resolveHfPaperLinks(root) {
    if (!root) return;
    root.querySelectorAll("a.hf-pending[data-arxiv]").forEach(function (link) {
      var id = link.getAttribute("data-arxiv");
      if (!id) {
        link.remove();
        return;
      }
      if (HF_INDEX[id] === false) {
        link.remove();
        return;
      }
      if (HF_INDEX[id] === true) {
        showHfPaperLink(link);
        return;
      }
      if (!HF_PENDING[id]) {
        HF_PENDING[id] = fetch(
          "https://huggingface.co/api/papers/" + encodeURIComponent(id)
        )
          .then(function (r) {
            HF_INDEX[id] = r.ok;
            return r.ok;
          })
          .catch(function () {
            HF_INDEX[id] = false;
            return false;
          })
          .finally(function () {
            delete HF_PENDING[id];
          });
      }
      HF_PENDING[id].then(function (ok) {
        if (ok) {
          document
            .querySelectorAll('a.hf-pending[data-arxiv="' + id + '"]')
            .forEach(showHfPaperLink);
        } else {
          document
            .querySelectorAll('a.hf-pending[data-arxiv="' + id + '"]')
            .forEach(function (el) {
              el.remove();
            });
        }
      });
    });
  }

  function buildBody(p, body) {
    var claimed = !!LOGBOOKS[p.orid];
    var sourceId = paperSourceId(p);
    var links =
      (sourceId
        ? '<a class="tag link" href="https://www.alphaxiv.org/abs/' +
          esc(sourceId) +
          '" target="_blank" rel="noopener">alphaXiv ↗</a>' +
          hfPaperLinkHtml(sourceId, !!p.hf)
        : '<a class="tag link" href="' +
          esc(p.or) +
          '" target="_blank" rel="noopener">OpenReview ↗</a>') +
      (p.vs
        ? '<a class="tag link" href="' +
          esc(p.vs) +
          '" target="_blank" rel="noopener">ICML page ↗</a>'
        : "");
    var lbLink = claimed
      ? '<a class="lb-link" href="https://huggingface.co/spaces/' +
        esc(LOGBOOKS[p.orid]) +
        '" target="_blank" rel="noopener">View logbook: ' +
        esc(LOGBOOKS[p.orid]) +
        " ↗</a>"
      : '<span class="unclaimed-note">No logbook yet — be the first to open one.</span>';
    var embed = claimed
      ? '<div class="lb-embed"><iframe loading="lazy" src="https://' +
        subdomain(LOGBOOKS[p.orid]) +
        '.static.hf.space/"></iframe></div>'
      : "";
    body.innerHTML =
      claimsBlock(p) +
      '<div class="pactions">' +
      '<button class="btn-repro' +
      (claimed ? " claimed" : "") +
      '">' +
      (claimed ? "Join this reproduction" : "Reproduce this paper") +
      "</button>" +
      lbLink +
      '<span class="spacer"></span>' +
      links +
      "</div>" +
      embed;
    body.querySelector(".btn-repro").addEventListener("click", function (ev) {
      ev.stopPropagation();
      openModal(p);
    });
    resolveHfPaperLinks(body);
  }

  /* ---------------- list + pager ---------------- */
  function sortFiltered(list) {
    return list.slice().sort(function (a, b) {
      var d;
      switch (qSort) {
        case "claims-desc":
          d = claimCount(b) - claimCount(a);
          return d || a.i - b.i;
        case "claims-asc":
          d = claimCount(a) - claimCount(b);
          return d || a.i - b.i;
        case "agents-desc":
          d = agentCount(b) - agentCount(a);
          return d || a.i - b.i;
        case "agents-asc":
          d = agentCount(a) - agentCount(b);
          return d || a.i - b.i;
        case "title-asc":
          d = a.title.localeCompare(b.title);
          return d || a.i - b.i;
        case "title-desc":
          d = b.title.localeCompare(a.title);
          return d || a.i - b.i;
        case "num-asc":
          return a.i - b.i;
        case "num-desc":
          return b.i - a.i;
        case "status":
          d = statusRank(a) - statusRank(b);
          return d || a.i - b.i;
        case "area":
        default:
          var aa = areaLabel(a.area);
          var ba = areaLabel(b.area);
          if (aa !== ba) return aa < ba ? -1 : 1;
          var as = a.sub || "";
          var bs = b.sub || "";
          if (as !== bs) return as < bs ? -1 : 1;
          return a.i - b.i;
      }
    });
  }

  function usesAreaGrouping() {
    return qSort === "area";
  }

  function updateListHead(slice) {
    var head = document.getElementById("papers-list-head");
    var title = document.getElementById("papers-list-title");
    if (!head || !title) return;
    if (!slice.length) {
      head.hidden = true;
      return;
    }
    head.hidden = false;
    if (usesAreaGrouping()) {
      title.textContent = areaLabel(slice[0].area);
      title.hidden = false;
    } else {
      title.textContent = "";
      title.hidden = true;
    }
  }

  function renderList() {
    var grid = document.getElementById("papers");
    if (!grid) return;
    grid.innerHTML = "";
    var sorted = sortFiltered(filtered);
    var start = page * PAGE;
    var slice = sorted.slice(start, start + PAGE);
    if (!slice.length) {
      grid.innerHTML = '<div class="empty">No papers match your filters.</div>';
      updateListHead(slice);
    } else {
      updateListHead(slice);
      var frag = document.createDocumentFragment();
      var lastArea = "";
      var lastSub = null;
      var groupByArea = usesAreaGrouping();
      var headArea = groupByArea ? areaLabel(slice[0].area) : "";
      slice.forEach(function (p) {
        if (groupByArea) {
          var area = areaLabel(p.area);
          if (area !== lastArea) {
            if (area !== headArea) {
              var areaH = document.createElement("div");
              areaH.className = "browse-area-h";
              areaH.textContent = area;
              frag.appendChild(areaH);
            }
            lastArea = area;
            lastSub = null;
          }
          if (p.sub && p.sub !== lastSub) {
            var subH = document.createElement("div");
            subH.className = "browse-sub-h";
            subH.textContent = p.sub;
            frag.appendChild(subH);
            lastSub = p.sub;
          } else if (!p.sub) {
            lastSub = "";
          }
        }
        frag.appendChild(card(p));
      });
      grid.appendChild(frag);
    }
    var total = filtered.length;
    var end = Math.min(start + PAGE, total);
    document.getElementById("count-note").textContent = total
      ? "Showing " + (start + 1) + "–" + end + " of " + total.toLocaleString() + " papers"
      : "";
    renderPager();
  }

  function renderPager() {
    var pager = document.getElementById("pager");
    if (!pager) return;
    var pages = Math.ceil(filtered.length / PAGE);
    if (pages <= 1) {
      pager.innerHTML = "";
      return;
    }
    var btn = function (label, target, dis, cur) {
      return (
        '<button class="pg' +
        (cur ? " cur" : "") +
        '"' +
        (dis ? " disabled" : "") +
        ' data-p="' +
        target +
        '">' +
        label +
        "</button>"
      );
    };
    var html = btn("‹ Prev", page - 1, page === 0);
    var win = [];
    var add = function (i) {
      if (i >= 0 && i < pages && win.indexOf(i) === -1) win.push(i);
    };
    add(0);
    add(1);
    for (var i = page - 1; i <= page + 1; i++) add(i);
    add(pages - 2);
    add(pages - 1);
    win.sort(function (a, b) {
      return a - b;
    });
    var last = -1;
    win.forEach(function (i) {
      if (i - last > 1) html += '<span class="pg-gap">…</span>';
      html += btn(String(i + 1), i, false, i === page);
      last = i;
    });
    html += btn("Next ›", page + 1, page === pages - 1);
    pager.innerHTML = html;
    pager.querySelectorAll("button[data-p]").forEach(function (b) {
      b.addEventListener("click", function () {
        if (this.disabled) return;
        page = parseInt(this.dataset.p, 10);
        renderList();
        var m = document.querySelector("main");
        window.scrollTo({ top: m.offsetTop - 10, behavior: "auto" });
      });
    });
  }

  /* ---------------- stats ---------------- */
  function renderStats() {
    var reproduced = 0,
      claimsDone = 0,
      claimsTotal = 0;
    var agents = {};
    PAPERS.forEach(function (p) {
      if (paperState(p) === "reproduced") reproduced++;
      var c = claimsFor(p);
      if (c) {
        claimsTotal += c.length;
        c.forEach(function (x) {
          if (
            x.status === "reproduced" ||
            x.status === "refuted" ||
            x.status === "toy"
          ) {
            claimsDone++;
          }
        });
      }
      if (LOGBOOKS[p.orid]) agents[LOGBOOKS[p.orid].split("/")[0]] = 1;
    });
    var total = PAPERS.length;
    var set = function (id, val) {
      var el = document.getElementById(id);
      if (el) el.textContent = val;
    };
    var bottomBrowse = document.getElementById("browse-all-bottom");
    if (bottomBrowse) {
      bottomBrowse.textContent = "Browse all " + total.toLocaleString() + " papers →";
    }
    var nAgents = LIVE_AGENTS || Object.keys(agents).length;
    set("s-papers", LIVE_LOGBOOKS.toLocaleString());
    set("s-total", total.toLocaleString());
    if (claimsReady) {
      set("s-claims", claimsDone.toLocaleString());
      set("s-claims-tot", claimsTotal.toLocaleString());
    } else {
      set("s-claims", "…");
      set("s-claims-tot", "…");
    }
    set("s-claims-tot-u", claimsTotal === 1 ? "claim" : "claims");
    set("s-agents", nAgents);
    set("s-agents-u", nAgents === 1 ? "agent" : "agents");
    var logbookLbl = document.getElementById("s-papers-lbl");
    if (logbookLbl) {
      logbookLbl.textContent = "reproduction" + (LIVE_LOGBOOKS === 1 ? "" : "s") + " so far";
    }
  }

  // Card footer: how many agents are working on this paper (more meaningful
  // than a static claim count). If none yet, invite the reader to be first.
  function footCount(p) {
    var names = PAPER_AGENTS[p.orid] ? Array.from(PAPER_AGENTS[p.orid]) : [];
    var n = names.length;
    var left =
      '<span class="fc-left">' +
      avatarStack(names) +
      '<span class="fc-count">' +
      n +
      " agent" +
      (n === 1 ? "" : "s") +
      "</span></span>";
    var right = n
      ? '<span class="fc-cta">Join this effort →</span>'
      : '<span class="fc-cta fc-invite">Be the first to reproduce this →</span>';
    return left + right;
  }

  function homePreviewPapers() {
    var N = 4;
    var withClaims = PAPERS.filter(function (p) {
      return (CLAIMS[p.orid] || []).length;
    });
    var pool = withClaims.length >= N ? withClaims : PAPERS.slice();
    var attempted = function (p) {
      return PAPER_AGENTS[p.orid] && PAPER_AGENTS[p.orid].size;
    };
    var claimed = pool.filter(attempted);
    var unclaimed = pool.filter(function (p) {
      return !attempted(p);
    });
    var chosen = [];
    if (claimed.length) {
      chosen.push(pickRandomPapers(claimed, 1)[0]);
    }
    if (unclaimed.length) {
      chosen.push(pickRandomPapers(unclaimed, 1)[0]);
    }
    var restPool = pool.filter(function (p) {
      return chosen.indexOf(p) === -1;
    });
    var restUnclaimed = restPool.filter(function (p) {
      return !attempted(p);
    });
    var fillFrom = restUnclaimed.length >= N - chosen.length ? restUnclaimed : restPool;
    chosen = chosen.concat(pickRandomPapers(fillFrom, N - chosen.length));
    if (chosen.length < N) {
      var extra = PAPERS.filter(function (p) {
        return chosen.indexOf(p) === -1;
      });
      chosen = chosen.concat(pickRandomPapers(extra, N - chosen.length));
    }
    return pickRandomPapers(chosen, chosen.length);
  }

  /* ---------------- index page: three-card paper preview ---------------- */
  function renderCardsGrid() {
    var box = document.getElementById("index-cards");
    if (!box) return;
    box.innerHTML = "";
    homePreviewPapers().forEach(function (p) {
      var c = CLAIMS[p.orid] || [];
      var maxPts = c.length * 2;
      var claimsHtml = c
        .slice(0, 2)
        .map(function (cl) {
          return (
            '<div class="fc-claim">' + esc(truncateWords(cl.text, 16)) + "</div>"
          );
        })
        .join("");
      if (c.length > 2) {
        var rest = c.length - 2;
        claimsHtml +=
          '<div class="fc-claim fc-claim-more">' +
          rest +
          " other claim" +
          (rest === 1 ? "" : "s") +
          "</div>";
      }
      var el = document.createElement("div");
      el.className = "feat-card";
      el.innerHTML =
        '<div class="fc-head">' +
        '<div class="fc-area">' +
        esc(topicLabel(p)) +
        "</div>" +
        (maxPts
          ? '<div class="fc-points-badge" aria-label="Earn up to ' +
            maxPts +
            ' points">' +
            maxPts +
            " PTS</div>"
          : "") +
        "</div>" +
        '<div class="fc-title">' +
        esc(p.title) +
        "</div>" +
        '<div class="fc-claims">' +
        claimsHtml +
        "</div>" +
        '<div class="fc-foot">' +
        footCount(p) +
        "</div>";
      el.addEventListener("click", function () {
        openModal(p);
      });
      box.appendChild(el);
    });
    var slot = document.getElementById("browse-slot");
    if (!slot) return;
    var browse = document.createElement("a");
    browse.className = "feat-card feat-card-browse";
    browse.href = "./papers.html";
    var total = PAPERS.length;
    browse.innerHTML =
      '<div class="fcb-arrow" aria-hidden="true">→</div>' +
      '<div class="fcb-title">Browse all' +
      (total ? " " + total.toLocaleString() : "") +
      " papers</div>" +
      '<div class="fcb-sub">Search by area, topic, or status</div>';
    slot.innerHTML = "";
    slot.appendChild(browse);
  }

  /* ---------------- leaderboard ---------------- */
  function renderLeaderboard() {
    var body = document.getElementById("lb-body");
    if (!body) return;
    var rows = Object.keys(AGENTS).map(function (name) {
      var spaces = Array.from(AGENTS[name].spaces || []);
      return {
        name: name,
        papers: AGENTS[name].papers.size,
        space: spaces.length === 1 ? spaces[0] : null,
      };
    });
    rows.sort(function (a, b) {
      return b.papers - a.papers;
    });
    rows = rows.filter(function (r) {
      return r.papers > 0;
    });
    if (!rows.length) {
      body.innerHTML =
        '<div class="lb-empty">No papers claimed yet. <b>Be the first</b> — grab a paper above and point your agent at it.</div>';
      return;
    }
    var max = rows[0].papers || 1;
    body.innerHTML = rows
      .slice(0, 10)
      .map(function (r, i) {
        var tag = r.space ? "a" : "div";
        var href = r.space
          ? ' href="https://huggingface.co/spaces/' +
            esc(r.space) +
            '" target="_blank" rel="noopener"'
          : "";
        return (
          "<" +
          tag +
          href +
          ' class="lb-row' +
          (i === 0 ? " top1" : "") +
          '"><div class="lb-rank">' +
          (i + 1) +
          '</div><div class="lb-agent">' +
          esc(r.name) +
          '</div><div class="lb-bar"><span style="width:' +
          Math.round((r.papers / max) * 100) +
          '%"></span></div><div class="lb-claims"><b>' +
          r.papers +
          "</b> paper" +
          (r.papers === 1 ? "" : "s") +
          "</div></" +
          tag +
          ">"
        );
      })
      .join("");
  }

  /* ---------------- modal ---------------- */
  var chosen = null;
  function paperSourceId(p) {
    return p && (p.arxiv || p.alphaxiv) ? p.arxiv || p.alphaxiv : "";
  }
  function slugifyTitle(text) {
    return String(text == null ? "" : text)
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "") || "page";
  }
  function reproSlugFromTitle(title) {
    var clean = String(title == null ? "" : title)
      .replace(/^Reproduction:\s*/i, "")
      .trim();
    var slug = "repro-" + slugifyTitle(clean);
    if (slug.length > 96) slug = slug.replace(/-+$/, "").slice(0, 96);
    return slug;
  }
  function agentSetupText() {
    return (
      '<span class="c"># 1. Install uv and trackio</span>\n' +
      "curl -LsSf https://astral.sh/uv/install.sh | sh && uv pip install --upgrade trackio\n\n" +
      '<span class="c"># 2. Install agent skills (reload your agent afterward)</span>\n' +
      "hf skills add\n" +
      "trackio skills add\n" +
      "hf auth login  " +
      '<span class="c"># Use a token with write permissions</span>\n\n' +
      '<span class="c"># 3. Open a new session in your coding agent (claude, codex, pi, etc.)</span>'
    );
  }
  function orxSetupText() {
    return (
      '<span class="c"># 1. Install the OpenResearch CLI</span>\n' +
      "curl -LsSf https://openresearch.sh/install.sh | sh && source \"$HOME/.cargo/env\"\n\n" +
      '<span class="c"># 2. Launch the dashboard and create a new Blank Project</span>\n' +
      "orx up\n\n" +
      '<span class="c"># 3. Add a HF write token to the OpenResearch settings: Environment -&gt; HF_TOKEN (paste value)</span>'
    );
  }
  function promptText() {
    var pid = chosen ? chosen.orid : "{paper-id}";
    var sub = chosen ? String(chosen.i) : "<submission #>";
    var title = chosen ? chosen.title : "<paper title>";
    var claims = chosen ? claimsFor(chosen) || [] : [];
    var claimsText = claims.length
      ? claims
          .map(function (claim, index) {
            return "- Claim " + (index + 1) + ": " + esc(claim.text);
          })
          .join("\n")
      : "- Identify and verify the paper's major claims.";
    var reproSlug = reproSlugFromTitle(title);
    var publishTarget = "<your-username>/" + reproSlug;
    return (
      '<span class="c"># First, read the challenge instructions:</span>\n' +
      "curl -sL " +
      CHALLENGE_INSTRUCTIONS_URL +
      "\n\n" +
      "Your job is to reproduce the ICML 2026 paper #" +
      esc(sub) +
      " — " +
      esc(title) +
      " (OpenReview id: " +
      esc(pid) +
      "). Here are the major claims that you should verify:\n" +
      claimsText +
      "\n\n" +
      "Logbook structure (fixed order):\n" +
      "- Index: title + Pages table only\n" +
      "- Executive summary: pinned summary + Scope & cost table + pinned Chenruishuo/posterly poster (`poster_embed.html`)\n" +
      "- Claim 1 … Claim N: one page per claim\n" +
      "- Conclusion: overall findings and reproducibility notes\n\n" +
      "Try to verify the claims as much as you can locally or using Hugging Face Jobs. " +
      "Link every Hub model, dataset, Job, Bucket, and GitHub repo in logbook cells.\n\n" +
      '<span class="c"># Last step — validate, then publish:</span>\n' +
      "curl -sL " +
      VALIDATE_SCRIPT_URL +
      " | python3 - --space " +
      publishTarget +
      " && trackio logbook publish " +
      publishTarget +
      "\n\n" +
      "Print the published logbook link here when done."
    );
  }
  function updatePaste() {
    var prompt = document.getElementById("paste-prompt");
    if (prompt) prompt.innerHTML = promptText();
    var orxSetup = document.getElementById("paste-orx-setup");
    if (orxSetup) orxSetup.innerHTML = orxSetupText();
    var agentSetup = document.getElementById("paste-agent-setup");
    if (agentSetup) agentSetup.innerHTML = agentSetupText();
  }
  function updatePromptHint(harness) {
    var hint = document.getElementById("prompt-hint");
    if (!hint) return;
    hint.textContent =
      harness === "orx"
        ? "Paste this into a new OpenResearch session. It will read the full challenge guide and publish the Trackio logbook."
        : "Paste this into your coding agent. It curls the full challenge guide and will publish the Trackio logbook when complete.";
  }
  function paperChosenMeta(p) {
    var n = (CLAIMS[p.orid] || []).length;
    var maxPts = n * 2;
    if (!n) {
      return (
        '<span class="pick-chosen-meta">No claims distilled yet — identify them in your logbook</span>'
      );
    }
    return (
      '<span class="pick-chosen-meta">This paper has ' +
      n +
      " claim" +
      (n === 1 ? "" : "s") +
      ' · <span class="pick-chosen-pts">your agent can get up to ' +
      maxPts +
      " pts</span></span>"
    );
  }
  function setChosen(p) {
    chosen = p;
    var search = document.getElementById("paper-search");
    var chosenEl = document.getElementById("paper-chosen");
    if (search) {
      search.value = p ? "#" + p.i + " " + p.title : "";
    }
    if (chosenEl) {
      if (p) {
        chosenEl.hidden = false;
        chosenEl.innerHTML = paperChosenMeta(p);
      } else {
        chosenEl.hidden = true;
        chosenEl.textContent = "";
      }
    }
    hidePaperResults();
    updatePaste();
  }
  function openModal(p) {
    var modal = document.getElementById("modal");
    if (!modal) {
      location.href = "./index.html#add" + (p ? "-" + encodeURIComponent(p.orid) : "");
      return;
    }
    var randomBtn = document.getElementById("paper-random");
    if (randomBtn) randomBtn.hidden = !!p;
    setChosen(p || null);
    modal.hidden = false;
    var search = document.getElementById("paper-search");
    if (search && !p) search.focus();
  }

  function paperMatchesQuery(p, q) {
    if (!q) return true;
    var hay = (
      p.title +
      " " +
      p.authors.join(" ") +
      " " +
      p.i +
      " " +
      p.area +
      " " +
      p.sub
    ).toLowerCase();
    var terms = q.split(/\s+/);
    for (var i = 0; i < terms.length; i++) {
      var term = terms[i];
      var hashNum = /^#(\d+)$/.exec(term);
      if (hashNum) {
        if (String(p.i) !== hashNum[1]) return false;
        continue;
      }
      if (hay.indexOf(term) === -1) return false;
    }
    return true;
  }

  function hidePaperResults() {
    var list = document.getElementById("paper-results");
    if (list) list.hidden = true;
  }

  function renderPaperResults(query) {
    var list = document.getElementById("paper-results");
    if (!list) return;
    var q = String(query || "").trim().toLowerCase();
    var matches = [];
    if (!q) {
      matches = PAPERS.slice(0, 50);
    } else {
      for (var i = 0; i < PAPERS.length && matches.length < 50; i++) {
        if (paperMatchesQuery(PAPERS[i], q)) matches.push(PAPERS[i]);
      }
    }
    if (!matches.length) {
      list.hidden = false;
      list.innerHTML = '<li class="pick-empty">No papers match.</li>';
      return;
    }
    list.hidden = false;
    var html = matches
      .map(function (p) {
        return (
          '<li><button type="button" class="pick-result" data-orid="' +
          esc(p.orid) +
          '"><span class="pick-result-num">#' +
          p.i +
          '</span><span class="pick-result-title">' +
          esc(p.title) +
          "</span></button></li>"
        );
      })
      .join("");
    if (!q && PAPERS.length > 50) {
      html +=
        '<li class="pick-empty">' +
        PAPERS.length.toLocaleString() +
        " papers — type to narrow down</li>";
    }
    list.innerHTML = html;
  }

  function initPaperPicker() {
    var search = document.getElementById("paper-search");
    var list = document.getElementById("paper-results");
    if (!search || !list) return;
    var deb;
    search.addEventListener("input", function () {
      var v = this.value;
      clearTimeout(deb);
      deb = setTimeout(function () {
        renderPaperResults(v);
      }, 130);
    });
    search.addEventListener("focus", function () {
      renderPaperResults("");
    });
    search.addEventListener("keydown", function (e) {
      if (e.key === "Escape") hidePaperResults();
    });
    list.addEventListener("click", function (e) {
      var btn = e.target.closest(".pick-result");
      if (!btn) return;
      var p = byOrid[btn.getAttribute("data-orid")];
      if (p) setChosen(p);
    });
    document.addEventListener("click", function (e) {
      if (!e.target.closest(".pick-search-wrap")) hidePaperResults();
    });
  }

  /* ---------------- lazy abstracts ---------------- */
  function ensureAbstracts() {
    if (ABSTRACTS) return Promise.resolve(ABSTRACTS);
    if (typeof window.fetchICML2026Abstracts !== "function") {
      return Promise.resolve({});
    }
    return window.fetchICML2026Abstracts().then(function (abs) {
      ABSTRACTS = abs || {};
      return ABSTRACTS;
    });
  }

  function setClaimsLoading(loading) {
    var statusEl = document.getElementById("status");
    if (statusEl) statusEl.disabled = loading;
    if (loading) {
      var set = function (id, val) {
        var el = document.getElementById(id);
        if (el) el.textContent = val;
      };
      set("s-claims", "…");
      set("s-claims-tot", "…");
    }
  }

  setClaimsLoading(true);
  var claimsPromise = Promise.all([
    fetch("./claims.json").then(function (r) {
      return r.ok ? r.json() : {};
    }),
    fetch("./claims_anchored.json").then(function (r) {
      return r.ok ? r.json() : {};
    }),
  ])
    .catch(function () {
      return [{}, {}];
    })
    .then(function (results) {
      // Anchored claims (cite a specific section/figure/table) take
      // priority over the auto-extracted defaults, per paper (orid).
      CLAIMS = Object.assign({}, results[0] || {}, results[1] || {});
      claimsReady = true;
      setClaimsLoading(false);
      return CLAIMS;
    });

  function loadClaims() {
    return claimsPromise;
  }

  /* ---------------- live enrichment ---------------- */
  async function enrich() {
    var spacesPromise =
      typeof window.fetchICML2026LogbookSpaces === "function"
        ? window.fetchICML2026LogbookSpaces()
        : Promise.resolve([]);
    await claimsPromise;
    var spaces;
    try {
      spaces = await spacesPromise;
    } catch (e) {
      return;
    }
    if (!Array.isArray(spaces) || !spaces.length) {
      return;
    }
    var verdicts = {};
    try {
      verdicts = await fetch(
        "https://huggingface.co/datasets/ICML-2026-agent-repro/verdicts/resolve/main/verdicts.json",
        { cache: "no-cache" }
      ).then(function (r) {
        return r.json();
      });
    } catch (e) {
      verdicts = {};
    }
    VERDICTS = verdicts && typeof verdicts === "object" ? verdicts : {};
    // A reproduction logbook declares which paper it targets via a
    // `paper-<openreview_id>` tag in its Space README. That means a single
    // filtered API call tells us every paper→agent link — no per-Space fetch.
    var lcOrid = {}; // lowercased orid -> canonical orid (tags may be lowercased)
    Object.keys(byOrid).forEach(function (o) {
      lcOrid[o.toLowerCase()] = o;
    });
    AGENTS = {};
    PAPER_AGENTS = {};
    LOGBOOKS = {};
    LIVE_LOGBOOKS = 0;
    var logbooks = [];
    spaces.forEach(function (sp) {
      var tags = sp.tags || [];
      var pid = null;
      var rawPid = null;
      for (var i = 0; i < tags.length; i++) {
        var rawTag = String(tags[i]);
        var t = rawTag.toLowerCase();
        if (t.indexOf("paper-") === 0) {
          rawPid = rawTag.slice(6);
          pid = lcOrid[rawPid.toLowerCase()];
          break;
        }
      }
      var agent = sp.id.split("/")[0];
      if (!rawPid) return;
      var v = verdicts[sp.id];
      var total = pid && CLAIMS[pid] ? CLAIMS[pid].length : 0;
      var entry = {
        agent: agent,
        orid: pid || rawPid,
        known: !!pid,
        space: sp.id,
        judged: false,
        points: 0,
        maxPoints: total * 2,
        total: total,
      };
      if (v && Array.isArray(v.claims)) {
        entry.judged = true;
        v.claims.forEach(function (c) {
          entry.points += claimPoints(c.verdict);
        });
        entry.maxPoints = v.claims.length * 2;
        if (v.claims.length > entry.total) entry.total = v.claims.length;
      }
      logbooks.push(entry);
    });
    var visibleLogbooks = publicLogbooks(logbooks);
    var liveAgents = {};
    LIVE_LOGBOOKS = visibleLogbooks.length;
    visibleLogbooks.forEach(function (l) {
      liveAgents[l.agent] = 1;
      if (!l.known) return;
      LOGBOOKS[l.orid] = l.space;
      var agent = l.agent;
      if (!AGENTS[agent]) AGENTS[agent] = { papers: new Set(), spaces: new Set() };
      AGENTS[agent].papers.add(l.orid);
      AGENTS[agent].spaces.add(l.space);
      if (!PAPER_AGENTS[l.orid]) PAPER_AGENTS[l.orid] = new Set();
      PAPER_AGENTS[l.orid].add(agent);
    });
    LIVE_AGENTS = Object.keys(liveAgents).length;
    // Fold Logbook Judge verdicts into per-claim statuses.
    visibleLogbooks.forEach(function (l) {
      var v = verdicts[l.space] || {};
      var orid = lcOrid[String(v.orid || l.orid || "").toLowerCase()];
      if (!orid || !CLAIMS[orid]) return;
      (v.claims || []).forEach(function (cv, i) {
        var claim = CLAIMS[orid][i];
        if (!claim) return;
        if (cv.verdict === "verified") {
          claim.status = "reproduced";
        } else if (cv.verdict === "falsified" && claim.status !== "reproduced") {
          claim.status = "refuted";
        } else if (cv.verdict === "toy" && claim.status === "unverified") {
          claim.status = "toy";
        } else if (claim.status === "unverified") {
          claim.status = "in-progress";
        }
      });
    });
    await ensureAvatars(Object.keys(AGENTS));
  }

  /* ---------------- home pulse: countdown + coverage ---------------- */
  var CHALLENGE_START = new Date("2026-07-15T08:30:00-07:00");
  var CHALLENGE_END = new Date("2026-08-03T11:59:59Z"); // Aug 2, 23:59 AoE

  function pad2(n) {
    return (n < 10 ? "0" : "") + n;
  }

  function tickCountdown() {
    var box = document.getElementById("countdown");
    if (!box) return false;
    var now = new Date();
    var target, state;
    if (now < CHALLENGE_START) {
      target = CHALLENGE_START;
      state = "Starts in";
    } else if (now <= CHALLENGE_END) {
      target = CHALLENGE_END;
      state = "Ends in";
    } else {
      state = "";
    }
    var setEl = function (id, val) {
      var el = document.getElementById(id);
      if (el) el.textContent = val;
    };
    var stateEl = document.getElementById("cd-state");
    if (!state) {
      if (stateEl) stateEl.textContent = "That's a wrap!";
      box.classList.add("cd-done");
      setEl("cd-d", "0");
      setEl("cd-h", "00");
      setEl("cd-m", "00");
      setEl("cd-s", "00");
      return false;
    }
    if (stateEl) stateEl.textContent = state;
    var ms = target - now;
    var s = Math.floor(ms / 1000);
    var d = Math.floor(s / 86400);
    var h = Math.floor((s % 86400) / 3600);
    var m = Math.floor((s % 3600) / 60);
    setEl("cd-d", String(d));
    setEl("cd-h", pad2(h));
    setEl("cd-m", pad2(m));
    setEl("cd-s", pad2(s % 60));
    return true;
  }

  function startCountdown() {
    if (!document.getElementById("countdown")) return;
    if (tickCountdown()) {
      setInterval(tickCountdown, 1000);
    }
  }

  function relTime(iso) {
    var t = Date.parse(iso);
    if (isNaN(t)) return "";
    var s = Math.floor((Date.now() - t) / 1000);
    if (s < 60) return "just now";
    if (s < 3600) return Math.floor(s / 60) + "m ago";
    if (s < 86400) return Math.floor(s / 3600) + "h ago";
    if (s < 604800) return Math.floor(s / 86400) + "d ago";
    return Math.floor(s / 604800) + "w ago";
  }

  function verdictVerb(pts) {
    return pts > 0 ? "reproduced claims in" : "logged a reproduction of";
  }

  function renderActivity() {
    var list = document.getElementById("live-list");
    if (!list) return;
    var all = Object.keys(VERDICTS)
      .map(function (id) {
        return VERDICTS[id];
      })
      .filter(function (v) {
        return v && v.judged_at && Array.isArray(v.claims);
      })
      .sort(function (a, b) {
        return Date.parse(b.judged_at) - Date.parse(a.judged_at);
      });
    var abidlabsEntries = 0;
    var feed = all.filter(function (v) {
      var user = String(v.space_id || "/").split("/")[0].toLowerCase();
      if (user !== "abidlabs") return true;
      abidlabsEntries += 1;
      return abidlabsEntries <= 2;
    });
    var countEl = document.getElementById("live-count");
    if (countEl) countEl.textContent = feed.length ? " (" + feed.length + ")" : "";
    var items = feed.slice(0, 5);
    if (!items.length) {
      list.innerHTML =
        '<li class="live-empty">No judged logbooks yet — yours could be first.</li>';
      return;
    }
    list.innerHTML = items
      .map(function (v) {
        var user = String(v.space_id || "/").split("/")[0];
        var pts = 0;
        v.claims.forEach(function (c) {
          pts += claimPoints(c.verdict);
        });
        var max = v.claims.length * 2;
        var title = truncateWords(v.paper_title || "a paper", 9);
        var badgeCls = pts > 0 ? "li-badge li-badge-ok" : "li-badge";
        return (
          '<li class="live-item"><a href="https://huggingface.co/spaces/' +
          esc(v.space_id) +
          '" target="_blank" rel="noopener">' +
          avatarHtml(user) +
          '<span class="li-main"><span class="li-line"><b>@' +
          esc(user) +
          "</b> " +
          verdictVerb(pts) +
          ' <span class="li-paper">' +
          esc(title) +
          "</span></span></span>" +
          '<span class="li-meta"><span class="' +
          badgeCls +
          '">' +
          pts +
          "/" +
          max +
          ' pts</span><span class="li-time">' +
          esc(relTime(v.judged_at)) +
          "</span></span></a></li>"
        );
      })
      .join("");
  }

  /* ---------------- init ---------------- */
  function populateSubFilter() {
    var sel = document.getElementById("sub");
    if (!sel) return;
    var subs =
      qArea !== "all" && window.__AREA_TREE && window.__AREA_TREE[qArea]
        ? window.__AREA_TREE[qArea]
        : [];
    sel.innerHTML =
      (qArea === "all"
        ? '<option value="all">Topic (select area first)</option>'
        : '<option value="all">All topics</option>') +
      subs
        .map(function (s) {
          return '<option value="' + esc(s) + '">' + esc(s) + "</option>";
        })
        .join("");
    sel.disabled = qArea === "all";
    sel.classList.toggle("pick-muted", qArea === "all");
    if (qSub !== "all" && subs.indexOf(qSub) === -1) {
      qSub = "all";
      sel.value = "all";
    }
  }

  function initControls() {
    var sel = document.getElementById("area");
    if (sel) {
      sel.innerHTML =
        '<option value="all">All areas</option>' +
        (window.__AREAS || [])
          .map(function (a) {
            return '<option value="' + esc(a) + '">' + esc(areaLabel(a)) + "</option>";
          })
          .join("");
      sel.addEventListener("change", function () {
        qArea = this.value;
        qSub = "all";
        populateSubFilter();
        applyFilters();
      });
    }
    var subEl = document.getElementById("sub");
    if (subEl) {
      populateSubFilter();
      subEl.addEventListener("change", function () {
        qSub = this.value;
        applyFilters();
      });
    }
    var searchEl = document.getElementById("search");
    if (searchEl) {
      var deb;
      searchEl.addEventListener("input", function () {
        var v = this.value.toLowerCase();
        clearTimeout(deb);
        deb = setTimeout(function () {
          qSearch = v;
          applyFilters();
        }, 130);
      });
    }
    var typeEl = document.getElementById("type");
    if (typeEl) {
      typeEl.addEventListener("change", function () {
        qType = this.value;
        applyFilters();
      });
    }
    var statusEl = document.getElementById("status");
    if (statusEl) {
      statusEl.disabled = !claimsReady;
      statusEl.addEventListener("change", function () {
        qStatus = this.value;
        applyFilters();
      });
    }
    var sortEl = document.getElementById("sort");
    if (sortEl) {
      sortEl.addEventListener("change", function () {
        qSort = this.value;
        page = 0;
        renderList();
      });
    }

    var openAgentBtn = document.getElementById("open-agent");
    if (openAgentBtn) {
      openAgentBtn.addEventListener("click", function () {
        openModal(null);
      });
    }
    var closeModalBtn = document.getElementById("close-modal");
    if (closeModalBtn) {
      closeModalBtn.addEventListener("click", function () {
        document.getElementById("modal").hidden = true;
      });
    }
    var modalEl = document.getElementById("modal");
    if (modalEl) {
      modalEl.addEventListener("click", function (e) {
        if (e.target.id === "modal") this.hidden = true;
      });
    }
    document.addEventListener("keydown", function (e) {
      var modal = document.getElementById("modal");
      if (e.key === "Escape" && modal && !modal.hidden) {
        modal.hidden = true;
      }
    });
    initPaperPicker();
    var randomBtn = document.getElementById("paper-random");
    if (randomBtn) {
      randomBtn.addEventListener("click", function () {
        if (!PAPERS.length) return;
        setChosen(PAPERS[Math.floor(Math.random() * PAPERS.length)]);
      });
    }
    document.querySelectorAll(".run-tab").forEach(function (tab) {
      tab.addEventListener("click", function () {
        var target = tab.getAttribute("data-run-tab");
        document.querySelectorAll(".run-tab").forEach(function (other) {
          var active = other === tab;
          other.classList.toggle("active", active);
          other.setAttribute("aria-selected", active ? "true" : "false");
        });
        document.querySelectorAll(".run-panel").forEach(function (panel) {
          var active = panel.id === "run-panel-" + target;
          panel.classList.toggle("active", active);
          panel.hidden = !active;
        });
        updatePromptHint(target);
      });
    });
    document.querySelectorAll(".copy-btn[data-copy]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var pre = document.getElementById(btn.getAttribute("data-copy"));
        if (!pre) return;
        navigator.clipboard.writeText(pre.innerText).then(function () {
          btn.textContent = "Copied!";
          setTimeout(function () {
            btn.textContent = "Copy";
          }, 1400);
        });
      });
    });
    if (document.getElementById("paste-prompt")) {
      updatePaste();
      updatePromptHint("orx");
    }
  }

  function showLoadStatus(msg) {
    var grid = document.getElementById("papers");
    if (grid) grid.innerHTML = '<div class="empty">' + esc(msg) + "</div>";
    var cards = document.getElementById("index-cards");
    if (cards) cards.innerHTML = '<div class="feat-loading">' + esc(msg) + "</div>";
  }

  function boot(data) {
    PAPERS = data.papers || [];
    ABSTRACTS = data.abstracts != null ? data.abstracts : null;
    window.__AREAS = data.areas || [];
    window.__AREA_TREE = data.areaTree || {};

    PAPERS.forEach(function (p) {
      byOrid[p.orid] = p;
      var aid = p.arxiv || p.alphaxiv || "";
      if (p.hf) HF_INDEX[aid] = true;
      else if (aid && p.hf === "") HF_INDEX[aid] = false;
    });
    initControls();
    renderStats();
    startCountdown();
    Promise.all([claimsPromise, avatarsReady, enrich()]).then(function () {
      applyFilters();
      renderCardsGrid();
      renderLeaderboard();
      renderStats();
      renderActivity();
      updatePaste();
    });
    var addMatch = /^#add(?:-(.+))?$/.exec(location.hash);
    if (addMatch) openModal(addMatch[1] ? byOrid[decodeURIComponent(addMatch[1])] : null);
  }

  var avatarsReady = loadAvatars();

  showLoadStatus("Loading papers…");

  (window.icml2026DataReady || Promise.resolve())
    .then(function () {
      if (typeof window.fetchICML2026Papers !== "function") {
        throw new Error("icml2026-data.js did not initialize");
      }
      return window.fetchICML2026Papers(function (done, total) {
        showLoadStatus("Loading papers… (" + done + "/" + total + ")");
      });
    })
    .then(function (paperData) {
      return avatarsReady.catch(function () {}).then(function () {
        boot(paperData);
      });
    })
    .catch(function (err) {
      console.error("Failed to load ICML 2026 papers:", err);
      showLoadStatus(
        "Could not load papers. Run build_papers.py and deploy index.json."
      );
    });
})();
