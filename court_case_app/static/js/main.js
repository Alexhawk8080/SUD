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

    // ---------- Судебные участки (stage11e) ----------

    var CA_FIELDS = ["номер", "судья", "дата_утверждения", "дата_акта",
                     "номер_акта", "секретарь", "дата_подписи",
                     "протокол_эк_дата", "протокол_эк_номер"];
    var caEditId = null;      // null = режим добавления, иначе id редактируемого
    var courtAreasCache = []; // участки для селекта на index
    var settingsCache = {};   // настройки для проверки заполненности

    function caFieldId(field) { return "ca-" + field; }

    function readCourtAreaForm() {
        var data = {};
        CA_FIELDS.forEach(function (f) {
            var el = document.getElementById(caFieldId(f));
            data[f] = el ? el.value.trim() : "";
        });
        return data;
    }

    function resetCourtAreaForm() {
        CA_FIELDS.forEach(function (f) {
            var el = document.getElementById(caFieldId(f));
            if (el) el.value = "";
        });
        caEditId = null;
        document.getElementById("court-area-add").textContent = "Добавить";
        document.getElementById("court-area-cancel").classList.add("hidden");
        var hint = document.getElementById("court-area-edit-hint");
        hint.classList.add("hidden");
        hint.textContent = "";
    }

    function fillCourtAreaForm(rec) {
        CA_FIELDS.forEach(function (f) {
            var el = document.getElementById(caFieldId(f));
            if (el) el.value = rec[f] || "";
        });
        caEditId = rec.id;
        document.getElementById("court-area-add").textContent = "Сохранить";
        document.getElementById("court-area-cancel").classList.remove("hidden");
        var hint = document.getElementById("court-area-edit-hint");
        hint.textContent = "Редактирование участка «" + rec["номер"] + " СУ»";
        hint.classList.remove("hidden");
    }

    function saveCourtAreaForm() {
        var data = readCourtAreaForm();
        var empty = CA_FIELDS.filter(function (f) { return !data[f]; });
        if (empty.length) {
            alert("Все 9 полей обязательны. Не заполнено: " + empty.join(", "));
            return;
        }
        var promise = caEditId === null
            ? request("POST", "/api/court_areas", data)
            : request("PUT", "/api/court_areas/" + caEditId, data);
        promise.then(function () {
            resetCourtAreaForm();
            loadCourtAreas();
        }).catch(showErr);
    }

    function loadCourtAreas() {
        request("GET", "/api/court_areas").then(function (list) {
            courtAreasCache = list || [];
            var tbody = document.querySelector("#court-areas-table tbody");
            tbody.innerHTML = "";
            courtAreasCache.forEach(function (rec) {
                var tr = document.createElement("tr");
                var tdn = document.createElement("td"); tdn.textContent = rec["номер"];
                var tds = document.createElement("td"); tds.textContent = rec["судья"];
                var tdk = document.createElement("td"); tdk.textContent = rec["секретарь"];
                var tdt = document.createElement("td");
                if (rec.is_incomplete) {
                    tdt.textContent = "⚠ требует заполнения";
                    tdt.className = "incomplete";
                } else {
                    tdt.textContent = "ок";
                }
                var tda = document.createElement("td");
                var bEdit = document.createElement("button");
                bEdit.className = "btn btn-secondary";
                bEdit.textContent = "Редактировать";
                bEdit.addEventListener("click", function () { fillCourtAreaForm(rec); });
                var bDel = document.createElement("button");
                bDel.className = "btn btn-danger";
                bDel.textContent = "Удалить";
                bDel.addEventListener("click", function () {
                    if (!window.confirm("Удалить участок «" + rec["номер"] + " СУ»?")) return;
                    request("DELETE", "/api/court_areas/" + rec.id)
                        .then(loadCourtAreas).catch(showErr);
                });
                tda.appendChild(bEdit);
                tda.appendChild(bDel);
                tr.appendChild(tdn); tr.appendChild(tds); tr.appendChild(tdk);
                tr.appendChild(tdt); tr.appendChild(tda);
                tbody.appendChild(tr);
            });
        }).catch(showErr);
    }

    function loadCourtAreasForIndex() {
        var select = document.getElementById("court-area");
        if (!select) return Promise.resolve();
        return request("GET", "/api/court_areas").then(function (list) {
            courtAreasCache = list || [];
            select.innerHTML = '<option value="">Не выбран — использовать настройки</option>';
            courtAreasCache.forEach(function (rec) {
                var opt = document.createElement("option");
                opt.value = String(rec.id);
                var suffix = rec.is_incomplete ? " ⚠" : "";
                opt.textContent = rec["номер"] + " СУ" + suffix +
                    (rec["судья"] ? " — " + rec["судья"] : "");
                select.appendChild(opt);
            });
        }).catch(function () { /* не блокируем index */ });
    }

    function loadSettingsForIndex() {
        return request("GET", "/api/settings").then(function (s) {
            settingsCache = s || {};
        }).catch(function () { settingsCache = {}; });
    }

    function checkRefsBeforeProcess() {
        var select = document.getElementById("court-area");
        var areaId = select ? select.value : "";
        if (areaId) {
            var area = courtAreasCache.find(function (a) {
                return String(a.id) === areaId;
            });
            if (area && area.is_incomplete) {
                return window.confirm(
                    "В выбранном участке «" + area["номер"] +
                    " СУ» есть незаполненные поля. Продолжить?");
            }
            return true;
        }
        // Не выбран — fallback на settings. Проверим заполненность.
        var keyMap = {
            "судебный_участок": "номер", "судья": "судья",
            "дата_утверждения": "дата утверждения", "дата_акта": "дата акта",
            "номер_акта": "номер акта", "секретарь": "секретарь",
            "дата_подписи": "дата подписи",
            "протокол_эк_дата": "протокол ЭК: дата",
            "протокол_эк_номер": "протокол ЭК: номер"
        };
        var empty = [];
        Object.keys(keyMap).forEach(function (k) {
            var v = settingsCache[k];
            if (!v || !String(v).trim()) empty.push(keyMap[k]);
        });
        if (empty.length) {
            return window.confirm(
                "Реквизиты из настроек неполные: " + empty.join(", ") +
                ". Продолжить?");
        }
        return true;
    }

    // ---------- Страница «Конвертация» (stage12d, B4) ----------

    var convSelectedFile = null;
    var convCurrentSheet = null;
    var convCurrentYear = null;

    var CONV_CA_FIELDS = ["номер", "судья", "дата_утверждения", "дата_акта",
                          "номер_акта", "секретарь", "дата_подписи",
                          "протокол_эк_дата", "протокол_эк_номер"];

    function convCaId(field) { return "conv-ca-" + field; }

    function convReadRefs() {
        var data = {};
        CONV_CA_FIELDS.forEach(function (f) {
            var el = document.getElementById(convCaId(f));
            data[f] = el ? el.value.trim() : "";
        });
        return data;
    }

    function convFillRefs(rec) {
        CONV_CA_FIELDS.forEach(function (f) {
            var el = document.getElementById(convCaId(f));
            if (el) el.value = (rec && rec[f]) || "";
        });
    }

    function loadConvertAreas() {
        var select = document.getElementById("conv-court-area");
        if (!select) return Promise.resolve();
        return request("GET", "/api/court_areas").then(function (list) {
            courtAreasCache = list || [];
            select.innerHTML = '<option value="">Не выбран — использовать настройки</option>';
            courtAreasCache.forEach(function (rec) {
                var opt = document.createElement("option");
                opt.value = String(rec.id);
                var suffix = rec.is_incomplete ? " ⚠" : "";
                opt.textContent = rec["номер"] + " СУ" + suffix +
                    (rec["судья"] ? " — " + rec["судья"] : "");
                select.appendChild(opt);
            });
        });
    }

    function fillRefsFromCurrentArea() {
        var select = document.getElementById("conv-court-area");
        var val = select ? select.value : "";
        var hint = document.getElementById("conv-refs-hint");
        if (val) {
            var rec = courtAreasCache.find(function (a) {
                return String(a.id) === val;
            });
            if (rec) {
                convFillRefs(rec);
                if (hint) {
                    hint.textContent = rec.is_incomplete
                        ? "⚠ Участок «" + rec["номер"] + " СУ» требует заполнения."
                        : "Реквизиты участка «" + rec["номер"] + " СУ» загружены.";
                }
                return;
            }
        }
        // Fallback: settings
        request("GET", "/api/settings").then(function (s) {
            settingsCache = s || {};
            convFillRefs({
                "номер": s["судебный_участок"] || "",
                "судья": s["судья"] || "",
                "секретарь": s["секретарь"] || "",
                "номер_акта": s["номер_акта"] || "",
                "дата_утверждения": s["дата_утверждения"] || "",
                "дата_акта": s["дата_акта"] || "",
                "дата_подписи": s["дата_подписи"] || "",
                "протокол_эк_дата": s["протокол_эк_дата"] || "",
                "протокол_эк_номер": s["протокол_эк_номер"] || "",
            });
            if (hint) hint.textContent = "Используются реквизиты из настроек.";
        });
    }

    function showConflictDialog(filename) {
        return new Promise(function (resolve) {
            var modal = document.getElementById("conflict-modal");
            var text = document.getElementById("conflict-text");
            var btnReplace = document.getElementById("conflict-replace");
            var btnCopy = document.getElementById("conflict-copy");
            var btnCancel = document.getElementById("conflict-cancel");
            text.textContent = "Файл «" + filename + "» уже существует. Что сделать?";
            modal.classList.remove("hidden");

            function close(val) {
                modal.classList.add("hidden");
                btnReplace.removeEventListener("click", onReplace);
                btnCopy.removeEventListener("click", onCopy);
                btnCancel.removeEventListener("click", onCancel);
                resolve(val);
            }
            function onReplace() { close("replace"); }
            function onCopy() { close("copy"); }
            function onCancel() { close("cancel"); }

            btnReplace.addEventListener("click", onReplace);
            btnCopy.addEventListener("click", onCopy);
            btnCancel.addEventListener("click", onCancel);
        });
    }

    App.initConvertPage = function () {
        var dropZone = document.getElementById("drop-zone");
        var fileInput = document.getElementById("file-input");
        var fileInfo = document.getElementById("file-info");

        function setFile(file) {
            convSelectedFile = file;
            fileInfo.textContent = file ? "Выбран файл: " + file.name : "";
            if (file) runInspect(file);
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

        document.getElementById("conv-sheet").addEventListener("change", function () {
            if (convSelectedFile) runInspect(convSelectedFile, this.value);
        });

        document.getElementById("conv-court-area").addEventListener("change",
            fillRefsFromCurrentArea);

        document.getElementById("conv-save-area").addEventListener("click", saveArea);
        document.getElementById("conv-create-area").addEventListener("click", createArea);
        document.getElementById("convert-btn").addEventListener("click", runConvert);

        // stage13d: переключение направления
        document.querySelectorAll('input[name="direction"]').forEach(function (r) {
            r.addEventListener("change", convSwitchDirection);
        });
        convSwitchDirection();

        loadConvertAreas().then(fillRefsFromCurrentArea);
    };

    // ---------- stage13d: Word -> Excel ----------

    function convCurrentDirection() {
        var r = document.querySelector('input[name="direction"]:checked');
        return r ? r.value : "xlsx_to_word";
    }

    function convSwitchDirection() {
        var dir = convCurrentDirection();
        var isW2X = dir === "word_to_xlsx";

        // drop-zone и input
        var hint = document.getElementById("drop-hint");
        var fileInput = document.getElementById("file-input");
        if (hint) {
            hint.textContent = isW2X
                ? "Перетащите .docx с актом или нажмите для выбора"
                : "Перетащите .xlsx/.xlsm сюда или нажмите для выбора";
        }
        if (fileInput) {
            fileInput.accept = isW2X ? ".docx" : ".xlsx,.xlsm";
        }

        // доп. опции Word -> Excel
        var extra = document.getElementById("w2x-extra");
        if (extra) extra.classList.toggle("hidden", !isW2X);

        // Заголовок карточки реквизитов
        var refsTitle = document.getElementById("refs-card-title");
        if (refsTitle) {
            refsTitle.textContent = isW2X
                ? "Реквизиты акта (извлекаются, только информация)"
                : "Реквизиты акта";
        }

        // сброс текущего состояния
        convSelectedFile = null;
        convCurrentSheet = null;
        convCurrentYear = null;
        document.getElementById("file-info").textContent = "";
        document.getElementById("params-card").classList.add("hidden");
        document.getElementById("refs-card").classList.add("hidden");
        document.getElementById("convert-action-card").classList.add("hidden");
        document.getElementById("result-card").classList.add("hidden");
        document.getElementById("attention-card").classList.add("hidden");
        document.getElementById("error-box").textContent = "";
        if (fileInput) fileInput.value = "";
    }

    function runInspectWord(file) {
        var errorBox = document.getElementById("error-box");
        errorBox.textContent = "";
        var formData = new FormData();
        formData.append("file", file);

        // Для Word -> Excel роут /inspect_file не подходит (он про .xlsx);
        // сразу показываем форму. Год пользователь введёт вручную.
        document.getElementById("params-card").classList.remove("hidden");
        document.getElementById("refs-card").classList.remove("hidden");
        document.getElementById("convert-action-card").classList.remove("hidden");
        document.getElementById("refs-card-title").textContent =
            "Реквизиты акта (извлекаются, только информация)";
    }

    function runConvertWord() {
        var errorBox = document.getElementById("error-box");
        errorBox.textContent = "";
        if (!convSelectedFile) {
            errorBox.textContent = "Выберите файл .docx.";
            return;
        }
        var year = document.getElementById("conv-year").value.trim();
        if (!year || !/^\d{4}$/.test(year)) {
            errorBox.textContent = "Укажите год (например, 2020).";
            return;
        }
        var restore = document.getElementById("restore-gaps");
        var formData = new FormData();
        formData.append("file", convSelectedFile);
        formData.append("year", year);
        if (restore && restore.checked) formData.append("restore_gaps", "1");

        var btn = document.getElementById("convert-btn");
        btn.disabled = true;
        btn.textContent = "Конвертация...";

        jsonPost("/convert/word_to_xlsx", formData).then(function (res) {
            if (res.ok) {
                renderConvertWordResult(res.data);
                return;
            }
            if (res.data && res.data.conflict) {
                return showConflictDialog(res.data.filename).then(function (choice) {
                    if (choice === "replace") {
                        formData.append("overwrite", "1");
                        return jsonPost("/convert/word_to_xlsx", formData)
                            .then(function (r2) {
                                if (r2.ok) renderConvertWordResult(r2.data);
                                else throw new Error((r2.data && r2.data.error) || "Ошибка");
                            });
                    }
                    if (choice === "copy") {
                        formData.append("copy", "1");
                        return jsonPost("/convert/word_to_xlsx", formData)
                            .then(function (r2) {
                                if (r2.ok) renderConvertWordResult(r2.data);
                                else throw new Error((r2.data && r2.data.error) || "Ошибка");
                            });
                    }
                    return null;
                });
            }
            throw new Error((res.data && res.data.error) || "Ошибка конвертации");
        }).catch(function (err) {
            errorBox.textContent = err.message;
        }).finally(function () {
            btn.disabled = false;
            btn.textContent = "Конвертировать";
        });
    }

    function renderConvertWordResult(data) {
        var stats = "Всего строк: " + data.total + "\n" +
                    "Распознано дел: " + data.count + "\n" +
                    "Определённый год: " + (data.year || "—") + "\n" +
                    "Метка: " + (data.marker && data.marker.found
                        ? "наша (" + data.marker.version + ")"
                        : "нет (чужой акт)");
        document.getElementById("conv-stats").textContent = stats;

        // Реквизиты (информационно)
        var refs = data.refs || {};
        var refsLines = Object.keys(refs).length
            ? Object.keys(refs).map(function (k) { return k + ": " + refs[k]; }).join("\n")
            : "Реквизиты не распознаны.";
        document.getElementById("conv-refs-used").textContent = refsLines;

        // Превью таблицы
        var tbody = document.querySelector("#conv-preview-table tbody");
        tbody.innerHTML = "";
        (data.preview || []).forEach(function (r) {
            var tr = document.createElement("tr");
            [r.sequential, r.title, r.dates, r.opis, r.unit,
             r.count, r.retention, r.note].forEach(function (val) {
                var td = document.createElement("td");
                td.textContent = String(val == null ? "" : val);
                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });

        // Attention
        var att = data.attention || [];
        var attBody = document.querySelector("#attention-table tbody");
        attBody.innerHTML = "";
        att.forEach(function (a) {
            var tr = document.createElement("tr");
            var td1 = document.createElement("td"); td1.textContent = a.row;
            var td2 = document.createElement("td"); td2.textContent = a.case_number || "—";
            var td3 = document.createElement("td"); td3.textContent = a.reason || "";
            tr.appendChild(td1); tr.appendChild(td2); tr.appendChild(td3);
            attBody.appendChild(tr);
        });
        document.getElementById("attention-card").classList.toggle("hidden", !att.length);

        // Скачать
        var link = document.getElementById("conv-download-link");
        link.href = "/download/" + encodeURIComponent(data.filename);
        link.classList.remove("hidden");

        document.getElementById("result-card").classList.remove("hidden");
    }

    function runInspect(file, sheet) {
        // stage13d: маршрутизация по направлению
        if (convCurrentDirection() === "word_to_xlsx") {
            runInspectWord(file);
            return;
        }
        var errorBox = document.getElementById("error-box");
        errorBox.textContent = "";
        var formData = new FormData();
        formData.append("file", file);
        if (sheet) formData.append("sheet", sheet);

        jsonPost("/inspect_file", formData).then(function (res) {
            if (!res.ok) throw new Error(res.data.error || "Не удалось открыть файл");
            renderInspect(res.data);
        }).catch(function (err) {
            errorBox.textContent = err.message;
            document.getElementById("params-card").classList.add("hidden");
            document.getElementById("refs-card").classList.add("hidden");
            document.getElementById("convert-action-card").classList.add("hidden");
        });
    }

    function renderInspect(data) {
        var sheetSelect = document.getElementById("conv-sheet");
        if (data.sheets) {
            sheetSelect.innerHTML = "";
            data.sheets.forEach(function (s) {
                var opt = document.createElement("option");
                opt.value = s;
                opt.textContent = s;
                if (s === data.sheet) opt.selected = true;
                sheetSelect.appendChild(opt);
            });
        }
        convCurrentSheet = data.sheet;

        var yearInput = document.getElementById("conv-year");
        if (data.year && !yearInput.value) {
            yearInput.value = data.year;
        }
        convCurrentYear = data.year;

        var warn = document.getElementById("conv-year-warning");
        warn.textContent = data.warning || "";

        document.getElementById("params-card").classList.remove("hidden");
        document.getElementById("refs-card").classList.remove("hidden");
        document.getElementById("convert-action-card").classList.remove("hidden");
        document.getElementById("result-card").classList.add("hidden");
    }

    function saveArea() {
        var select = document.getElementById("conv-court-area");
        var val = select ? select.value : "";
        if (!val) {
            alert("Сначала выберите участок в списке (или создайте новый).");
            return;
        }
        var data = convReadRefs();
        var empty = CONV_CA_FIELDS.filter(function (f) { return !data[f]; });
        if (empty.length) {
            alert("Все 9 полей обязательны. Не заполнено: " + empty.join(", "));
            return;
        }
        request("PUT", "/api/court_areas/" + val, data).then(function () {
            alert("Участок обновлён.");
            loadConvertAreas().then(fillRefsFromCurrentArea);
        }).catch(showErr);
    }

    function createArea() {
        var data = convReadRefs();
        var empty = CONV_CA_FIELDS.filter(function (f) { return !data[f]; });
        if (empty.length) {
            alert("Все 9 полей обязательны. Не заполнено: " + empty.join(", "));
            return;
        }
        request("POST", "/api/court_areas", data).then(function (res) {
            alert("Создан участок с id=" + res.id + ".");
            loadConvertAreas().then(function () {
                var select = document.getElementById("conv-court-area");
                select.value = String(res.id);
                fillRefsFromCurrentArea();
            });
        }).catch(showErr);
    }

    function runConvert() {
        // stage13d: маршрутизация по направлению
        if (convCurrentDirection() === "word_to_xlsx") {
            runConvertWord();
            return;
        }
        var errorBox = document.getElementById("error-box");
        errorBox.textContent = "";
        if (!convSelectedFile) {
            errorBox.textContent = "Выберите файл.";
            return;
        }
        var year = document.getElementById("conv-year").value.trim();
        if (!year || !/^\d{4}$/.test(year)) {
            errorBox.textContent = "Укажите год (например, 2020).";
            return;
        }
        // Предупреждение о неполных реквизитах (решение 47/48)
        var refs = convReadRefs();
        var empty = CONV_CA_FIELDS.filter(function (f) { return !refs[f]; });
        if (empty.length) {
            if (!window.confirm("Не заполнено: " + empty.join(", ") +
                    ". Продолжить конвертацию?")) {
                return;
            }
        }
        doConvert({year: year});
    }

    function doConvert(opts) {
        var formData = new FormData();
        formData.append("file", convSelectedFile);
        formData.append("year", opts.year);
        if (convCurrentSheet) formData.append("sheet", convCurrentSheet);
        var caSel = document.getElementById("conv-court-area");
        if (caSel && caSel.value) formData.append("court_area_id", caSel.value);
        if (opts.overwrite) formData.append("overwrite", "1");
        if (opts.copy) formData.append("copy", "1");

        var btn = document.getElementById("convert-btn");
        btn.disabled = true;
        btn.textContent = "Конвертация...";

        jsonPost("/convert/xlsx_to_word", formData).then(function (res) {
            if (res.ok) {
                renderConvertResult(res.data);
                return;
            }
            if (res.data && res.data.conflict) {
                return showConflictDialog(res.data.filename).then(function (choice) {
                    if (choice === "replace") return doConvert({year: opts.year, overwrite: true});
                    if (choice === "copy") return doConvert({year: opts.year, copy: true});
                    return null;
                });
            }
            throw new Error((res.data && res.data.error) || "Ошибка конвертации");
        }).catch(function (err) {
            errorBox.textContent = err.message;
        }).finally(function () {
            btn.disabled = false;
            btn.textContent = "Конвертировать";
        });
    }

    function renderConvertResult(data) {
        var stats = "Дел в файле: " + data.count + "\n" +
                    "Строк (с пустыми): " + data.total;
        document.getElementById("conv-stats").textContent = stats;

        var tbody = document.querySelector("#conv-preview-table tbody");
        tbody.innerHTML = "";
        (data.preview || []).forEach(function (r) {
            var tr = document.createElement("tr");
            [r.sequential, r.title, r.dates, r.opis, r.unit,
             r.count, r.retention, r.note].forEach(function (val) {
                var td = document.createElement("td");
                td.innerHTML = String(val == null ? "" : val);
                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });

        var link = document.getElementById("conv-download-link");
        link.href = "/download/" + encodeURIComponent(data.filename);
        link.classList.remove("hidden");

        var refs = convReadRefs();
        var refsLines = CONV_CA_FIELDS.map(function (f) {
            return f + ": " + (refs[f] || "—");
        }).join("\n");
        document.getElementById("conv-refs-used").textContent = refsLines;

        document.getElementById("result-card").classList.remove("hidden");
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

        // stage11e: подгружаем участки и настройки для селекта/валидации
        loadCourtAreasForIndex();
        loadSettingsForIndex();

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

        // stage11e: предупреждение о неполных реквизитах
        if (!checkRefsBeforeProcess()) return;

        var formData = new FormData();
        formData.append("file", file);
        formData.append("year", year);
        formData.append("alimony", document.getElementById("alimony").checked ? "1" : "0");
        formData.append("header_row", document.getElementById("header-row").value || "");
        formData.append("format", document.querySelector('input[name="format"]:checked').value);
        var caSel = document.getElementById("court-area");
        formData.append("court_area_id", caSel ? caSel.value : "");

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

        // stage11e: судебные участки
        loadCourtAreas();
        document.getElementById("court-area-add").addEventListener("click",
            function () { saveCourtAreaForm(); });
        document.getElementById("court-area-cancel").addEventListener("click",
            function () { resetCourtAreaForm(); });

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

    // ---------- Внутренняя опись (stage14e) ----------

    function invSetText(id, text) {
        var el = document.getElementById(id);
        if (el) el.textContent = text;
    }

    function invRenderStats(s) {
        var lines = [
            "Файлов обработано: " + s.files,
            "Тип дел: " + (s.type_word || "не определён"),
            "Год потока: " + (s.year || "—"),
            "Дел (строк записано): " + s.count,
            "Первое дело: " + (s.first != null ? s.first : "—"),
            "Последнее дело: " + (s.last != null ? s.last : "—"),
            "Пропущено строк: " + s.skipped,
            "Требует внимания: " + s.attention
        ];
        invSetText("inv-stats", lines.join("\n"));
        document.getElementById("inv-stats-card").classList.remove("hidden");
    }

    function invRenderPreview(rows) {
        var body = document.getElementById("inv-preview-body");
        body.textContent = "";
        rows.forEach(function (r) {
            var tr = document.createElement("tr");
            [r.C, r.D, r.E, r.G, r.H].forEach(function (v) {
                var td = document.createElement("td");
                td.textContent = (v == null ? "" : String(v));
                tr.appendChild(td);
            });
            body.appendChild(tr);
        });
        document.getElementById("inv-preview-card").classList.remove("hidden");
    }

    function invRenderAttention(rows) {
        var body = document.getElementById("inv-attention-body");
        body.textContent = "";
        rows.forEach(function (r) {
            var tr = document.createElement("tr");
            [r.file, r.word_row, r.number, r.reason, r.action].forEach(
                function (v) {
                    var td = document.createElement("td");
                    td.textContent = (v == null ? "" : String(v));
                    tr.appendChild(td);
                });
            body.appendChild(tr);
        });
        document.getElementById("inv-attention-card")
            .classList.toggle("hidden", rows.length === 0);
    }

    App.initInventoryPage = function () {
        var tpl = document.getElementById("inv-template");
        var files = document.getElementById("inv-files");
        var msg = document.getElementById("inv-message");
        var inspectBtn = document.getElementById("inv-inspect-btn");
        var convertBtn = document.getElementById("inv-convert-btn");

        function refresh() {
            var hasFiles = !!(files.files && files.files.length);
            inspectBtn.disabled = !hasFiles;
            convertBtn.disabled = !(hasFiles &&
                (tpl.files && tpl.files.length));
        }
        tpl.addEventListener("change", refresh);
        files.addEventListener("change", refresh);
        refresh();

        function buildData(withTemplate) {
            var fd = new FormData();
            if (withTemplate && tpl.files[0]) {
                fd.append("template", tpl.files[0]);
            }
            for (var i = 0; i < files.files.length; i++) {
                fd.append("files", files.files[i]);
            }
            var area = document.getElementById("inv-area");
            var year = document.getElementById("inv-year");
            var name = document.getElementById("inv-name");
            if (area.value.trim()) fd.append("court_area", area.value.trim());
            if (year.value.trim()) fd.append("year", year.value.trim());
            if (name.value.trim()) fd.append("name", name.value.trim());
            return fd;
        }

        function showResp(j) {
            if (j.stats) invRenderStats(j.stats);
            if (j.preview) invRenderPreview(j.preview);
            if (j.attention) invRenderAttention(j.attention);
            msg.textContent = j.filename ? ("Готово: " + j.filename)
                                         : "Анализ завершён";
        }

        inspectBtn.addEventListener("click", function () {
            msg.textContent = "Анализ…";
            jsonPost("/inventory/inspect", buildData(false)).then(
                function (res) {
                    if (!res.ok) throw new Error(res.data.error || "Ошибка");
                    showResp(res.data);
                    var el = document.getElementById("inv-year-choice");
                    if (res.data.needs_choice) {
                        el.textContent = "Обнаружены годы: " +
                            (res.data.years || []).join(", ") +
                            ". Уточните год потока в поле выше.";
                        el.classList.remove("hidden");
                    } else {
                        el.classList.add("hidden");
                    }
                }).catch(function (e) { msg.textContent = e.message; });
        });

        convertBtn.addEventListener("click", function () {
            msg.textContent = "Конвертация…";
            fetch("/inventory/convert",
                  { method: "POST", body: buildData(true) })
                .then(function (resp) {
                    if (resp.status === 409) {
                        return resp.json().then(function (d) {
                            throw new Error("Файл уже существует: " +
                                            d.filename);
                        });
                    }
                    return resp.json().then(function (d) {
                        return { ok: resp.ok, data: d };
                    });
                })
                .then(function (res) {
                    if (!res.ok) throw new Error(res.data.error || "Ошибка");
                    showResp(res.data);
                })
                .catch(function (e) { msg.textContent = e.message; });
        });
    };

    // ---------- Страница настроек (stage_42) ----------

    App.initSettingsPage = function () {
        var saveBtn = document.getElementById("settings-save");
        var statusEl = document.getElementById("settings-status");
        var boxes = document.querySelectorAll(
            "#set-auto-fix, #set-taxonomy-diff");

        function setStatus(text, isError) {
            if (!statusEl) return;
            statusEl.textContent = text;
            statusEl.style.color = isError ? "#c00" : "#080";
        }

        function load() {
            request("GET", "/api/settings").then(function (s) {
                boxes.forEach(function (b) {
                    var key = b.dataset.key;
                    var v = (s && s[key] != null) ? String(s[key]) : "";
                    b.checked = (v === "1");
                });
                setStatus("", false);
            }).catch(function (err) {
                setStatus("Ошибка загрузки: " + err.message, true);
            });
        }

        function save() {
            var data = {};
            boxes.forEach(function (b) {
                data[b.dataset.key] = b.checked ? "1" : "0";
            });
            request("POST", "/api/settings", data).then(function () {
                setStatus("Сохранено", false);
            }).catch(function (err) {
                setStatus("Ошибка сохранения: " + err.message, true);
            });
        }

        saveBtn.addEventListener("click", save);
        load();
    };

    // Автоинициализация и heartbeat
    document.addEventListener("DOMContentLoaded", function () {
        startHeartbeat();
        if (document.getElementById("process-btn")) App.initIndexPage();
        if (document.getElementById("check-btn")) App.initCheckPage();
        if (document.getElementById("convert-btn")) App.initConvertPage();
        if (document.getElementById("settings-save")) App.initSettingsPage();
        if (document.getElementById("inv-inspect-btn")) {
            App.initInventoryPage();
        }
    });

    window.App = App;
})();