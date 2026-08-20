const STORAGE_KEY = "exam-practice-app-v1";

const seedQuestions = [
  {
    id: uid(),
    bank: "示例题库",
    type: "single",
    tags: ["Verilog"],
    text: "Verilog 中，下列哪项语法通常不被综合支持？",
    options: [
      { key: "A", text: "initial" },
      { key: "B", text: "logic" },
      { key: "C", text: "tri" },
      { key: "D", text: "generate-for 循环" },
    ],
    answer: "A",
    explanation: "initial 常用于仿真初始化，综合支持情况受工具和场景限制，笔试中常按不可综合处理。",
    starred: false,
    wrongCount: 0,
    createdAt: new Date().toISOString(),
  },
];

const state = loadState();
let activeView = "practice";
let currentQuestion = null;
let selectedAnswers = new Set();
let editingId = null;
let parsedImport = [];
let questionHistory = [];
let answeredCurrent = false;

const viewTitles = {
  practice: "练习",
  library: "题库",
  review: "错题",
  history: "记录",
  import: "导入",
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

function uid() {
  if (globalThis.crypto && typeof crypto.randomUUID === "function") return crypto.randomUUID();
  if (globalThis.crypto && crypto.getRandomValues) {
    return [...crypto.getRandomValues(new Uint8Array(16))].map((b) => b.toString(16).padStart(2, "0")).join("");
  }
  return "xxxxxxxxxxxx4xxxyxxxxxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}

function loadState() {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    return { questions: seedQuestions, attempts: [] };
  }
  try {
    const parsed = JSON.parse(raw);
    return {
      questions: Array.isArray(parsed.questions) ? parsed.questions : seedQuestions,
      attempts: Array.isArray(parsed.attempts) ? parsed.attempts : [],
    };
  } catch {
    return { questions: seedQuestions, attempts: [] };
  }
}

function saveState() {
  persistState();
  renderAll();
}

function persistState() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch (error) {
    console.warn("localStorage 写入失败，数据仅在本次会话有效：", error);
  }
}

function normalizeAnswer(answer) {
  return String(answer || "")
    .toUpperCase()
    .replace(/[^A-Z0-9\u4e00-\u9fa5]/g, "")
    .split("")
    .sort()
    .join("");
}

function normalizeChoiceAnswer(answer) {
  return String(answer || "")
    .toUpperCase()
    .replace(/[^A-H]/g, "")
    .split("")
    .sort()
    .join("");
}

function getBanks() {
  return [...new Set(state.questions.map((q) => q.bank || "未分组"))].sort();
}

function typeLabel(type) {
  return { single: "单选", multiple: "多选", text: "简答" }[type] || "题目";
}

function switchView(view) {
  activeView = view;
  $$(".nav-item").forEach((btn) => btn.classList.toggle("active", btn.dataset.view === view));
  $$(".view").forEach((section) => section.classList.remove("active"));
  $(`#${view}View`).classList.add("active");
  $("#viewTitle").textContent = viewTitles[view];
  renderAll();
}

function renderAll() {
  renderStats();
  renderBankFilters();
  renderPractice();
  renderLibrary();
  renderReview();
  renderHistory();
}

function renderStats() {
  const total = state.attempts.length;
  const correct = state.attempts.filter((a) => a.correct).length;
  const today = new Date().toDateString();
  $("#todayCount").textContent = state.attempts.filter((a) => new Date(a.time).toDateString() === today).length;
  $("#statQuestions").textContent = state.questions.length;
  $("#statAccuracy").textContent = total ? `${Math.round((correct / total) * 100)}%` : "0%";
  $("#statWrong").textContent = state.questions.filter((q) => q.wrongCount > 0).length;
  $("#statStarred").textContent = state.questions.filter((q) => q.starred).length;
}

function renderBankFilters() {
  const banks = getBanks();
  const filters = [$("#bankFilter"), $("#libraryBankFilter")];
  filters.forEach((select) => {
    const value = select.value;
    select.innerHTML = `<option value="all">全部题库</option>${banks.map((bank) => `<option value="${escapeHtml(bank)}">${escapeHtml(bank)}</option>`).join("")}`;
    select.value = banks.includes(value) ? value : "all";
  });
}

function practicePool() {
  const bank = $("#bankFilter").value;
  const mode = $("#practiceMode").value;
  return state.questions.filter((q) => {
    const bankMatch = bank === "all" || q.bank === bank;
    const modeMatch = mode === "all" || (mode === "wrong" && q.wrongCount > 0) || (mode === "starred" && q.starred);
    return bankMatch && modeMatch;
  });
}

function pickQuestion(pushHistory = true) {
  const pool = practicePool();
  if (!pool.length) {
    currentQuestion = null;
    selectedAnswers = new Set();
    answeredCurrent = false;
    renderPractice();
    return;
  }
  if (pushHistory && currentQuestion) questionHistory.push(currentQuestion.id);
  let next;
  if (pool.length === 1) {
    next = pool[0];
  } else {
    do {
      next = pool[Math.floor(Math.random() * pool.length)];
    } while (next.id === currentQuestion?.id);
  }
  currentQuestion = next;
  selectedAnswers = new Set();
  answeredCurrent = false;
  renderPractice();
}

function previousQuestion() {
  const previousId = questionHistory.pop();
  if (!previousId) return;
  const previous = state.questions.find((q) => q.id === previousId);
  if (!previous) return;
  currentQuestion = previous;
  selectedAnswers = new Set();
  answeredCurrent = false;
  renderPractice();
}

function renderPractice() {
  if (activeView !== "practice") return;
  const card = $("#questionCard");
  const empty = $("#emptyPractice");
  if (!currentQuestion || !practicePool().some((q) => q.id === currentQuestion.id)) {
    const pool = practicePool();
    currentQuestion = pool[0] || null;
  }
  if (!currentQuestion) {
    card.classList.add("hidden");
    empty.classList.remove("hidden");
    return;
  }
  empty.classList.add("hidden");
  card.classList.remove("hidden");
  $("#questionBank").textContent = currentQuestion.bank || "未分组";
  $("#questionType").textContent = typeLabel(currentQuestion.type);
  $("#questionSource").textContent = questionSourceText(currentQuestion);
  $("#starBtn").textContent = currentQuestion.starred ? "取消收藏" : "收藏";
  $("#questionText").textContent = currentQuestion.text;
  $("#resultBox").className = "result-box hidden";
  $("#resultBox").textContent = "";
  $("#submitBtn").textContent = "提交答案";
  $("#submitBtn").disabled = false;

  const options = currentQuestion.options || [];
  $("#optionList").innerHTML = options.length
    ? options.map((option) => `<label class="option" data-key="${escapeHtml(option.key)}"><input type="${currentQuestion.type === "multiple" ? "checkbox" : "radio"}" name="answer" value="${escapeHtml(option.key)}" /> <span><strong>${escapeHtml(option.key)}.</strong> ${escapeHtml(option.text)}</span></label>`).join("")
    : `<textarea id="textAnswer" placeholder="输入你的答案"></textarea>`;

  $$(".option").forEach((option) => {
    option.querySelector("input").addEventListener("change", syncSelectedAnswers);
  });
}

function questionSourceText(question) {
  const source = question.sourceFile || question.source || "";
  const page = question.page ? `第 ${question.page} 页` : "";
  const duplicate = question.duplicateSource ? `重复：${question.duplicateSource}` : "";
  return [source, page, duplicate].filter(Boolean).join(" | ");
}

function syncSelectedAnswers() {
  selectedAnswers = new Set(
    $$(".option input")
      .filter((input) => input.checked)
      .map((input) => input.value)
  );
  $$(".option").forEach((item) => {
    item.classList.toggle("selected", item.querySelector("input").checked);
  });
}

function submitAnswer(revealOnly = false) {
  if (!currentQuestion) return;
  if (answeredCurrent && !revealOnly) {
    pickQuestion();
    return;
  }
  const userAnswer = currentQuestion.type === "text" || !(currentQuestion.options || []).length ? ($("#textAnswer")?.value || "") : [...selectedAnswers].sort().join("");
  const isChoice = (currentQuestion.options || []).length > 0 && currentQuestion.type !== "text";
  const correctAnswer = isChoice ? normalizeChoiceAnswer(currentQuestion.answer) : normalizeAnswer(currentQuestion.answer);
  const normalizedUser = isChoice ? normalizeChoiceAnswer(userAnswer) : normalizeAnswer(userAnswer);
  const correct = Boolean(correctAnswer) && normalizedUser === correctAnswer;
  if (!revealOnly) {
    currentQuestion.wrongCount = correct ? currentQuestion.wrongCount : (currentQuestion.wrongCount || 0) + 1;
    state.attempts.unshift({
      id: uid(),
      questionId: currentQuestion.id,
      bank: currentQuestion.bank,
      questionText: currentQuestion.text,
      userAnswer,
      correctAnswer: currentQuestion.answer || "未设置",
      correct,
      time: new Date().toISOString(),
    });
    state.attempts = state.attempts.slice(0, 500);
  }
  const box = $("#resultBox");
  box.className = `result-box ${revealOnly ? "" : correct ? "correct" : "wrong"}`;
  const explanation = currentQuestion.explanation || "暂无解析。";
  box.innerHTML = `${revealOnly ? "" : correct ? "答对了。" : "这题先记入错题。"}<br>答案：${escapeHtml(currentQuestion.answer || "未设置")}${answerDetailsHtml(currentQuestion)}<br>解析：${formatMultiline(explanation)}`;
  box.classList.remove("hidden");
  answeredCurrent = true;
  $$(".option input").forEach((input) => input.disabled = true);
  const textAnswer = $("#textAnswer");
  if (textAnswer) textAnswer.disabled = true;
  $("#submitBtn").textContent = "下一题";
  persistState();
  renderStats();
  renderReview();
  renderHistory();
}

function openAnswerDialog() {
  if (!currentQuestion) return;
  $("#quickAnswer").value = currentQuestion.answer || "";
  $("#quickExplain").value = currentQuestion.explanation || "";
  $("#answerDialog").showModal();
}

function saveCurrentAnswer(event) {
  event.preventDefault();
  if (!currentQuestion) return;
  const answer = $("#quickAnswer").value.trim().toUpperCase();
  const explanation = $("#quickExplain").value.trim();
  const index = state.questions.findIndex((q) => q.id === currentQuestion.id);
  if (index >= 0) {
    state.questions[index] = {
      ...state.questions[index],
      answer,
      explanation,
      updatedAt: new Date().toISOString(),
    };
    currentQuestion = state.questions[index];
  } else {
    currentQuestion.answer = answer;
    currentQuestion.explanation = explanation;
  }
  persistState();
  $("#answerDialog").close();
  renderPractice();
}

function renderLibrary() {
  if (activeView !== "library") return;
  renderBankDeleteList();
  const keyword = $("#searchInput").value.trim().toLowerCase();
  const bank = $("#libraryBankFilter").value;
  const list = state.questions.filter((q) => {
    const haystack = [q.text, q.answer, q.explanation, q.bank, ...(q.tags || []), ...(q.options || []).map((o) => o.text)].join(" ").toLowerCase();
    return (bank === "all" || q.bank === bank) && (!keyword || haystack.includes(keyword));
  });
  $("#questionList").innerHTML = list.length ? list.map(questionItemHtml).join("") : `<div class="empty-state">没有匹配的题目。</div>`;
  bindQuestionItemActions();
}

function renderBankDeleteList() {
  const banks = getBanks();
  $("#bankDeleteList").innerHTML = banks.length
    ? banks.map((bank) => `<label><input type="checkbox" class="bank-delete-check" value="${escapeHtml(bank)}" /> ${escapeHtml(bank)}</label>`).join("")
    : "";
}

function questionFingerprint(question) {
  const normalize = (value) => String(value || "")
    .toLowerCase()
    .replace(/[\s\uFEFF\u200B-\u200D]/g, "")
    .replace(/[，。；：、,.?:;!！?？()（）\[\]【】"'“”‘’`]/g, "");
  const optionText = (question.options || [])
    .slice()
    .sort((a, b) => a.key.localeCompare(b.key))
    .map((option) => `${option.key}:${normalize(option.text)}`)
    .join("|");
  return `${normalize(question.text)}::${optionText}`;
}

function upsertQuestions(questions) {
  let added = 0;
  let updated = 0;
  let existing = new Map(state.questions.map((question, index) => [questionFingerprint(question), index]));
  for (const question of questions) {
    const key = questionFingerprint(question);
    const index = existing.get(key);
    if (index === undefined) {
      state.questions.unshift(question);
      existing = new Map(state.questions.map((item, itemIndex) => [questionFingerprint(item), itemIndex]));
      added += 1;
      continue;
    }
    const current = state.questions[index];
    state.questions[index] = {
      ...current,
      bank: question.bank || current.bank,
      type: question.type || current.type,
      tags: question.tags?.length ? question.tags : current.tags,
      text: question.text || current.text,
      options: question.options?.length ? question.options : current.options,
      answer: question.answer,
      explanation: question.explanation,
      aiAnswer: question.aiAnswer || "",
      originalAnswer: question.originalAnswer || "",
      sourceFile: question.sourceFile || current.sourceFile,
      page: question.page || current.page,
      duplicateSource: question.duplicateSource || current.duplicateSource,
      updatedAt: new Date().toISOString(),
    };
    existing.set(questionFingerprint(state.questions[index]), index);
    updated += 1;
  }
  return { added, updated };
}

function deleteSelectedBank() {
  const banks = $$(".bank-delete-check")
    .filter((input) => input.checked)
    .map((input) => input.value);
  if (!banks.length) {
    alert("请先勾选要删除的题库。");
    return;
  }
  const bankSet = new Set(banks);
  const count = state.questions.filter((q) => bankSet.has(q.bank)).length;
  if (!count) return;
  if (!confirm(`确定删除选中的 ${banks.length} 个题库吗？将删除 ${count} 道题，做题记录会保留。`)) return;
  state.questions = state.questions.filter((q) => !bankSet.has(q.bank));
  if (currentQuestion && bankSet.has(currentQuestion.bank)) currentQuestion = null;
  saveState();
}

function renderReview() {
  if (activeView !== "review") return;
  const list = state.questions.filter((q) => q.wrongCount > 0 || q.starred);
  $("#reviewList").innerHTML = list.length ? list.map(questionItemHtml).join("") : `<div class="empty-state">还没有错题或收藏。</div>`;
  bindQuestionItemActions();
}

function questionItemHtml(q) {
  const tags = (q.tags || []).map((tag) => `<span class="pill">${escapeHtml(tag)}</span>`).join("");
  return `<article class="list-item" data-id="${q.id}">
    <p class="list-title">${escapeHtml(q.text)}</p>
    <div class="list-meta">
      <span>${escapeHtml(q.bank || "未分组")}</span>
      <span>${typeLabel(q.type)}</span>
      <span>答案：${escapeHtml(q.answer || "未设置")}</span>
      ${q.aiAnswer ? `<span>AI：${escapeHtml(q.aiAnswer)}</span>` : ""}
      ${q.originalAnswer ? `<span>参考：${escapeHtml(q.originalAnswer)}</span>` : ""}
      <span>错 ${q.wrongCount || 0} 次</span>
      ${q.starred ? "<span>已收藏</span>" : ""}
      ${tags}
    </div>
    <div class="item-actions">
      <button class="ghost-btn edit-btn">编辑</button>
      <button class="ghost-btn star-list-btn">${q.starred ? "取消收藏" : "收藏"}</button>
      <button class="danger-btn delete-btn">删除</button>
    </div>
  </article>`;
}

function bindQuestionItemActions() {
  $$(".list-item").forEach((item) => {
    const id = item.dataset.id;
    item.querySelector(".edit-btn")?.addEventListener("click", () => openDialog(id));
    item.querySelector(".star-list-btn")?.addEventListener("click", () => toggleStar(id));
    item.querySelector(".delete-btn")?.addEventListener("click", () => deleteQuestion(id));
  });
}

function renderHistory() {
  if (activeView !== "history") return;
  $("#historyList").innerHTML = state.attempts.length
    ? state.attempts.map((a) => `<article class="list-item">
      <p class="list-title">${escapeHtml(a.questionText)}</p>
      <div class="list-meta">
        <span>${new Date(a.time).toLocaleString()}</span>
        <span>${escapeHtml(a.bank || "未分组")}</span>
        <span>${a.correct ? "正确" : "错误"}</span>
        <span>你的答案：${escapeHtml(a.userAnswer || "空")}</span>
        <span>答案：${escapeHtml(a.correctAnswer || "未设置")}</span>
      </div>
    </article>`).join("")
    : `<div class="empty-state">还没有做题记录。</div>`;
}

function openDialog(id = null) {
  editingId = id;
  const q = state.questions.find((item) => item.id === id);
  $("#dialogTitle").textContent = q ? "编辑题目" : "新增题目";
  $("#formBank").value = q?.bank || "数字芯片";
  $("#formTags").value = (q?.tags || []).join(", ");
  $("#formType").value = q?.type || "single";
  $("#formText").value = q?.text || "";
  $("#formOptions").value = (q?.options || []).map((o) => `${o.key}. ${o.text}`).join("\n");
  $("#formAnswer").value = q?.answer || "";
  $("#formExplain").value = q?.explanation || "";
  $("#questionDialog").showModal();
}

function saveQuestionFromDialog(event) {
  event.preventDefault();
  const question = {
    id: editingId || uid(),
    bank: $("#formBank").value.trim() || "未分组",
    type: $("#formType").value,
    tags: $("#formTags").value.split(/[,，]/).map((tag) => tag.trim()).filter(Boolean),
    text: $("#formText").value.trim(),
    options: parseOptions($("#formOptions").value),
    answer: $("#formAnswer").value.trim().toUpperCase(),
    explanation: $("#formExplain").value.trim(),
    starred: state.questions.find((q) => q.id === editingId)?.starred || false,
    wrongCount: state.questions.find((q) => q.id === editingId)?.wrongCount || 0,
    createdAt: state.questions.find((q) => q.id === editingId)?.createdAt || new Date().toISOString(),
  };
  if (!question.text) return;
  const index = state.questions.findIndex((q) => q.id === editingId);
  if (index >= 0) state.questions[index] = question;
  else state.questions.unshift(question);
  $("#questionDialog").close();
  saveState();
}

function parseOptions(text) {
  return text
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line, index) => {
      const match = line.match(/^([A-Z])[\.\、．\s]+(.+)$/i);
      return match ? { key: match[1].toUpperCase(), text: match[2].trim() } : { key: String.fromCharCode(65 + index), text: line };
    });
}

function parseImportText(text, bank) {
  const normalized = text.replace(/\r/g, "").trim();
  if (!normalized) return [];
  const blocks = normalized.split(/\n(?=\s*\d+[\.\、])/);
  return blocks.map((block) => parseQuestionBlock(block, bank)).filter((q) => q.text);
}

function parseQuestionBlock(block, bank) {
  const lines = block.split("\n").map((line) => line.trim()).filter(Boolean);
  let answer = "";
  let explanation = "";
  const bodyLines = [];
  for (const line of lines) {
    const answerMatch = line.match(/^(参考答案|答案|正确答案)[:：\s]*(.+)$/);
    const explainMatch = line.match(/^(解析)[:：\s]*(.+)$/);
    if (answerMatch) answer = answerMatch[2].trim().toUpperCase();
    else if (explainMatch) explanation = explainMatch[2].trim();
    else bodyLines.push(line);
  }
  const optionStart = bodyLines.findIndex((line) => /^[A-Z][\.\、．\s]/i.test(line));
  const stemLines = optionStart >= 0 ? bodyLines.slice(0, optionStart) : bodyLines;
  const optionLines = optionStart >= 0 ? bodyLines.slice(optionStart) : [];
  const text = stemLines.join("\n").replace(/^\d+[\.\、]\s*/, "").trim();
  const options = parseOptions(optionLines.join("\n"));
  return {
    id: uid(),
    bank: bank || "未分组",
    type: normalizeAnswer(answer).length > 1 ? "multiple" : "single",
    tags: [],
    text,
    options,
    answer,
    explanation,
    starred: false,
    wrongCount: 0,
    createdAt: new Date().toISOString(),
  };
}

function renderImportPreview() {
  $("#importPreview").innerHTML = parsedImport.length
    ? parsedImport.slice(0, 20).map((q) => `<article class="list-item"><p class="list-title">${escapeHtml(q.text)}</p><div class="list-meta"><span>${q.options.length} 个选项</span><span>答案：${escapeHtml(q.answer || "未设置")}</span>${q.aiAnswer ? `<span>AI：${escapeHtml(q.aiAnswer)}</span>` : ""}${q.originalAnswer ? `<span>参考：${escapeHtml(q.originalAnswer)}</span>` : ""}</div></article>`).join("")
    : `<div class="empty-state">解析后会在这里预览。</div>`;
}

function toggleStar(id = currentQuestion?.id) {
  const q = state.questions.find((item) => item.id === id);
  if (!q) return;
  q.starred = !q.starred;
  saveState();
}

function deleteQuestion(id) {
  if (!confirm("确定删除这道题吗？")) return;
  const index = state.questions.findIndex((q) => q.id === id);
  if (index >= 0) state.questions.splice(index, 1);
  if (currentQuestion?.id === id) currentQuestion = null;
  saveState();
}

function exportBackup() {
  const blob = new Blob([JSON.stringify(state, null, 2)], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `笔试题库备份-${new Date().toISOString().slice(0, 10)}.json`;
  link.click();
  URL.revokeObjectURL(link.href);
}

function importBackup(file) {
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const data = JSON.parse(reader.result);
      if (!Array.isArray(data.questions)) throw new Error("invalid");
      state.questions = data.questions;
      state.attempts = Array.isArray(data.attempts) ? data.attempts : [];
      saveState();
      alert("备份已导入。");
    } catch {
      alert("这个备份文件无法识别。");
    }
  };
  reader.readAsText(file);
}

async function importExcel(file) {
  try {
    const sheets = await readXlsxRows(file);
    const optionKeys = "ABCDEFGH".split("");
    const allQuestions = [];
    const sheetSummary = [];
    for (const sheet of sheets) {
      if (!sheet.rows.length) continue;
      const header = sheet.rows[0].map((v) => String(v || "").trim());
      const hasStem = header.some((h) => normalizeHeader(h) === "题干") || header.includes("题干");
      const optionCount = optionKeys.filter((k) => header.includes(k)).length;
      if (!hasStem || optionCount < 2) continue; // 跳过核验记录、汇总等非题库工作表
      const questions = rowsToQuestions(sheet.rows);
      if (questions.length) {
        allQuestions.push(...questions);
        sheetSummary.push(`${sheet.name || "未命名"}：${questions.length} 道`);
      }
    }
    if (!allQuestions.length) {
      alert("没有识别到题目。请确认 Excel 表头包含“题干”和 A/B/C/D 选项列，且题目放在含题干与选项的工作表中。");
      return;
    }
    const { added, updated } = upsertQuestions(allQuestions);
    saveState();
    const withAnswer = allQuestions.filter((q) => q.answer).length;
    const withExplanation = allQuestions.filter((q) => q.explanation).length;
    alert(`已处理 ${allQuestions.length} 道题（来源：${sheetSummary.join("，")}）：新增 ${added} 道，覆盖更新 ${updated} 道。其中 ${withAnswer} 道带答案，${withExplanation} 道带解析。`);
  } catch (error) {
    console.error(error);
    alert("Excel 导入失败：" + (error && error.message ? error.message : error) + "\n\n请确认文件是 .xlsx；若仍失败，可先用转换脚本重新生成。");
  }
}

function stripNamespace(xml) {
  // 兼容带命名空间前缀的 xlsx（如 <x:sheet>），去掉前缀使手写解析器能匹配标签
  return String(xml || "").replace(/<(\/?)([A-Za-z_][\w.-]*):([A-Za-z_][\w.-]*)/g, "<$1$3");
}

async function readXlsxRows(file) {
  const buffer = await file.arrayBuffer();
  const files = unzip(buffer);
  const decode = (name) => textDecoder(files[name] || new Uint8Array());
  const workbookXml = stripNamespace(decode("xl/workbook.xml"));
  const relsXml = stripNamespace(decode("xl/_rels/workbook.xml.rels"));
  const sharedStrings = parseSharedStrings(stripNamespace(decode("xl/sharedStrings.xml")));
  const sheets = [];
  for (const sheetMatch of workbookXml.matchAll(/<sheet\b([^>]*)>/g)) {
    const attrs = sheetMatch[1];
    const rid = attrs.match(/r:id="([^"]+)"/)?.[1];
    if (!rid) continue;
    const name = attrs.match(/name="([^"]*)"/)?.[1] || "";
    const relEl = relsXml.match(new RegExp(`<Relationship[^>]*Id="${rid}"[^>]*>`))?.[0];
    const target = relEl?.match(/Target="([^"]+)"/)?.[1] || "worksheets/sheet1.xml";
    const sheetPath = `xl/${target.replace(/^\/?xl\//, "")}`;
    const sheetXml = stripNamespace(decode(sheetPath));
    sheets.push({ name, rows: parseSheetRows(sheetXml, sharedStrings) });
  }
  if (!sheets.length) {
    const sheetXml = stripNamespace(decode("xl/worksheets/sheet1.xml"));
    sheets.push({ name: "Sheet1", rows: parseSheetRows(sheetXml, sharedStrings) });
  }
  return sheets;
}

function rowsToQuestions(rows) {
  if (!rows.length) return [];
  const headers = rows[0].map((value) => String(value || "").trim());
  const index = Object.fromEntries(headers.map((header, i) => [header, i]));
  const normalizedIndex = Object.fromEntries(headers.map((header, i) => [normalizeHeader(header), i]));
  const optionKeys = "ABCDEFGH".split("");
  const col = (...names) => {
    for (const name of names) {
      if (index[name] !== undefined) return index[name];
      const normalized = normalizeHeader(name);
      if (normalizedIndex[normalized] !== undefined) return normalizedIndex[normalized];
    }
    return undefined;
  };
  return rows.slice(1).map((row) => {
    const firstValue = (...names) => {
      for (const name of names) {
        const i = col(name);
        if (i !== undefined) {
          const v = cell(row, i);
          if (v) return v;
        }
      }
      return "";
    };
    const text = cell(row, col("题干", "棰樺共"));
    if (!text) return null;
    let options = optionKeys
      .map((key) => ({ key, text: cell(row, index[key]) }))
      .filter((option) => option.text);
    const aiAnswerSource = firstValue("AI判断答案", "AI答案", "答案", "参考答案", "正确答案");
    const originalAnswerSource = firstValue("原文答案");
    const calibrationNote = firstValue("校准备注");
    let answer = hasInvalidChoiceNote(calibrationNote)
      ? deriveDirectChoiceAnswer([aiAnswerSource])
      : deriveDirectChoiceAnswer([aiAnswerSource, originalAnswerSource]) || deriveChoiceAnswer([calibrationNote]) || deriveChoiceAnswer([firstValue("解析")]);
    const displayAiAnswer = aiAnswerSource;
    const displayOriginalAnswer = originalAnswerSource;
    const explanationParts = [
      labeledText("AI判断答案", displayAiAnswer),
      labeledText("参考答案", displayOriginalAnswer),
      labeledText("解析", cell(row, col("解析", "瑙ｆ瀽"))),
      labeledText("知识点", cell(row, col("知识点", "鐭ヨ瘑鐐?"))),
      labeledText("校准备注", cell(row, col("校准备注"))),
    ].filter(Boolean);
    const rawType = cell(row, col("题型", "棰樺瀷"));
    if (options.length < 2 && !String(rawType).toLowerCase().includes("text")) {
      const fallback = buildFallbackOptions(rawType, text, explanationParts);
      options = fallback.options;
      answer = answer || fallback.answer;
    }
    const type = normalizeType(rawType, options, answer);
    return {
      id: uid(),
      bank: cell(row, col("题库", "棰樺簱")) || $("#importBank").value.trim() || "未分组",
      type,
      tags: cell(row, col("标签", "知识点", "鏍囩", "鐭ヨ瘑鐐?")).split(/[,，]/).map((tag) => tag.trim()).filter(Boolean),
      text,
      options,
      answer,
      explanation: explanationParts.join("\n"),
      aiAnswer: displayAiAnswer,
      originalAnswer: displayOriginalAnswer,
      sourceFile: cell(row, col("来源文件", "文件", "来源", "鏉ユ簮鏂囦欢")) || cellAt(row, 18),
      page: cell(row, col("页码", "页", "椤电爜")) || cellAt(row, 19),
      duplicateSource: cell(row, col("重复来源", "重复题来源", "閲嶅鏉ユ簮")) || cellAt(row, 20),
      starred: false,
      wrongCount: 0,
      createdAt: new Date().toISOString(),
    };
  }).filter(Boolean);
}

function deriveChoiceAnswer(values) {
  const patterns = [
    /(?:答案|判断为|应为|对应)\s*[：:为是]?\s*([A-H]{1,8})(?=[\s，。；;、）)]|$)/i,
    /答案\s*([A-H]{1,8})/i,
    /([A-H]{1,8})\s*(?:项|为正确|正确)/i,
  ];
  for (const value of values) {
    const text = String(value || "").toUpperCase();
    for (const pattern of patterns) {
      const match = text.match(pattern);
      if (match) {
        const answer = normalizeChoiceAnswer(match[1]);
        if (answer) return answer;
      }
    }
  }
  return "";
}

function deriveDirectChoiceAnswer(values) {
  for (const value of values) {
    const text = String(value || "").replace(/\s/g, "");
    const direct = normalizeChoiceAnswer(text);
    if (direct && direct.length <= 8 && direct.length === text.length) return direct;
  }
  return "";
}

function hasInvalidChoiceNote(value) {
  const text = String(value || "");
  return /(?:选项存在错误|无正确选项|没有正确选项|不强行选|无法从\s*[A-H](?:\s*-\s*[A-H])?\s*中选|无法从选项)/i.test(text);
}

function buildFallbackOptions(rawType, text, explanationParts) {
  const source = [rawType, text, ...(explanationParts || [])].join("\n");
  if (/(?:判断|对错|是否|正确|错误|true|false)/i.test(source)) {
    return {
      options: [
        { key: "A", text: "正确" },
        { key: "B", text: "错误" },
      ],
      answer: "",
    };
  }
  const resultMatch = source.match(/(?:最终|结果|答案)(?:\s*[为是：:])?\s*([^。；;\n]{2,40})/);
  const result = resultMatch ? resultMatch[1].trim() : "答案见解析";
  return {
    options: [
      { key: "A", text: result },
      { key: "B", text: "其他结果" },
    ],
    answer: "A",
  };
}

function choiceAnswerText(value) {
  const text = String(value || "").trim();
  if (!text) return "";
  return /^[A-H]{1,8}$/i.test(text.replace(/\s/g, "")) ? "" : text;
}

function labeledText(label, value) {
  const text = String(value || "").trim();
  return text ? `${label}：${text}` : "";
}

function normalizeHeader(header) {
  return String(header || "")
    .replace(/[\s\uFEFF\u200B-\u200D]/g, "")
    .replace(/[：:]/g, "")
    .toLowerCase();
}

function normalizeType(rawType, options, answer) {
  const value = String(rawType || "").toLowerCase();
  if (value.includes("multiple") || value.includes("多") || value.includes("澶")) return "multiple";
  if (value.includes("text") || value.includes("简") || value.includes("绠")) return "text";
  if (value.includes("single") || value.includes("单") || value.includes("鍗")) return "single";
  return options.length < 2 ? "text" : normalizeAnswer(answer).length > 1 ? "multiple" : "single";
}

function cell(row, index) {
  return index === undefined ? "" : String(row[index] || "").trim();
}

function cellAt(row, oneBasedIndex) {
  return String(row[oneBasedIndex - 1] || "").trim();
}

function textDecoder(bytes) {
  return new TextDecoder("utf-8").decode(bytes);
}

function parseSharedStrings(xml) {
  if (!xml) return [];
  return [...xml.matchAll(/<si\b[\s\S]*?<\/si>/g)].map((match) => {
    return [...match[0].matchAll(/<t[^>]*>([\s\S]*?)<\/t>/g)]
      .map((part) => decodeXml(part[1]))
      .join("");
  });
}

function parseSheetRows(xml, sharedStrings) {
  const rows = [];
  for (const rowMatch of xml.matchAll(/<row\b[^>]*>([\s\S]*?)<\/row>/g)) {
    const values = [];
    for (const cellMatch of rowMatch[1].matchAll(/<c\b([^>]*)>([\s\S]*?)<\/c>/g)) {
      const attrs = cellMatch[1];
      const body = cellMatch[2];
      const ref = attrs.match(/\br="([A-Z]+)\d+"/)?.[1] || "";
      const column = columnIndex(ref);
      const type = attrs.match(/\bt="([^"]+)"/)?.[1] || "";
      let value = "";
      if (type === "inlineStr") {
        value = [...body.matchAll(/<t[^>]*>([\s\S]*?)<\/t>/g)].map((part) => decodeXml(part[1])).join("");
      } else {
        const raw = body.match(/<v>([\s\S]*?)<\/v>/)?.[1] || "";
        value = type === "s" ? sharedStrings[Number(raw)] || "" : decodeXml(raw);
      }
      values[column] = value;
    }
    rows.push(values);
  }
  return rows;
}

function columnIndex(ref) {
  let value = 0;
  for (const char of ref) value = value * 26 + char.charCodeAt(0) - 64;
  return Math.max(0, value - 1);
}

function decodeXml(value) {
  const doc = new DOMParser().parseFromString(`<x>${value}</x>`, "application/xml");
  return doc.documentElement.textContent || "";
}

function unzip(buffer) {
  const bytes = new Uint8Array(buffer);
  const files = {};
  let offset = 0;
  while (offset < bytes.length - 4) {
    const signature = readUint32(bytes, offset);
    if (signature !== 0x04034b50) {
      offset += 1;
      continue;
    }
    const method = readUint16(bytes, offset + 8);
    const compressedSize = readUint32(bytes, offset + 18);
    const uncompressedSize = readUint32(bytes, offset + 22);
    const nameLength = readUint16(bytes, offset + 26);
    const extraLength = readUint16(bytes, offset + 28);
    const name = new TextDecoder().decode(bytes.slice(offset + 30, offset + 30 + nameLength));
    const dataStart = offset + 30 + nameLength + extraLength;
    const data = bytes.slice(dataStart, dataStart + compressedSize);
    if (method === 0) files[name] = data;
    if (method === 8) files[name] = inflateRaw(data, uncompressedSize);
    offset = dataStart + compressedSize;
  }
  return files;
}

function inflateRaw(data, expectedSize) {
  const state = { data, bitPos: 0 };
  const output = [];
  let finalBlock = false;
  while (!finalBlock) {
    finalBlock = readBits(state, 1) === 1;
    const type = readBits(state, 2);
    if (type === 0) inflateStored(state, output);
    else if (type === 1) inflateHuffman(state, output, fixedLiteralTree(), fixedDistanceTree());
    else if (type === 2) {
      const trees = dynamicTrees(state);
      inflateHuffman(state, output, trees.literalTree, trees.distanceTree);
    } else {
      throw new Error("Unsupported deflate block");
    }
  }
  return new Uint8Array(output.slice(0, expectedSize || output.length));
}

function inflateStored(state, output) {
  state.bitPos = Math.ceil(state.bitPos / 8) * 8;
  const bytePos = state.bitPos >> 3;
  const len = state.data[bytePos] | (state.data[bytePos + 1] << 8);
  state.bitPos += 32;
  for (let i = 0; i < len; i++) output.push(state.data[(state.bitPos >> 3) + i]);
  state.bitPos += len * 8;
}

function inflateHuffman(state, output, literalTree, distanceTree) {
  const lengthBases = [3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35, 43, 51, 59, 67, 83, 99, 115, 131, 163, 195, 227, 258];
  const lengthExtra = [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0];
  const distanceBases = [1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513, 769, 1025, 1537, 2049, 3073, 4097, 6145, 8193, 12289, 16385, 24577];
  const distanceExtra = [0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13];
  while (true) {
    const symbol = decodeSymbol(state, literalTree);
    if (symbol < 256) output.push(symbol);
    else if (symbol === 256) return;
    else {
      const lengthIndex = symbol - 257;
      const length = lengthBases[lengthIndex] + readBits(state, lengthExtra[lengthIndex]);
      const distanceSymbol = decodeSymbol(state, distanceTree);
      const distance = distanceBases[distanceSymbol] + readBits(state, distanceExtra[distanceSymbol]);
      for (let i = 0; i < length; i++) output.push(output[output.length - distance]);
    }
  }
}

function dynamicTrees(state) {
  const hlit = readBits(state, 5) + 257;
  const hdist = readBits(state, 5) + 1;
  const hclen = readBits(state, 4) + 4;
  const order = [16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15];
  const codeLengths = Array(19).fill(0);
  for (let i = 0; i < hclen; i++) codeLengths[order[i]] = readBits(state, 3);
  const codeTree = buildTree(codeLengths);
  const lengths = [];
  while (lengths.length < hlit + hdist) {
    const symbol = decodeSymbol(state, codeTree);
    if (symbol <= 15) lengths.push(symbol);
    else if (symbol === 16) {
      const repeat = readBits(state, 2) + 3;
      lengths.push(...Array(repeat).fill(lengths[lengths.length - 1] || 0));
    } else if (symbol === 17) {
      lengths.push(...Array(readBits(state, 3) + 3).fill(0));
    } else if (symbol === 18) {
      lengths.push(...Array(readBits(state, 7) + 11).fill(0));
    }
  }
  return {
    literalTree: buildTree(lengths.slice(0, hlit)),
    distanceTree: buildTree(lengths.slice(hlit, hlit + hdist)),
  };
}

function fixedLiteralTree() {
  const lengths = [];
  for (let i = 0; i <= 287; i++) lengths[i] = i <= 143 ? 8 : i <= 255 ? 9 : i <= 279 ? 7 : 8;
  return buildTree(lengths);
}

function fixedDistanceTree() {
  return buildTree(Array(32).fill(5));
}

function buildTree(lengths) {
  const root = {};
  const maxBits = Math.max(...lengths);
  let code = 0;
  const blCount = Array(maxBits + 1).fill(0);
  const nextCode = Array(maxBits + 1).fill(0);
  lengths.forEach((length) => { if (length) blCount[length] += 1; });
  for (let bits = 1; bits <= maxBits; bits++) {
    code = (code + blCount[bits - 1]) << 1;
    nextCode[bits] = code;
  }
  lengths.forEach((length, symbol) => {
    if (!length) return;
    const currentCode = nextCode[length]++;
    let node = root;
    for (let i = 0; i < length; i++) {
      const bit = (currentCode >> (length - i - 1)) & 1;
      node[bit] ||= {};
      node = node[bit];
    }
    node.symbol = symbol;
  });
  return root;
}

function decodeSymbol(state, tree) {
  let node = tree;
  while (node.symbol === undefined) {
    node = node[readBits(state, 1)];
    if (!node) throw new Error("Bad huffman code");
  }
  return node.symbol;
}

function readBits(state, count) {
  let value = 0;
  for (let i = 0; i < count; i++) {
    const bit = (state.data[state.bitPos >> 3] >> (state.bitPos & 7)) & 1;
    value |= bit << i;
    state.bitPos += 1;
  }
  return value;
}

function readUint16(bytes, offset) {
  return bytes[offset] | (bytes[offset + 1] << 8);
}

function readUint32(bytes, offset) {
  return (bytes[offset] | (bytes[offset + 1] << 8) | (bytes[offset + 2] << 16) | (bytes[offset + 3] << 24)) >>> 0;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function formatMultiline(value) {
  return escapeHtml(value).replace(/\n/g, "<br>");
}

function answerDetailsHtml(question) {
  const parts = [
    question?.aiAnswer ? `AI判断答案：${question.aiAnswer}` : "",
    question?.originalAnswer ? `参考答案：${question.originalAnswer}` : "",
  ].filter(Boolean);
  return parts.length ? `<br>${formatMultiline(parts.join("\n"))}` : "";
}

function bindEvents() {
  $$(".nav-item").forEach((btn) => btn.addEventListener("click", () => switchView(btn.dataset.view)));
  $("#nextBtn").addEventListener("click", pickQuestion);
  $("#prevBtn").addEventListener("click", previousQuestion);
  $("#submitBtn").addEventListener("click", () => submitAnswer(false));
  $("#revealBtn").addEventListener("click", () => submitAnswer(true));
  $("#starBtn").addEventListener("click", () => toggleStar());
  $("#quickEditAnswerBtn").addEventListener("click", openAnswerDialog);
  $("#answerDialog .dialog-form").addEventListener("submit", saveCurrentAnswer);
  $("#cancelAnswerBtn").addEventListener("click", () => $("#answerDialog").close());
  $("#bankFilter").addEventListener("change", pickQuestion);
  $("#practiceMode").addEventListener("change", pickQuestion);
  $("#searchInput").addEventListener("input", renderLibrary);
  $("#libraryBankFilter").addEventListener("change", renderLibrary);
  $("#deleteBankBtn").addEventListener("click", deleteSelectedBank);
  $("#addQuestionBtn").addEventListener("click", () => openDialog());
  $("#questionDialog .dialog-form").addEventListener("submit", saveQuestionFromDialog);
  $("#cancelQuestionBtn").addEventListener("click", () => $("#questionDialog").close());
  $("#practiceWrongBtn").addEventListener("click", () => {
    switchView("practice");
    $("#practiceMode").value = "wrong";
    pickQuestion();
  });
  $("#clearHistoryBtn").addEventListener("click", () => {
    if (confirm("确定清空做题记录吗？题库不会被删除。")) {
      state.attempts = [];
      saveState();
    }
  });
  $("#parseBtn").addEventListener("click", () => {
    parsedImport = parseImportText($("#importText").value, $("#importBank").value.trim());
    renderImportPreview();
  });
  $("#saveImportBtn").addEventListener("click", () => {
    parsedImport = parsedImport.length ? parsedImport : parseImportText($("#importText").value, $("#importBank").value.trim());
    const { added, updated } = upsertQuestions(parsedImport);
    parsedImport = [];
    $("#importText").value = "";
    renderImportPreview();
    saveState();
    alert(`题目已保存：新增 ${added} 道，覆盖更新 ${updated} 道。`);
  });
  $("#exportBtn").addEventListener("click", exportBackup);
  $("#backupInput").addEventListener("change", (event) => {
    const file = event.target.files?.[0];
    if (file) importBackup(file);
    event.target.value = "";
  });
  $("#excelInput").addEventListener("change", (event) => {
    const file = event.target.files?.[0];
    if (file) importExcel(file);
    event.target.value = "";
  });
}

bindEvents();
renderImportPreview();
pickQuestion();
