// Логика интерфейса «Акт уничтожения гражданских дел»
(function () {
    "use strict";

    var App = window.App || {};

    // ---------- Сервис: запросы ----------

    function jsonPost(url, body) {
        return fetch(url, { method: "POST", body: body }).then(function (resp) {
            return resp.json().then(function (d) { return { ok: resp.ok, data: d }; });
        });
    }

    function request(method, url, body) {
        var opts = { method: method, headers: { "Content-Type": "application/json" } };
        if (body) opts.body = JSON.stringify(body);
        return fetch(url, opts).then(function (resp) {
            return resp.json().then(function (d) { return { ok: resp.ok, data: d }; });
        }).then(function (res) {
            if (!res.ok) throw new Error(res.data.error || "Ошибка запроса");
            return res.data;
        });
    }

    // ---------- Heartbeat: сервер остановится при закрытии вкладки ----------
    // Web Worker шлёт /heartbeat каждые 4 с стабильно даже в фоновой вкладке
    // (Chrome не замедляет Worker'ы) и уничтожается вместе с вкладкой — после
    // пропажи heartbeat watchdog на сервере сам завершает процесс.
    // Намеренно НЕ используется sendBeacon('/shutdown') на pagehide:
    // он убивал сервер при переходе между страницами приложения.

    function startHeartbeat() {
        if (window.Worker) {
            var hbWorker = new Worker("/static/js/heartbeat_worker.js");
            window.addEventListener("pagehide", function () {
                try { hbWorker.terminate(); } catch (e) { /* ignore */ }
            });
        } else {
            // Резервный путь (старые браузеры без Worker)
            setInterval(function () {
                fetch("/heartbeat", { cache: "no-store" }).catch(function () {});
            }, 4000);
        }
    }

    // ---------- Главная страница: обработка ----------

    App.initIndexPage = function () {
        var dropZone = document.getElementById("drop-zone");
        var fileInput = document.getElementById("file-input");
        var fileInfo = document.getElementById("file-info");
        var selectedFile = null;

        function setFile(file) {
            selectedFile = file;
            fileInfo.textContent = file ? "Выбран файл: " + file.name : "";
            if (file) loadPreview(file);
        }

        dropZone.addEventListener("click", function () { fileInput.click(); });
        dropZone.addEventListener("dragover", function (e) {
            e.preventDefault();
            dropZone.classList.add("dragover");
        });
        dropZone.addEventListener("dragleave", function () {
            dropZone.classList.remove("dragover");
        });
        dropZone.addEventListener("drop", function (e) {
            e.preventDefault();
            dropZone.classList.remove("dragover");
            if (e.dataTransfer.files.length) setFile(e.dataTransfer.files[0]);
        });
        fileInput.addEventListener("change", function () {
            if (fileInput.files.length) setFile(fileInput.files[0]);
        });

        document.getElementById("process-btn").addEventListener("click", function () {
            process(selectedFile);
        });

        var radios = document.querySelectorAll('input[name="format"]');
        radios.forEach(function (r) {
            r.addEventListener("change", function () {
                var row = document.getElementById("columns-row");
                row.style.display = document.querySelector(
                    'input[name="format"]:checked').value === "excel" ? "" : "none";
            });
        });
    };

    function loadPreview(file) {
        var formData = new FormData();
        formData.append("file", file);
        jsonPost("/preview", formData).then(function (res) {
            if (!res.ok) throw new Error(res.data.error || "Не удалось открыть файл");
            showPreview(res.data);
        }).catch(function (err) {
            var box = document.getElementById("error-box");
            if (box) box.textContent = err.message;
        });
    }

    function showPreview(data) {
        var block = document.getElementById("preview-block");
        block.classList.remove("hidden");
        var info = document.getElementById("preview-info");
        var roles = { date: "дата", case_number: "№ дела", applicants: "заявители",
                      respondents: "ответчики", category: "категория",
                      opis_number: "№ описи", unit_number: "№ ед.хр.",
                      note: "примечание", end_date: "дата окончания" };
        var mapText = Object.keys(data.mapping).map(function (k) {
            return roles[k] + " → столбец " + data.mapping[k];
        }).join("; ");
        info.textContent = "Строка заголовков: " + data.header_row +
            (mapText ? ". Определено: " + mapText : "");

        var table = document.getElementById("preview-source");
        var html = "<tbody>";
        data.rows.forEach(function (row, i) {
            html += "<tr>";
            row.forEach(function (cell) {
                var cls = (data.header_row === i + 1) ? ' class="hl"' : "";
                html += "<td" + cls + ">" + escapeHtml(String(cell)) + "</td>";
            });
            html += "</tr>";
        });
        html += "</tbody>";
        table.innerHTML = html;
    }

    function escapeHtml(text) {
        var div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    }

    function process(file) {
        var errorBox = document.getElementById("error-box");
        errorBox.textContent = "";

        if (!file) {
            errorBox.textContent = "Выберите файл с исходной таблицей.";
            return;
        }
        var year = document.getElementById("year").value.trim();
        if (!year || !/^\d{4}$/.test(year)) {
            errorBox.textContent = "Укажите год обработки (например, 2023).";
            return;
        }

        var formData = new FormData();
        formData.append("file", file);
        formData.append("year", year);
        formData.append("alimony", document.getElementById("alimony").checked ? "1" : "0");
        formData.append("header_row", document.getElementById("header-row").value || "");
        formData.append("format", document.querySelector('input[name="format"]:checked').value);

        document.querySelectorAll(".col-check:checked").forEach(function (c) {
            formData.append("columns", c.value);
        });

        var btn = document.getElementById("process-btn");
        btn.disabled = true;
        btn.textContent = "Обработка...";

        jsonPost("/process", formData)
            .then(function (res) {
                if (!res.ok) throw new Error(res.data.error || "Ошибка обработки");
                showResult(res.data);
            })
            .catch(function (err) {
                errorBox.textContent = err.message;
            })
            .finally(function () {
                btn.disabled = false;
                btn.textContent = "Обработать";
            });
    }

    function showResult(data) {
        document.getElementById("stats-box").textContent = data.stats_message;
        document.getElementById("result-card").classList.remove("hidden");

        var tbody = document.querySelector("#preview-table tbody");
        tbody.innerHTML = "";
        data.records.forEach(function (r) {
            var tr = document.createElement("tr");
            [r.sequential, r.title, r.dates, r.opis, r.unit,
             r.count, r.retention, r.note].forEach(function (val) {
                var td = document.createElement("td");
                // fix_07: textContent вместо innerHTML — защита от XSS
                // (значения приходят из Excel, могут содержать HTML)
                td.textContent = String(val == null ? "" : val);
                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });

        var link = document.getElementById("download-link");
        link.href = "/download/" + encodeURIComponent(data.filename);
        link.classList.remove("hidden");
    }

    // ---------- Страница базы данных ----------

    App.initDbPage = function () {
        loadOrganizations();
        loadRules();
        loadSettings();

        document.getElementById("org-add").addEventListener("click", function () {
            var name = document.getElementById("org-name").value.trim();
            var type = document.getElementById("org-type").value;
            if (!name) return alert("Введите слово");
            request("POST", "/api/organizations", { name: name, claim_type: type })
                .then(loadOrganizations)
                .catch(showErr);
        });

        document.getElementById("rule-add").addEventListener("click", function () {
            var keyword = document.getElementById("rule-keyword").value.trim();
            var code = document.getElementById("rule-code").value.trim();
            var text = document.getElementById("rule-text").value.trim();
            if (!keyword || !code) return alert("Укажите корень и код типа");
            request("POST", "/api/retention_rules",
                { keyword: keyword, code: code, result_text: text })
                .then(loadRules)
                .catch(showErr);
        });

        document.getElementById("settings-save").addEventListener("click", function () {
            var data = {};
            document.querySelectorAll("#settings-form input").forEach(function (inp) {
                data[inp.dataset.key] = inp.value;
            });
            request("POST", "/api/settings", data)
                .then(function () { alert("Настройки сохранены"); })
                .catch(showErr);
        });

        // Импорт базы из Excel
        document.getElementById("db-import-btn").addEventListener("click", function () {
            var input = document.getElementById("db-import-file");
            if (!input.files.length) return alert("Выберите файл .xlsx/.xlsm");
            var formData = new FormData();
            formData.append("file", input.files[0]);
            jsonPost("/api/db/import", formData).then(function (res) {
                if (!res.ok) throw new Error(res.data.error || "Ошибка импорта");
                alert("Импортировано организаций: " + res.data.added);
                loadOrganizations();
            }).catch(showErr);
        });
    };

    // ---------- Страница проверки категорий (Доработка 6) ----------

    var rowInputs = {};    // номер дела -> input категории
    var groupData = [];    // группы «Без аналогов»
    var checkYear = "";    // год проверки (для выгрузки таблицы)
    var checkFileType = "source";  // тип загруженного файла

    function hasPhrase(text) {
        // «о ...» / «об ...»: «о» в начале строки или после пробела,
        // за которым следует пробел (не «оборот», не «ООО»)
        return /(^|\s)о(б)?\s/i.test(String(text || ""));
    }

    App.initCheckPage = function () {
        var dropZone = document.getElementById("drop-zone");
        var fileInput = document.getElementById("file-input");
        var fileInfo = document.getElementById("file-info");
        var selectedFile = null;

        function setFile(file) {
            selectedFile = file;
            fileInfo.textContent = file ? "Выбран файл: " + file.name : "";
        }

        dropZone.addEventListener("click", function () { fileInput.click(); });
        dropZone.addEventListener("dragover", function (e) {
            e.preventDefault();
            dropZone.classList.add("dragover");
        });
        dropZone.addEventListener("dragleave", function () {
            dropZone.classList.remove("dragover");
        });
        dropZone.addEventListener("drop", function (e) {
            e.preventDefault();
            dropZone.classList.remove("dragover");
            if (e.dataTransfer.files.length) setFile(e.dataTransfer.files[0]);
        });
        fileInput.addEventListener("change", function () {
            if (fileInput.files.length) setFile(fileInput.files[0]);
        });

        // Тип файла: для готовых результатов строка заголовков не нужна
        function syncFileType() {
            var legacy = document.querySelector(
                'input[name="file_type"]:checked').value === "legacy";
            document.getElementById("header-row-field").style.display =
                legacy ? "none" : "";
            fileInput.accept = legacy ? ".xlsx,.docx" : ".xlsx,.xlsm";
        }
        document.querySelectorAll('input[name="file_type"]').forEach(function (r) {
            r.addEventListener("change", syncFileType);
        });
        syncFileType();

        document.getElementById("check-btn").addEventListener("click", function () {
            runCheck(selectedFile);
        });
        document.getElementById("process-check-btn").addEventListener("click", function () {
            processChecked(selectedFile);
        });
        document.getElementById("download-table-btn").addEventListener("click",
            downloadNoAnalogTable);
    };

    function runCheck(file) {
        var errorBox = document.getElementById("error-box");
        errorBox.textContent = "";
        if (!file) {
            errorBox.textContent = "Выберите файл для проверки.";
            return;
        }
        var year = document.getElementById("year").value.trim();
        if (!year || !/^\d{4}$/.test(year)) {
            errorBox.textContent = "Укажите год дел (например, 2023).";
            return;
        }
        checkFileType = document.querySelector('input[name="file_type"]:checked').value;

        var formData = new FormData();
        formData.append("file", file);
        formData.append("file_type", checkFileType);
        formData.append("year", year);
        formData.append("alimony", document.getElementById("alimony").checked ? "1" : "0");
        formData.append("header_row", document.getElementById("header-row").value || "");

        var btn = document.getElementById("check-btn");
        btn.disabled = true;
        btn.textContent = "Проверка...";

        jsonPost("/check_categories", formData)
            .then(function (res) {
                if (!res.ok) throw new Error(res.data.error || "Ошибка проверки");
                renderCheckResult(res.data, year);
            })
            .catch(function (err) { errorBox.textContent = err.message; })
            .finally(function () {
                btn.disabled = false;
                btn.textContent = "Проверить категории";
            });
    }

    function renderCheckResult(data, year) {
        checkYear = year;
        groupData = data.groups || [];

        var st = data.stats || {};
        var box = document.getElementById("stats-box");
        box.textContent =
            "Всего дел за год: " + data.cases_total +
            "\nПроблемных дел (нет категории «о/об»): " + st.total +
            "\n  — с найденными аналогами: " + st.with_analogs +
            "\n  — предложены из словаря БД: " + st.from_dictionary +
            "\n  — без аналогов (групп: " + st.groups + "): " + st.no_analog +
            (data.auto_fix_enabled ? "" : "\nВНИМАНИЕ: автоисправление из словаря отключено");
        document.getElementById("summary-card").classList.remove("hidden");

        renderProblemTable(data.problematic || []);
        renderGroups(data.groups || []);

        document.getElementById("problem-card").classList.toggle(
            "hidden", !(data.problematic || []).length);
        document.getElementById("no-analog-card").classList.toggle(
            "hidden", !(data.groups || []).length);
    }

    function sourceText(src) {
        if (src === "analog") return "аналог";
        if (src === "dictionary") return "словарь БД";
        return "нет";
    }

    function renderProblemTable(items) {
        var tbody = document.querySelector("#problem-table tbody");
        tbody.innerHTML = "";
        rowInputs = {};
        document.querySelector("#analog-details").textContent = "";
        // fix_07: убираем datalist предыдущего рендера (иначе утечка DOM
        // и дублирующиеся id в <datalist>)
        document.querySelectorAll("datalist.auto-list").forEach(function (el) {
            el.remove();
        });

        items.forEach(function (p) {
            var tr = document.createElement("tr");

            var tdNum = document.createElement("td");
            tdNum.textContent = p.case_number || "—";

            var tdPl = document.createElement("td");
            tdPl.textContent = p.plaintiff_label || "—";

            var tdCur = document.createElement("td");
            tdCur.textContent = p.current_category || "—";

            var tdFix = document.createElement("td");
            var input = document.createElement("input");
            input.type = "text";
            input.className = "cat-input";
            input.placeholder = "о ... / об ...";
            input.value = p.suggested || "";
            if (p.options && p.options.length) {
                var dl = document.createElement("datalist");
                dl.className = "auto-list";  // fix_07: пометка для очистки
                dl.id = "dl-" + String(p.case_number).replace(/[^a-z0-9]/gi, "");
                p.options.forEach(function (o) {
                    var opt = document.createElement("option");
                    opt.value = o;
                    dl.appendChild(opt);
                });
                document.body.appendChild(dl);
                input.setAttribute("list", dl.id);
            }
            rowInputs[p.case_number] = input;
            tdFix.appendChild(input);

            var tdSrc = document.createElement("td");
            tdSrc.textContent = sourceText(p.source);

            var tdAct = document.createElement("td");
            var btnAnalog = document.createElement("button");
            btnAnalog.className = "btn btn-secondary";
            btnAnalog.textContent = "Аналоги (" + (p.analogs ? p.analogs.length : 0) + ")";
            btnAnalog.addEventListener("click", function () { toggleAnalogs(p); });
            var btnSave = document.createElement("button");
            btnSave.className = "btn btn-success small";
            btnSave.textContent = "Сохранить в БД";
            btnSave.addEventListener("click", function () { saveRowToDb(p); });
            tdAct.appendChild(btnAnalog);
            tdAct.appendChild(btnSave);

            tr.appendChild(tdNum); tr.appendChild(tdPl); tr.appendChild(tdCur);
            tr.appendChild(tdFix); tr.appendChild(tdSrc); tr.appendChild(tdAct);
            tbody.appendChild(tr);
        });
    }

    function toggleAnalogs(p) {
        var box = document.getElementById("analog-details");
        var analogs = p.analogs || [];
        if (!analogs.length) {
            box.textContent = "Аналогов не найдено.";
            return;
        }
        var text = "Аналоги по истцу «" + (p.plaintiff_label || "") + "»:\n" +
            analogs.map(function (a) {
                return "  • " + a.case_number + " — " + a.category;
            }).join("\n");
        box.textContent = (box.textContent === text) ? "" : text;
    }

    function saveRowToDb(p) {
        var input = rowInputs[p.case_number];
        var category = input ? input.value.trim() : "";
        if (!category) return alert("Введите категорию перед сохранением.");
        request("POST", "/apply_corrections", { saves: [{
            key: p.plaintiff_key, label: p.plaintiff_label,
            category: category, is_organization: p.is_organization
        }] }).then(function () {
            alert("Сохранено в словарь: «" + p.plaintiff_label + "» → «" + category + "»");
        }).catch(showErr);
    }

    function renderGroups(groups) {
        var box = document.getElementById("groups-box");
        box.innerHTML = "";
        // fix_07: убираем datalist предыдущего рендера
        document.querySelectorAll("datalist.auto-list").forEach(function (el) {
            el.remove();
        });
        groups.forEach(function (g, gi) {
            var block = document.createElement("div");
            block.className = "group-block";
            var title = document.createElement("h3");
            title.textContent = (g.label || "Без истца") +
                " — дел: " + (g.cases || []).length;
            block.appendChild(title);

            var cases = document.createElement("p");
            cases.className = "group-cases";
            cases.textContent = (g.cases || []).map(function (c) {
                return c.case_number;
            }).join(", ");
            block.appendChild(cases);

            var input = document.createElement("input");
            input.type = "text";
            input.className = "cat-input";
            input.placeholder = "о ... / об ...";
            if (g.dictionary_options && g.dictionary_options.length) {
                var dl = document.createElement("datalist");
                dl.className = "auto-list";  // fix_07: пометка для очистки
                dl.id = "gd-" + gi;
                g.dictionary_options.forEach(function (o) {
                    var opt = document.createElement("option");
                    opt.value = o;
                    dl.appendChild(opt);
                });
                document.body.appendChild(dl);
                input.setAttribute("list", dl.id);
            }
            block.appendChild(input);

            var btnApply = document.createElement("button");
            btnApply.className = "btn btn-primary small";
            btnApply.textContent = "Применить ко всем";
            btnApply.addEventListener("click", function () {
                applyGroupToRows(g, input.value.trim());
            });
            var btnSave = document.createElement("button");
            btnSave.className = "btn btn-success small";
            btnSave.textContent = "Сохранить в БД";
            btnSave.addEventListener("click", function () {
                var category = input.value.trim();
                if (!category) return alert("Введите категорию.");
                request("POST", "/apply_corrections", { saves: [{
                    key: g.key, label: g.label, category: category,
                    is_organization: g.is_organization
                }] }).then(function () {
                    alert("Сохранено в словарь для группы «" + g.label + "»");
                }).catch(showErr);
            });
            var btns = document.createElement("div");
            btns.className = "actions";
            btns.appendChild(btnApply);
            btns.appendChild(btnSave);
            block.appendChild(btns);

            if (g.dictionary_options && g.dictionary_options.length) {
                var hint = document.createElement("p");
                hint.className = "hint";
                hint.textContent = "Варианты из словаря: " +
                    g.dictionary_options.join("; ");
                block.appendChild(hint);
            }
            box.appendChild(block);
        });
    }

    function applyGroupToRows(g, value) {
        if (!value) return alert("Введите категорию.");
        (g.cases || []).forEach(function (c) {
            if (rowInputs[c.case_number]) rowInputs[c.case_number].value = value;
        });
        alert("Категория применена к " + g.cases.length + " делу (делам).");
    }

    function downloadNoAnalogTable() {
        if (!groupData.length) return alert("Нет групп для выгрузки.");
        fetch("/download_no_analog_table", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ groups: groupData, year: checkYear })
        }).then(function (resp) {
            if (!resp.ok) throw new Error("Ошибка выгрузки");
            return resp.blob();
        }).then(function (blob) {
            var a = document.createElement("a");
            a.href = URL.createObjectURL(blob);
            a.download = "без_аналогов_" + checkYear + ".xlsx";
            document.body.appendChild(a);
            a.click();
            setTimeout(function () {
                URL.revokeObjectURL(a.href);
                a.remove();
            }, 1000);
        }).catch(showErr);
    }

    function processChecked(file) {
        var errorBox = document.getElementById("error-box");
        errorBox.textContent = "";
        if (!file) {
            errorBox.textContent = "Выберите файл.";
            return;
        }
        var year = document.getElementById("year").value.trim();
        if (!year || !/^\d{4}$/.test(year)) {
            errorBox.textContent = "Укажите год дел (например, 2023).";
            return;
        }

        // Сбор исправлений и подсчёт неисправленных дел
        var fixes = {};
        var missing = 0;
        Object.keys(rowInputs).forEach(function (num) {
            var value = rowInputs[num].value.trim();
            if (!value) { missing++; return; }
            fixes[num] = value;
            if (!hasPhrase(value)) missing++;
        });
        if (missing > 0 && !window.confirm(
            "Дела с пустой или некорректной категорией: " + missing +
            ".\nОбработать всё равно?")) {
            return;
        }
        if (checkFileType === "legacy" && !window.confirm(
            "Вы обрабатываете готовый результат: даты дела, № описи и " +
            "№ ед.хр. не восстановятся (останутся пустыми).\nПродолжить?")) {
            return;
        }

        var formData = new FormData();
        formData.append("file", file);
        formData.append("file_type", checkFileType);
        formData.append("year", year);
        formData.append("alimony", document.getElementById("alimony").checked ? "1" : "0");
        formData.append("header_row", document.getElementById("header-row").value || "");
        formData.append("format", document.querySelector(
            'input[name="format"]:checked').value);
        formData.append("fixes", JSON.stringify(fixes));
        formData.append("auto_fix", document.getElementById("auto-fix").checked ? "1" : "0");

        var btn = document.getElementById("process-check-btn");
        btn.disabled = true;
        btn.textContent = "Обработка...";

        jsonPost("/process", formData)
            .then(function (res) {
                if (!res.ok) throw new Error(res.data.error || "Ошибка обработки");
                showCheckResult(res.data);
            })
            .catch(function (err) { errorBox.textContent = err.message; })
            .finally(function () {
                btn.disabled = false;
                btn.textContent = "Обработать с исправлениями";
            });
    }

    function showCheckResult(data) {
        document.getElementById("stats-box-result").textContent = data.stats_message;
        document.getElementById("result-card").classList.remove("hidden");
        var link = document.getElementById("download-link");
        link.href = "/download/" + encodeURIComponent(data.filename);
        link.classList.remove("hidden");
    }

    function showErr(err) {
        var box = document.getElementById("error-box");
        if (box) box.textContent = err.message;
    }

    function loadOrganizations() {
        request("GET", "/api/organizations").then(function (list) {
            var tbody = document.querySelector("#org-table tbody");
            tbody.innerHTML = "";
            list.forEach(function (o) {
                var tr = document.createElement("tr");
                var tdName = document.createElement("td");
                tdName.textContent = o.name;
                var tdType = document.createElement("td");
                tdType.textContent = o.claim_type;
                var tdBtn = document.createElement("td");
                var btn = document.createElement("button");
                btn.className = "btn btn-danger";
                btn.textContent = "Удалить";
                btn.addEventListener("click", function () {
                    request("DELETE", "/api/organizations/" + o.id)
                        .then(loadOrganizations).catch(showErr);
                });
                tdBtn.appendChild(btn);
                tr.appendChild(tdName); tr.appendChild(tdType); tr.appendChild(tdBtn);
                tbody.appendChild(tr);
            });
        }).catch(showErr);
    }

    function loadRules() {
        request("GET", "/api/retention_rules").then(function (list) {
            var tbody = document.querySelector("#rule-table tbody");
            tbody.innerHTML = "";
            list.forEach(function (r) {
                var tr = document.createElement("tr");
                var td1 = document.createElement("td"); td1.textContent = r.keyword;
                var td2 = document.createElement("td"); td2.textContent = r.code;
                var td3 = document.createElement("td"); td3.textContent = r.result_text || "—";
                var td4 = document.createElement("td");
                var btn = document.createElement("button");
                btn.className = "btn btn-danger";
                btn.textContent = "Удалить";
                btn.addEventListener("click", function () {
                    request("DELETE", "/api/retention_rules/" + r.id)
                        .then(loadRules).catch(showErr);
                });
                td4.appendChild(btn);
                tr.appendChild(td1); tr.appendChild(td2); tr.appendChild(td3); tr.appendChild(td4);
                tbody.appendChild(tr);
            });
        }).catch(showErr);
    }

    function loadSettings() {
        request("GET", "/api/settings").then(function (settings) {
            var box = document.getElementById("settings-form");
            box.innerHTML = "";
            var titles = {
                "судебный_участок": "Судебный участок №",
                "судья": "Мировой судья (ФИО)",
                "дата_утверждения": "Дата утверждения",
                "дата_акта": "Дата акта",
                "номер_акта": "№ акта",
                "секретарь": "Секретарь (ФИО)",
                "дата_подписи": "Дата подписи",
                "протокол_эк_дата": "Протокол ЭК: дата",
                "протокол_эк_номер": "Протокол ЭК: номер"
            };
            Object.keys(titles).forEach(function (key) {
                var label = document.createElement("label");
                label.textContent = titles[key];
                var input = document.createElement("input");
                input.type = "text";
                input.dataset.key = key;
                input.value = settings[key] || "";
                label.appendChild(input);
                box.appendChild(label);
            });
        }).catch(showErr);
    }

    // Автоинициализация и heartbeat
    document.addEventListener("DOMContentLoaded", function () {
        startHeartbeat();
        if (document.getElementById("process-btn")) App.initIndexPage();
        if (document.getElementById("check-btn")) App.initCheckPage();
    });

    window.App = App;
})();