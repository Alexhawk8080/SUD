// Страница года (D7): клиентский роутинг по URL + разделы.
//
// URL-схема:
//   /db/year/<id>                          — обзорная сводка
//   /db/year/<id>/refs                     — реквизиты (уровень года)
//   /db/year/<id>/<civil|admin>/files      — файлы типа
//   /db/year/<id>/<civil|admin>/cases      — дела типа
//   /db/year/<id>/<civil|admin>/inventory  — опись (заглушка)
//   /db/year/<id>/<civil|admin>/process    — обработка типа
//   /db/year/<id>/<civil|admin>/result     — результат типа
//
// Переходы внутри страницы — history.pushState + fetch, без перезагрузки.
// Прямые ссылки работают: при загрузке раздел выбирается по pathname.

(function () {
    "use strict";

    var YEAR_ID = window.YEAR_ID;
    console.log("[year_page] init, year=" + YEAR_ID);

    var CASE_TYPES = ["civil", "admin"];
    var SECTIONS = ["files", "cases", "inventory", "process", "result"];
    var TYPE_TITLES = { civil: "Гражданские дела", admin: "Административные дела" };
    var SECTION_TITLES = {
        files: "Файлы", cases: "Дела", inventory: "Опись",
        process: "Обработка", result: "Результат"
    };

    // =================================================================
    // Общие помощники
    // =================================================================

    function el(id) { return document.getElementById(id); }

    function escapeHtml(s) {
        var d = document.createElement("div");
        d.textContent = (s == null) ? "" : String(s);
        return d.innerHTML;
    }

    function showError(id, msg) {
        var e = el(id);
        if (e) e.textContent = msg || "";
    }

    // =================================================================
    // Роутинг
    // =================================================================

    // Разбирает pathname в {view, caseType, section}.
    //   view: 'overview' | 'refs' | 'section'
    function parseRoute(pathname) {
        var m = String(pathname || "").match(
            /\/db\/year\/(\d+)(?:\/([^/]+))?(?:\/([^/]+))?/);
        if (!m) return { view: "overview", caseType: null, section: null };
        var seg1 = m[2] || "";
        var seg2 = m[3] || "";
        if (!seg1) return { view: "overview", caseType: null, section: null };
        if (seg1 === "refs") {
            return { view: "refs", caseType: null, section: null };
        }
        if (CASE_TYPES.indexOf(seg1) !== -1 &&
                SECTIONS.indexOf(seg2) !== -1) {
            return { view: "section", caseType: seg1, section: seg2 };
        }
        return { view: "overview", caseType: null, section: null };
    }

    function routeUrl(caseType, section) {
        if (!caseType) return "/db/year/" + YEAR_ID;
        return "/db/year/" + YEAR_ID + "/" + caseType + "/" + section;
    }

    function navigate(caseType, section, push) {
        var url = routeUrl(caseType, section);
        if (push !== false) {
            try { history.pushState({}, "", url); } catch (e) { /* ignore */ }
        }
        renderRoute(parseRoute(url));
    }

    function renderRoute(route) {
        // Тип дел фиксируется из URL для разделов
        if (route.view === "section") currentCaseType = route.caseType;

        // Скрыть все представления
        document.querySelectorAll(".year-view").forEach(function (v) {
            v.classList.add("hidden");
        });

        var viewId = "view-overview";
        if (route.view === "refs") viewId = "view-refs";
        else if (route.view === "section") viewId = "view-" + route.section;

        var target = el(viewId);
        if (target) target.classList.remove("hidden");

        renderBreadcrumb(route);

        // Загрузка данных для активного раздела
        if (route.view === "overview") loadOverview();
        else if (route.view === "refs") loadYear();
        else if (route.view === "section") {
            if (route.section === "files") loadFiles();
            else if (route.section === "cases") loadSourcesIntoSelect();
            else if (route.section === "inventory") renderInventoryStub(route.caseType);
            else if (route.section === "process") loadSourcesIntoProcess();
            else if (route.section === "result") loadResult();
        }
    }

    function renderBreadcrumb(route) {
        var box = el("year-breadcrumb");
        if (!box) return;
        var year = (window._yearData && window._yearData.year) || "";
        var parts = [];
        parts.push('<a href="/db/year/' + YEAR_ID +
            '" data-nav="overview">Год ' + escapeHtml(year) + '</a>');
        if (route.view === "refs") {
            parts.push('<span class="sep">›</span><span>Реквизиты</span>');
        } else if (route.view === "section") {
            parts.push('<span class="sep">›</span><span>' +
                escapeHtml(TYPE_TITLES[route.caseType] || route.caseType) +
                '</span>');
            parts.push('<span class="sep">›</span><span>' +
                escapeHtml(SECTION_TITLES[route.section] || route.section) +
                '</span>');
        }
        box.innerHTML = parts.join(" ");

        box.querySelectorAll("a[data-nav]").forEach(function (a) {
            a.addEventListener("click", function (ev) {
                ev.preventDefault();
                navigate(null, null);
            });
        });
    }

    // =================================================================
    // Обзорная сводка (D7a)
    // =================================================================

    function loadOverview() {
        showError("overview-error", "");
        fetch("/api/court_years/" + YEAR_ID + "/summary", { cache: "no-store" })
            .then(function (r) {
                if (!r.ok) throw new Error("HTTP " + r.status);
                return r.json();
            })
            .then(renderOverview)
            .catch(function (err) {
                showError("overview-error",
                    "Не удалось загрузить сводку: " + err.message);
            });
    }

    function renderOverview(data) {
        window._yearData = data.year;
        applyYearHeader(data.year);

        var grid = el("overview-grid");
        if (!grid) return;
        grid.innerHTML = "";

        CASE_TYPES.forEach(function (ct) {
            var t = (data.types && data.types[ct]) || {};
            var block = document.createElement("div");
            block.className = "summary-block";

            var h = document.createElement("h3");
            h.textContent = TYPE_TITLES[ct];
            block.appendChild(h);

            var lines = [
                "Файлов: " + (t.files_count || 0) +
                    " (исходных: " + (t.source_files_count || 0) +
                    ", обработанных: " + (t.processed_files_count || 0) + ")",
                "Дел: " + (t.cases_count || 0) +
                    " (валидных: " + (t.valid_count || 0) +
                    ", проблемных: " + (t.problematic_count || 0) +
                    ", алиментных: " + (t.alimony_count || 0) + ")",
                "Результат: " + (t.result_id
                    ? (t.result_processed_at || "есть") +
                      (t.result_is_stale ? " ⚠ устарел" : "")
                    : "—"),
                "Опись: " + (t.inventory_id ? "есть" : "—")
            ];
            var ul = document.createElement("ul");
            ul.className = "summary-list";
            lines.forEach(function (line) {
                var li = document.createElement("li");
                li.textContent = line;
                ul.appendChild(li);
            });
            block.appendChild(ul);

            var btn = document.createElement("button");
            btn.className = "btn btn-primary";
            btn.textContent = "Открыть";
            btn.addEventListener("click", function () {
                navigate(ct, "files");
            });
            block.appendChild(btn);

            grid.appendChild(block);
        });
    }

    function applyYearHeader(y) {
        if (!y) return;
        var title = el("year-title");
        if (title) title.textContent = "Год " + y.year;
        var fi = el("flag-incomplete");
        if (fi) fi.classList.toggle("hidden", !y.is_incomplete);
        var fc = el("flag-closed");
        if (fc) fc.classList.toggle("hidden", !y.is_closed);
    }

    // =================================================================
    // Раздел «Реквизиты» (D7c)
    // =================================================================

    var REF_FIELDS = [
        "судья", "секретарь", "номер_акта",
        "дата_утверждения", "дата_акта", "дата_подписи",
        "протокол_эк_дата", "протокол_эк_номер",
        "admin_retention",
        "note"
    ];

    function showRefsError(msg) {
        showError("refs-error", msg);
        var ok = el("refs-ok"); if (ok) ok.textContent = "";
    }
    function showRefsOk(msg) {
        var ok = el("refs-ok"); if (ok) ok.textContent = msg || "";
        showError("refs-error", "");
    }

    function loadYear() {
        fetch("/api/court_years/" + YEAR_ID, { cache: "no-store" })
            .then(function (r) {
                if (!r.ok) throw new Error("HTTP " + r.status);
                return r.json();
            })
            .then(renderYear)
            .catch(function (err) {
                showRefsError("Не удалось загрузить год: " + err.message);
            });
    }

    function renderYear(y) {
        window._yearData = y;
        applyYearHeader(y);

        REF_FIELDS.forEach(function (f) {
            var inp = el("ref-" + f);
            if (inp) inp.value = y[f] || "";
        });
        var closed = el("ref-is_closed");
        if (closed) closed.checked = !!y.is_closed;
        applyClosedState(y.is_closed);
    }

    function applyClosedState(isClosed) {
        REF_FIELDS.forEach(function (f) {
            var inp = el("ref-" + f);
            if (inp) inp.disabled = !!isClosed;
        });
        var saveBtn = el("refs-save");
        if (saveBtn) saveBtn.disabled = !!isClosed;
        var unlockBtn = el("refs-unlock");
        if (unlockBtn) unlockBtn.classList.toggle("hidden", !isClosed);

        var upBtn = el("files-upload-btn"); if (upBtn) upBtn.disabled = !!isClosed;
        var kind = el("files-kind"); if (kind) kind.disabled = !!isClosed;
        var hr = el("files-header-row"); if (hr) hr.disabled = !!isClosed;

        window._yearClosed = !!isClosed;
        if (typeof loadFiles === "function") loadFiles();
    }

    function collectRefs() {
        var data = { is_closed: el("ref-is_closed").checked };
        REF_FIELDS.forEach(function (f) {
            var inp = el("ref-" + f);
            data[f] = inp ? inp.value.trim() : "";
        });
        return data;
    }

    function saveRefs(e) {
        e.preventDefault();
        showRefsError("");

        var data = collectRefs();

        if (data.is_closed && !window._wasClosed) {
            if (!window.confirm("Пометить год как закрытый? После этого " +
                    "редактирование реквизитов и файлов будет запрещено.")) {
                el("ref-is_closed").checked = false;
                data.is_closed = false;
                return;
            }
        }

        fetch("/api/court_years/" + YEAR_ID, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data)
        })
            .then(function (r) {
                return r.json().then(function (j) {
                    return { ok: r.ok, data: j };
                });
            })
            .then(function (res) {
                if (!res.ok) {
                    throw new Error((res.data && res.data.error) ||
                                    ("HTTP " + res));
                }
                showRefsOk("Сохранено.");
                loadYear();
                if (window.refreshDbTree) window.refreshDbTree();
            })
            .catch(function (err) {
                showRefsError("Ошибка сохранения: " + err.message);
            });
    }

    function unlockYear() {
        if (!window.confirm("Разблокировать год? Все предупреждения о " +
                "закрытии будут сняты.")) return;
        var data = collectRefs();
        data.is_closed = false;
        fetch("/api/court_years/" + YEAR_ID, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data)
        })
            .then(function (r) {
                if (!r.ok) throw new Error("HTTP " + r.status);
                return r.json();
            })
            .then(function () {
                showRefsOk("Год разблокирован.");
                loadYear();
            })
            .catch(function (err) { showRefsError("Ошибка: " + err.message); });
    }

    // =================================================================
    // Раздел «Файлы» (D7d)
    // =================================================================

    var FILES = [];
    var filesKind = null;
    var currentCaseType = "civil";

    function showFilesError(msg) {
        showError("files-error", msg);
        var ok = el("files-ok"); if (ok) ok.textContent = "";
    }
    function showFilesOk(msg) {
        var ok = el("files-ok"); if (ok) ok.textContent = msg || "";
        showError("files-error", "");
    }

    function initFilesTab() {
        var drop = el("files-drop-zone");
        var input = el("files-file-input");
        if (!drop || !input) return;

        drop.addEventListener("click", function () {
            fetch("/api/ping", { method: "POST", cache: "no-store" })
                .catch(function () {});
            input.click();
        });
        drop.addEventListener("dragover", function (e) {
            e.preventDefault();
            drop.classList.add("dragover");
        });
        drop.addEventListener("dragleave", function () {
            drop.classList.remove("dragover");
        });
        drop.addEventListener("drop", function (e) {
            e.preventDefault();
            drop.classList.remove("dragover");
            if (e.dataTransfer.files.length) setFile(e.dataTransfer.files[0]);
        });
        input.addEventListener("change", function () {
            if (input.files.length) setFile(input.files[0]);
        });

        el("files-upload-btn").addEventListener("click", uploadFile);

        document.querySelectorAll('input[name="files-filter"]').forEach(
            function (r) {
                r.addEventListener("change", renderFiles);
            });
    }

    function setFile(file) {
        filesKind = file;
        var info = el("files-file-info");
        if (info) info.textContent = file ? ("Выбран файл: " + file.name) : "";
    }

    function loadFiles() {
        fetch("/api/court_years/" + YEAR_ID + "/source_files",
              { cache: "no-store" })
            .then(function (r) {
                if (!r.ok) throw new Error("HTTP " + r.status);
                return r.json();
            })
            .then(function (list) {
                FILES = list || [];
                renderFiles();
            })
            .catch(function (err) {
                showFilesError("Не удалось загрузить файлы: " + err.message);
            });
    }

    function renderFiles() {
        var tbody = document.querySelector("#files-table tbody");
        if (!tbody) return;

        var filter = "all";
        var f = document.querySelector('input[name="files-filter"]:checked');
        if (f) filter = f.value;

        var rows = FILES.filter(function (r) {
            return filter === "all" || r.file_kind === filter;
        });

        tbody.innerHTML = "";
        var empty = el("files-empty");
        if (rows.length) empty.classList.add("hidden");
        else empty.classList.remove("hidden");

        var closed = !!window._yearClosed;

        rows.forEach(function (r) {
            var tr = document.createElement("tr");
            function td(text, cls) {
                var c = document.createElement("td");
                c.textContent = (text == null) ? "" : String(text);
                if (cls) c.className = cls;
                return c;
            }

            tr.appendChild(td("v" + r.version));
            tr.appendChild(td(r.file_kind));
            tr.appendChild(td(r.filename));
            tr.appendChild(td(r.row_count));
            var imp = (r.imported_at || "").replace("T", " ").slice(0, 16);
            tr.appendChild(td(imp));

            var st = document.createElement("td");
            if (r.is_current) {
                st.textContent = "актуальный";
                st.style.color = "#2e7d32";
            } else {
                st.textContent = "—";
            }
            tr.appendChild(st);

            var act = document.createElement("td");
            act.style.whiteSpace = "nowrap";

            var a = document.createElement("a");
            a.href = "/api/source_files/" + r.id + "/content";
            a.className = "btn btn-secondary";
            a.textContent = "Скачать";
            act.appendChild(a);

            if (!r.is_current) {
                var bCur = document.createElement("button");
                bCur.className = "btn btn-primary";
                bCur.textContent = "Сделать актуальной";
                bCur.disabled = closed;
                bCur.addEventListener("click", function () {
                    setCurrentFile(r.id, r.filename);
                });
                act.appendChild(bCur);
            }

            var bDel = document.createElement("button");
            bDel.className = "btn btn-danger";
            bDel.textContent = "Удалить";
            bDel.disabled = closed;
            bDel.addEventListener("click", function () {
                deleteFile(r.id, r.filename, r.is_current);
            });
            act.appendChild(bDel);

            tr.appendChild(act);
            tbody.appendChild(tr);
        });
    }

    function uploadFile() {
        showFilesError("");
        if (!filesKind) { showFilesError("Выберите файл."); return; }

        var kind = el("files-kind").value;
        var hrRaw = el("files-header-row").value.trim();
        var form = new FormData();
        form.append("file", filesKind);
        form.append("file_kind", kind);
        form.append("case_type", currentCaseType);
        if (hrRaw !== "") form.append("header_row", hrRaw);

        var btn = el("files-upload-btn");
        btn.disabled = true;
        btn.textContent = "Загрузка…";

        fetch("/api/court_years/" + YEAR_ID + "/source_files", {
            method: "POST",
            body: form
        })
            .then(function (r) {
                return r.json().then(function (j) {
                    return { ok: r.ok, data: j };
                });
            })
            .then(function (res) {
                if (!res.ok) {
                    throw new Error((res.data && res.data.error) ||
                                    "Ошибка загрузки");
                }
                var d = res.data;
                showFilesOk("Загружено: " + d.row_count + " строк, " +
                            "годных: " + d.valid_count +
                            ", проблемных: " + d.problematic_count);
                filesKind = null;
                el("files-file-input").value = "";
                el("files-file-info").textContent = "";
                loadFiles();
                if (window.refreshDbTree) window.refreshDbTree();
            })
            .catch(function (err) { showFilesError(err.message); })
            .finally(function () {
                btn.disabled = !!window._yearClosed;
                btn.textContent = "Загрузить";
            });
    }

    function setCurrentFile(fileId, filename) {
        if (!window.confirm("Сделать версию «" + filename +
                            "» актуальной для этого года?")) return;
        fetch("/api/source_files/" + fileId + "/set_current",
              { method: "POST" })
            .then(function (r) {
                if (!r.ok) throw new Error("HTTP " + r.status);
                return r.json();
            })
            .then(function () {
                showFilesOk("Актуальная версия обновлена.");
                loadFiles();
                if (window.refreshDbTree) window.refreshDbTree();
            })
            .catch(function (err) { showFilesError(err.message); });
    }

    function deleteFile(fileId, filename, isCurrent) {
        var msg = "Удалить версию «" + filename + "»? " +
                  "Связанные дела тоже будут удалены.";
        if (isCurrent) msg = "ВНИМАНИЕ: это актуальная версия. " + msg;
        if (!window.confirm(msg)) return;
        fetch("/api/source_files/" + fileId, { method: "DELETE" })
            .then(function (r) {
                if (!r.ok) throw new Error("HTTP " + r.status);
                return r.json();
            })
            .then(function () {
                showFilesOk("Версия удалена.");
                loadFiles();
                if (window.refreshDbTree) window.refreshDbTree();
            })
            .catch(function (err) { showFilesError(err.message); });
    }

    // =================================================================
    // Раздел «Дела» (D7d)
    // =================================================================

    var CASES = [];
    var casesSourceId = null;

    function showCasesError(msg) {
        showError("cases-error", msg);
    }

    function initCasesTab() {
        var sel = el("cases-source");
        if (!sel) return;
        sel.addEventListener("change", function () {
            casesSourceId = sel.value ? parseInt(sel.value, 10) : null;
            loadCases();
        });
        ["cases-only-valid", "cases-only-problematic", "cases-only-alimony"]
            .forEach(function (id) {
                var ch = el(id);
                if (ch) ch.addEventListener("change", renderCases);
            });
    }

    function loadSourcesIntoSelect() {
        var apply = function (list) {
            var sel = el("cases-source");
            if (!sel) return;
            var keep = sel.value;
            sel.innerHTML = '<option value="">— выберите файл —</option>';
            list.forEach(function (f) {
                var opt = document.createElement("option");
                opt.value = String(f.id);
                var mark = f.is_current ? " ⭐" : "";
                opt.textContent = "v" + f.version + " · " + f.file_kind +
                    " · " + f.filename + mark;
                sel.appendChild(opt);
            });
            var wanted = keep;
            if (!wanted) {
                var cur = list.find(function (f) {
                    return f.is_current && f.file_kind === "source";
                });
                if (cur) wanted = String(cur.id);
            }
            if (wanted) {
                sel.value = wanted;
                casesSourceId = parseInt(wanted, 10);
            }
            loadCases();
        };
        if (FILES && FILES.length) {
            apply(FILES);
        } else {
            fetch("/api/court_years/" + YEAR_ID + "/source_files",
                  { cache: "no-store" })
                .then(function (r) { return r.json(); })
                .then(apply)
                .catch(function () {
                    showCasesError("Не удалось загрузить список файлов");
                });
        }
    }

    function loadCases() {
        showCasesError("");
        if (!casesSourceId) { CASES = []; renderCases(); return; }
        fetch("/api/source_files/" + casesSourceId + "/cases?case_type=" +
              currentCaseType, { cache: "no-store" })
            .then(function (r) {
                if (!r.ok) throw new Error("HTTP " + r.status);
                return r.json();
            })
            .then(function (list) { CASES = list || []; renderCases(); })
            .catch(function (err) {
                showCasesError("Не удалось загрузить дела: " + err.message);
            });
    }

    function renderCases() {
        var tbody = document.querySelector("#cases-table tbody");
        if (!tbody) return;

        var onlyValid = el("cases-only-valid").checked;
        var onlyProblem = el("cases-only-problematic").checked;
        var onlyAlim = el("cases-only-alimony").checked;

        var rows = CASES.filter(function (c) {
            if (onlyValid && !c.is_valid) return false;
            if (onlyProblem && !c.is_problematic) return false;
            if (onlyAlim && !c.is_alimony) return false;
            return true;
        });

        var info = el("cases-info");
        if (info) info.textContent = "Всего дел в файле: " + CASES.length +
            " · показано: " + rows.length;

        tbody.innerHTML = "";
        var empty = el("cases-empty");
        if (rows.length) empty.classList.add("hidden");
        else empty.classList.remove("hidden");

        rows.forEach(function (c, idx) {
            var tr = document.createElement("tr");
            if (!c.is_valid) tr.style.background = "#fdecea";
            else if (c.is_alimony) tr.style.background = "#fff7e0";
            else if (c.is_problematic) tr.style.background = "#fff9e6";

            function cell(text) {
                var td = document.createElement("td");
                td.textContent = (text == null) ? "" : String(text);
                return td;
            }

            tr.appendChild(cell(c.row_index || (idx + 1)));
            tr.appendChild(cell(c.case_number));
            tr.appendChild(cell(c.date));
            tr.appendChild(cell(c.applicants));
            tr.appendChild(cell(c.respondents));
            tr.appendChild(cell(c.category));
            tr.appendChild(cell(c.opis_number));
            tr.appendChild(cell(c.unit_number));
            tr.appendChild(cell(c.note));

            var status = document.createElement("td");
            if (!c.is_valid) {
                status.textContent = "пропуск: " +
                    (c.skip_reason || "невалидное");
                status.style.color = "#c62828";
            } else if (c.is_alimony) {
                status.textContent = "алиментное";
                status.style.color = "#a06d00";
            } else if (c.is_problematic) {
                status.textContent = "проблемная категория";
                status.style.color = "#a06d00";
            } else {
                status.textContent = "ok";
                status.style.color = "#2e7d32";
            }
            tr.appendChild(status);
            tbody.appendChild(tr);
        });
    }

    // =================================================================
    // Раздел «Опись» (D7e, заглушка)
    // =================================================================

    function renderInventoryStub(caseType) {
        var note = el("inventory-stub-note");
        if (note) {
            note.textContent = "Тип дел: " +
                (TYPE_TITLES[caseType] || caseType) +
                ". Раздел пока не реализован.";
        }
    }

    // =================================================================
    // Раздел «Обработка» (D7d)
    // =================================================================

    function showProcessError(msg) {
        showError("process-error", msg);
        var ok = el("process-ok"); if (ok) ok.textContent = "";
    }
    function showProcessOk(msg) {
        var ok = el("process-ok"); if (ok) ok.textContent = msg || "";
        showError("process-error", "");
    }

    function initProcessTab() {
        var btn = el("process-btn");
        if (btn) btn.addEventListener("click", runProcess);
    }

    function loadSourcesIntoProcess() {
        var sel = el("process-source");
        if (!sel) return;
        var apply = function (list) {
            var keep = sel.value;
            sel.innerHTML = '<option value="">— актуальный source —</option>';
            list.forEach(function (f) {
                if (f.file_kind !== "source") return;
                var opt = document.createElement("option");
                opt.value = String(f.id);
                var mark = f.is_current ? " ⭐" : "";
                opt.textContent = "v" + f.version + " · " + f.filename + mark;
                sel.appendChild(opt);
            });
            if (keep) sel.value = keep;
        };
        if (FILES && FILES.length) {
            apply(FILES);
        } else {
            fetch("/api/court_years/" + YEAR_ID + "/source_files",
                  { cache: "no-store" })
                .then(function (r) { return r.json(); })
                .then(apply)
                .catch(function () {});
        }
    }

    function runProcess() {
        showProcessError("");
        var sel = el("process-source");
        var sourceId = (sel && sel.value) ? parseInt(sel.value, 10) : null;

        var body = {
            case_type: currentCaseType,
            process_alimony: el("process-alimony").checked,
            auto_fix: el("process-autofix").checked,
            source_file_id: sourceId
        };

        var btn = el("process-btn");
        btn.disabled = true;
        btn.textContent = "Обработка…";

        fetch("/api/court_years/" + YEAR_ID + "/process", {
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
                                    "Ошибка обработки");
                }
                var d = res.data;
                showProcessOk("Готово. Записей: " + d.record_count +
                              " · в диапазоне: " +
                              ((d.stats && d.stats.total_in_range) || "—"));
                if (window.refreshDbTree) window.refreshDbTree();
            })
            .catch(function (err) { showProcessError(err.message); })
            .finally(function () {
                btn.disabled = false;
                btn.textContent = "Обработать";
            });
    }

    // =================================================================
    // Раздел «Результат» (D7d)
    // =================================================================

    var CURRENT_RESULT = null;

    function showResultError(msg) {
        showError("result-error", msg);
    }

    function initResultTab() {
        var rl = el("result-reload");
        if (rl) rl.addEventListener("click", loadResult);
        var dlW = el("result-dl-word");
        if (dlW) dlW.addEventListener("click", function () {
            exportResult("word");
        });
        var dlE = el("result-dl-excel");
        if (dlE) dlE.addEventListener("click", function () {
            exportResult("excel");
        });
        var del = el("result-delete");
        if (del) del.addEventListener("click", deleteResult);
    }

    function loadResult() {
        showResultError("");
        fetch("/api/court_years/" + YEAR_ID + "/results",
              { cache: "no-store" })
            .then(function (r) { return r.json(); })
            .then(function (list) {
                var found = (list || []).find(function (x) {
                    return x.case_type === currentCaseType;
                });
                if (!found) {
                    CURRENT_RESULT = null;
                    renderResult(null);
                    return;
                }
                return fetch("/api/results/" + found.id,
                             { cache: "no-store" })
                    .then(function (r) { return r.json(); })
                    .then(function (full) {
                        CURRENT_RESULT = full;
                        renderResult(full);
                    });
            })
            .catch(function (e) { showResultError("Ошибка: " + e.message); });
    }

    function renderResult(r) {
        var tbody = document.querySelector("#result-table tbody");
        if (!tbody) return;
        tbody.innerHTML = "";

        var empty = el("result-empty");
        var actions = el("result-actions");
        var info = el("result-info");

        if (!r) {
            empty.classList.remove("hidden");
            if (actions) actions.classList.add("hidden");
            if (info) info.textContent = "";
            return;
        }
        empty.classList.add("hidden");
        if (actions) actions.classList.remove("hidden");

        var parts = [
            "Обработано: " + r.processed_at,
            "Записей: " + r.record_count,
            "Формат: " + r.output_format,
            "Год дел: " + r.target_year,
            "Алименты: " + (r.process_alimony ? "включены" : "исключены")
        ];
        if (r.is_stale) {
            parts.push("⚠ результат построен по неактуальной версии источника");
        }
        if (info) info.textContent = parts.join(" · ");

        (r.rows || []).forEach(function (row) {
            var tr = document.createElement("tr");
            var cells = [row.sequential, row.title, row.dates, row.opis,
                         row.unit, row.count, row.retention, row.note];
            cells.forEach(function (val) {
                var td = document.createElement("td");
                var s = (val == null) ? "" : String(val);
                td.innerHTML = s.replace(/\n/g, "<br>");
                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });
    }

    // Разбор Content-Disposition:
    //   1) сначала filename*=UTF-8''<url-encoded>  (правильное имя)
    //   2) если нет — filename="<ascii-fallback>" (может содержать _)
    function parseContentDisposition(cd) {
        if (!cd) return "";
        var mStar = cd.match(/filename\*\s*=\s*([^;]+)/i);
        if (mStar) {
            var raw = mStar[1].trim();
            var m2 = raw.match(/^([\w-]+)'([\w-]*)'(.*)$/);
            var enc = m2 ? m2[3] : raw;
            enc = enc.replace(/^["']|["']$/g, "");
            try {
                return decodeURIComponent(enc);
            } catch (e) {
                return enc;
            }
        }
        var mAscii = cd.match(/filename\s*=\s*["]?([^";]+)["]?/i);
        if (mAscii) {
            return mAscii[1].trim();
        }
        return "";
    }

    function exportResult(fmt) {
        if (!CURRENT_RESULT) return;
        showResultError("");

        fetch("/api/results/" + CURRENT_RESULT.id + "/export", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ output_format: fmt })
        })
            .then(function (r) {
                if (!r.ok) {
                    return r.json().then(function (j) {
                        throw new Error((j && j.error) || ("HTTP " + r.status));
                    });
                }
                var cd = r.headers.get("Content-Disposition") || "";
                var fname = parseContentDisposition(cd) ||
                            ("акт." + (fmt === "word" ? "docx" : "xlsx"));
                return r.blob().then(function (b) {
                    var a = document.createElement("a");
                    a.href = URL.createObjectURL(b);
                    a.download = fname;
                    document.body.appendChild(a);
                    a.click();
                    setTimeout(function () {
                        URL.revokeObjectURL(a.href);
                        a.remove();
                    }, 500);
                });
            })
            .catch(function (e) { showResultError(e.message); });
    }

    function deleteResult() {
        if (!CURRENT_RESULT) return;
        if (!window.confirm("Удалить результат за этот год и тип дел?")) return;
        showResultError("");
        fetch("/api/results/" + CURRENT_RESULT.id, { method: "DELETE" })
            .then(function (r) {
                if (!r.ok) throw new Error("HTTP " + r.status);
                return r.json();
            })
            .then(function () {
                CURRENT_RESULT = null;
                loadResult();
                if (window.refreshDbTree) window.refreshDbTree();
            })
            .catch(function (e) { showResultError(e.message); });
    }

    // =================================================================
    // Init
    // =================================================================

    function init() {
        try {
            var form = el("refs-form");
            if (form) form.addEventListener("submit", saveRefs);
            var unlock = el("refs-unlock");
            if (unlock) unlock.addEventListener("click", unlockYear);
            initFilesTab();
            initCasesTab();
            initProcessTab();
            initResultTab();

            // Кнопки «назад/вперёд» браузера
            window.addEventListener("popstate", function () {
                renderRoute(parseRoute(window.location.pathname));
            });

            // Первичный рендер по текущему URL
            var route = parseRoute(window.location.pathname);
            if (route.view === "section") currentCaseType = route.caseType;
            renderRoute(route);
        } catch (e) {
            console.error("[year_page] init failed:", e);
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
