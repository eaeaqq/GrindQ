#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import sys

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pdf_to_excel as parser


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "八股" / "华为笔试题" / "输出" / "2027届华为实习数字芯片20260415_考卷版_无答案.pdf"
OUTPUT = ROOT / "八股" / "华为笔试题" / "输出" / "2027届华为实习数字芯片20260415_答案解析拓展版.pdf"


ANSWERS = {
    1: ("特殊", "按标准 Verilog 运算符优先级，&a 是归约与，8'haa 中有 0，所以 &a=1'b0；再与 8'h55 相加，结果应为 8'h55，题目选项中没有该值。若出题人想考 &(a+b)，则 a+b=8'hff，归约与为 1，对应 D。", "遇到 reduction operator 和算术运算混写时，先查优先级并主动加括号。笔试里这种题常考无符号扩展、截断和表达式位宽。"),
    2: ("D", "时序收敛主要看 skew、WNS/TNS/负 slack、Fmax 等。面积利用率影响布线拥塞和时序，但不是直接衡量时序收敛质量的核心指标。", "后端常见收敛指标：WNS 看最差路径，TNS 看总违例规模，NVP 看违例路径数。"),
    3: ("A", "initial 主要用于仿真初始化和 testbench，通常不作为可综合 RTL 依赖。logic、tri、generate-for 在合适条件下可综合或可用于综合代码。", "不可综合常见项：#delay、initial、fork/join、wait、$display、$finish、动态无限循环。"),
    4: ("A", "测试点通常应被明确的用例覆盖；若一个测试点必须靠多个用例共同通过才算覆盖，往往说明测试点拆分过粗或可观测性定义不清。", "验证计划中常见闭环：feature -> testpoint -> testcase -> coverage -> regression。"),
    5: ("B", "hold 违例表示数据到得太快，常通过数据路径插 delay/buffer 修复。setup 违例表示数据太慢，通常降频、优化组合逻辑、换快单元、流水线等。", "口诀：setup 修慢路径，hold 修快路径；setup 可借周期，hold 与频率关系弱。"),
    6: ("D", "sequence 本身不是 component，常通过 get_sequencer()/m_sequencer 作为 config_db 查询上下文来获取 sequencer 侧配置。", "UVM 配置传递要注意 context 和 instance path；sequence 里随手用 this 经常取不到 component 层级配置。"),
    7: ("B", "DFT 不只覆盖 stuck-at，也可通过 transition/path delay 等 at-speed 测试覆盖部分时序相关缺陷，所以“不能覆盖时序问题”过于绝对。", "DFT 关注制造缺陷可测性；STA 关注设计时序正确性，二者互补。"),
    8: ("A", "F=AC+BC'+AB 中 AB 是 AC 与 BC' 关于 C 的 consensus 项，可消除对应静态 1 冒险。", "组合冒险来自不同路径延迟不一致。同步电路中毛刺若不被采样通常无害，但会增加动态功耗。"),
    9: ("C", "MBIST 是存储器自测试技术，不是低功耗技术。Multi-Vdd、clock gating、power gating 都常用于降功耗。", "低功耗分动态功耗和静态功耗：clock gating 降翻转，power gating 降漏电。"),
    10: ("B", "若丙打破：甲说“乙打破”为假，乙说“不是我”为真，丙说“不是我”为假，恰好只有一真。", "逻辑题可枚举嫌疑人，逐项统计真话数。"),
    11: ("C", "时钟树目标是控制 skew 和 latency，并非要求所有寄存器输入延迟完全相同。实际设计会在功耗、拥塞、OCV 和 skew 之间折中。", "Clock Mesh skew 小但功耗/布线资源大；H-tree 适合规则阵列。"),
    12: ("D", "False path 是实际功能上不存在或不需要进行时序检查的路径，可用 set_false_path 等约束排除。", "False path 不等于 CDC 安全；跨时钟路径通常还需要同步器、FIFO 或握手。"),
    13: ("A", "setup time 要求数据在有效时钟沿到来前稳定一段最小时间。", "hold time 是有效时钟沿之后继续保持稳定的最小时间。"),
    14: ("a=2, b=2", "若代码中 a=b; b=a; 为阻塞赋值，则顺序执行：先 a 变成 2，再 b 读取新的 a，也变成 2。原无答案卷未给选项。", "若改成非阻塞赋值 a<=b; b<=a;，同一时间步末尾更新，结果会交换为 a=2、b=1。"),
    15: ("B", "assert property (@(posedge ck) a |=> b) 是完整并带采样时钟的并发断言写法。", "|=> 表示 overlapped? 不，|=> 是下一拍蕴含；|-> 是同拍/重叠蕴含。"),
    16: ("D", "减小信号线间距会增强耦合串扰，通常不利于信号完整性。", "SI 常关注反射、串扰、过冲/下冲、眼图、阻抗连续性和返回路径。"),
    17: ("B", "时钟门控主要是低功耗技术，不是直接的时序优化方法。逻辑复制、流水线、retiming 都可改善时序。", "高扇出网络可通过复制、buffer tree、物理约束共同优化。"),
    18: ("B", "奇数分频要做 50% 占空比，常分别利用上升沿/下降沿产生中间信号，再组合得到接近严格 50% 占空比的输出。", "只用单沿计数翻转，奇数分频天然会出现高低电平周期数不等。"),
    19: ("B", "automatic int idx=i 为每个 fork 线程创建独立自动变量，三个线程分别捕获 0、1、2。", "若没有 automatic 捕获，循环变量延迟执行时可能都看到最终值，这是 SV fork/join_none 常见坑。"),
    20: ("A", "芯片管脚输出中断通常更推荐电平信号或可保持/可清除机制，短脉冲可能被对端漏采。", "中断设计关注可屏蔽、可查询、可清除，以及边沿/电平触发语义。"),
    21: ("ABCD", "bit、logic、int、real 都是 SystemVerilog 支持的数据类型。", "bit/int 是 2 态类型；logic 是 4 态类型；real 用于实数建模，通常不可综合。"),
    22: ("ACD", "提高 Vdd、增大 W/L 提升驱动能力、减小负载电容都可降低门延时；降低 Vdd 会变慢。", "门延时近似与负载电容、驱动电阻、电源电压裕量相关。"),
    23: ("ABCD", "综合将 RTL 转为门级网表，包含逻辑优化/映射优化，受时序/面积等约束驱动；流片前还需后端布局布线和时序修复。", "综合后的 netlist 不是最终版图，还要 CTS、route、STA、物理验证等。"),
    24: ("ABDE", "漏电与温度、设计规模/结构、电压、工艺和 Vt 强相关；频率主要影响动态功耗，不直接决定静态漏电。", "静态功耗约为 I_leak * Vdd；温度升高通常会显著增加漏电。"),
    25: ("ABC", "clone 返回新复制对象的 uvm_object 句柄；copy 用于已有对象拷贝，component 通常不做 copy；p3 可不预先 new，$cast 后接收 clone 返回句柄。p2.copy(p1) 的 p2 必须已有对象。", "clone = create + copy；copy = 把右侧对象内容拷到当前对象。"),
    26: ("BCD", "AOCV、POCV、CRPR/CPPR 都用于减少 OCV/公共路径带来的悲观度；增加 clock uncertainty 是加悲观余量。", "OCV 建模越精细，越能减少无谓 pessimism，但 signoff 成本也更高。"),
    27: ("ABCD", "Clock Mesh 通常 skew 更小、抗工艺变化更强，但面积/功耗更大；Tree 通常资源更省、插入延迟也更容易控制。", "Mesh 适合高性能核心或大规模同步阵列，普通模块多用 CTS tree。"),
    28: ("ACD", "A 是 hold 定义，C 是 setup 定义，D 是 removal 定义。B 错在 recovery 是异步控制释放到有效时钟沿前需满足的最小时间，不是最大时间。", "异步复位检查常成对出现：recovery 类似 setup，removal 类似 hold。"),
    29: ("ABC", "均衡路径减少毛刺、逻辑重组和输入排序都可能降低开关活动性，从而降低动态功耗。", "动态功耗 P=alpha*C*V^2*f，alpha 就是活动因子。"),
    30: ("ABC", "抬高电压、加 pipeline、用 LVT 器件都有助于提高速度；HVT 器件漏电小但速度慢。", "高频优化往往以功耗和面积为代价，需要在 PPA 中折中。"),
    31: ("AB", "transition 测试属于典型 at-speed scan 测试；MBIST 也常以目标频率测试存储器读写时序。IDDQ 是静态电流测试，stuck-at 通常不是 at-speed。", "At-speed 重点捕获延迟类缺陷，如 transition fault、path delay fault。"),
    32: ("BCD", "完整扫描要求触发器可扫描、时钟/复位可控，并避免组合反馈环破坏可测性。芯片不一定必须有复位电路。", "Scan DRC 常检查 controllability、observability、clock/reset rule。"),
    33: ("ABCD", "模拟 IP 数字接口需要做 CDC/同步、电压域适配、数模隔离以及上下电时序管理。", "PLL lock、ADC valid、power good 这类信号都要按异步/跨域信号处理。"),
    34: ("B", "semaphore.get() 默认阻塞；try_get() 非阻塞并通过返回值判断是否获取成功。put() 释放资源，会唤醒等待进程但不是无条件唤醒所有线程。", "Semaphore 常用于 testbench 资源仲裁；mailbox 用于线程间消息传递。"),
    35: ("AC", "脉冲同步和握手协议都是常见 CDC 同步结构。Mutex 和异步 RAM 本身不是通用 CDC 同步方案。", "单 bit 慢到快可用两级同步；脉冲、bus、多 bit 数据需用脉冲同步、握手或异步 FIFO。"),
    37: ("BCD", "形式验证适合从小模块/简单属性开始，配合合理 assume 和抽象技术缩小状态空间；一次性验证复杂整芯片通常不可取。", "形式验证三件事：assert 写对，assume 约束不过强，cover 帮助确认场景可达。"),
    38: ("BD", "A 把 setup 写成了 hold；B 对同步/异步逻辑关系描述正确；C 中 FPGA 资源表述不严谨；D 对 Moore 状态机在同步设计中的输出/状态关系描述基本正确。", "Moore 输出只依赖 state，Mealy 输出依赖 state 和 input。"),
    39: ("ACD", "串扰可能增加无效翻转功耗，也可能造成延迟变化导致时序违例，严重时形成毛刺并引发逻辑错误；不会直接导致面积增加。", "串扰分 noise bump 和 delay effect，STA-SI 会分析 aggressor/victim 的耦合影响。"),
    40: ("D", "格雷码相邻两个码值只有 1 bit 翻转。A 若指标准二进制到格雷码转换则通常唯一；B、C 明显不正确。", "标准转换：gray = binary ^ (binary >> 1)。跨时钟 FIFO 指针常用格雷码降低多 bit 同时翻转风险。"),
}


def font_name() -> str:
    candidates = [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simsun.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
    ]
    for path in candidates:
        if path.exists():
            pdfmetrics.registerFont(TTFont("CN", str(path)))
            return "CN"
    return "Helvetica"


def esc(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )


def parse_questions():
    pages = parser.extract_pages(SOURCE)
    blocks = parser.split_question_blocks(pages)
    questions = []
    for page, section, block in blocks:
        match = re.match(r"\s*(\d+)", block)
        if not match:
            continue
        number = int(match.group(1))
        parsed = parser.parse_block(block, "华为数字芯片2027实习", SOURCE.name, page, section)
        stem = parsed["题干"] if parsed else re.sub(r"^\s*\d+[\.\、．]\s*", "", block).strip()
        options = []
        if parsed:
            for key in "ABCDEFGH":
                if parsed.get(key):
                    options.append((key, parsed[key]))
        questions.append(
            {
                "number": number,
                "section": section,
                "stem": stem,
                "options": options,
                "page": page,
            }
        )
    return questions


def on_page(canvas, doc):
    canvas.saveState()
    canvas.setFont("CN", 9)
    canvas.setFillColor(colors.HexColor("#667085"))
    canvas.drawString(18 * mm, 12 * mm, "2027届华为实习数字芯片 - 答案解析拓展版")
    canvas.drawRightString(192 * mm, 12 * mm, f"第 {doc.page} 页")
    canvas.restoreState()


def build():
    fn = font_name()
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="TitleCN",
            fontName=fn,
            fontSize=22,
            leading=30,
            textColor=colors.HexColor("#111827"),
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SubCN",
            fontName=fn,
            fontSize=10.5,
            leading=16,
            textColor=colors.HexColor("#475467"),
            spaceAfter=14,
        )
    )
    styles.add(
        ParagraphStyle(
            name="QTitle",
            fontName=fn,
            fontSize=12.5,
            leading=18,
            textColor=colors.HexColor("#0b4b40"),
            spaceBefore=8,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyCN",
            fontName=fn,
            fontSize=9.5,
            leading=15,
            textColor=colors.HexColor("#1f2937"),
            spaceAfter=5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SmallCN",
            fontName=fn,
            fontSize=8.5,
            leading=13,
            textColor=colors.HexColor("#475467"),
        )
    )

    doc = BaseDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
        title="2027届华为实习数字芯片答案解析拓展版",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=on_page)])

    story = [
        Paragraph("2027届华为实习数字芯片答案解析拓展版", styles["TitleCN"]),
        Paragraph(
            "说明：本资料基于输出目录中的无答案考卷整理。原卷缺少第36题，第14题未给选项；第1题按标准 Verilog 语义计算结果不在选项中，已在解析中标注。答案为复习参考，建议结合课程/工具手册核对有争议题。",
            styles["SubCN"],
        ),
    ]

    questions = parse_questions()
    numbers = {q["number"] for q in questions}
    if 36 not in numbers:
        story.append(Paragraph("原卷异常：题号 36 缺失，答案版保留该提示。", styles["BodyCN"]))
        story.append(Spacer(1, 4))

    for question in questions:
        number = question["number"]
        answer, explanation, extension = ANSWERS.get(number, ("待核对", "暂无解析。", "建议回到原题确认题面和选项。"))
        story.append(Paragraph(f"{number}. 答案：{esc(answer)}", styles["QTitle"]))
        story.append(Paragraph(f"<b>题干：</b>{esc(question['stem'])}", styles["BodyCN"]))
        if question["options"]:
            option_text = "；".join(f"{key}. {text}" for key, text in question["options"])
            story.append(Paragraph(f"<b>选项：</b>{esc(option_text)}", styles["SmallCN"]))
        else:
            story.append(Paragraph("<b>选项：</b>原卷未抽取到选项，按简答/代码题整理。", styles["SmallCN"]))

        rows = [
            [Paragraph("<b>简析</b>", styles["SmallCN"]), Paragraph(esc(explanation), styles["SmallCN"])],
            [Paragraph("<b>举一反三</b>", styles["SmallCN"]), Paragraph(esc(extension), styles["SmallCN"])],
        ]
        table = Table(rows, colWidths=[23 * mm, 152 * mm], hAlign="LEFT")
        table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "CN"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef8f5")),
                    ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#0b4b40")),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d8dee7")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(table)
        story.append(Spacer(1, 7))

    doc.build(story)
    print(OUTPUT)


if __name__ == "__main__":
    build()
