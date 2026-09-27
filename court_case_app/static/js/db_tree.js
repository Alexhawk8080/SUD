// Сайдбар с деревом «участок → год» и созданием (D6a + D6f).
//
// Загружает /api/db_tree, рендерит дерево, обрабатывает клики:
//   - клик по участку     — раскрыть/свернуть;
//   - клик по «+» участка — создать год в нём;
//   - клик по году        — переход на /db/year/<id>;
//   - кнопка «+ Участок»  — создать участок;
//   - кнопка ≡            — свернуть сайдбар (localStorage).

(function () {
    "use strict";

    var STORAGE_KEY = "sidebar_collapsed";
    var ACTIVE_KEY = "sidebar_active_year";

    function escapeHtml(s) {
        var d = document.createElement("div");
        d.textContent = (s == null) ? "" : String(s);
        return d.innerHTML;
    }

    function el(id) { return document.getElementById(id); }

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
            var open = a.years_count > 0 ? " open" : "";
            html += '<div class="tree-area' + open + '" data-area-id="' +
                a.id + '">';
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
                var badges = "";
                if (y.is_closed) {
                    badges += '<span class="tree-year-badge">закрыт</span>';
                }
                if (y.is_incomplete) {
                    badges += '<span class="tree-year-badge warn">⚠</span>';
                }
                if (y.result_is_stale) {
                    badges += '<span class="tree-year-badge stale">устарел</span>';
                }
                html += '<div class="tree-year-row" data-year-id="' +
                    y.id + '">';
                html += '<span class="tree-year-label">' +
                    escapeHtml(y.year) + '</span>';
                html += '<span class="tree-year-badge">' +
                    y.cases_count + ' дел</span>';
                html += badges;
                html += '</div>';
            });
            html += '</div></div>';
        });
        body.innerHTML = html;

        // Раскрытие/сворачивание участка
        body.querySelectorAll(".tree-area-row").forEach(function (row) {
            row.addEventListener("click", function (ev) {
                // Клик по кнопке «+» — не сворачивать
                if (ev.target.classList.contains("tree-area-add")) return;
                var area = row.parentElement;
                area.classList.toggle("open");
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

        // Переход на год
        body.querySelectorAll(".tree-year-row").forEach(function (row) {
            row.addEventListener("click", function () {
                var yid = row.getAttribute("data-year-id");
                try { localStorage.setItem(ACTIVE_KEY, yid); } catch (e) {}
                window.location.href = "/db/year/" + yid;
            });
        });

        highlightActive();
    }

    function highlightActive() {
        var activeId = null;
        try { activeId = localStorage.getItem(ACTIVE_KEY); } catch (e) {}
        var m = window.location.pathname.match(/\/db\/year\/(\d+)/);
        if (m) activeId = m[1];
        if (!activeId) return;
        document.querySelectorAll(".tree-year-row").forEach(function (el2) {
            if (el2.getAttribute("data-year-id") === activeId) {
                el2.classList.add("active");
                var area = el2.closest(".tree-area");
                if (area) area.classList.add("open");
            }
        });
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
                'заполнить позже на странице года, таб «Реквизиты».</p>';

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
                // Если нужно — скопировать реквизиты
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
                // Переходим на созданный год
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
