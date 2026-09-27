// Сайдбар с деревом «участок → год» (stage16d6a)
//
// Загружает /api/db_tree, рендерит дерево, обрабатывает клики:
//   - клик по участку — раскрыть/свернуть годы;
//   - клик по году   — переход на /db/year/<id>;
//   - кнопка ≡       — свернуть сайдбар (сохраняется в localStorage).

(function () {
    "use strict";

    var STORAGE_KEY = "sidebar_collapsed";
    var ACTIVE_KEY = "sidebar_active_year";

    function escapeHtml(s) {
        var d = document.createElement("div");
        d.textContent = s == null ? "" : String(s);
        return d.innerHTML;
    }

    function loadTree() {
        var body = document.getElementById("db-tree");
        if (!body) return;

        fetch("/api/db_tree", { cache: "no-store" })
            .then(function (r) { return r.json(); })
            .then(function (data) { renderTree(data); })
            .catch(function () {
                body.innerHTML =
                    '<p class="sidebar-hint">Не удалось загрузить дерево</p>';
            });
    }

    function renderTree(data) {
        var body = document.getElementById("db-tree");
        if (!body) return;
        var areas = (data && data.areas) || [];
        if (!areas.length) {
            body.innerHTML = '<p class="sidebar-hint">Нет участков. ' +
                'Создайте участок на странице «База данных».</p>';
            return;
        }

        var html = "";
        areas.forEach(function (a) {
            var open = a.years_count > 0 ? " open" : "";
            html += '<div class="tree-area' + open + '" data-area-id="' +
                a.id + '">';
            html += '<div class="tree-area-row">';
            html += '<span class="tree-arrow">&#9654;</span>';
            html += '<span class="tree-area-label">' +
                escapeHtml(a["номер"] + " СУ" +
                    (a.name ? " — " + a.name : "")) +
                '</span>';
            html += '<span class="tree-area-count">' +
                a.years_count + '</span>';
            html += '</div>';
            html += '<div class="tree-years">';
            (a.years || []).forEach(function (y) {
                var classes = "tree-year-row";
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
                html += '<div class="' + classes + '" data-year-id="' +
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

        // Обработчики
        body.querySelectorAll(".tree-area-row").forEach(function (el) {
            el.addEventListener("click", function () {
                el.parentElement.classList.toggle("open");
            });
        });
        body.querySelectorAll(".tree-year-row").forEach(function (el) {
            el.addEventListener("click", function () {
                var yid = el.getAttribute("data-year-id");
                try { localStorage.setItem(ACTIVE_KEY, yid); } catch (e) {}
                window.location.href = "/db/year/" + yid;
            });
        });

        // Подсветка активного года
        highlightActive();
    }

    function highlightActive() {
        var activeId = null;
        try { activeId = localStorage.getItem(ACTIVE_KEY); } catch (e) {}
        // Также — по URL
        var m = window.location.pathname.match(/\/db\/year\/(\d+)/);
        if (m) activeId = m[1];
        if (!activeId) return;
        var rows = document.querySelectorAll(".tree-year-row");
        rows.forEach(function (el) {
            if (el.getAttribute("data-year-id") === activeId) {
                el.classList.add("active");
                // Раскрыть родителя
                var area = el.closest(".tree-area");
                if (area) area.classList.add("open");
            }
        });
    }

    function initToggle() {
        var btn = document.getElementById("sidebar-toggle");
        var sidebar = document.getElementById("db-sidebar");
        if (!btn || !sidebar) return;

        var collapsed = false;
        try { collapsed = localStorage.getItem(STORAGE_KEY) === "1"; } catch (e) {}
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

    function init() {
        if (!document.getElementById("db-sidebar")) return;
        document.body.classList.add("has-sidebar");
        initToggle();
        loadTree();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
