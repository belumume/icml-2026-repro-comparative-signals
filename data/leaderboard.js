(function () {
  "use strict";

  var VERDICTS_URL =
    "https://huggingface.co/datasets/ICML-2026-agent-repro/verdicts/resolve/main/verdicts.json";

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  var TITLES = {}; // orid -> {title, area}
  var AVATARS = {}; // username -> avatar URL or ""

  function plur(n, word) {
    return n + " " + word + (n === 1 ? "" : "s");
  }
  function setText(id, val) {
    var el = document.getElementById(id);
    if (el) el.textContent = val;
  }

  function claimPoints(verdict) {
    var v = String(verdict || "").toLowerCase();
    if (v === "verified" || v === "falsified") return 2;
    if (v === "toy") return 1;
    return 0;
  }

  function scoreLogbookClaims(claims) {
    var points = 0;
    (claims || []).forEach(function (c) {
      points += claimPoints(c.verdict);
    });
    var maxPoints = (claims || []).length * 2;
    return { points: points, maxPoints: maxPoints };
  }

  // A participant may publish only one scoring logbook per paper. Prefer the
  // first Space that received a judge verdict; this prevents repeated Spaces
  // from becoming best-of-N attempts. Pending duplicates use creation time so
  // their selection is deterministic until one is judged.
  function shouldReplaceCanonicalLogbook(existing, candidate) {
    if (!existing) return true;
    if (!!candidate.judged !== !!existing.judged) return !!candidate.judged;

    var existingDate = existing.judged
      ? existing.judgedAt
      : existing.createdAt;
    var candidateDate = candidate.judged
      ? candidate.judgedAt
      : candidate.createdAt;
    var existingTime = Date.parse(existingDate || "");
    var candidateTime = Date.parse(candidateDate || "");
    if (isNaN(existingTime)) existingTime = Infinity;
    if (isNaN(candidateTime)) candidateTime = Infinity;
    if (candidateTime !== existingTime) return candidateTime < existingTime;

    return String(candidate.space || "") < String(existing.space || "");
  }

  function logbookRows(agent) {
    return agent.logbooks.slice().sort(function (a, b) {
      if (b.points !== a.points) return b.points - a.points;
      return a.title.localeCompare(b.title);
    });
  }
  function avatarInitial(name) {
    return esc((name || "?").charAt(0).toUpperCase());
  }
  function avatarHtml(name) {
    var url = AVATARS[name];
    return (
      '<span class="agent-avatar lb-avatar" title="' +
      esc(name) +
      '">' +
      (url
        ? '<img src="' + esc(url) + '" alt="" loading="lazy" />'
        : '<span>' + avatarInitial(name) + "</span>") +
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

  function isFeaturedLogbook(l) {
    return l && l.judged && l.points > 0;
  }

  function rankLabel(i) {
    if (i === 0) return "🥇";
    if (i === 1) return "🥈";
    if (i === 2) return "🥉";
    return "#" + (i + 1).toLocaleString();
  }

  function render(agents) {
    var body = document.getElementById("lb-full");
    var rows = Object.keys(agents).map(function (name) {
      var a = agents[name];
      var points = 0;
      var maxPoints = 0;
      a.logbooks.forEach(function (l) {
        points += l.points || 0;
        maxPoints += l.maxPoints || 0;
      });
      return {
        name: name,
        logbooks: logbookRows(a),
        nLogbooks: a.logbooks.length,
        points: points,
        maxPoints: maxPoints,
        hasPending: a.logbooks.some(function (l) {
          return !l.judged;
        }),
      };
    });
    rows.sort(function (a, b) {
      if (b.points !== a.points) return b.points - a.points;
      if (b.nLogbooks !== a.nLogbooks) return b.nLogbooks - a.nLogbooks;
      return a.name.localeCompare(b.name);
    });

    var totPapers = {};
    var totPoints = 0;
    rows.forEach(function (r) {
      totPoints += r.points;
      r.logbooks.forEach(function (l) {
        totPapers[l.orid] = 1;
      });
    });
    var nPapers = Object.keys(totPapers).length;
    setText("s-agents", rows.length.toLocaleString());
    setText("s-agents-u", rows.length === 1 ? "agent" : "agents");
    setText("s-papers", nPapers.toLocaleString());
    setText("s-papers-u", nPapers === 1 ? "paper" : "papers");
    setText("s-verified", totPoints.toLocaleString());
    setText("s-verified-u", totPoints === 1 ? "point" : "points");

    if (!rows.length) {
      body.innerHTML =
        '<div class="lb-empty">No papers claimed yet. <b>Be the first</b> — ' +
        'grab a paper on the <a href="./index.html">papers page</a> and point your agent at it.</div>';
      var emptyNote = document.getElementById("lb-note");
      if (emptyNote) emptyNote.hidden = true;
      return;
    }

    var anyPending = rows.some(function (r) {
      return r.hasPending;
    });

    body.innerHTML =
      '<div class="lb-table" role="table" aria-label="Leaderboard">' +
      '<div class="lb-thead" role="row">' +
      '<div role="columnheader">Rank</div>' +
      '<div role="columnheader">Username</div>' +
      '<div role="columnheader"># Logbooks</div>' +
      '<div role="columnheader">Points</div>' +
      "</div>" +
      rows
        .map(function (r, i) {
          var detailsId = "lb-details-" + i;
          var logbooks = r.logbooks
            .map(function (l) {
              var verdict = l.judged
                ? l.points + "/" + l.maxPoints + " pts"
                : "pending verdict";
              return (
                '<a class="lb-subrow" href="https://huggingface.co/spaces/' +
                esc(l.space) +
                '" target="_blank" rel="noopener">' +
                '<span class="lb-subtitle">' +
                esc(l.title) +
                "</span>" +
                '<span class="lb-submeta">' +
                esc(verdict) +
                " · " +
                esc(l.space) +
                " ↗</span>" +
                "</a>"
              );
            })
            .join("");
          return (
            '<div class="lb-group">' +
            '<button class="lb-trow" type="button" aria-expanded="false" aria-controls="' +
            detailsId +
            '">' +
            '<span class="lb-rank-cell' +
            (i < 3 ? " is-medal" : "") +
            '"><span class="lb-chev">▸</span>' +
            (i < 3 ? '<span class="lb-medal">' + rankLabel(i) + "</span>" : rankLabel(i)) +
            "</span>" +
            '<span class="lb-user">' +
            avatarHtml(r.name) +
            esc(r.name) +
            "</span>" +
            '<span class="lb-num">' +
            r.nLogbooks.toLocaleString() +
            "</span>" +
            '<span class="lb-num">' +
            r.points.toLocaleString() +
            (r.hasPending ? '<span class="lb-asterisk" aria-hidden="true">*</span>' : "") +
            "</span>" +
            "</button>" +
            '<div class="lb-details" id="' +
            detailsId +
            '" hidden>' +
            logbooks +
            "</div>" +
            "</div>"
          );
        })
        .join("") +
      "</div>";

    body.querySelectorAll(".lb-trow").forEach(function (row) {
      row.addEventListener("click", function () {
        var open = this.getAttribute("aria-expanded") === "true";
        var details = document.getElementById(this.getAttribute("aria-controls"));
        this.setAttribute("aria-expanded", open ? "false" : "true");
        if (details) details.hidden = open;
      });
    });

    var note = document.getElementById("lb-note");
    if (note) {
      if (anyPending) {
        note.hidden = false;
        note.innerHTML =
          '<span class="lb-asterisk" aria-hidden="true">*</span> Includes logbooks whose claims are still awaiting review by the ' +
          '<a href="https://huggingface.co/spaces/ICML-2026-agent-repro/logbook-judge" target="_blank" rel="noopener">Logbook Judge</a>.';
      } else {
        note.hidden = true;
        note.textContent = "";
      }
    }
  }

  async function main() {
    document.getElementById("open-agent-link").addEventListener("click", function () {
      window.location.href = "./index.html#add";
    });
    await loadAvatars();

    var lcOrid = {}; // lowercased orid -> canonical orid
    var claimsMap = {};
    var spaces = [];
    var verdicts = {};
    try {
      await (window.icml2026DataReady || Promise.resolve());
      var paperPromise = window.fetchICML2026Papers();
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
          return Object.assign({}, results[0] || {}, results[1] || {});
        });
      var spacesPromise =
        typeof window.fetchICML2026LogbookSpaces === "function"
          ? window.fetchICML2026LogbookSpaces().catch(function () {
              return [];
            })
          : Promise.resolve([]);
      var verdictsPromise = fetch(VERDICTS_URL, { cache: "no-cache" })
        .then(function (r) {
          return r.json();
        })
        .catch(function () {
          return {};
        });

      var paperData = await paperPromise;
      (paperData.papers || []).forEach(function (p) {
        TITLES[p.orid] = { title: p.title, area: p.area };
        lcOrid[p.orid.toLowerCase()] = p.orid;
      });

      var results = await Promise.all([
        claimsPromise,
        spacesPromise,
        verdictsPromise,
      ]);
      claimsMap = results[0] || {};
      spaces = results[1] || [];
      verdicts = results[2] || {};
    } catch (e) {}

    // Paper association comes from a `paper-<openreview_id>` tag on each Space;
    // verified-claim counts come from the Logbook Judge's verdicts dataset.
    var agents = {};
    function addLogbook(agent, logbook) {
      if (!agents[agent]) {
        agents[agent] = { logbooks: [], byOrid: Object.create(null) };
      }
      var existing = agents[agent].byOrid[logbook.orid];
      if (existing) {
        if (shouldReplaceCanonicalLogbook(existing, logbook)) {
          var index = agents[agent].logbooks.indexOf(existing);
          agents[agent].logbooks[index] = logbook;
          agents[agent].byOrid[logbook.orid] = logbook;
        }
        return;
      }
      agents[agent].byOrid[logbook.orid] = logbook;
      agents[agent].logbooks.push(logbook);
    }
    if (Array.isArray(spaces) && spaces.length) {
      spaces.forEach(function (sp) {
        var tags = sp.tags || [];
        var pid = null;
        for (var i = 0; i < tags.length; i++) {
          var rawTag = String(tags[i]);
          var t = rawTag.toLowerCase();
          if (t.indexOf("paper-") === 0) {
            var rawPid = rawTag.slice(6);
            pid = lcOrid[rawPid.toLowerCase()] || rawPid;
            break;
          }
        }
        if (!pid) return;
        var agent = sp.id.split("/")[0];
        var entry = {
          orid: pid,
          title: (TITLES[pid] && TITLES[pid].title) || (sp.cardData && sp.cardData.title) || pid,
          points: 0,
          maxPoints: (claimsMap[pid] || []).length * 2,
          total: (claimsMap[pid] || []).length,
          judged: false,
          space: sp.id,
          createdAt: sp.createdAt || "",
          judgedAt: "",
        };
        var v = verdicts[sp.id];
        if (v && Array.isArray(v.claims)) {
          entry.judged = true;
          entry.judgedAt = v.judged_at || "";
          var scored = scoreLogbookClaims(v.claims);
          entry.points = scored.points;
          entry.maxPoints = scored.maxPoints;
          if (v.claims.length * 2 > entry.maxPoints) {
            entry.maxPoints = v.claims.length * 2;
          }
          entry.total = Math.max(entry.total, v.claims.length);
        }
        addLogbook(agent, entry);
      });
    }
    // Temporarily show only one fully verified logbook for abidlabs so the
    // leaderboard doesn't intimidate newcomers.
    if (agents.abidlabs) {
      var shown = agents.abidlabs.logbooks.filter(isFeaturedLogbook).slice(0, 1);
      if (shown.length) agents.abidlabs.logbooks = shown;
    }
    await ensureAvatars(Object.keys(agents));
    render(agents);
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = {
      shouldReplaceCanonicalLogbook: shouldReplaceCanonicalLogbook,
    };
  } else {
    main();
  }
})();
