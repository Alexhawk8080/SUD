// Сайдбар с деревом «участок → год → тип дел → раздел» (D6a + D6f + D7b).
//
// Загружает /api/db_tree, рендерит дерево, обрабатывает клики:
//   - клик по участку     — раскрыть/свернуть;
//   - клик по «+» участка — создать год в нём;
//   - клик по году        — обзорная страница /db/year/<id>;
//   - клик по «Реквизиты» — /db/year/<id>/refs;
//   - клик по типу дел    — раскрыть/свернуть ветвь;
//   - клик по разделу     — /db/year/<id>/<civil|admin>/<section>;
//   - кнопка «+ Участок»  — создать участок;
//   - кнопка ≡            — свернуть сайдбар (localStorage).

(function () {
    "use strict";

    var STORAGE_KEY = "sidebar_collapsed";
    var ACTIVE_KEY = "sidebar_active_year";
    var OPEN_KEY = "sidebar_open_nodes";

    var TYPE_TITLES = { civil: "Гражданские дела", admin: "Административные дела" };
    var SECTIONS = [
        { key: "files", title: "Файлы" },
        { key: "cases", title: "Дела" },
        { key: "inventory", title: "Опись" },
        { key: "process", title: "Обработка" },
        { key: "result", title: "Результат" }
    ];

    function escapeHtml(s) {
        var d = document.createElement("div");
        d.textContent = (s == null) ? "" : String(s);
        return d.innerHTML;
    }

    function el(id) { return document.getElementById(id); }

    // =============================================================
    // Состояние раскрытия узлов (localStorage)
    // =============================================================

    function loadOpenSet() {
        try {
            var raw = localStorage.getItem(OPEN_KEY);
            return raw ? JSON.parse(raw) : {};
        } catch (e) { return {}; }
    }

    function saveOpenSet(obj) {
        try { localStorage.setItem(OPEN_KEY, JSON.stringify(obj)); }
        catch (e) { /* ignore */ }
    }

    var OPEN = loadOpenSet();

    function isOpen(key, def) {
        if (Object.prototype.hasOwnProperty.call(OPEN, key)) return !!OPEN[key];
        return !!def;
    }

    function setOpen(key, val) {
        OPEN[key] = !!val;
        saveOpenSet(OPEN);
    }

    // =============================================================
    // Загрузка и рендер дерева
    // =============================================================

    function loadTree() {
        var body = el("db-tree");
        if (!body) return;

        fetch("/api/db_tree", { cache: "no-store" })
            .then(function (r) { return r.json(); })
            .then(renderTree)
            .catch(function () {
                body.innerHTML =
                    '<p class="sidebar-hint">Не удалось загрузить дерево</p>';
            });
    }
    // Публичный метод, чтобы страница могла обновить дерево
    window.refreshDbTree = loadTree;

    function renderTree(data) {
        var body = el("db-tree");
        if (!body) return;
        var areas = (data && data.areas) || [];
        if (!areas.length) {
            body.innerHTML = '<p class="sidebar-hint">Нет участков. ' +
                'Нажмите «+ Участок» ниже.</p>';
            return;
        }

        var html = "";
        areas.forEach(function (a) {
            var areaOpen = isOpen("area:" + a.id, a.years_count > 0);
            html += '<div class="tree-area' + (areaOpen ? " open" : "") +
                '" data-area-id="' + a.id + '">';
            html += '<div class="tree-area-row" data-area-row="1">';
            html += '<span class="tree-arrow">&#9654;</span>';
            html += '<span class="tree-area-label">' +
                escapeHtml(a["номер"] + " СУ" +
                    (a.name ? " — " + a.name : "")) +
                '</span>';
            html += '<span class="tree-area-count">' +
                a.years_count + '</span>';
            html += '<button class="tree-area-add" data-area-add="' + a.id +
                '" title="Добавить год">+</button>';
            html += '</div>';
            html += '<div class="tree-years">';
            (a.years || []).forEach(function (y) {
                html += renderYearNode(y);
            });
            html += '</div></div>';
        });
        body.innerHTML = html;

        bindTreeEvents(body, areas);
        highlightActive();
    }

    function renderYearNode(y) {
        var badges = "";
        if (y.is_closed) {
            badges += '<span class="tree-year-badge">закрыт</span>';
        }
        if (y.is_incomplete) {
            badges += '<span class="tree-year-badge warn">⚠</span>';
        }
        var yearOpen = isOpen("year:" + y.id, false);

        var html = '<div class="tree-year' + (yearOpen ? " open" : "") +
            '" data-year-id="' + y.id + '">';
        html += '<div class="tree-year-row" data-year-row="1">';
        html += '<span class="tree-arrow">&#9654;</span>';
        html += '<span class="tree-year-label">' +
            escapeHtml(y.year) + '</span>';
        html += badges;
        html += '</div>';

        html += '<div class="tree-year-children">';
        // Реквизиты — уровень года
        html += '<div class="tree-leaf" data-year-id="' + y.id +
            '" data-section="refs">Реквизиты</div>';

        // Ветви по типам дел (обе всегда)
        ["civil", "admin"].forEach(function (ct) {
            var t = (y.types && y.types[ct]) || {};
            var typeOpen = isOpen("type:" + y.id + ":" + ct, false);
            html += '<div class="tree-type' + (typeOpen ? " open" : "") +
                '" data-year-id="' + y.id + '" data-case-type="' + ct + '">';
            html += '<div class="tree-type-row" data-type-row="1">';
            html += '<span class="tree-arrow">&#9654;</span>';
            html += '<span class="tree-type-label">' +
                escapeHtml(TYPE_TITLES[ct]) + '</span>';
            html += '<span class="tree-type-count">' +
                (t.cases_count || 0) + '</span>';
            html += '</div>';
            html += '<div class="tree-type-children">';
            SECTIONS.forEach(function (s) {
                var extra = "";
                if (s.key === "result" && t.result_is_stale) {
                    extra = '<span class="tree-year-badge stale">устарел</span>';
                }
                html += '<div class="tree-leaf" data-year-id="' + y.id +
                    '" data-case-type="' + ct + '" data-section="' + s.key +
                    '">' + escapeHtml(s.title) + extra + '</div>';
            });
            html += '</div></div>';
        });

        html += '</div></div>';
        return html;
    }

    function bindTreeEvents(body, areas) {
        // Раскрытие/сворачивание участка
        body.querySelectorAll(".tree-area-row").forEach(function (row) {
            row.addEventListener("click", function (ev) {
                if (ev.target.classList.contains("tree-area-add")) return;
                var area = row.parentElement;
                var open = area.classList.toggle("open");
                setOpen("area:" + area.getAttribute("data-area-id"), open);
            });
        });

        // Кнопки «+ год» рядом с участком
        body.querySelectorAll(".tree-area-add").forEach(function (btn) {
            btn.addEventListener("click", function (ev) {
                ev.stopPropagation();
                var areaId = parseInt(btn.getAttribute("data-area-add"), 10);
                var area = areas.find(function (x) { return x.id === areaId; });
                if (!area) return;
                openYearModal(area);
            });
        });

        // Клик по году — обзорная страница
        body.querySelectorAll(".tree-year-row").forEach(function (row) {
            row.addEventListener("click", function (ev) {
                ev.stopPropagation();
                var node = row.parentElement;
                var yid = node.getAttribute("data-year-id");
                var open = node.classList.toggle("open");
                setOpen("year:" + yid, open);
                goToYear(yid);
            });
        });

        // Раскрытие/сворачивание типа дел
        body.querySelectorAll(".tree-type-row").forEach(function (row) {
            row.addEventListener("click", function (ev) {
                ev.stopPropagation();
                var node = row.parentElement;
                var open = node.classList.toggle("open");
                setOpen("type:" + node.getAttribute("data-year-id") + ":" +
                        node.getAttribute("data-case-type"), open);
            });
        });

        // Клик по листу (раздел)
        body.querySelectorAll(".tree-leaf").forEach(function (leaf) {
            leaf.addEventListener("click", function (ev) {
                ev.stopPropagation();
                var yid = leaf.getAttribute("data-year-id");
                var ct = leaf.getAttribute("data-case-type");
                var section = leaf.getAttribute("data-section");
                goToSection(yid, ct, section);
            });
        });
    }

    function goToYear(yid) {
        try { localStorage.setItem(ACTIVE_KEY, yid); } catch (e) {}
        window.location.href = "/db/year/" + yid;
    }

    function goToSection(yid, caseType, section) {
        try { localStorage.setItem(ACTIVE_KEY, yid); } catch (e) {}
        if (section === "refs") {
            window.location.href = "/db/year/" + yid + "/refs";
            return;
        }
        window.location.href = "/db/year/" + yid + "/" + caseType + "/" + section;
    }

    function highlightActive() {
        var activeId = null;
        try { activeId = localStorage.getItem(ACTIVE_KEY); } catch (e) {}
        var m = window.location.pathname.match(/\/db\/year\/(\d+)/);
        if (m) activeId = m[1];
        if (!activeId) return;

        // Активный год
        document.querySelectorAll(".tree-year").forEach(function (node) {
            if (node.getAttribute("data-year-id") === activeId) {
                node.classList.add("active");
                node.classList.add("open");
                var area = node.closest(".tree-area");
                if (area) area.classList.add("open");
            }
        });

        // Активный раздел
        var route = window.location.pathname.match(
            /\/db\/year\/(\d+)\/([^/]+)\/([^/]+)/);
        if (route) {
            var yid = route[1], ct = route[2], section = route[3];
            document.querySelectorAll(".tree-leaf").forEach(function (leaf) {
                if (leaf.getAttribute("data-year-id") === yid &&
                        leaf.getAttribute("data-case-type") === ct &&
                        leaf.getAttribute("data-section") === section) {
                    leaf.classList.add("active");
                    var type = leaf.closest(".tree-type");
                    if (type) type.classList.add("open");
                }
            });
        } else if (/\/db\/year\/\d+\/refs/.test(window.location.pathname)) {
            document.querySelectorAll('.tree-leaf[data-section="refs"]')
                .forEach(function (leaf) {
                    if (leaf.getAttribute("data-year-id") === activeId) {
                        leaf.classList.add("active");
                    }
                });
        }
    }

    // =============================================================
    // Модальное окно: создание участка / года
    // =============================================================

    var MODAL = {
        mode: null,       // 'area' | 'year'
        areaId: null,
        areaLabel: "",
        years: [],        // годы участка (для опции «копировать из»)
    };

    function openModal(title, bodyHtml) {
        var m = el("sidebar-modal");
        el("sidebar-modal-title").textContent = title;
        el("sidebar-modal-body").innerHTML = bodyHtml;
        el("sidebar-modal-error").textContent = "";
        m.classList.remove("hidden");
    }

    function closeModal() {
        el("sidebar-modal").classList.add("hidden");
    }

    function fieldRow(id, label, placeholder, value) {
        return '<div class="form-row"><label class="field">' + label +
            '<input type="text" id="' + id + '" placeholder="' +
            (placeholder || "") + '" value="' + (value || "") + '">' +
            '</label></div>';
    }

    function openAreaModal() {
        MODAL.mode = "area";
        MODAL.areaId = null;
        MODAL.areaLabel = "";
        MODAL.years = [];
        var html = "";
        html += fieldRow("sa-номер", "Номер участка", "например, 9");
        html += fieldRow("sa-name", "Название (опц.)",
                         "например, СУ № 9 г. Оренбурга");
        html += fieldRow("sa-address", "Адрес (опц.)", "");
        html += fieldRow("sa-note", "Заметка (опц.)", "");
        openModal("Новый судебный участок", html);
        setTimeout(function () {
            var inp = el("sa-номер");
            if (inp) inp.focus();
        }, 50);
    }

    function openYearModal(area) {
        MODAL.mode = "year";
        MODAL.areaId = area.id;
        MODAL.areaLabel = area["номер"] + " СУ";
        MODAL.years = area.years || [];

        var html = "";
        html += fieldRow("sy-year", "Год", "например, 2020");

        if (MODAL.years.length) {
            html += '<div class="form-row"><label class="field">' +
                'Скопировать реквизиты из' +
                '<select id="sy-copy-from">' +
                '<option value="">— не копировать —</option>';
            MODAL.years.forEach(function (y) {
                html += '<option value="' + y.year + '">' +
                    escapeHtml(y.year) + '</option>';
            });
            html += '</select></label></div>';
        }

        html += '<p class="hint">Реквизиты нового года можно будет ' +
                'заполнить позже на странице года, раздел «Реквизиты».</p>';

        openModal("Новый год — " + MODAL.areaLabel, html);
        setTimeout(function () {
            var inp = el("sy-year");
            if (inp) inp.focus();
        }, 50);
    }

    function showModalError(msg) {
        var e = el("sidebar-modal-error");
        if (e) e.textContent = msg || "";
    }

    function submitModal() {
        showModalError("");
        if (MODAL.mode === "area") submitArea();
        else if (MODAL.mode === "year") submitYear();
    }

    function submitArea() {
        var номер = (el("sa-номер").value || "").trim();
        if (!номер) { showModalError("Укажите номер участка."); return; }
        var body = {
            "номер": номер,
            "name": (el("sa-name").value || "").trim(),
            "address": (el("sa-address").value || "").trim(),
            "note": (el("sa-note").value || "").trim(),
        };
        fetch("/api/court_areas", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
        })
            .then(function (r) {
                return r.json().then(function (j) {
                    return { ok: r.ok, data: j };
                });
            })
            .then(function (res) {
                if (!res.ok) {
                    throw new Error((res.data && res.data.error) ||
                                    "Ошибка создания");
                }
                closeModal();
                loadTree();
            })
            .catch(function (e) { showModalError(e.message); });
    }

    function submitYear() {
        var yraw = (el("sy-year").value || "").trim();
        if (!yraw || !/^\d{4}$/.test(yraw)) {
            showModalError("Укажите год (4 цифры).");
            return;
        }
        var year = parseInt(yraw, 10);
        var copyFromEl = el("sy-copy-from");
        var copyFrom = copyFromEl ? copyFromEl.value : "";

        var payload = {
            year: year,
            "судья": "", "секретарь": "",
            "дата_утверждения": "", "дата_акта": "",
            "номер_акта": "", "дата_подписи": "",
            "протокол_эк_дата": "", "протокол_эк_номер": ""
        };

        var areaId = MODAL.areaId;
        fetch("/api/court_areas/" + areaId + "/years", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        })
            .then(function (r) {
                return r.json().then(function (j) {
                    return { ok: r.ok, data: j };
                });
            })
            .then(function (res) {
                if (!res.ok) {
                    throw new Error((res.data && res.data.error) ||
                                    "Ошибка создания года");
                }
                var newYearId = res.data.id;
                if (copyFrom) {
                    return fetch("/api/court_areas/" + areaId +
                                 "/copy_refs", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            from_year: parseInt(copyFrom, 10),
                            to_year: year
                        })
                    }).then(function (r) {
                        if (!r.ok) throw new Error(
                            "Год создан, но копирование реквизитов не удалось");
                        return newYearId;
                    });
                }
                return newYearId;
            })
            .then(function (newYearId) {
                closeModal();
                loadTree();
                window.location.href = "/db/year/" + newYearId;
            })
            .catch(function (e) { showModalError(e.message); });
    }

    function initModal() {
        var btnOk = el("sidebar-modal-ok");
        var btnCancel = el("sidebar-modal-cancel");
        var modal = el("sidebar-modal");
        if (!modal) return;

        if (btnOk) btnOk.addEventListener("click", submitModal);
        if (btnCancel) btnCancel.addEventListener("click", closeModal);
        modal.addEventListener("click", function (ev) {
            if (ev.target === modal) closeModal();
        });
        document.addEventListener("keydown", function (ev) {
            if (ev.key === "Escape" && !modal.classList.contains("hidden")) {
                closeModal();
            } else if (ev.key === "Enter" &&
                       !modal.classList.contains("hidden")) {
                submitModal();
            }
        });

        var btnArea = el("sidebar-add-area");
        if (btnArea) btnArea.addEventListener("click", openAreaModal);
    }

    // =============================================================
    // Сворачивание
    // =============================================================

    function initToggle() {
        var btn = el("sidebar-toggle");
        var sidebar = el("db-sidebar");
        if (!btn || !sidebar) return;

        var collapsed = false;
        try { collapsed = localStorage.getItem(STORAGE_KEY) === "1"; }
        catch (e) {}
        if (collapsed) {
            sidebar.classList.add("collapsed");
            document.body.classList.add("sidebar-collapsed");
        }

        btn.addEventListener("click", function () {
            var isCollapsed = sidebar.classList.toggle("collapsed");
            document.body.classList.toggle("sidebar-collapsed", isCollapsed);
            try {
                localStorage.setItem(STORAGE_KEY, isCollapsed ? "1" : "0");
            } catch (e) {}
        });
    }

    // =============================================================
    // Init
    // =============================================================

    function init() {
        if (!el("db-sidebar")) return;
        document.body.classList.add("has-sidebar");
        initToggle();
        initModal();
        loadTree();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
