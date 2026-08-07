(function () {
  "use strict";

  var DATASET_BASE =
    "https://huggingface.co/datasets/ICML-2026-agent-repro/challenge/resolve/main";
  var DATASET_RAW_BASE =
    "https://huggingface.co/datasets/ICML-2026-agent-repro/challenge/raw/main";
  var INDEX_URL = DATASET_BASE + "/index.json";
  var ABSTRACTS_URL = DATASET_BASE + "/abstracts.json";
  var PAPERS_URL = DATASET_BASE + "/papers.json";
  var PROMPT_URL = "./PROMPT.md";

  var AREA_MAP = {
    deep_learning: "Deep Learning",
    applications: "Applications",
    general_machine_learning: "General Machine Learning",
    social_aspects: "Social Aspects",
    theory: "Theory",
    reinforcement_learning: "Reinforcement Learning",
    optimization: "Optimization",
    probabilistic_methods: "Probabilistic Methods",
    uncategorized: "Uncategorized",
  };

  function titleCase(s) {
    return String(s || "")
      .split("_")
      .filter(Boolean)
      .map(function (w) {
        return w.charAt(0).toUpperCase() + w.slice(1);
      })
      .join(" ");
  }

  function parseArea(primaryArea) {
    var parts = String(primaryArea || "").split("->");
    var prefix = parts[0] || "uncategorized";
    var area = AREA_MAP[prefix] || titleCase(prefix);
    var sub = parts[1] ? titleCase(parts[1]) : "";
    return { area: area, sub: sub };
  }

  function parseType(type) {
    if (type === "Oral") return { type: "Oral", spot: false };
    if (type === "Spotlight") return { type: "Poster", spot: true };
    return { type: "Poster", spot: false };
  }

  function rowToPaper(row, index) {
    var area = parseArea(row.primary_area);
    var typ = parseType(row.type);
    var subNo = row.submission_number;
    // Prefer precomputed ICML virtual event fields. Submission numbers are not
    // valid icml.cc/virtual/.../poster/<id> IDs.
    var pid = row.pid != null && row.pid !== "" ? String(row.pid) : "";
    var vs = row.vs || "";
    return {
      i: subNo != null ? subNo : index + 1,
      pid: pid,
      orid: row.paper_id,
      title: row.title,
      authors: row.authors || [],
      insts: [],
      area: area.area,
      sub: area.sub,
      type: typ.type,
      spot: typ.spot,
      or: row.paper_url,
      vs: vs,
      arxiv: row.arxiv_id || "",
      alphaxiv: row.arxiv_id || "",
      hf: row.hf || "",
    };
  }

  function buildPayload(rows) {
    var papers = [];
    var abstracts = {};
    var areas = {};
    var areaTree = {};
    rows.forEach(function (row, index) {
      var paper = rowToPaper(row, index);
      papers.push(paper);
      if (row.abstract) abstracts[paper.orid] = row.abstract;
      areas[paper.area] = 1;
      if (paper.sub) {
        if (!areaTree[paper.area]) areaTree[paper.area] = {};
        areaTree[paper.area][paper.sub] = 1;
      }
    });
    papers.sort(function (a, b) {
      return a.i - b.i;
    });
    var tree = {};
    Object.keys(areaTree)
      .sort()
      .forEach(function (area) {
        tree[area] = Object.keys(areaTree[area]).sort();
      });
    return {
      papers: papers,
      abstracts: abstracts,
      areas: Object.keys(areas).sort(),
      areaTree: tree,
    };
  }

  function fetchJson(url) {
    return fetch(url).then(function (r) {
      if (!r.ok) throw new Error(url + " returned " + r.status);
      return r.json();
    });
  }

  function areaTreeFromPapers(papers) {
    var areaTree = {};
    papers.forEach(function (p) {
      if (p.sub) {
        if (!areaTree[p.area]) areaTree[p.area] = {};
        areaTree[p.area][p.sub] = 1;
      }
    });
    var tree = {};
    Object.keys(areaTree)
      .sort()
      .forEach(function (area) {
        tree[area] = Object.keys(areaTree[area]).sort();
      });
    return tree;
  }

  function metadataFromPapers(papers, areas, areaTree) {
    var tree = areaTree;
    if (!tree || !Object.keys(tree).length) {
      tree = areaTreeFromPapers(papers);
    }
    var areaList = areas && areas.length ? areas : Object.keys(tree).sort();
    if (!areaList.length) {
      var areaSet = {};
      papers.forEach(function (p) {
        areaSet[p.area] = 1;
      });
      areaList = Object.keys(areaSet).sort();
    }
    return {
      papers: papers,
      areas: areaList,
      areaTree: tree,
    };
  }

  function fromIndexData(data) {
    if (data.papers) {
      return metadataFromPapers(data.papers, data.areas, data.areaTree);
    }
    if (Array.isArray(data)) {
      return fromIndexList(data);
    }
    throw new Error("unexpected index.json shape");
  }

  function fromIndexList(rows) {
    var papers = rows.slice();
    var areas = {};
    var areaTree = {};
    papers.forEach(function (p) {
      areas[p.area] = 1;
      if (p.sub) {
        if (!areaTree[p.area]) areaTree[p.area] = {};
        areaTree[p.area][p.sub] = 1;
      }
    });
    papers.sort(function (a, b) {
      return a.i - b.i;
    });
    var tree = {};
    Object.keys(areaTree)
      .sort()
      .forEach(function (area) {
        tree[area] = Object.keys(areaTree[area]).sort();
      });
    return metadataFromPapers(papers, Object.keys(areas).sort(), tree);
  }

  function loadIndex(onProgress) {
    if (onProgress) onProgress(0, 1);
    return fetchJson(INDEX_URL).then(function (data) {
      if (onProgress) onProgress(1, 1);
      return fromIndexData(data);
    });
  }

  function loadBundled(onProgress) {
    if (onProgress) onProgress(0, 1);
    return fetchJson(PAPERS_URL).then(function (data) {
      if (onProgress) onProgress(1, 1);
      if (data.papers) return metadataFromPapers(data.papers, data.areas, data.areaTree);
      if (Array.isArray(data)) {
        return buildPayload(
          data.map(function (p) {
            return {
              paper_id: p.orid,
              title: p.title,
              paper_url: p.or,
              authors: p.authors,
              type: p.spot ? "Spotlight" : p.type,
              primary_area:
                (p.area || "uncategorized").toLowerCase().replace(/ /g, "_") +
                (p.sub
                  ? "->" + p.sub.toLowerCase().replace(/ /g, "_")
                  : ""),
              abstract: null,
              submission_number: p.i,
              arxiv_id: p.arxiv || p.alphaxiv || "",
              hf: p.hf || "",
            };
          })
        );
      }
      throw new Error("unexpected papers.json shape");
    });
  }

  function loadLegacy(onProgress) {
    if (onProgress) onProgress(0, 1);
    return fetchJson("./index.json").then(function (data) {
      if (onProgress) onProgress(1, 1);
      return fromIndexData(data);
    });
  }

  var abstractsPromise = null;

  window.fetchICML2026Papers = function (onProgress) {
    return loadIndex(onProgress)
      .catch(function () {
        return loadBundled(onProgress);
      })
      .catch(function () {
        return loadLegacy(onProgress);
      });
  };

  window.fetchICML2026Abstracts = function () {
    if (abstractsPromise) return abstractsPromise;
    abstractsPromise = fetchJson(ABSTRACTS_URL)
      .catch(function () {
        return fetchJson("./abstracts.json");
      })
      .catch(function () {
        return {};
      });
    return abstractsPromise;
  };

  var challengePromptPromise = null;

  function stripYamlFrontmatter(text) {
    return String(text || "").replace(/^---[\s\S]*?---\n?/, "");
  }

  window.fetchICML2026ChallengePrompt = function (force) {
    if (challengePromptPromise && !force) return challengePromptPromise;
    challengePromptPromise = fetch(PROMPT_URL, { cache: "no-store" })
      .then(function (r) {
        return r.ok ? r.text() : Promise.reject(new Error("prompt fetch failed"));
      })
      .then(function (text) {
        return stripYamlFrontmatter(text);
      })
      .catch(function () {
        return null;
      });
    return challengePromptPromise;
  };

  // Back-compat alias for older callers.
  window.fetchICML2026ChallengeReadme = window.fetchICML2026ChallengePrompt;

  // Spaces listing ignores offset and caps each page; walk Link rel="next"
  // cursors instead. createdAt avoids lastModified-tail 504s past ~1000 rows.
  var LOGBOOK_SPACES_URL =
    "https://huggingface.co/api/spaces?filter=icml2026-repro" +
    "&expand[]=tags&expand[]=sha&sort=createdAt&direction=-1&limit=500";

  function nextLinkFromHeader(linkHeader) {
    if (!linkHeader) return null;
    var parts = String(linkHeader).split(",");
    for (var i = 0; i < parts.length; i++) {
      var m = parts[i].match(/<([^>]+)>\s*;\s*rel="?next"?/i);
      if (m) return m[1];
    }
    return null;
  }

  window.fetchICML2026LogbookSpaces = function () {
    var all = [];
    var url = LOGBOOK_SPACES_URL;
    var seen = {};

    function step() {
      if (!url || seen[url]) return Promise.resolve(all);
      seen[url] = true;
      return fetch(url).then(function (r) {
        if (!r.ok) throw new Error("spaces listing returned " + r.status);
        url = nextLinkFromHeader(r.headers.get("link"));
        return r.json().then(function (page) {
          if (Array.isArray(page) && page.length) {
            all = all.concat(page);
          } else {
            url = null;
          }
          return step();
        });
      });
    }

    return step();
  };

  window.icml2026DataReady = Promise.resolve();
})();
