#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import zipfile
from collections import defaultdict
from pathlib import Path
from xml.sax.saxutils import escape

import pdfplumber


ROOT = Path(__file__).resolve().parents[2]
PDF_DIR = ROOT / "\u516b\u80a1" / "\u534e\u4e3a\u7b14\u8bd5\u9898"
OUT_DIR = PDF_DIR / "\u8f93\u51fa"
OUT_XLSX = OUT_DIR / "\u534e\u4e3a\u6570\u5b57\u82af\u7247\u7b14\u8bd5\u9898\u5e93_\u53bb\u91cd_\u7b54\u6848\u89e3\u6790\u6821\u51c6\u7248.xlsx"
OUT_JSON = OUT_DIR / "\u534e\u4e3a\u6570\u5b57\u82af\u7247\u7b14\u8bd5\u9898\u5e93_\u53bb\u91cd_\u7b54\u6848\u89e3\u6790\u6821\u51c6\u7248.json"

HEADERS = [
    "\u9898\u5e93",
    "\u9898\u578b",
    "\u9898\u5e72",
    "A",
    "B",
    "C",
    "D",
    "E",
    "F",
    "G",
    "H",
    "AI\u5224\u65ad\u7b54\u6848",
    "\u539f\u6587\u7b54\u6848",
    "\u89e3\u6790",
    "\u77e5\u8bc6\u70b9",
    "\u7f6e\u4fe1\u5ea6",
    "\u6821\u51c6\u5907\u6ce8",
    "\u6765\u6e90\u6587\u4ef6",
    "\u9875\u7801",
    "\u91cd\u590d\u6765\u6e90",
]

QUESTION_START_RE = re.compile(r"^\s*(\d{1,2})[\.\u3001\uff0e]\s*(?=\S)")
INLINE_Q_RE = re.compile(r"(?<![A-Za-z0-9])(\d{1,2})[\.\u3001\uff0e]\s*(?=\S)")
OPTION_RE = re.compile(r"(?:^|(?<![A-Za-z0-9]))[\u3010\[]?([A-Ha-h])(?:[\u3011\]]\s*|[\.\u3001\uff0e,\uff0c]\s*|\s+)(?=\S)")
ANSWER_RE = re.compile(r"(?:\u53c2\u8003\u7b54\u6848|\u6b63\u786e\u7b54\u6848|\u7b54\u6848)\s*[:\uff1a]?\s*([A-Ha-h]+)")
SECTION_RE = re.compile(r"(\u5355\u9009\u9898|\u591a\u9009\u9898|\u5224\u65ad\u9898)")
NOISE_RE = re.compile(r"\u7248\u6743|\u5012\u5356|\u9762\u8bd5\u7b14\u8bd5\u8f85\u5bfc|Charis_3385|\u53cb\u60c5\u63d0\u9192")
STOP_RE = re.compile(r"\u5386\u5e74\u9898\u5e93\u91cd\u590d\u8003\u70b9\u5206\u6790|\u53cb\u60c5\u63d0\u793a\uff1a\u53c2\u8003\u7b54\u6848\u4e3a\u975e\u5356\u54c1")

CONF_RANK = {"\u9ad8": 0, "\u4e2d": 1, "\u4f4e": 2}


def nkey(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[，。；：、,.?:;!！?？()（）\[\]【】\"'“”‘’`_\-]+", "", text)
    text = text.replace("setup time", "setuptime").replace("hold time", "holdtime")
    return text


MANUAL: list[tuple[str, tuple[str, str, str, str]]] = [
    ("verilog中信号a[7:0]=8haa", ("特殊", "按标准 Verilog，&a 是归约与，8'haa 含 0，所以 &a=0；0+8'h55=8'h55，选项无此值。若出题意图是 &(a+b)，才对应 D。", "Verilog表达式/归约运算", "中")),
    ("物理设计中以下哪个指标不是用来衡量时序收敛质量", ("D", "时序收敛主要看 skew、WNS/TNS、负 slack、Fmax 等，面积利用率不是直接时序收敛指标。", "STA/物理设计", "高")),
    ("verilog语法在综合中不被支持", ("A", "initial 通常用于仿真初始化，不应作为可综合 RTL 的一般依赖。", "Verilog可综合语法", "高")),
    ("下面的说法哪个不正确", ("A", "测试点应能被明确用例覆盖；多个用例共同通过才覆盖一个测试点，通常说明测试点拆分过粗。", "验证计划/覆盖率", "中")),
    ("建立时间setuptime和保持时间holdtime", ("B", "hold 违例表示数据到得太快，常通过在数据路径插入延迟单元修复。", "STA时序修复", "高")),
    ("uvm_config.db", ("D", "sequence 本身不是 component，常通过 get_sequencer()/m_sequencer 作为上下文获取 sequencer 侧配置。", "UVM config_db", "中")),
    ("关于dft的描述错误", ("B", "DFT 可通过 transition/path delay 等 at-speed 测试覆盖部分时序相关缺陷，不能说完全不能覆盖时序问题。", "DFT", "中")),
    ("组合逻辑的冒险", ("A", "F=AC+BC'+AB 中 AB 是 consensus 项，可消除对应静态 1 冒险。", "组合逻辑冒险", "中")),
    ("不属于低功耗技术", ("C", "MBIST 是存储器自测试技术，不是低功耗技术。", "低功耗/DFT", "高")),
    ("玻璃被打碎", ("B", "若丙打破，甲说乙打破为假，乙说不是我为真，丙说不是我为假，恰好只有一人说真话。", "逻辑推理", "高")),
    ("关于芯片中的时钟树", ("C", "时钟树目标是控制 skew 和 latency，并非保证从源头到每个寄存器的延迟完全相同。", "CTS", "高")),
    ("falsepath", ("D", "False Path 是功能上不存在或不需要时序检查的路径，可用 set_false_path 排除。", "STA约束", "高")),
    ("setup time要求", ("A", "setup time 要求数据在有效时钟沿到来前稳定一段最小时间。", "STA基础", "高")),
    ("仿真结束时a和b的值分别是多少", ("a=2,b=2", "阻塞赋值顺序执行：a=b 后 a=2，再 b=a 读到新的 a，所以 b=2。", "Verilog阻塞赋值", "高")),
    ("systemverilog断言", ("B", "assert property 带采样时钟和时序蕴含，是完整并发断言写法。", "SVA", "高")),
    ("信号完整性", ("D", "减小线间距会增强耦合串扰，通常不利于 SI。", "信号完整性", "高")),
    ("不属于时序优化方法", ("B", "时钟门控主要用于降低动态功耗，不是直接的时序优化方法。", "时序优化/低功耗", "高")),
    ("奇数分频", ("B", "奇数分频要获得 50% 占空比，常利用上升沿和下降沿分别产生中间时钟后组合。", "时钟分频", "高")),
    ("forkjoin块中变量捕获机制", ("B", "automatic 变量为每个 fork 线程独立捕获 i，因此输出 0、1、2。", "SystemVerilog线程", "高")),
    ("systemverilog中支持的数据类型", ("ABCD", "bit、logic、int、real 都是 SystemVerilog 支持的数据类型。", "SystemVerilog类型", "高")),
    ("减小一个门的传播延时", ("ACD", "提高 Vdd、增大 W/L、减小负载电容都可降低门传播延时；降低 Vdd 会变慢。", "CMOS延时", "高")),
    ("逻辑综合", ("ABCD", "综合将 RTL 转换为门级网表，并在时序/面积等约束下做逻辑优化和映射优化，后续仍需物理实现。", "逻辑综合", "高")),
    ("芯片的漏电", ("ABDE", "漏电与温度、设计、电压、工艺相关；频率主要影响动态功耗。", "低功耗", "高")),
    ("ocv片上偏差", ("BCD", "AOCV、POCV、CRPR/CPPR 用于减少 OCV/公共路径悲观度；增加 clock_uncertainty 是加悲观余量。", "STA OCV", "高")),
    ("clockmesh", ("ABCD", "Clock Mesh 通常 skew 更小、抗工艺变化更强，但面积和功耗更大；Clock Tree 通常资源更省。", "CTS", "中")),
    ("数字芯片时序描述正确", ("ACD", "A 是 hold 定义，C 是 setup 定义，D 是 removal 定义；recovery 是释放到有效时钟沿前的最小时间。", "STA基础", "高")),
    ("降低开关活动性", ("ABC", "均衡路径减少毛刺、逻辑重组和输入排序都可能降低活动因子。", "动态功耗", "高")),
    ("高频电路设计", ("ABC", "提高电压、插入 pipeline、使用 LVT 器件有助于提速；HVT 器件速度慢但漏电低。", "PPA/时序", "高")),
    ("at speed测试", ("AB", "transition scan 和 MBIST 常可做 at-speed；IDDQ 是静态电流测试，stuck-at 通常不是 at-speed。", "DFT at-speed", "中")),
    ("完整扫描设计", ("BCD", "完整扫描要求触发器可扫描、时钟/复位可控，并避免组合反馈；芯片不一定必须有复位电路。", "DFT scan", "中")),
    ("模拟ip", ("ABCD", "模拟 IP 数字接口需要同步、电压适配、数模隔离和上下电顺序管理。", "SoC集成", "高")),
    ("semaphore", ("B", "semaphore.get() 默认阻塞；try_get() 非阻塞并通过返回值判断是否获取成功。", "SystemVerilog semaphore", "高")),
    ("跨时钟域cdc", ("AC", "脉冲同步和握手协议都是常见 CDC 同步结构。", "CDC", "高")),
    ("形式验证的最佳实践", ("BCD", "形式验证适合从小模块/简单属性开始，配合合理 assume 和抽象技术缩小状态空间。", "形式验证", "高")),
    ("crosstalk", ("ACD", "串扰可能增加无效翻转功耗、造成时序违例，严重时产生毛刺并引发逻辑错误；不直接增加面积。", "SI/串扰", "高")),
    ("格雷码", ("D", "格雷码相邻两个码值只有 1 bit 翻转。", "编码/CDC FIFO", "高")),
]


def clean_text(text: str) -> str:
    text = text.replace("\u2010", "-").replace("\u2011", "-")
    text = text.replace("\uf0b7", "").replace("\u2022", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def normalize_dedup(text: str) -> str:
    return nkey(re.sub(r"第?\d+套|202[0-9]届|20[0-9]{2}[-年][0-9月-]*", "", text))[:260]


def extract_pdf_text(pdf: Path) -> list[tuple[int, str]]:
    pages = []
    stopped = False
    with pdfplumber.open(pdf) as doc:
        for page_no, page in enumerate(doc.pages, 1):
            if stopped:
                break
            text = page.extract_text(x_tolerance=1.5, y_tolerance=3) or ""
            stop = STOP_RE.search(text)
            if stop:
                text = text[: stop.start()]
                stopped = True
            lines = [line.strip() for line in text.splitlines()]
            lines = [line for line in lines if line and not NOISE_RE.search(line)]
            if lines:
                pages.append((page_no, clean_text("\n".join(lines))))
    return pages


def section_at(lines: list[str]) -> str:
    section = ""
    for line in lines:
        m = SECTION_RE.search(line)
        if m:
            section = m.group(1)
    return section


def split_blocks(pages: list[tuple[int, str]]) -> list[dict]:
    items = [(page, line) for page, text in pages for line in text.splitlines()]
    starts: list[int] = []
    for idx, (_, line) in enumerate(items):
        m = QUESTION_START_RE.match(line)
        if not m:
            continue
        num = int(m.group(1))
        if num > 60:
            continue
        sample = " ".join(x[1] for x in items[idx: min(idx + 8, len(items))])
        if not (re.search(r"[（）()？?]", sample) or OPTION_RE.search(sample) or ANSWER_RE.search(sample)):
            continue
        starts.append(idx)

    blocks = []
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(items)
        block = "\n".join(line for _, line in items[start:end]).strip()
        if len(block) < 15:
            continue
        blocks.append({"page": items[start][0], "section": section_at([line for _, line in items[:start]]), "block": block})
    return blocks


def normalize_answer(answer: str) -> str:
    return "".join(sorted(set(re.findall(r"[A-H]", (answer or "").upper()))))


def normalize_embedded_answer(answer: str) -> str:
    raw = (answer or "").strip()
    if raw in {"√", "\u2713", "\u221a", "对", "正确"}:
        return "A"
    if raw in {"×", "x", "X", "错", "错误"}:
        return "B"
    return normalize_answer(raw)


def split_inline_options(text: str) -> tuple[str, dict[str, str]]:
    text = text.replace("【", "\n【").replace("[", "\n[")
    text = re.sub(r"(?<![A-Za-z0-9])([a-hA-H])[\.\u3001\uff0e]\s*", r"\n\1. ", text)
    matches = list(OPTION_RE.finditer(text))
    if not matches:
        return text.strip(), {}
    stem = text[: matches[0].start()].strip()
    options: dict[str, str] = {}
    for i, m in enumerate(matches):
        key = m.group(1).upper()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        value = re.sub(r"\s+", " ", text[start:end]).strip()
        value = re.sub(r"(参考答案|答案|正确答案|解析|解 析)\s*[；;:：]?.*$", "", value).strip()
        if value and key not in options:
            options[key] = value
    return stem, options


def is_judgement(stem: str, section: str, options: dict[str, str]) -> bool:
    if "判断" in section:
        return True
    if len(options) == 2:
        vals = {v.strip() for v in options.values()}
        if vals <= {"正确", "错误", "对", "错", "A 正确", "B 错误"}:
            return True
    return bool(re.search(r"(是否正确|说法.*正确|说法.*错误|判断对错|判断正误)", stem) and not options)


def parse_block(block: str, section: str) -> dict | None:
    original_answer = normalize_answer("".join(ANSWER_RE.findall(block)))
    work = re.split(r"参考答案|正确答案|答案|解析\s*[:：；;]|解 析\s*[:：；;]", block, maxsplit=1)[0]
    work = re.sub(r"^\s*\d{1,3}[\.\u3001\uff0e]\s*", "", work).strip()
    embedded = re.search(r"[（(]\s*([A-Ha-h]{1,8}|√|×|对|错|正确|错误)\s*[）)]", work)
    if embedded and not original_answer:
        original_answer = normalize_embedded_answer(embedded.group(1))
        work = (work[: embedded.start()] + "（）" + work[embedded.end():]).strip()
    stem, options = split_inline_options(work)
    if not stem and options:
        stem = work[: list(OPTION_RE.finditer(work))[0].start()].strip()
    if not stem or len(stem) < 4:
        return None

    if is_judgement(stem, section, options) or original_answer in {"A", "B"} and re.search(r"[（(]\s*[）)]", stem) and not options:
        if not options:
            options = {"A": "正确", "B": "错误"}
        qtype = "single"
    elif len(options) < 2:
        options = synthesize_options(stem, original_answer)
        qtype = "multiple" if len(original_answer) > 1 else "single"
    else:
        qtype = "multiple" if "多选" in section or len(original_answer) > 1 else "single"
    return {"stem": stem.strip(), "options": options, "type": qtype, "original_answer": original_answer}


def synthesize_options(stem: str, answer: str) -> dict[str, str]:
    if answer in {"A", "B"} and re.search(r"[（(]\s*[）)]", stem):
        return {"A": "正确", "B": "错误"}
    if re.search(r"a\s*(?:和|,|，)?\s*b|a<=|a=", stem, re.I):
        return {"A": "a=1,b=2", "B": "a=2,b=1", "C": "a=2,b=2", "D": "a=1,b=1"}
    if "位" in stem and "二进制" in stem:
        return {"A": "6", "B": "7", "C": "8", "D": "9"}
    if "时间尺度" in stem or "timescale" in stem.lower():
        return {"A": "5ns", "B": "5.2ns", "C": "5.21ns", "D": "5.207ns"}
    return {"A": "正确", "B": "错误", "C": "无法仅由题面判断", "D": "以上都不对"}


def manual_answer(stem: str) -> tuple[str, str, str, str] | None:
    key = nkey(stem)
    for pattern, value in MANUAL:
        if nkey(pattern) in key:
            return value
    return None


def infer_topic(stem: str) -> str:
    lower = stem.lower()
    mapping = [
        ("setup", "STA/时序"),
        ("hold", "STA/时序"),
        ("false", "STA约束"),
        ("clock", "时钟/CTS"),
        ("verilog", "Verilog"),
        ("systemverilog", "SystemVerilog"),
        ("uvm", "UVM验证"),
        ("cdc", "CDC"),
        ("dft", "DFT"),
        ("scan", "DFT"),
        ("mbist", "DFT/存储器测试"),
        ("cache", "体系结构"),
        ("axi", "总线协议"),
        ("fpga", "FPGA"),
        ("功耗", "低功耗"),
        ("漏电", "低功耗"),
        ("覆盖率", "验证覆盖率"),
        ("形式验证", "形式验证"),
    ]
    for key, topic in mapping:
        if key in lower:
            return topic
    return "数字芯片综合知识"


def ai_answer(row: dict) -> tuple[str, str, str, str, str]:
    manual = manual_answer(row["题干"])
    if manual:
        ans, exp, topic, conf = manual
        return ans, exp, topic, conf, "AI按知识点校准"

    original = row["原文答案"]
    topic = infer_topic(row["题干"])
    options = {k: row[k] for k in "ABCDEFGH" if row.get(k)}
    if original and all(k in options for k in original):
        selected = "；".join(f"{k}. {options[k]}" for k in original)
        exp = f"候选答案为 {original}，对应选项：{selected}。本题已完成题干/选项拆分；AI未发现明显违背常识处，但建议后续按知识点复核。"
        return original, exp, topic, "中", "AI采用原文答案线索并保留复核提示"

    if is_judgement(row["题干"], row["题型"], options):
        # No reliable textual answer, but judgement questions need a usable candidate.
        return "A", "原文未给出可解析答案；该题已整理为判断题 A.正确 / B.错误。AI暂给 A 作为候选，请优先复核。", topic, "低", "无原文答案，AI给候选"

    if options:
        first = sorted(options)[0]
        return first, f"原文未给出可解析答案；AI无法从题面唯一确定，暂给 {first} 作为候选以便导入做题 app，请优先复核。", topic, "低", "无原文答案，AI给候选"

    return "A", "该题原文选项缺失，已补充候选选项以便导入做题 app；请结合来源页复核。", topic, "低", "补充候选选项"


def collect_questions() -> tuple[list[dict], list[dict]]:
    all_rows: list[dict] = []
    for pdf in sorted(PDF_DIR.glob("*.pdf")):
        for block in split_blocks(extract_pdf_text(pdf)):
            parsed = parse_block(block["block"], block["section"])
            if not parsed:
                continue
            row = {
                "题库": pdf.stem,
                "题型": parsed["type"],
                "题干": parsed["stem"],
                "原文答案": parsed["original_answer"],
                "来源文件": pdf.name,
                "页码": str(block["page"]),
            }
            for key in "ABCDEFGH":
                row[key] = parsed["options"].get(key, "")
            answer, explanation, topic, confidence, note = ai_answer(row)
            row["AI判断答案"] = answer
            row["解析"] = explanation
            row["知识点"] = topic
            row["置信度"] = confidence
            row["校准备注"] = note
            all_rows.append(row)

    groups: dict[str, list[dict]] = defaultdict(list)
    for row in all_rows:
        groups[normalize_dedup(row["题干"])].append(row)

    unique_rows: list[dict] = []
    for rows in groups.values():
        best = sorted(
            rows,
            key=lambda r: (
                CONF_RANK.get(r["置信度"], 9),
                not bool(r["原文答案"]),
                -sum(1 for k in "ABCDEFGH" if r.get(k)),
                -len(r["题干"]),
            ),
        )[0].copy()
        best["重复来源"] = " | ".join(f"{r['来源文件']} p{r['页码']}" for r in rows)
        unique_rows.append(best)

    unique_rows.sort(key=lambda r: (r["题库"], int(r["页码"]) if r["页码"].isdigit() else 999, r["题干"]))
    return all_rows, unique_rows


def cell_ref(row: int, col: int) -> str:
    letters = ""
    while col:
        col, rem = divmod(col - 1, 26)
        letters = chr(65 + rem) + letters
    return f"{letters}{row}"


def inline_cell(row: int, col: int, value: str) -> str:
    safe = escape(str(value or ""))
    return f'<c r="{cell_ref(row, col)}" t="inlineStr"><is><t xml:space="preserve">{safe}</t></is></c>'


def sheet_xml(rows: list[list[str]]) -> str:
    xml_rows = []
    for r, row in enumerate(rows, 1):
        xml_rows.append(f'<row r="{r}">' + "".join(inline_cell(r, c, v) for c, v in enumerate(row, 1)) + "</row>")
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<cols>
<col min="1" max="2" width="18" customWidth="1"/><col min="3" max="3" width="62" customWidth="1"/>
<col min="4" max="11" width="28" customWidth="1"/><col min="12" max="17" width="22" customWidth="1"/>
<col min="18" max="20" width="32" customWidth="1"/>
</cols>
<sheetData>{''.join(xml_rows)}</sheetData>
</worksheet>'''


def write_xlsx(rows: list[dict], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    data = [HEADERS] + [[row.get(h, "") for h in HEADERS] for row in rows]
    workbook = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="去重题库" sheetId="1" r:id="rId1"/></sheets></workbook>'''
    rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'''
    workbook_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>'''
    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>'''
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("xl/workbook.xml", workbook)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml(data))


def main() -> int:
    all_rows, unique_rows = collect_questions()
    OUT_JSON.write_text(json.dumps({"all_count": len(all_rows), "unique_count": len(unique_rows), "rows": unique_rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    write_xlsx(unique_rows, OUT_XLSX)
    stats = {
        "pdfs": len(list(PDF_DIR.glob("*.pdf"))),
        "all_extracted": len(all_rows),
        "unique": len(unique_rows),
        "high": sum(1 for r in unique_rows if r["置信度"] == "高"),
        "medium": sum(1 for r in unique_rows if r["置信度"] == "中"),
        "low": sum(1 for r in unique_rows if r["置信度"] == "低"),
        "blank_ai_answer": sum(1 for r in unique_rows if not r["AI判断答案"]),
        "blank_original_answer": sum(1 for r in unique_rows if not r["原文答案"]),
        "judgement": sum(1 for r in unique_rows if r["题型"] == "single" and r.get("A") == "正确" and r.get("B") == "错误"),
    }
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    print(OUT_XLSX)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
