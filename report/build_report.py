"""
Builds the RailSaathi AI project report in the Karunya "Project-Based
Evaluation Report" format (report/template/karunya_template.docx supplies
the logo, watermark, header/footer and evaluation-sheet table).

Layout target: 10 pages - cover, title + abstract, contents, chapters 1-5,
references and the evaluation sheet. Body: Times New Roman 12 pt, 1.5 line
spacing, justified; numbered figure/table captions; IEEE references.
"""
import copy
import json
from pathlib import Path

import pandas as pd
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
FIG, RES = ROOT / "figures", ROOT / "results"
TEMPLATE = ROOT / "report" / "template" / "karunya_template.docx"
OUT = ROOT / "report" / "RailSaathi_AI_Report.docx"

NAME = "ASWIN SAMUEL.A"
REGNO = "URK24CS9014"
TITLE = "RAILSAATHI AI"
SUBTITLE = "AI-Powered Complaint Management for Rail Madad (SIH1711)"
GITHUB = "https://github.com/aswinsamuel-codes/RailSaathi-AI"

R = lambda n: pd.read_csv(RES / n, index_col=0)  # noqa: E731
J = lambda n: json.loads((RES / f"{n}.json").read_text())  # noqa: E731
pct = lambda v, d=1: f"{100 * float(v):.{d}f}%"  # noqa: E731


def font(run, size=12, bold=False, italic=False, name="Times New Roman"):
    run.font.name = name
    rpr = run._element.get_or_add_rPr()
    rpr.get_or_add_rFonts().set(qn("w:eastAsia"), name)
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = RGBColor(0, 0, 0)
    return run


def field(paragraph, instr, placeholder=""):
    run = paragraph.add_run()
    for kind, text in (("begin", None), ("instr", instr), ("separate", None), ("text", placeholder), ("end", None)):
        if kind == "instr":
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = text
        elif kind == "text":
            el = OxmlElement("w:t")
            el.text = text
        else:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), kind)
        run._r.append(el)
    return run


class Report:
    def __init__(self):
        self.doc = Document(TEMPLATE)
        body = self.doc.element.body
        kids = list(body.iterchildren())
        self.logo = copy.deepcopy(kids[0])
        self.eval_table = copy.deepcopy(kids[1])
        body.remove(kids[0])
        body.remove(kids[1])
        self.fig_no = self.tab_no = 0
        self._styles()

    def _styles(self):
        for name, size in (("Heading 1", 15), ("Heading 2", 12)):
            st = self.doc.styles[name]
            st.font.name = "Times New Roman"
            rf = st.element.get_or_add_rPr().get_or_add_rFonts()
            for a in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
                rf.set(qn(a), "Times New Roman")
            st.font.size = Pt(size)
            st.font.bold = True
            st.font.italic = False
            st.font.color.rgb = RGBColor(0, 0, 0)
            pf = st.paragraph_format
            pf.alignment = WD_ALIGN_PARAGRAPH.CENTER
            pf.space_before = Pt(10 if name == "Heading 1" else 6)
            pf.space_after = Pt(4)
            pf.line_spacing = 1.15
            pf.keep_with_next = True
        for name in ("TOC 1", "TOC 2"):
            try:
                st = self.doc.styles[name]
                st.font.name = "Times New Roman"
                st.font.size = Pt(12)
                st.font.bold = name == "TOC 1"
            except KeyError:
                pass

    # ------------------------------------------------------------- blocks --
    def p(self, text="", size=12, bold=False, align=WD_ALIGN_PARAGRAPH.JUSTIFY, ls=1.5, sb=0, sa=4, fontname="Times New Roman"):
        para = self.doc.add_paragraph()
        para.alignment = align
        pf = para.paragraph_format
        pf.line_spacing, pf.space_before, pf.space_after = ls, Pt(sb), Pt(sa)
        if text:
            font(para.add_run(text), size, bold, name=fontname)
        return para

    def rich(self, parts, ls=1.5, sa=4, indent=None):
        """parts: list of (text, bold) tuples in one justified paragraph."""
        para = self.p(ls=ls, sa=sa)
        if indent is not None:
            para.paragraph_format.left_indent = Inches(indent)
            para.paragraph_format.first_line_indent = Inches(-indent)
        for text, bold in parts:
            font(para.add_run(text), bold=bold)
        return para

    def chapter(self, text):
        self.doc.add_heading(text, level=1)

    def section(self, text):
        self.doc.add_heading(text.upper(), level=2)

    def figure(self, name, caption, width):
        self.fig_no += 1
        para = self.p(align=WD_ALIGN_PARAGRAPH.CENTER, ls=1.0, sb=4, sa=0)
        para.paragraph_format.keep_with_next = True
        para.add_run().add_picture(str(FIG / f"{name}.png"), width=Inches(width))
        cap = self.p(align=WD_ALIGN_PARAGRAPH.CENTER, ls=1.0, sa=8)
        font(cap.add_run(f"Fig. {self.fig_no}. "), 11, True)
        font(cap.add_run(caption), 11)

    def table(self, df, caption, widths, size=10):
        self.tab_no += 1
        cap = self.p(align=WD_ALIGN_PARAGRAPH.CENTER, ls=1.0, sb=4, sa=3)
        cap.paragraph_format.keep_with_next = True
        font(cap.add_run(f"Table {self.tab_no}. "), 11, True)
        font(cap.add_run(caption), 11)
        t = self.doc.add_table(rows=1, cols=len(df.columns))
        t.style = "Table Grid"
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        rows = [list(df.columns)] + df.astype(str).values.tolist()
        for i, row in enumerate(rows):
            cells = t.rows[0].cells if i == 0 else t.add_row().cells
            for j, v in enumerate(row):
                cells[j].text = ""
                cp = cells[j].paragraphs[0]
                cp.paragraph_format.line_spacing = 1.0
                cp.paragraph_format.space_after = Pt(0)
                cp.paragraph_format.keep_with_next = i < len(rows) - 1  # keep the table on one page
                cp.alignment = WD_ALIGN_PARAGRAPH.LEFT if j == 0 else WD_ALIGN_PARAGRAPH.CENTER
                bold = i == 0 or v.endswith("*")
                font(cp.add_run(v), size, bold)
                cells[j].width = Inches(widths[j])
                if i == 0:
                    shd = OxmlElement("w:shd")
                    shd.set(qn("w:val"), "clear")
                    shd.set(qn("w:fill"), "D9E2F3")
                    cells[j]._tc.get_or_add_tcPr().append(shd)
        self.p(ls=1.0, sa=2)

    def page_break(self):
        self.doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    def label_line(self, label, value, size=14, fontname="Bookman Old Style", sa=10):
        para = self.p(align=WD_ALIGN_PARAGRAPH.LEFT, ls=1.15, sa=sa)
        para.paragraph_format.left_indent = Inches(0.1)
        para.paragraph_format.tab_stops.add_tab_stop(Inches(2.2), WD_TAB_ALIGNMENT.LEFT)
        font(para.add_run(f"{label}\t: {value}"), size, True, name=fontname)


# ---------------------------------------------------------------------------
def build():
    rp = Report()
    doc = rp.doc
    B = "Bookman Old Style"
    C = WD_ALIGN_PARAGRAPH.CENTER

    # ---------------- page 1: cover -----------------------------------------
    rp.p("DIVISION OF COMPUTER SCIENCE AND ENGINEERING", 15.5, True, C, 1.15, sb=30, sa=14, fontname=B)
    doc.element.body.insert(0, rp.logo)
    rp.p("SCHOOL OF COMPUTER SCIENCE AND TECHNOLOGY", 12, True, C, 1.15, sa=60, fontname=B)
    rp.p("PROJECT-BASED EVALUATION REPORT", 17, True, C, 1.15, sa=24, fontname=B)
    rp.p("Academic Year 2026-2027", 14, True, C, 1.15, sa=24, fontname=B)
    rp.p("ODD SEMESTER", 14, True, C, 1.15, sa=48, fontname=B)
    rp.label_line("Name", NAME)
    rp.label_line("Register Number", REGNO)
    rp.label_line("Course Code", "23CS2024")
    rp.label_line("Course Name", "Data Science Ecosystem", sa=60)
    rp.p("Oct 2026", 14, True, C, 1.15, fontname=B)
    rp.page_break()

    # ---------------- page 2: title + abstract ------------------------------
    rp.p(TITLE, 22, True, C, 1.15, sb=24, sa=4)
    rp.p(SUBTITLE, 14, True, C, 1.15, sa=14)
    rp.p(f"{NAME} ({REGNO})", 15, True, C, 1.15, sa=4)
    rp.p("Smart India Hackathon 2024 · Problem Statement SIH1711 · Ministry of Railways", 11, False, C, 1.15, sa=30)
    rp.p("ABSTRACT", 14, True, C, 1.15, sa=8)

    ov = R("dataset_overview.csv")["value"]
    comp = R("categorisation_model_comparison.csv")
    best = comp.loc["Linear SVM (calibrated)"]
    abl = R("categorisation_ablation.csv")
    urg = R("urgency_results.csv")
    prop, lr_u = urg.loc["LR + minimum expected cost (proposed)"], urg.loc["Logistic Regression (arg-max)"]
    routing, hot, sent, gps, qs = (J("routing_summary"), J("hotspot_detection"), J("sentiment_results"),
                                   J("gps_metadata"), J("queue_summary"))
    mf = R("maintenance_forecast.csv")
    sla = R("sla_breach_model.csv")
    dup = pd.read_csv(RES / "duplicate_grouping.csv")
    dup_best = dup[dup["method"] == "text + coach"].sort_values("pair_F1").iloc[-1]
    ext = pd.read_csv(RES / "entity_extraction.csv")
    e1 = ext[ext["Source"] == "Text + OCR"].set_index("Field")
    e0 = ext[ext["Source"] == "Complaint text only"].set_index("Field")
    dev_cut = 1 - mf.loc["Gradient Boosting (Poisson)", "Poisson deviance"] / mf.loc["Naive (last week)", "Poisson deviance"]
    web = json.loads((ROOT / "docs" / "js" / "model-data.js").read_text(encoding="utf-8")
                     .split("=", 1)[1].rstrip().rstrip(";"))["metrics"]

    rp.p("Rail Madad is the grievance platform through which railway passengers report problems during a journey. "
         "Complaints arrive as typed text, Hinglish messages, photographs, videos and voice notes, and today they are "
         "largely categorised, prioritised and forwarded by hand. RailSaathi AI is a data-science pipeline, developed "
         "for Smart India Hackathon problem statement SIH1711, that automates these steps.")
    rp.p(f"A process-driven simulator produced {int(float(ov['complaints'])):,} realistic multimodal complaints for 60 "
         "trains. Complaint text, OCR text from photos and image tags are fused into one TF-IDF feature space. A "
         f"calibrated linear SVM assigns the category with {pct(best['Accuracy'])} accuracy, and confidence-aware "
         f"routing automates {pct(routing['auto_routed_share'])} of assignments at {pct(routing['auto_routed_accuracy'])} "
         f"accuracy. A cost-sensitive urgency rule raises critical recall to {pct(prop['Critical recall'])}. In a queue "
         f"simulation, it cuts the average wait for critical complaints from {qs['critical_wait_fifo']:.0f} to "
         f"{qs['critical_wait_ai']:.0f} minutes. Graph-based grouping merges duplicate reports, and Poisson gradient "
         "boosting flags deteriorating trains for predictive maintenance.")
    rp.p("The trained model also runs inside an interactive WebGL website with a 3D complaint galaxy and a live "
         "demo. The project shows that lightweight, explainable machine learning can make complaint handling "
         "faster and safer.")
    rp.page_break()

    # ---------------- page 3: contents --------------------------------------
    rp.p("TABLE OF CONTENTS", 14, True, C, 1.15, sa=12)
    toc = rp.p(align=WD_ALIGN_PARAGRAPH.LEFT, ls=1.5)
    field(toc, 'TOC \\o "1-2" \\h \\z \\u', "Update field to build the table of contents.")
    rp.page_break()

    # ---------------- chapter 1 -----------------------------------------------
    rp.chapter("1. INTRODUCTION")
    rp.section("Background of the Project")
    rp.p("Indian Railways carries millions of passengers every day, and Rail Madad is their single window for "
         "help and grievances [1]. A complaint may be about a broken AC, a dirty toilet, a rude staff member or a "
         "medical emergency, and it may arrive through the app, the web portal, the 139 helpline or social media. "
         "Each one has to be read, given a category, sent to the right department and handled in time. As volumes "
         "grow, doing this manually becomes slow and error-prone.")
    rp.section("Problem Statement")
    rp.p("Problem statement SIH1711 [2] asks for an AI solution that categorises and prioritises Rail Madad "
         "complaints, extracts extra information from photos, videos and metadata, routes complaints to the right "
         "official, predicts recurring issues for proactive maintenance and monitors performance through feedback "
         "sentiment. The difficulty is that complaints are short, noisy, often code-mixed (Hinglish) and sometimes "
         "consist of only an image or a voice note.")
    rp.section("Objectives")
    for i, o in enumerate([
        "Build a realistic multimodal complaint dataset with categories, severities and operational patterns.",
        "Categorise complaints by fusing text, OCR and image tags, and route only confident predictions automatically.",
        "Predict urgency with a cost-sensitive rule that avoids under-prioritising emergencies.",
        "Extract train, coach and PNR details, merge duplicate reports and forecast maintenance hotspots.",
        "Present the working model through an interactive web interface.",
    ], 1):
        rp.rich([(f"{i}. ", True), (o, False)], ls=1.5, sa=0, indent=0.25)
    rp.section("Scope of the Project")
    rp.p("The project covers data generation, preprocessing, machine-learning models, evaluation and an "
         "interactive website. It uses classical, explainable machine learning rather than large language models. "
         "Image and speech recognition are represented by their outputs (OCR text, image tags, transcripts), and "
         "the real Rail Madad platform is not modified.")

    # ---------------- chapter 2 -----------------------------------------------
    rp.chapter("2. LITERATURE REVIEW")
    rp.section("Review of Existing Research")
    rp.p("TF-IDF weighting [3] with linear classifiers remains a strong approach for short texts, and support vector "
         "machines handle the sparse, high-dimensional features of text well [4]. Platt scaling converts SVM scores "
         "into calibrated probabilities [5], and selective classification lets a model abstain when unsure [6]. "
         "When errors have unequal costs, choosing the class with minimum expected cost is optimal [7]. Queueing "
         "theory shows why priority ordering shortens waits for urgent jobs [8]. Poisson models suit count data [9], "
         "and t-SNE is a standard tool for visualising high-dimensional data in two or three dimensions [10]. "
         "Hindi-English code-mixing is common in Indian social media text and complicates word-based models [11].")
    rp.section("Research Gap and Limitations of Existing Systems")
    rp.p("The existing Rail Madad workflow relies on manual or menu-based categorisation, handles complaints largely "
         "first-come-first-served, does not mine the text and metadata inside attached media, registers duplicate "
         "reports of one fault as separate tickets and reacts to faults instead of predicting them. Most published "
         "complaint classifiers also optimise accuracy alone, ignoring the much higher cost of missing an emergency.")

    # ---------------- chapter 3 -----------------------------------------------
    rp.chapter("3. METHODOLOGY AND SYSTEM DESIGN")
    rp.section("Proposed Methodology and System Architecture")
    rp.p("RailSaathi AI converts every complaint into one fused document: typed text or a voice transcript, "
         "OCR text from photos (prefixed ocr_) and image-model tags (prefixed img_). Hinglish and SMS words are "
         "normalised with a small lexicon, and word 1-2-gram and character n-gram TF-IDF features are extracted. "
         "Three models then act on this representation (Fig. 1): categorisation with confidence-aware routing, "
         "cost-sensitive urgency detection and duplicate grouping. An analytics layer adds maintenance forecasting, "
         "SLA-breach prediction and sentiment monitoring.")
    rp.figure("fig01_architecture", "System architecture of RailSaathi AI.", 6.1)
    rp.section("Dataset")
    rp.p(f"Because real Rail Madad records are not public, a simulator generated {int(float(ov['complaints'])):,} "
         "complaints across 13 categories, 7 departments and 4 severity levels (January 2025 to September 2026). Each "
         "train has a latent condition that evolves over time, eight trains deteriorate steadily, and seasonal "
         f"effects such as summer AC failures and winter fog delays are built in. {pct(ov['share_hinglish'], 0)} of "
         "complaints are in Hinglish, many contain typos, 4% are vague and 3% carry wrong labels, which keeps the "
         "task realistic. The last six months form the test set.")
    rp.section("Tools and Technologies Used")
    rp.p("Python 3.11 with pandas, NumPy and SciPy was used for data handling. scikit-learn [12] provided the models, "
         "Matplotlib the figures and python-docx this report. The website uses HTML, CSS, JavaScript and Three.js "
         "(WebGL) [13], and Git and GitHub were used for version control and hosting.")
    rp.section("Module Description")
    for name, desc in [
        ("Categorisation and routing: ", "compares Naive Bayes, logistic regression, calibrated linear SVM and random "
         "forest, and auto-routes a complaint only when its confidence exceeds a threshold."),
        ("Urgency detection: ", "applies a cost matrix in which predicting Critical as Low costs 16 and over-triage "
         "costs 1, and picks the severity with minimum expected cost."),
        ("Extraction and grouping: ", "uses regular expressions for train, coach and PNR; GPS for the nearest station; "
         "and links reports of the same train, coach, category and 6-hour window into one incident."),
        ("Predictive maintenance: ", "uses Poisson gradient boosting on weekly complaint counts per train."),
        ("Feedback analytics: ", "includes a sentiment classifier and an SLA-breach risk model."),
    ]:
        rp.rich([(name, True), (desc, False)], sa=0)

    # ---------------- chapter 4 -----------------------------------------------
    rp.chapter("4. IMPLEMENTATION AND RESULTS")
    rp.section("Implementation Details")
    rp.p("Each module is a separate Python script, and run_all.py executes the complete pipeline in under two "
         "minutes on a laptop. All randomness is seeded, so every reported number is reproducible. Results are "
         f"saved as CSV/JSON files and figures as 300-dpi images. The source code is available at {GITHUB}.")
    rp.section("Application Integration and Deployment")
    rp.p("A compact version of the model (word and character TF-IDF with logistic regression) was exported to "
         "JavaScript, so the website classifies complaints entirely in the browser. On 300 test complaints it "
         f"produced exactly the same predictions as Python, with {pct(web['category_accuracy'])} accuracy. The "
         "website (Fig. 2) shows 2,600 test complaints as a rotatable 3D t-SNE galaxy and offers a live demo, "
         "animated result charts and the report figures. It is hosted with GitHub Pages from the docs folder.")
    rp.figure("fig13_website", "RailSaathi AI website: 3D complaint galaxy (left) and live demo (right).", 6.2)
    rp.section("Results and Analysis")
    t = comp[["Accuracy", "Macro-F1", "Dept. routing acc."]].copy()
    t = (100 * t).round(2).astype(str)
    t.insert(0, "Model", [i + "*" if i == "Linear SVM (calibrated)" else i for i in t.index])
    t.columns = ["Model", "Accuracy (%)", "Macro-F1 (%)", "Correct department (%)"]
    rp.table(t.reset_index(drop=True), "Categorisation results on the six-month test set (* best).", [2.4, 1.1, 1.1, 1.6])
    rp.p(f"The calibrated linear SVM performed best (Table 1). Adding OCR text and image tags raised accuracy on "
         f"photo/video complaints from {abl.iloc[0]['Accuracy (photo/video)'] * 100:.1f}% to "
         f"{abl.iloc[-1]['Accuracy (photo/video)'] * 100:.1f}%. For urgency, plain arg-max logistic regression missed "
         f"{100 - lr_u['Critical recall'] * 100:.1f}% of critical cases. The cost-sensitive rule lowered under-triage from "
         f"{pct(lr_u['Under-triage rate'])} to {pct(prop['Under-triage rate'])} at a small cost in overall accuracy, "
         "and in the queue simulation critical complaints were served almost immediately (Fig. 3).")
    rp.figure("fig09_urgency_queue", "(a) Effect of the cost-sensitive rule; (b) mean waiting time by severity "
              "under three queueing policies.", 6.0)
    rp.p(f"For predictive maintenance, Poisson gradient boosting reduced forecast deviance by {dev_cut * 100:.0f}% "
         "compared with a naive last-week forecast. Ranking trains by predicted complaints flagged deteriorating "
         f"rakes at {hot['precision_at_k_deteriorating'] * 100:.0f}% precision, against "
         f"{hot['random_baseline'] * 100:.0f}% by chance (Fig. 4). Table 2 summarises all modules.")
    rp.figure("fig11_maintenance_forecast", "(a) Weekly maintenance-complaint forecast for all trains; (b) history "
              "and forecast of the highest-risk train.", 6.0)
    summary = pd.DataFrame([
        ["Smart routing", f"{pct(routing['auto_routed_share'])} auto-routed at {pct(routing['auto_routed_accuracy'])} accuracy"],
        ["Urgency (critical recall)", f"{pct(lr_u['Critical recall'])} to {pct(prop['Critical recall'])}"],
        ["Critical waiting time", f"{qs['critical_wait_fifo']:.0f} min to {qs['critical_wait_ai']:.0f} min"],
        ["Entity extraction (OCR)", f"Train no. recovered {e0.loc['train_no', 'Recall (%)']:.0f}% to {e1.loc['train_no', 'Recall (%)']:.0f}%; GPS station {pct(gps['nearest_station_accuracy'])}"],
        ["Duplicate grouping", f"Pair F1 {dup_best['pair_F1']:.2f}; {int(dup_best['tickets_before']):,} to {int(dup_best['tickets_after_grouping']):,} tickets"],
        ["Predictive maintenance", f"Deviance -{dev_cut * 100:.0f}% vs naive; {hot['precision_at_k_deteriorating'] * 100:.0f}% of flagged trains truly failing ({hot['random_baseline'] * 100:.0f}% by chance)"],
        ["Feedback analytics", f"Sentiment accuracy {pct(sent['accuracy'])}; SLA-breach ROC-AUC {sla.loc['Logistic Regression', 'ROC-AUC']:.2f}"],
    ], columns=["Module", "Key result"])
    rp.table(summary, "Summary of results of all modules.", [2.0, 4.4])

    # ---------------- chapter 5 -----------------------------------------------
    rp.chapter("5. CONCLUSION AND FUTURE ENHANCEMENT")
    rp.section("Summary of the Work")
    rp.p("RailSaathi AI turns raw, multimodal Rail Madad complaints into categorised, prioritised and de-duplicated "
         "tickets, and turns the complaint stream into maintenance and service-quality insights. Multimodal fusion "
         "helps most where manual handling struggles, on photo and video complaints. Cost-aware decisions protect "
         "emergencies, and metadata such as the booked coach makes duplicate detection reliable.")
    rp.section("Future Enhancements")
    rp.p("Future work includes validating the system on real, anonymised Rail Madad data. Real image and speech "
         "models could replace the simulated tags and transcripts, and multilingual transformer embeddings could "
         "cover regional languages. A chatbot could ask passengers for missing PNR or coach details. Maintenance "
         "alerts could also be linked to depot schedules for staff allocation.")
    rp.section("Conclusion")
    rp.p("The project shows that explainable machine learning, evaluated with the right metrics, can make railway "
         "grievance handling faster, fairer and more proactive. The main limitation is the synthetic dataset, so "
         "absolute scores may be lower on real records.")

    # ---------------- references ------------------------------------------------
    rp.chapter("REFERENCES")
    refs = [
        'Ministry of Railways, Government of India, "Rail Madad." [Online]. Available: https://railmadad.indianrailways.gov.in',
        'Ministry of Education\'s Innovation Cell, "Smart India Hackathon 2024, Problem Statement SIH1711: Enhancing Rail Madad with AI-powered complaint management," 2024.',
        'G. Salton and C. Buckley, "Term-weighting approaches in automatic text retrieval," Inf. Process. Manage., vol. 24, no. 5, pp. 513-523, 1988.',
        'T. Joachims, "Text categorization with support vector machines: Learning with many relevant features," in Proc. ECML, 1998, pp. 137-142.',
        'J. Platt, "Probabilistic outputs for support vector machines and comparisons to regularized likelihood methods," in Advances in Large Margin Classifiers, MIT Press, 1999, pp. 61-74.',
        'Y. Geifman and R. El-Yaniv, "Selective classification for deep neural networks," in Proc. NeurIPS, 2017.',
        'C. Elkan, "The foundations of cost-sensitive learning," in Proc. IJCAI, 2001, pp. 973-978.',
        "L. Kleinrock, Queueing Systems, Vol. 1: Theory. New York, NY, USA: Wiley, 1975.",
        "P. McCullagh and J. A. Nelder, Generalized Linear Models, 2nd ed. London, U.K.: Chapman & Hall, 1989.",
        'L. van der Maaten and G. Hinton, "Visualizing data using t-SNE," J. Mach. Learn. Res., vol. 9, pp. 2579-2605, 2008.',
        'K. Bali, J. Sharma, M. Choudhury, and Y. Vyas, "\'I am borrowing ya mixing?\' An analysis of English-Hindi code mixing in Facebook," in Proc. 1st Workshop Comput. Approaches Code Switching, 2014, pp. 116-126.',
        'F. Pedregosa et al., "Scikit-learn: Machine learning in Python," J. Mach. Learn. Res., vol. 12, pp. 2825-2830, 2011.',
        'three.js authors, "three.js - JavaScript 3D library." [Online]. Available: https://threejs.org',
    ]
    for i, ref in enumerate(refs, 1):
        para = rp.p(align=WD_ALIGN_PARAGRAPH.LEFT, ls=1.0, sa=3)
        para.paragraph_format.left_indent = Inches(0.4)
        para.paragraph_format.first_line_indent = Inches(-0.4)
        font(para.add_run(f"[{i}]\t{ref}"), 11)

    # ---------------- evaluation sheet ----------------------------------------
    rp.page_break()
    rp.p("EVALUATION SHEET", 14, True, C, 1.15, sb=10, sa=24, fontname=B)
    rp.label_line("Reg.No", REGNO, sa=8)
    rp.label_line("Name", NAME, sa=8)
    rp.label_line("Title of the Project", "RAILSAATHI AI", sa=8)
    rp.label_line("Course Code", "23CS2024", sa=8)
    rp.label_line("Course Name", "Data Science Ecosystem", sa=30)
    sect = doc.element.body.find(qn("w:sectPr"))
    sect.addprevious(rp.eval_table)
    sig = rp.p("Signature of the Faculty-in-charge", 14, True, WD_ALIGN_PARAGRAPH.RIGHT, 1.15, sb=70, fontname=B)
    sect.addprevious(sig._p)

    doc.save(OUT)
    print(f"Saved {OUT} ({rp.fig_no} figures, {rp.tab_no} tables, {len(refs)} references)")


if __name__ == "__main__":
    build()
