// stage_49c
"use strict";
(function () {
  const invId = document.body.dataset.inventoryId;
  const tbody = document.getElementById("tbody");
  const statusEl = document.getElementById("status");

  function setStatus(msg, isErr) {
    statusEl.textContent = msg || "";
    statusEl.style.color = isErr ? "#b00" : "#080";
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return {"&": "&amp;", "<": "&lt;", ">": "&gt;",
              "\"": "&quot;", "'": "&#39;"}[c];
    });
  }

  // 1:1 с core.inventory_editor.calculator.compute_derived
  function computeDerived(docs) {
    const out = [];
    let prevA = 1, prevB = 0, prevI = 0, prevJ = null, prevCase = 0;
    for (let i = 0; i < docs.length; i++) {
      const d = docs[i];
      const effPrevI = prevJ === null ? prevI : prevJ;
      let A, B;
      if (i === 0) { A = 1; B = 1; }
      else if (effPrevI >= 150) {
        A = d.case_number === prevCase ? prevA : prevA + 1;
        B = d.case_number === prevCase ? prevB + 1 : 1;
      } else { A = prevA; B = prevB + 1; }
      const E = d.case_number - prevCase;
      const I = (effPrevI >= 150 && d.case_number !== prevCase)
                  ? 1 : effPrevI + 1;
      const J = d.pages_count === 1 ? null : I + d.pages_count - 1;
      out.push({ A: A, B: B, E: E, I: I, J: J });
      prevA = A; prevB = B; prevI = I; prevJ = J; prevCase = d.case_number;
    }
    return out;
  }

  function render(state) {
    const rows = state.rows || [];
    const check = computeDerived(rows);
    tbody.innerHTML = "";
    rows.forEach(function (r, i) {
      const c = check[i];
      const tr = document.createElement("tr");
      tr.dataset.rowId = r.row_id != null ? r.row_id : "";
      tr.dataset.caseNumber = r.case_number;
      tr.dataset.year = r.year;
      tr.innerHTML =
        "<td>" + r.A + "</td>" +
        "<td>" + r.B + "</td>" +
        "<td contenteditable=\"true\" data-field=\"title\">" +
          escapeHtml(r.title) + "</td>" +
        "<td>" + escapeHtml(r.prefix) + "</td>" +
        "<td>" + r.E + "</td>" +
        "<td>" + r.case_number + "</td>" +
        "<td>" + r.year + "</td>" +
        "<td contenteditable=\"true\" data-field=\"pages_count\">" +
          r.pages_count + "</td>" +
        "<td>" + r.I + "</td>" +
        "<td>" + (r.J == null ? "" : r.J) + "</td>" +
        "<td>" +
          "<button type=\"button\" data-act=\"del-row\" title=\"Удалить строку\">\u00d7</button>" +
          "<button type=\"button\" data-act=\"del-case\" title=\"Удалить всё дело\">\u232b</button>" +
        "</td>";
      if (r.A !== c.A || r.B !== c.B || r.E !== c.E ||
          r.I !== c.I || r.J !== c.J) {
        console.warn("Расхождение калькулятора на строке", i,
                     {server: {A: r.A, B: r.B, E: r.E, I: r.I, J: r.J},
                      client: c});
      }
      tbody.appendChild(tr);
    });
    setStatus("Строк: " + rows.length +
              ", дел: " + ((state.groups || []).length));
  }

  async function api(url, opts) {
    const r = await fetch(url, opts);
    let data = {};
    try { data = await r.json(); } catch (e) { /* not json */ }
    if (!r.ok) {
      setStatus(data.error || ("Ошибка " + r.status), true);
      throw data;
    }
    return data;
  }

  async function loadRows() {
    try {
      const data = await api("/api/inventory_editor/" + invId + "/rows");
      render(data);
    } catch (e) { /* status уже выставлен */ }
  }

  document.getElementById("btn-add-case").addEventListener("click",
    async function () {
      const prefix = prompt("Префикс (2, 2а, 5):", "2");
      if (prefix === null) return;
      const cnStr = prompt("Номер дела (целое число):");
      if (!cnStr) return;
      const yearStr = prompt("Год:", String(new Date().getFullYear()));
      if (!yearStr) return;
      const title = prompt("Наименование документа:",
                           "Решение по гражданскому делу");
      if (!title) return;
      const pagesStr = prompt("Кол-во страниц:", "1") || "1";
      try {
        const data = await api("/api/inventory_editor/" + invId + "/rows", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            prefix: prefix,
            case_number: parseInt(cnStr, 10),
            year: parseInt(yearStr, 10),
            docs: [{ title: title,
                     pages_count: parseInt(pagesStr, 10) || 1 }]
          })
        });
        render(data);
        setStatus("Дело добавлено");
      } catch (e) { /* status уже выставлен */ }
    });

  document.getElementById("btn-generate").addEventListener("click",
    async function () {
      const yearStr = prompt("Год дел:", String(new Date().getFullYear()));
      if (!yearStr) return;
      const kind = (prompt("Тип (civil | admin):", "civil") || "civil").trim();
      try {
        const data = await api("/api/inventory_editor/" + invId + "/generate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ year: parseInt(yearStr, 10), kind: kind })
        });
        render(data);
        setStatus("Сформировано строк: " + (data.generated || 0));
      } catch (e) { /* status уже выставлен */ }
    });

  const fileImport = document.getElementById("file-import");
  document.getElementById("btn-import").addEventListener("click",
    function () { fileImport.click(); });
  fileImport.addEventListener("change", async function (ev) {
    const file = ev.target.files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      const data = await api("/api/inventory_editor/" + invId + "/import", {
        method: "POST", body: fd
      });
      render(data);
      setStatus("Импортировано строк: " + (data.imported || 0));
    } catch (e) { /* status уже выставлен */ }
    finally { ev.target.value = ""; }
  });

  const fileTemplate = document.getElementById("file-template");
  document.getElementById("btn-export").addEventListener("click",
    function () { fileTemplate.click(); });
  fileTemplate.addEventListener("change", async function (ev) {
    const file = ev.target.files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("template", file);
    const outName = "Опись_" + invId + ".xlsx";
    fd.append("output_filename", outName);
    try {
      const r = await fetch("/api/inventory_editor/" + invId + "/export",
                            { method: "POST", body: fd });
      if (!r.ok) {
        let data = {};
        try { data = await r.json(); } catch (e) { /* not json */ }
        setStatus(data.error || ("Ошибка " + r.status), true);
        return;
      }
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = outName;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      setStatus("Файл сохранён: " + outName);
    } finally {
      ev.target.value = "";
    }
  });

  tbody.addEventListener("blur", async function (ev) {
    const td = ev.target.closest("td[contenteditable]");
    if (!td) return;
    const tr = td.closest("tr");
    const rowId = tr.dataset.rowId;
    if (!rowId) return;
    const field = td.dataset.field;
    let val = td.textContent.trim();
    if (field === "pages_count") {
      val = parseInt(val, 10) || 1;
    }
    const body = {};
    body[field] = val;
    try {
      const data = await api(
        "/api/inventory_editor/" + invId + "/rows/" + rowId,
        { method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body) });
      render(data);
    } catch (e) { /* status уже выставлен */ }
  }, true);

  tbody.addEventListener("click", async function (ev) {
    const btn = ev.target.closest("button[data-act]");
    if (!btn) return;
    const tr = btn.closest("tr");
    const rowId = tr.dataset.rowId;
    const year = tr.dataset.year;
    const cn = tr.dataset.caseNumber;
    if (btn.dataset.act === "del-row") {
      if (!rowId) return;
      if (!confirm("Удалить строку?")) return;
      try {
        const data = await api(
          "/api/inventory_editor/" + invId + "/rows/" + rowId,
          { method: "DELETE" });
        render(data);
        setStatus("Строка удалена");
      } catch (e) { /* status уже выставлен */ }
    } else if (btn.dataset.act === "del-case") {
      if (!confirm("Удалить всё дело " + cn + "/" + year + "?")) return;
      try {
        const data = await api(
          "/api/inventory_editor/" + invId + "/cases/" + year + "/" + cn,
          { method: "DELETE" });
        render(data);
        setStatus("Дело удалено (строк: " + (data.removed || 0) + ")");
      } catch (e) { /* status уже выставлен */ }
    }
  });

  loadRows();
})();
